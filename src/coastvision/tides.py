"""Corrección mareal reproducible con FES2014.

El modelo (aprox. 4,5 GB) se mantiene fuera del repositorio y se referencia
mediante ``TIDE_MODEL_DIR``. La corrección se aplica a cada escena individual,
usando su fecha/hora UTC, antes de calcular una línea anual o una tendencia.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Point


WGS84 = "EPSG:4326"
UTM_19S = "EPSG:32719"
EXPECTED_CONSTITUENTS = {
    "2n2", "eps2", "j1", "k1", "k2", "l2", "la2", "m2", "m3", "m4",
    "m6", "m8", "mf", "mks2", "mm", "mn4", "ms4", "msf", "msqm", "mtm",
    "mu2", "n2", "n4", "nu2", "o1", "p1", "q1", "r2", "s1", "s2", "s4",
    "sa", "ssa", "t2",
}
FES_EXTRAPOLATION_CUTOFF_KM = 10.0


@dataclass(frozen=True)
class TideCorrection:
    acquired_at_utc: str | None
    tide_height_m: float
    beach_slope: float
    horizontal_shift_m: float
    datum: str
    model: str
    direction_method: str
    interpolation_method: str
    extrapolation_cutoff_km: float
    convention: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _candidate_model_roots(path: Path) -> list[tuple[Path, Path]]:
    """Devuelve pares ``(raíz pyTMD, carpeta ocean_tide)`` plausibles."""
    path = path.expanduser().resolve()
    return [
        (path, path / "fes2014" / "ocean_tide"),
        (path.parent, path / "ocean_tide") if path.name.lower() == "fes2014" else (path, path / "ocean_tide"),
        (path.parent.parent, path) if path.name.lower() == "ocean_tide" else (path, path),
    ]


def resolve_fes2014_directory(model_dir: str | Path | None = None) -> tuple[Path, Path]:
    configured = model_dir or os.environ.get("TIDE_MODEL_DIR")
    if not configured:
        raise FileNotFoundError(
            "FES2014 no está configurado. Defina TIDE_MODEL_DIR apuntando a la raíz "
            "que contiene fes2014/ocean_tide; el modelo no se guarda en Git."
        )
    for root, ocean_tide in _candidate_model_roots(Path(configured)):
        if ocean_tide.is_dir() and (ocean_tide / "m2.nc").is_file():
            return root, ocean_tide
    raise FileNotFoundError(
        f"No se encontró fes2014/ocean_tide con m2.nc bajo la ruta configurada: {configured}"
    )


def validate_fes2014_directory(model_dir: str | Path | None = None) -> dict[str, Any]:
    root, ocean_tide = resolve_fes2014_directory(model_dir)
    files = sorted(ocean_tide.glob("*.nc"))
    names = {path.stem.lower() for path in files}
    invalid_headers: list[str] = []
    for path in files:
        with path.open("rb") as handle:
            # Los NetCDF4 de FES2014 son contenedores HDF5.
            if handle.read(8) != b"\x89HDF\r\n\x1a\n":
                invalid_headers.append(path.name)
    missing = sorted(EXPECTED_CONSTITUENTS - names)
    return {
        "model": "FES2014b ocean_tide",
        "model_root": str(root),
        "ocean_tide_directory": str(ocean_tide),
        "constituent_count": len(files),
        "expected_constituent_count": len(EXPECTED_CONSTITUENTS),
        "missing_constituents": missing,
        "unexpected_constituents": sorted(names - EXPECTED_CONSTITUENTS),
        "invalid_hdf5_headers": invalid_headers,
        "total_bytes": sum(path.stat().st_size for path in files),
        "valid": not missing and not invalid_headers,
        "validation_scope": "constituent_filenames_and_hdf5_headers",
        "numeric_prediction_validated": False,
    }


@lru_cache(maxsize=2)
def _open_fes2014(model_root: str):
    import pyTMD.io

    model = pyTMD.io.model(directory=model_root).from_database("FES2014", group=("z",))
    model.compressed = False
    dataset = model.open_dataset(group="z", chunks="auto")
    return model, dataset


def clear_fes2014_cache() -> None:
    # functools no expone los valores almacenados; los datasets se liberan al
    # retirar la última referencia y el proceso de pipeline es de vida corta.
    _open_fes2014.cache_clear()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("La fecha de la escena debe incluir zona horaria UTC.")
    return value.astimezone(timezone.utc)


def predict_tides_fes2014(
    lat: float,
    lon: float,
    acquired_at: Iterable[datetime],
    model_dir: str | Path | None = None,
) -> list[float]:
    """Predice mareas para varias escenas interpolando FES2014 una sola vez."""
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Latitud/longitud fuera de rango.")
    dates = [_as_utc(value) for value in acquired_at]
    if not dates:
        raise ValueError("Se requiere al menos una fecha de escena.")
    model_root, _ = resolve_fes2014_directory(model_dir)
    model, dataset = _open_fes2014(str(model_root))

    import timescale

    ts = timescale.from_calendar(
        np.asarray([value.year for value in dates]),
        np.asarray([value.month for value in dates]),
        np.asarray([value.day for value in dates]),
        hour=np.asarray([value.hour for value in dates]),
        minute=np.asarray([value.minute for value in dates]),
        second=np.asarray([
            value.second + value.microsecond / 1_000_000 for value in dates
        ]),
    )
    deltat = np.zeros_like(ts.tide) if model.format == "FES-netcdf" else ts.tt_ut1
    x, y = dataset.tmd.coords_as(lon, lat, crs=4326)
    local = dataset.tmd.interp(
        x,
        y,
        extrapolate=True,
        cutoff=FES_EXTRAPOLATION_CUTOFF_KM,
    ).tmd.to_units("m")

    try:
        result = local.tmd.predict(
            ts.tide,
            deltat=deltat,
            corrections=model.corrections,
        )
        values = np.asarray(result, dtype=float).ravel()
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"FES2014 no pudo predecir la serie de mareas: {exc}") from exc
    if len(values) != len(dates):
        raise RuntimeError(
            f"FES2014 devolvió {len(values)} valores para {len(dates)} fechas."
        )
    if not np.isfinite(values).all():
        raise ValueError("FES2014 devolvió una o más alturas no finitas.")
    return [float(value) for value in values]


def predict_tide_fes2014(
    lat: float,
    lon: float,
    acquired_at: datetime,
    model_dir: str | Path | None = None,
) -> float:
    """Predice altura de marea (m) para una escena individual."""
    return predict_tides_fes2014(
        lat,
        lon,
        [acquired_at],
        model_dir=model_dir,
    )[0]


def horizontal_tide_shift(tide_height_m: float, beach_slope: float) -> float:
    if not np.isfinite(tide_height_m):
        raise ValueError("La altura de marea debe ser finita.")
    if not 0 < beach_slope <= 1:
        raise ValueError("La pendiente de playa debe estar entre 0 y 1.")
    return float(tide_height_m / beach_slope)


def _land_normal(
    point: Point,
    left_normal: tuple[float, float],
    water_polygon,
    land_reference: Point | None,
    probe_m: float = 5.0,
) -> tuple[float, float, str]:
    nx, ny = left_normal
    if water_polygon is not None and not water_polygon.is_empty:
        left = Point(point.x + nx * probe_m, point.y + ny * probe_m)
        right = Point(point.x - nx * probe_m, point.y - ny * probe_m)
        left_water = water_polygon.covers(left)
        right_water = water_polygon.covers(right)
        if left_water != right_water:
            return ((-nx, -ny, "water_polygon") if left_water else (nx, ny, "water_polygon"))
    if land_reference is not None:
        vx, vy = land_reference.x - point.x, land_reference.y - point.y
        if vx * nx + vy * ny >= 0:
            return nx, ny, "land_reference"
        return -nx, -ny, "land_reference"
    raise ValueError(
        "No se puede determinar el lado tierra/mar: entregue water_polygon_wgs84 "
        "o land_reference_wgs84."
    )


def correct_shoreline_to_msl(
    shoreline_wgs84: LineString,
    tide_height_m: float,
    beach_slope: float,
    *,
    water_polygon_wgs84=None,
    land_reference_wgs84: Point | tuple[float, float] | None = None,
    acquired_at: datetime | None = None,
    metric_crs: str = UTM_19S,
) -> tuple[LineString, TideCorrection]:
    """Normaliza una línea de agua observada al nivel medio del mar.

    Convención: marea positiva sitúa la línea observada hacia tierra; para
    llevarla a MSL se desplaza en sentido marino ``altura/pendiente``.
    """
    if shoreline_wgs84.is_empty or len(shoreline_wgs84.coords) < 2:
        raise ValueError("La línea de costa debe contener al menos dos vértices.")
    shift_m = horizontal_tide_shift(tide_height_m, beach_slope)
    shoreline_utm = gpd.GeoSeries([shoreline_wgs84], crs=WGS84).to_crs(metric_crs).iloc[0]
    water_utm = None
    if water_polygon_wgs84 is not None:
        water_utm = gpd.GeoSeries([water_polygon_wgs84], crs=WGS84).to_crs(metric_crs).iloc[0]
    land_utm = None
    if land_reference_wgs84 is not None:
        land_point = (
            land_reference_wgs84
            if isinstance(land_reference_wgs84, Point)
            else Point(*land_reference_wgs84)
        )
        land_utm = gpd.GeoSeries([land_point], crs=WGS84).to_crs(metric_crs).iloc[0]

    coordinates = list(shoreline_utm.coords)
    corrected: list[tuple[float, float]] = []
    methods: set[str] = set()
    for index, (x, y) in enumerate(coordinates):
        if index == 0:
            dx, dy = coordinates[1][0] - x, coordinates[1][1] - y
        elif index == len(coordinates) - 1:
            dx, dy = x - coordinates[-2][0], y - coordinates[-2][1]
        else:
            dx = coordinates[index + 1][0] - coordinates[index - 1][0]
            dy = coordinates[index + 1][1] - coordinates[index - 1][1]
        length = float(np.hypot(dx, dy))
        if length == 0:
            corrected.append((x, y))
            continue
        left_normal = (-dy / length, dx / length)
        land_x, land_y, method = _land_normal(
            Point(x, y), left_normal, water_utm, land_utm
        )
        methods.add(method)
        # Observación -> MSL: restar el avance tierra adentro producido por la marea.
        corrected.append((x - land_x * shift_m, y - land_y * shift_m))

    corrected_wgs84 = gpd.GeoSeries(
        [LineString(corrected)], crs=metric_crs
    ).to_crs(WGS84).iloc[0]
    metadata = TideCorrection(
        acquired_at_utc=_as_utc(acquired_at).isoformat() if acquired_at else None,
        tide_height_m=round(float(tide_height_m), 4),
        beach_slope=float(beach_slope),
        horizontal_shift_m=round(float(shift_m), 3),
        datum="MSL",
        model="FES2014b",
        direction_method="+".join(sorted(methods)) or "unchanged_zero_length",
        interpolation_method="linear_with_nearest_valid_extrapolation",
        extrapolation_cutoff_km=FES_EXTRAPOLATION_CUTOFF_KM,
        convention=(
            "tide>0: observed waterline landward of MSL; correction moves seaward"
        ),
    )
    return corrected_wgs84, metadata


def apply_fes2014_correction(
    shoreline_wgs84: LineString,
    lat: float,
    lon: float,
    acquired_at: datetime,
    beach_slope: float,
    *,
    model_dir: str | Path | None = None,
    water_polygon_wgs84=None,
    land_reference_wgs84: Point | tuple[float, float] | None = None,
) -> tuple[LineString, TideCorrection]:
    tide_height = predict_tide_fes2014(lat, lon, acquired_at, model_dir=model_dir)
    return correct_shoreline_to_msl(
        shoreline_wgs84,
        tide_height,
        beach_slope,
        water_polygon_wgs84=water_polygon_wgs84,
        land_reference_wgs84=land_reference_wgs84,
        acquired_at=acquired_at,
    )
