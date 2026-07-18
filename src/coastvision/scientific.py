"""Lectura y consulta de las salidas científicas consolidadas de CoastVision."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


EXPECTED_YEARS = set(range(2016, 2027))
WGS84 = "EPSG:4326"
UTM_19S = "EPSG:32719"


@dataclass(frozen=True)
class NearestInfrastructureAssessment:
    """Elemento del inventario evaluado más cercano a un clic del mapa."""

    risk_level: str
    risk_label: str
    color: str
    explanation: str
    feature_type: str
    osm_id: str
    name: str | None
    click_distance_to_feature_m: float
    distance_to_shoreline_m: float
    nearest_transect_id: str
    erosion_rate_m_per_year: float
    years_to_impact: float | None
    horizon_years: int
    latitude: float
    longitude: float
    evidence_source: str = "pipeline_fes2014_lrr_osm"


def scientific_pipeline_ready(
    pipeline: dict[str, Any],
    infrastructure: dict[str, Any],
    *,
    shorelines_exist: bool,
    rates_exist: bool,
    buildings_exist: bool,
    roads_exist: bool,
) -> tuple[bool, list[str]]:
    """Valida que el semáforo pueda atribuirse al pipeline completo y no al demo."""

    problems: list[str] = []
    corrected = {int(year) for year in pipeline.get("fes2014_corrected_years", [])}
    extracted = {int(year) for year in pipeline.get("extracted_ndwi_years", [])}
    change = pipeline.get("change_analysis", {})
    if corrected != EXPECTED_YEARS:
        problems.append("la corrección FES2014 no cubre 2016-2026")
    if extracted != EXPECTED_YEARS:
        problems.append("la extracción NDWI no cubre 2016-2026")
    if not bool(pipeline.get("satellite_tide_change_complete_2016_2026")):
        problems.append("la cadena satélite-marea-cambio no está marcada como completa")
    if change.get("status") != "OK" or int(change.get("valid_lrr_count", 0) or 0) <= 0:
        problems.append("no existen tasas LRR válidas")
    if not shorelines_exist or not rates_exist:
        problems.append("faltan capas científicas de costa o tasas")
    if not buildings_exist or not roads_exist or not infrastructure:
        problems.append("falta el screening OSM de edificios o caminos")
    return not problems, problems


def _risk_presentation(level: str) -> tuple[str, str]:
    normalized = str(level or "").casefold()
    if normalized == "critico":
        return "Crítico", "#B42318"
    if normalized in {"moderado", "precaucion"}:
        return "Precaución", "#B97512"
    if normalized == "bajo":
        return "Bajo", "#2E7D55"
    return "Sin clasificar", "#62727D"


def assess_nearest_infrastructure(
    lat: float,
    lon: float,
    buildings_path: str | Path,
    roads_path: str | Path,
) -> NearestInfrastructureAssessment:
    """Devuelve la clase ya calculada por el pipeline para el elemento OSM más cercano.

    La función no reclasifica el clic ni inventa una franja continua: conserva exactamente
    ``risk_level``, distancia a costa y LRR exportadas por el screening de infraestructura.
    """

    if not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
        raise ValueError("Coordenadas WGS84 inválidas.")
    layers: list[gpd.GeoDataFrame] = []
    for path in (Path(buildings_path), Path(roads_path)):
        if not path.is_file():
            continue
        layer = gpd.read_file(path)
        if layer.crs is None:
            raise ValueError(f"La capa {path.name} no declara CRS.")
        if not layer.empty:
            layers.append(layer.to_crs(UTM_19S))
    if not layers:
        raise ValueError("No hay infraestructura evaluada por el pipeline.")

    point = gpd.GeoSeries([Point(float(lon), float(lat))], crs=WGS84).to_crs(UTM_19S).iloc[0]
    nearest_row = None
    nearest_distance = float("inf")
    for layer in layers:
        distances = layer.geometry.distance(point)
        index = distances.idxmin()
        distance = float(distances.loc[index])
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_row = layer.loc[index]
    if nearest_row is None:
        raise ValueError("No fue posible localizar infraestructura evaluada.")

    level = str(nearest_row.get("risk_level") or "sin_clasificar")
    label, color = _risk_presentation(level)
    years_to_impact = nearest_row.get("years_to_impact")
    if years_to_impact is not None and not pd.isna(years_to_impact):
        years_to_impact = float(years_to_impact)
    else:
        years_to_impact = None
    name = nearest_row.get("name")
    if name is not None and pd.isna(name):
        name = None
    return NearestInfrastructureAssessment(
        risk_level=level,
        risk_label=label,
        color=color,
        explanation=str(nearest_row.get("risk_explanation") or "Sin explicación exportada"),
        feature_type=str(nearest_row.get("feature_type") or "infrastructure"),
        osm_id=str(nearest_row.get("osm_id") or "sin_id"),
        name=str(name) if name is not None else None,
        click_distance_to_feature_m=round(nearest_distance, 1),
        distance_to_shoreline_m=float(nearest_row.get("distance_to_shoreline_m")),
        nearest_transect_id=str(nearest_row.get("nearest_transect_id") or "sin_transecto"),
        erosion_rate_m_per_year=float(nearest_row.get("erosion_rate_m_per_year")),
        years_to_impact=years_to_impact,
        horizon_years=int(nearest_row.get("horizon_years") or 30),
        latitude=float(lat),
        longitude=float(lon),
    )
