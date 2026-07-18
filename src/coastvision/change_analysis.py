"""Análisis multitemporal de cambio costero equivalente a DSAS.

El módulo construye transectos *fijos* sobre una línea base, intersecta en
ellos las líneas costeras anuales y calcula las métricas habituales de DSAS:

``NSM``
    Movimiento neto, posición del año más reciente menos la del más antiguo.
``EPR``
    NSM dividido por el intervalo temporal entre esos dos años.
``LRR``
    Pendiente de una regresión lineal que usa **todas** las observaciones.

Convención de signo
--------------------
Los transectos se orientan desde el lado negativo hacia el positivo. Por
defecto el lado positivo es la izquierda de la línea base digitalizada. En el
proyecto CoastVision la costa se digitaliza dejando la tierra a la izquierda;
por tanto, valores positivos significan retroceso/avance tierra adentro y
valores negativos significan acreción/avance hacia el mar. Si la línea base
tiene la orientación contraria se debe usar ``positive_side="right"``.

Todas las distancias y tasas se calculan en EPSG:32719 (UTM 19S) por defecto.
Las propiedades ``*_wgs84`` del resultado solo reproyectan las geometrías
para visualización; nunca se calculan distancias en grados.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Literal

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    Point,
)
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, nearest_points, unary_union


WGS84 = "EPSG:4326"
UTM_19S = "EPSG:32719"

PositiveSide = Literal["left", "right"]
BaselineInput = LineString | MultiLineString | gpd.GeoSeries | gpd.GeoDataFrame


@dataclass(frozen=True)
class ChangeAnalysisResult:
    """Capas y tabla producidas por :func:`analyze_shoreline_change`.

    ``transects``, ``intersections`` y ``metrics`` conservan el CRS métrico
    del análisis. ``metrics_table`` entrega una tabla sin geometría apta para
    CSV, mientras que las propiedades WGS84 son adecuadas para el mapa web.
    """

    transects: gpd.GeoDataFrame
    intersections: gpd.GeoDataFrame
    metrics: gpd.GeoDataFrame

    @property
    def metrics_table(self) -> pd.DataFrame:
        return pd.DataFrame(self.metrics.drop(columns=self.metrics.geometry.name))

    @property
    def transects_wgs84(self) -> gpd.GeoDataFrame:
        return self.transects.to_crs(WGS84)

    @property
    def intersections_wgs84(self) -> gpd.GeoDataFrame:
        return self.intersections.to_crs(WGS84)

    @property
    def metrics_wgs84(self) -> gpd.GeoDataFrame:
        return self.metrics.to_crs(WGS84)


def _sign_description(positive_side: PositiveSide) -> str:
    return (
        f"positivo=hacia el lado {positive_side} de la línea base; "
        "si ese lado es tierra, positivo=retroceso y negativo=acreción"
    )


def _continuous_line(geometries: Iterable[BaseGeometry]) -> LineString:
    valid = [geometry for geometry in geometries if geometry is not None and not geometry.is_empty]
    if not valid:
        raise ValueError("La línea base no contiene geometrías válidas.")

    combined = unary_union(valid)
    if isinstance(combined, LineString):
        line = combined
    elif isinstance(combined, MultiLineString):
        merged = linemerge(combined)
        if not isinstance(merged, LineString):
            raise ValueError("La línea base debe ser una LineString continua.")
        line = merged
    else:
        raise ValueError("La línea base debe contener geometría lineal.")
    if math.isclose(line.length, 0.0, abs_tol=1e-9):
        raise ValueError("La línea base debe tener longitud mayor que cero.")
    if isinstance(line, LineString):
        return line
    raise ValueError("La línea base debe ser una LineString continua.")


def _project_baseline(
    baseline: BaselineInput,
    *,
    baseline_crs: str | int | CRS,
    target_crs: str | int | CRS,
) -> LineString:
    if isinstance(baseline, gpd.GeoDataFrame):
        if baseline.crs is None:
            raise ValueError("La línea base GeoDataFrame debe declarar su CRS.")
        source = baseline.geometry
    elif isinstance(baseline, gpd.GeoSeries):
        if baseline.crs is None:
            raise ValueError("La línea base GeoSeries debe declarar su CRS.")
        source = baseline
    elif isinstance(baseline, (LineString, MultiLineString)):
        source = gpd.GeoSeries([baseline], crs=baseline_crs)
    else:
        raise TypeError("baseline debe ser LineString, GeoSeries o GeoDataFrame.")

    projected = source.to_crs(target_crs)
    return _continuous_line(projected.tolist())


def _validate_metric_crs(target_crs: str | int | CRS) -> CRS:
    crs = CRS.from_user_input(target_crs)
    if not crs.is_projected:
        raise ValueError("target_crs debe ser un CRS proyectado con unidades métricas.")
    axis_units = {axis.unit_name.lower() for axis in crs.axis_info if axis.unit_name}
    if axis_units and not any("metre" in unit or "meter" in unit for unit in axis_units):
        raise ValueError("target_crs debe usar metros.")
    return crs


def _sampling_distances(length_m: float, spacing_m: float) -> list[float]:
    distances = list(np.arange(0.0, length_m + spacing_m * 1e-9, spacing_m))
    if not distances or not math.isclose(distances[-1], length_m, abs_tol=1e-7):
        distances.append(length_m)
    return distances


def _local_tangent(line: LineString, chainage_m: float, spacing_m: float) -> tuple[float, float]:
    window_m = min(10.0, max(0.5, spacing_m / 10.0, line.length / 10_000.0))
    start = line.interpolate(max(0.0, chainage_m - window_m))
    end = line.interpolate(min(line.length, chainage_m + window_m))
    dx, dy = end.x - start.x, end.y - start.y
    norm = math.hypot(dx, dy)
    if math.isclose(norm, 0.0, abs_tol=1e-12):
        raise ValueError(f"No se pudo obtener la tangente en {chainage_m:.3f} m.")
    return dx / norm, dy / norm


def build_fixed_transects(
    baseline: BaselineInput,
    *,
    spacing_m: float = 100.0,
    seaward_m: float = 100.0,
    landward_m: float = 300.0,
    positive_side: PositiveSide = "left",
    baseline_crs: str | int | CRS = WGS84,
    target_crs: str | int | CRS = UTM_19S,
    id_prefix: str = "T",
) -> gpd.GeoDataFrame:
    """Construye transectos fijos normales a una línea base.

    El primer vértice queda a ``seaward_m`` en el lado negativo y el último
    a ``landward_m`` en el lado positivo. Los nombres se conservan por
    compatibilidad con el caso habitual; la semántica real depende de
    ``positive_side`` y de la orientación de la línea base.
    """

    metric_crs = _validate_metric_crs(target_crs)
    if spacing_m <= 0:
        raise ValueError("spacing_m debe ser mayor que cero.")
    if seaward_m <= 0 or landward_m <= 0:
        raise ValueError("seaward_m y landward_m deben ser mayores que cero.")
    if positive_side not in {"left", "right"}:
        raise ValueError("positive_side debe ser 'left' o 'right'.")

    line = _project_baseline(
        baseline,
        baseline_crs=baseline_crs,
        target_crs=metric_crs,
    )
    records: list[dict[str, object]] = []
    for index, chainage_m in enumerate(_sampling_distances(line.length, spacing_m), start=1):
        origin = line.interpolate(chainage_m)
        tangent_x, tangent_y = _local_tangent(line, chainage_m, spacing_m)
        # Normal izquierda = (-ty, tx); para lado derecho se invierte.
        positive_dx, positive_dy = -tangent_y, tangent_x
        if positive_side == "right":
            positive_dx, positive_dy = -positive_dx, -positive_dy

        negative_end = Point(
            origin.x - positive_dx * seaward_m,
            origin.y - positive_dy * seaward_m,
        )
        positive_end = Point(
            origin.x + positive_dx * landward_m,
            origin.y + positive_dy * landward_m,
        )
        records.append(
            {
                "transect_id": f"{id_prefix}{index:03d}",
                "chainage_m": float(chainage_m),
                "baseline_x": float(origin.x),
                "baseline_y": float(origin.y),
                "positive_dx": float(positive_dx),
                "positive_dy": float(positive_dy),
                "positive_side": positive_side,
                "seaward_m": float(seaward_m),
                "landward_m": float(landward_m),
                "sign_convention": _sign_description(positive_side),
                "geometry": LineString([negative_end, positive_end]),
            }
        )

    transects = gpd.GeoDataFrame(records, geometry="geometry", crs=metric_crs)
    transects.attrs["sign_convention"] = _sign_description(positive_side)
    transects.attrs["distance_units"] = "metres"
    return transects


def _point_candidates(geometry: BaseGeometry) -> tuple[list[Point], bool]:
    """Devuelve puntos de una intersección y marca solapamientos lineales."""

    if geometry is None or geometry.is_empty:
        return [], False
    if isinstance(geometry, Point):
        return [geometry], False
    if isinstance(geometry, MultiPoint):
        return list(geometry.geoms), False
    if isinstance(geometry, (LineString, MultiLineString)):
        return [], True
    if isinstance(geometry, GeometryCollection):
        points: list[Point] = []
        overlap = False
        for part in geometry.geoms:
            part_points, part_overlap = _point_candidates(part)
            points.extend(part_points)
            overlap = overlap or part_overlap
        return points, overlap
    return [], False


def _normalise_years(shorelines: gpd.GeoDataFrame, year_column: str) -> gpd.GeoDataFrame:
    if year_column not in shorelines.columns:
        raise ValueError(f"Falta la columna temporal '{year_column}'.")
    years = pd.to_numeric(shorelines[year_column], errors="coerce")
    if years.isna().any():
        raise ValueError("Todos los años deben ser numéricos y no nulos.")
    if not np.allclose(years, np.round(years)):
        raise ValueError("Los años deben ser enteros para el análisis anual.")
    normalised = shorelines.copy()
    normalised[year_column] = years.round().astype(int)
    return normalised


def intersect_annual_shorelines(
    transects: gpd.GeoDataFrame,
    shorelines: gpd.GeoDataFrame,
    *,
    year_column: str = "year",
) -> gpd.GeoDataFrame:
    """Intersecta cada transecto fijo con cada línea costera anual.

    Si una costa tiene varios fragmentos para el mismo año, estos se unen
    antes de intersectar. Si aparecen varios cruces se conserva el más cercano
    a la línea base, una regla determinista que evita saltos a brazos espurios.
    Las combinaciones sin cruce también se registran con geometría nula para
    poder auditar la completitud temporal.
    """

    required = {
        "transect_id",
        "baseline_x",
        "baseline_y",
        "positive_dx",
        "positive_dy",
        "sign_convention",
    }
    missing = sorted(required.difference(transects.columns))
    if missing:
        raise ValueError(f"Faltan columnas de transectos: {', '.join(missing)}.")
    if transects.crs is None:
        raise ValueError("Los transectos deben declarar su CRS.")
    if shorelines.crs is None:
        raise ValueError("Las líneas costeras deben declarar su CRS.")

    annual = _normalise_years(shorelines, year_column).to_crs(transects.crs)
    grouped_shorelines: list[tuple[int, BaseGeometry]] = []
    for year, group in annual.groupby(year_column, sort=True):
        valid = [geometry for geometry in group.geometry if geometry is not None and not geometry.is_empty]
        if valid:
            grouped_shorelines.append((int(year), unary_union(valid)))
        else:
            grouped_shorelines.append((int(year), GeometryCollection()))

    records: list[dict[str, object]] = []
    for transect in transects.itertuples(index=False):
        origin = Point(float(transect.baseline_x), float(transect.baseline_y))
        for year, shoreline in grouped_shorelines:
            intersection = transect.geometry.intersection(shoreline)
            candidates, overlap = _point_candidates(intersection)
            if candidates:
                selected = min(candidates, key=origin.distance)
                method = "nearest_of_multiple" if len(candidates) > 1 else "single_point"
            elif overlap:
                # Un solapamiento no define un cruce único. Se usa el punto del
                # solapamiento más cercano al origen y se deja trazabilidad.
                selected = nearest_points(origin, intersection)[1]
                method = "nearest_on_overlap"
            else:
                selected = None
                method = "no_intersection"

            signed_position = math.nan
            if selected is not None:
                signed_position = (
                    (selected.x - origin.x) * float(transect.positive_dx)
                    + (selected.y - origin.y) * float(transect.positive_dy)
                )
            records.append(
                {
                    "transect_id": transect.transect_id,
                    "year": year,
                    "position_m": float(signed_position),
                    "intersection_found": selected is not None,
                    "intersection_method": method,
                    "candidate_count": len(candidates),
                    "sign_convention": transect.sign_convention,
                    "geometry": selected,
                }
            )

    intersections = gpd.GeoDataFrame(
        records,
        columns=[
            "transect_id",
            "year",
            "position_m",
            "intersection_found",
            "intersection_method",
            "candidate_count",
            "sign_convention",
            "geometry",
        ],
        geometry="geometry",
        crs=transects.crs,
    )
    intersections.attrs["sign_convention"] = transects.attrs.get(
        "sign_convention",
        str(transects.iloc[0]["sign_convention"]) if not transects.empty else "",
    )
    intersections.attrs["distance_units"] = "metres"
    return intersections


_T_975 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def _t_critical_95(degrees_freedom: int) -> float:
    if degrees_freedom <= 0:
        return math.nan
    if degrees_freedom <= 30:
        return _T_975[degrees_freedom]
    if degrees_freedom <= 40:
        return 2.021
    if degrees_freedom <= 60:
        return 2.000
    if degrees_freedom <= 120:
        return 1.980
    return 1.960


def _regression_metrics(years: np.ndarray, positions: np.ndarray) -> dict[str, float]:
    x_mean = float(years.mean())
    y_mean = float(positions.mean())
    centered_years = years - x_mean
    sxx = float(np.dot(centered_years, centered_years))
    slope = float(np.dot(centered_years, positions - y_mean) / sxx)
    fitted = y_mean + slope * centered_years
    residuals = positions - fitted
    ss_residual = float(np.dot(residuals, residuals))
    centered_positions = positions - y_mean
    ss_total = float(np.dot(centered_positions, centered_positions))
    if math.isclose(ss_total, 0.0, abs_tol=1e-12):
        r_squared = 1.0 if math.isclose(ss_residual, 0.0, abs_tol=1e-12) else math.nan
    else:
        r_squared = max(0.0, min(1.0, 1.0 - ss_residual / ss_total))

    standard_error = math.nan
    ci_low = math.nan
    ci_high = math.nan
    degrees_freedom = len(years) - 2
    if degrees_freedom > 0:
        variance = max(0.0, ss_residual / degrees_freedom)
        standard_error = math.sqrt(variance / sxx)
        margin = _t_critical_95(degrees_freedom) * standard_error
        ci_low, ci_high = slope - margin, slope + margin

    return {
        "lrr_m_per_year": slope,
        "lrr_r2": r_squared,
        "lrr_reference_year": x_mean,
        "lrr_position_at_reference_m": y_mean,
        "lrr_standard_error_m_per_year": standard_error,
        "lrr_ci95_low_m_per_year": ci_low,
        "lrr_ci95_high_m_per_year": ci_high,
    }


def calculate_change_metrics(
    intersections: gpd.GeoDataFrame,
    transects: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Calcula NSM, EPR y LRR por transecto.

    El LRR usa todas las posiciones anuales válidas. Su error estándar y el
    intervalo de confianza bilateral de 95 % (Student-t) se entregan cuando
    existen al menos tres años. Con una sola observación, las tasas quedan
    ``NaN`` y el estado explica la insuficiencia.
    """

    required = {"transect_id", "year", "position_m"}
    missing = sorted(required.difference(intersections.columns))
    if missing:
        raise ValueError(f"Faltan columnas de intersecciones: {', '.join(missing)}.")
    if intersections.crs is None or transects.crs is None:
        raise ValueError("Intersecciones y transectos deben declarar su CRS.")
    if CRS.from_user_input(intersections.crs) != CRS.from_user_input(transects.crs):
        raise ValueError("Intersecciones y transectos deben usar el mismo CRS.")

    expected_years = int(intersections["year"].nunique()) if not intersections.empty else 0
    records: list[dict[str, object]] = []
    for transect in transects.itertuples(index=False):
        subset = intersections.loc[
            intersections["transect_id"] == transect.transect_id,
            ["year", "position_m"],
        ].dropna(subset=["position_m"])
        # Si existen varios registros del mismo año, el promedio impide que
        # ese año pese artificialmente más en la regresión.
        annual = subset.groupby("year", as_index=False, sort=True)["position_m"].mean()
        years = annual["year"].to_numpy(dtype=float)
        positions = annual["position_m"].to_numpy(dtype=float)
        n_observations = len(annual)

        record: dict[str, object] = {
            "transect_id": transect.transect_id,
            "chainage_m": float(transect.chainage_m),
            "n_observations": n_observations,
            "n_expected_years": expected_years,
            "temporal_completeness_pct": (
                100.0 * n_observations / expected_years if expected_years else 0.0
            ),
            "first_year": int(years[0]) if n_observations else pd.NA,
            "last_year": int(years[-1]) if n_observations else pd.NA,
            "first_position_m": float(positions[0]) if n_observations else math.nan,
            "last_position_m": float(positions[-1]) if n_observations else math.nan,
            "nsm_m": math.nan,
            "epr_m_per_year": math.nan,
            "lrr_m_per_year": math.nan,
            "lrr_r2": math.nan,
            "lrr_reference_year": math.nan,
            "lrr_position_at_reference_m": math.nan,
            "lrr_standard_error_m_per_year": math.nan,
            "lrr_ci95_low_m_per_year": math.nan,
            "lrr_ci95_high_m_per_year": math.nan,
            "uncertainty_method": "not_available",
            "analysis_status": "no_intersections" if n_observations == 0 else "insufficient_observations",
            "sign_convention": transect.sign_convention,
            "geometry": transect.geometry,
        }

        if n_observations >= 2:
            interval_years = float(years[-1] - years[0])
            if interval_years <= 0:
                record["analysis_status"] = "insufficient_time_span"
            else:
                nsm = float(positions[-1] - positions[0])
                record["nsm_m"] = nsm
                record["epr_m_per_year"] = nsm / interval_years
                record.update(_regression_metrics(years, positions))
                if n_observations >= 3:
                    record["uncertainty_method"] = "student_t_95"
                    record["analysis_status"] = "ok"
                else:
                    record["analysis_status"] = "ok_without_lrr_uncertainty"
        records.append(record)

    metrics = gpd.GeoDataFrame(records, geometry="geometry", crs=transects.crs)
    metrics.attrs["sign_convention"] = transects.attrs.get(
        "sign_convention",
        str(transects.iloc[0]["sign_convention"]) if not transects.empty else "",
    )
    metrics.attrs["rate_units"] = "metres/year"
    metrics.attrs["lrr_observations"] = "all valid unique annual observations"
    return metrics


def analyze_shoreline_change(
    baseline: BaselineInput,
    shorelines: gpd.GeoDataFrame,
    *,
    year_column: str = "year",
    spacing_m: float = 100.0,
    seaward_m: float = 100.0,
    landward_m: float = 300.0,
    positive_side: PositiveSide = "left",
    baseline_crs: str | int | CRS = WGS84,
    target_crs: str | int | CRS = UTM_19S,
    id_prefix: str = "T",
) -> ChangeAnalysisResult:
    """Ejecuta el pipeline completo de cambio costero tipo DSAS."""

    transects = build_fixed_transects(
        baseline,
        spacing_m=spacing_m,
        seaward_m=seaward_m,
        landward_m=landward_m,
        positive_side=positive_side,
        baseline_crs=baseline_crs,
        target_crs=target_crs,
        id_prefix=id_prefix,
    )
    intersections = intersect_annual_shorelines(
        transects,
        shorelines,
        year_column=year_column,
    )
    metrics = calculate_change_metrics(intersections, transects)
    return ChangeAnalysisResult(
        transects=transects,
        intersections=intersections,
        metrics=metrics,
    )


__all__ = [
    "ChangeAnalysisResult",
    "WGS84",
    "UTM_19S",
    "analyze_shoreline_change",
    "build_fixed_transects",
    "calculate_change_metrics",
    "intersect_annual_shorelines",
]
