from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import transform


WGS84 = "EPSG:4326"
UTM_19S = "EPSG:32719"
BASE_YEAR = 2026
HISTORICAL_YEAR = 2017
DEFAULT_RETREAT_RATE = 1.5

# Centro visual aproximado; el mapa usa fit_bounds sobre el corredor completo.
CENTER_LAT = -33.5083
CENTER_LON = -71.6154

STATION_COUNT = 11
TRANSECT_SEAWARD_M = 50.0
TRANSECT_LANDWARD_M = 260.0
ELEVATION_OFFSETS_M = (50, 150, 250)
CRITICAL_DISTANCE_M = 25.0
CAUTION_DISTANCE_M = 60.0

ELEVATION_SOURCE = "Copernicus DEM GLO-90 vía Open-Meteo"
ELEVATION_SOURCE_URL = "https://open-meteo.com/en/docs/elevation-api"
ELEVATION_RESOLUTION_M = 90

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COASTLINE_PATH = PROJECT_ROOT / "data" / "playa_grande_shoreline_osm.geojson"
ELEVATION_PATH = PROJECT_ROOT / "data" / "elevation_profile_open_meteo.json"
PROVENANCE_PATH = PROJECT_ROOT / "data" / "provenance_manifest.json"

_TO_UTM = Transformer.from_crs(WGS84, UTM_19S, always_xy=True)
_TO_WGS84 = Transformer.from_crs(UTM_19S, WGS84, always_xy=True)


@dataclass(frozen=True)
class RiskAssessment:
    level: str
    label: str
    color: str
    distance_m: float
    signed_margin_m: float
    baseline_margin_m: float
    retreat_m: float
    reached_by_projection: bool
    recommendation: str
    latitude: float
    longitude: float
    alongshore_m: float
    nearest_station_id: str
    station_distance_m: float
    elevation_m: float | None
    elevation_sample_distance_m: float | None
    elevation_offset_m: int | None
    elevation_source: str
    elevation_resolution_m: int


RISK_STYLE = {
    "critico": (
        "Crítico",
        "#B42318",
        "No recomendado para decisiones operacionales sin un estudio costero detallado.",
    ),
    "precaucion": (
        "Precaución",
        "#B97512",
        "Revisar diseño, retiro y medidas de adaptación antes de definir intervenciones.",
    ),
    "bajo": (
        "Bajo en este escenario",
        "#2E7D55",
        "Mantener monitoreo: un riesgo bajo no equivale a riesgo cero.",
    ),
    "fuera": (
        "Fuera del corredor terrestre",
        "#62727D",
        "Seleccione un punto dentro del corredor ampliado de 260 m tierra adentro.",
    ),
}


def _to_wgs84(geometry):
    return transform(_TO_WGS84.transform, geometry)


def _to_utm(geometry):
    return transform(_TO_UTM.transform, geometry)


@lru_cache(maxsize=1)
def _base_shoreline_wgs84() -> LineString:
    payload = json.loads(COASTLINE_PATH.read_text(encoding="utf-8"))
    geometry = shape(payload["features"][0]["geometry"])
    if not isinstance(geometry, LineString):
        raise ValueError("La geometría costera base debe ser LineString.")
    return geometry


@lru_cache(maxsize=1)
def _base_shoreline_utm() -> LineString:
    return _to_utm(_base_shoreline_wgs84())


def _local_frame(line: LineString, distance_m: float) -> tuple[Point, float, float, float, float]:
    distance_m = min(max(distance_m, 0.0), line.length)
    window = min(8.0, max(2.0, line.length / 500.0))
    start = line.interpolate(max(0.0, distance_m - window))
    end = line.interpolate(min(line.length, distance_m + window))
    dx = end.x - start.x
    dy = end.y - start.y
    norm = math.hypot(dx, dy)
    if norm == 0:
        raise ValueError("No se pudo calcular la orientación local de la costa.")
    tx, ty = dx / norm, dy / norm
    # El arco marino se extrae del polígono OSM natural=beach y se orienta
    # norte-sur; con esa orientación, la tierra queda al lado izquierdo.
    nx, ny = -ty, tx
    return line.interpolate(distance_m), tx, ty, nx, ny


def _normal_offset(line: LineString, offset_m: float) -> LineString:
    """Genera un offset paralelo simple y topológicamente robusto.

    Desplazar cada vértice por su normal local pliega la línea cuando el
    trazado OSM contiene giros cortos y cerrados. ``offset_curve`` resuelve las
    uniones cóncavas/convexas en GEOS y elimina esos cruces espurios.
    """
    if math.isclose(offset_m, 0.0, abs_tol=1e-9):
        return LineString(line.coords)

    shifted = line.offset_curve(
        offset_m,
        quad_segs=8,
        join_style="round",
    )
    if not isinstance(shifted, LineString) or shifted.is_empty:
        raise ValueError("El offset costero no produjo una línea continua.")
    if not shifted.is_simple:
        raise ValueError("El offset costero produjo una autointersección.")
    return shifted


def _corridor_polygon(
    shoreline: LineString,
    seaward_m: float,
    landward_m: float,
) -> Polygon:
    seaward = _normal_offset(shoreline, -seaward_m)
    landward = _normal_offset(shoreline, landward_m)
    polygon = Polygon(list(seaward.coords) + list(reversed(landward.coords)))
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty:
        raise ValueError("El corredor de estudio quedó vacío.")
    return polygon


def _offset_band_polygon(
    shoreline: LineString,
    start_m: float,
    end_m: float,
) -> Polygon:
    """Construye una franja entre dos offsets tierra adentro desde la costa base."""
    start_m = max(0.0, start_m)
    end_m = max(start_m, end_m)
    if math.isclose(start_m, end_m, abs_tol=1e-9):
        return Polygon()
    inner = _normal_offset(shoreline, start_m)
    outer = _normal_offset(shoreline, end_m)
    polygon = Polygon(list(inner.coords) + list(reversed(outer.coords)))
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return polygon


def projected_shoreline_utm(
    year: int,
    retreat_rate: float = DEFAULT_RETREAT_RATE,
) -> LineString:
    retreat_m = max(0, year - BASE_YEAR) * retreat_rate
    return _normal_offset(_base_shoreline_utm(), retreat_m)


def _risk_for_margin(signed_margin_m: float) -> str:
    if signed_margin_m <= CRITICAL_DISTANCE_M:
        return "critico"
    if signed_margin_m <= CAUTION_DISTANCE_M:
        return "precaucion"
    return "bajo"


def _signed_margin(
    point: Point,
    projected: LineString,
    impact_zone,
) -> tuple[float, bool]:
    distance_m = point.distance(projected)
    reached = not impact_zone.is_empty and impact_zone.buffer(0.15).covers(point)
    return (-distance_m if reached else distance_m), reached


@lru_cache(maxsize=1)
def _elevation_lookup() -> dict[tuple[str, int], float]:
    if not ELEVATION_PATH.exists():
        return {}
    payload = json.loads(ELEVATION_PATH.read_text(encoding="utf-8"))
    return {
        (str(item["station_id"]), int(item["offset_m"])): float(item["elevation_m"])
        for item in payload.get("samples", [])
        if item.get("elevation_m") is not None
    }


def elevation_query_points_for_shoreline(
    shoreline_wgs84: LineString,
) -> list[dict[str, float | int | str]]:
    shoreline = _to_utm(shoreline_wgs84)
    records: list[dict[str, float | int | str]] = []
    spacing = shoreline.length / (STATION_COUNT - 1)
    for index in range(STATION_COUNT):
        station_id = f"E{index + 1:02d}"
        distance_m = spacing * index
        coast, _, _, nx, ny = _local_frame(shoreline, distance_m)
        for offset_m in ELEVATION_OFFSETS_M:
            sample_utm = Point(coast.x + nx * offset_m, coast.y + ny * offset_m)
            sample_wgs84 = _to_wgs84(sample_utm)
            records.append(
                {
                    "station_id": station_id,
                    "offset_m": offset_m,
                    "latitude": round(sample_wgs84.y, 7),
                    "longitude": round(sample_wgs84.x, 7),
                }
            )
    return records


def elevation_query_points() -> list[dict[str, float | int | str]]:
    return elevation_query_points_for_shoreline(_base_shoreline_wgs84())


@lru_cache(maxsize=1)
def load_provenance_manifest() -> dict:
    if not PROVENANCE_PATH.exists():
        return {}
    return json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))


def _measurement_network_utm() -> tuple[list[dict], list[dict], list[dict]]:
    shoreline = _base_shoreline_utm()
    spacing = shoreline.length / (STATION_COUNT - 1)
    elevations = _elevation_lookup()
    stations: list[dict] = []
    transects: list[dict] = []
    samples: list[dict] = []

    for index in range(STATION_COUNT):
        station_id = f"E{index + 1:02d}"
        alongshore_m = spacing * index
        coast, _, _, nx, ny = _local_frame(shoreline, alongshore_m)
        coast_wgs84 = _to_wgs84(coast)
        seaward = Point(
            coast.x - nx * TRANSECT_SEAWARD_M,
            coast.y - ny * TRANSECT_SEAWARD_M,
        )
        landward = Point(
            coast.x + nx * TRANSECT_LANDWARD_M,
            coast.y + ny * TRANSECT_LANDWARD_M,
        )
        transects.append(
            {
                "station_id": station_id,
                "alongshore_m": round(alongshore_m, 1),
                "seaward_m": TRANSECT_SEAWARD_M,
                "landward_m": TRANSECT_LANDWARD_M,
                "length_m": TRANSECT_SEAWARD_M + TRANSECT_LANDWARD_M,
                "geometry": LineString([seaward, landward]),
            }
        )

        station_elevations: dict[int, float | None] = {}
        for offset_m in ELEVATION_OFFSETS_M:
            sample_utm = Point(coast.x + nx * offset_m, coast.y + ny * offset_m)
            elevation_m = elevations.get((station_id, offset_m))
            station_elevations[offset_m] = elevation_m
            samples.append(
                {
                    "station_id": station_id,
                    "offset_m": offset_m,
                    "elevation_m": elevation_m,
                    "geometry": sample_utm,
                }
            )

        elevation_50 = station_elevations[50]
        elevation_250 = station_elevations[250]
        slope_pct = None
        if elevation_50 is not None and elevation_250 is not None:
            slope_pct = round((elevation_250 - elevation_50) / 200.0 * 100.0, 2)
        stations.append(
            {
                "station_id": station_id,
                "alongshore_m": round(alongshore_m, 1),
                "latitude": round(coast_wgs84.y, 7),
                "longitude": round(coast_wgs84.x, 7),
                "elevation_50m": elevation_50,
                "elevation_150m": station_elevations[150],
                "elevation_250m": elevation_250,
                "slope_pct_50_250": slope_pct,
                "geometry": coast,
            }
        )
    return stations, transects, samples


def _building_polygon(
    coast: Point,
    tx: float,
    ty: float,
    nx: float,
    ny: float,
    offset_m: float,
) -> Polygon:
    cx, cy = coast.x + nx * offset_m, coast.y + ny * offset_m
    half_along, half_cross = 8.0, 6.0
    return Polygon(
        [
            (cx - tx * half_along - nx * half_cross, cy - ty * half_along - ny * half_cross),
            (cx + tx * half_along - nx * half_cross, cy + ty * half_along - ny * half_cross),
            (cx + tx * half_along + nx * half_cross, cy + ty * half_along + ny * half_cross),
            (cx - tx * half_along + nx * half_cross, cy - ty * half_along + ny * half_cross),
        ]
    )


def _buildings_utm() -> list[dict]:
    shoreline = _base_shoreline_utm()
    spacing = shoreline.length / (STATION_COUNT - 1)
    features: list[dict] = []
    building_id = 1
    for index in range(STATION_COUNT):
        coast, tx, ty, nx, ny = _local_frame(shoreline, spacing * index)
        for offset_m in (18.0, 48.0, 95.0):
            features.append(
                {
                    "predio_id": f"PG-{building_id:02d}",
                    "geometry": _building_polygon(coast, tx, ty, nx, ny, offset_m),
                }
            )
            building_id += 1
    return features


def _nearest_measurement(point: Point) -> tuple[str, float, float | None, float | None, int | None]:
    stations, _, samples = _measurement_network_utm()
    nearest_station = min(stations, key=lambda item: point.distance(item["geometry"]))
    nearest_sample = min(samples, key=lambda item: point.distance(item["geometry"]))
    sample_distance = point.distance(nearest_sample["geometry"])
    elevation = nearest_sample["elevation_m"]
    return (
        str(nearest_station["station_id"]),
        point.distance(nearest_station["geometry"]),
        float(elevation) if elevation is not None else None,
        sample_distance if elevation is not None else None,
        int(nearest_sample["offset_m"]) if elevation is not None else None,
    )


def evaluate_location(
    lat: float,
    lon: float,
    year: int = 2035,
    retreat_rate: float = DEFAULT_RETREAT_RATE,
) -> RiskAssessment:
    point = _to_utm(Point(lon, lat))
    current = _base_shoreline_utm()
    retreat_m = max(0, year - BASE_YEAR) * retreat_rate
    projected = projected_shoreline_utm(year, retreat_rate)
    land = _corridor_polygon(current, 0.0, TRANSECT_LANDWARD_M)
    impact_zone = _offset_band_polygon(current, 0.0, retreat_m).intersection(land).buffer(0)
    signed_margin, reached = _signed_margin(point, projected, impact_zone)
    distance = abs(signed_margin)
    baseline_margin = point.distance(current)
    station_id, station_distance, elevation, elevation_distance, elevation_offset = (
        _nearest_measurement(point)
    )
    alongshore_m = current.project(point)

    if not land.buffer(5).contains(point):
        label, color, recommendation = RISK_STYLE["fuera"]
        return RiskAssessment(
            level="fuera",
            label=label,
            color=color,
            distance_m=distance,
            signed_margin_m=signed_margin,
            baseline_margin_m=baseline_margin,
            retreat_m=retreat_m,
            reached_by_projection=reached,
            recommendation=recommendation,
            latitude=lat,
            longitude=lon,
            alongshore_m=alongshore_m,
            nearest_station_id=station_id,
            station_distance_m=station_distance,
            elevation_m=elevation,
            elevation_sample_distance_m=elevation_distance,
            elevation_offset_m=elevation_offset,
            elevation_source=ELEVATION_SOURCE,
            elevation_resolution_m=ELEVATION_RESOLUTION_M,
        )

    level = _risk_for_margin(signed_margin)
    label, color, recommendation = RISK_STYLE[level]
    if reached:
        recommendation = (
            "La línea proyectada ya supera este punto en el escenario seleccionado; "
            "trátelo como zona crítica alcanzada."
        )
    return RiskAssessment(
        level=level,
        label=label,
        color=color,
        distance_m=distance,
        signed_margin_m=signed_margin,
        baseline_margin_m=baseline_margin,
        retreat_m=retreat_m,
        reached_by_projection=reached,
        recommendation=recommendation,
        latitude=lat,
        longitude=lon,
        alongshore_m=alongshore_m,
        nearest_station_id=station_id,
        station_distance_m=station_distance,
        elevation_m=elevation,
        elevation_sample_distance_m=elevation_distance,
        elevation_offset_m=elevation_offset,
        elevation_source=ELEVATION_SOURCE,
        elevation_resolution_m=ELEVATION_RESOLUTION_M,
    )


def build_demo_layers(
    year: int = 2035,
    retreat_rate: float = DEFAULT_RETREAT_RATE,
) -> dict[str, object]:
    current = _base_shoreline_utm()
    retreat_m = max(0, year - BASE_YEAR) * retreat_rate
    historical = _normal_offset(
        current,
        -(BASE_YEAR - HISTORICAL_YEAR) * DEFAULT_RETREAT_RATE,
    )
    projected = projected_shoreline_utm(year, retreat_rate)
    land = _corridor_polygon(current, 0.0, TRANSECT_LANDWARD_M)
    study_area = _corridor_polygon(current, TRANSECT_SEAWARD_M, TRANSECT_LANDWARD_M)

    # Las franjas se construyen acumulativamente desde la costa base 2026.
    # Así, el terreno ya sobrepasado por la proyección nunca reaparece como verde.
    impact_zone = _offset_band_polygon(current, 0.0, retreat_m).intersection(land).buffer(0)
    red = (
        _offset_band_polygon(current, 0.0, retreat_m + CRITICAL_DISTANCE_M)
        .intersection(land)
        .buffer(0)
    )
    amber = (
        _offset_band_polygon(
            current,
            retreat_m + CRITICAL_DISTANCE_M,
            retreat_m + CAUTION_DISTANCE_M,
        )
        .intersection(land)
        .buffer(0)
    )
    green = land.difference(red.union(amber)).buffer(0)
    base_caution_boundary = _normal_offset(current, CAUTION_DISTANCE_M)
    scenario_caution_boundary = _normal_offset(current, retreat_m + CAUTION_DISTANCE_M)

    station_records, transect_records, sample_records = _measurement_network_utm()
    stations_utm = gpd.GeoDataFrame(station_records, crs=UTM_19S)
    transects_utm = gpd.GeoDataFrame(transect_records, crs=UTM_19S)
    samples_utm = gpd.GeoDataFrame(sample_records, crs=UTM_19S)

    buildings = []
    counts = {"critico": 0, "precaucion": 0, "bajo": 0}
    for item in _buildings_utm():
        centroid = item["geometry"].centroid
        signed_margin, reached = _signed_margin(centroid, projected, impact_zone)
        distance = abs(signed_margin)
        level = _risk_for_margin(signed_margin)
        counts[level] += 1
        label, color, _ = RISK_STYLE[level]
        buildings.append(
            {
                "predio_id": item["predio_id"],
                "nivel": level,
                "riesgo": label,
                "color": color,
                "distancia_m": round(distance, 1),
                "margen_firmado_m": round(signed_margin, 1),
                "alcanzado": reached,
                "geometry": _to_wgs84(item["geometry"]),
            }
        )

    stations = stations_utm.to_crs(WGS84)
    transects = transects_utm.to_crs(WGS84)
    elevation_samples = samples_utm.to_crs(WGS84)
    base_wgs84 = _base_shoreline_wgs84()
    min_lon, min_lat, max_lon, max_lat = _to_wgs84(study_area).bounds
    profile = stations.drop(columns="geometry").copy()

    return {
        "year": year,
        "retreat_rate": retreat_rate,
        "retreat_m": round(retreat_m, 1),
        "counts": counts,
        "area_metrics": {
            "impact_area_m2": round(impact_zone.area, 1),
            "impact_area_ha": round(impact_zone.area / 10_000.0, 2),
            "critical_area_m2": round(red.area, 1),
            "caution_area_m2": round(amber.area, 1),
            "low_area_m2": round(green.area, 1),
            "critical_limit_from_2026_m": round(retreat_m + CRITICAL_DISTANCE_M, 1),
            "caution_limit_from_2026_m": round(retreat_m + CAUTION_DISTANCE_M, 1),
        },
        "coverage": {
            "length_m": round(current.length, 1),
            "lat_min": round(base_wgs84.bounds[1], 7),
            "lat_max": round(base_wgs84.bounds[3], 7),
            "lon_min": round(base_wgs84.bounds[0], 7),
            "lon_max": round(base_wgs84.bounds[2], 7),
            "station_count": STATION_COUNT,
            "spacing_m": round(current.length / (STATION_COUNT - 1), 1),
            "transect_length_m": TRANSECT_SEAWARD_M + TRANSECT_LANDWARD_M,
            "bounds": [[min_lat, min_lon], [max_lat, max_lon]],
            "elevation_source": ELEVATION_SOURCE,
            "elevation_source_url": ELEVATION_SOURCE_URL,
            "elevation_resolution_m": ELEVATION_RESOLUTION_M,
        },
        "provenance": load_provenance_manifest(),
        "shorelines": gpd.GeoDataFrame(
            [
                {
                    "year": HISTORICAL_YEAR,
                    "type": "historica",
                    "data_status": "escenario_demostrativo_no_observado",
                    "observed": False,
                    "geometry": _to_wgs84(historical),
                },
                {
                    "year": BASE_YEAR,
                    "type": "actual",
                    "data_status": "referencia_osm_anio_cero_no_observacion_2026",
                    "observed": False,
                    "geometry": _to_wgs84(current),
                },
                {
                    "year": year,
                    "type": "proyectada",
                    "data_status": "escenario_demostrativo_no_observado",
                    "observed": False,
                    "geometry": _to_wgs84(projected),
                },
            ],
            crs=WGS84,
        ),
        "risk_bands": gpd.GeoDataFrame(
            [
                {
                    "nivel": "critico",
                    "desde_m": 0,
                    "hasta_m": retreat_m + CRITICAL_DISTANCE_M,
                    "label": (
                        f"Crítico: referencia base hasta {CRITICAL_DISTANCE_M:.0f} m "
                        f"tierra adentro de la línea {year}"
                    ),
                    "geometry": _to_wgs84(red).buffer(0),
                },
                {
                    "nivel": "precaucion",
                    "desde_m": retreat_m + CRITICAL_DISTANCE_M,
                    "hasta_m": retreat_m + CAUTION_DISTANCE_M,
                    "label": f"Precaución: 25-60 m tierra adentro de la línea {year}",
                    "geometry": _to_wgs84(amber).buffer(0),
                },
                {
                    "nivel": "bajo",
                    "desde_m": retreat_m + CAUTION_DISTANCE_M,
                    "hasta_m": TRANSECT_LANDWARD_M,
                    "label": f"Bajo: más de 60 m tierra adentro de la línea {year}",
                    "geometry": _to_wgs84(green).buffer(0),
                },
            ],
            crs=WGS84,
        ),
        "impact_zone": gpd.GeoDataFrame(
            [
                {
                    "name": f"Área alcanzada por la proyección 2026-{year}",
                    "retreat_m": retreat_m,
                    "geometry": _to_wgs84(impact_zone).buffer(0),
                }
            ],
            crs=WGS84,
        ),
        "risk_boundaries": gpd.GeoDataFrame(
            [
                {
                    "year": BASE_YEAR,
                    "type": "base",
                    "distance_from_2026_m": CAUTION_DISTANCE_M,
                    "geometry": _to_wgs84(base_caution_boundary),
                },
                {
                    "year": year,
                    "type": "scenario",
                    "distance_from_2026_m": retreat_m + CAUTION_DISTANCE_M,
                    "geometry": _to_wgs84(scenario_caution_boundary),
                },
            ],
            crs=WGS84,
        ),
        "study_area": gpd.GeoDataFrame(
            [
                {
                    "name": "Corredor de medición ampliado",
                    "seaward_m": TRANSECT_SEAWARD_M,
                    "landward_m": TRANSECT_LANDWARD_M,
                    "geometry": _to_wgs84(study_area).buffer(0),
                }
            ],
            crs=WGS84,
        ),
        "stations": stations,
        "transects": transects,
        "elevation_samples": elevation_samples,
        "elevation_profile": profile,
        "buildings": gpd.GeoDataFrame(buildings, crs=WGS84),
    }
