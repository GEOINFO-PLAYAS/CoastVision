"""Geometría mínima para ubicar las consultas de elevación del hito v05."""

from __future__ import annotations

import math

from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform


WGS84 = "EPSG:4326"
UTM_19S = "EPSG:32719"
STATION_COUNT = 11
ELEVATION_OFFSETS_M = (50, 150, 250)

_TO_UTM = Transformer.from_crs(WGS84, UTM_19S, always_xy=True)
_TO_WGS84 = Transformer.from_crs(UTM_19S, WGS84, always_xy=True)


def _to_utm(geometry):
    return transform(_TO_UTM.transform, geometry)


def _to_wgs84(geometry):
    return transform(_TO_WGS84.transform, geometry)


def _local_frame(line: LineString, distance_m: float) -> tuple[Point, float, float]:
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
    return line.interpolate(distance_m), -ty, tx


def elevation_query_points_for_shoreline(
    shoreline_wgs84: LineString,
) -> list[dict[str, float | int | str]]:
    """Genera E01-E11 y offsets 50/150/250 m para consultar el DEM."""
    shoreline = _to_utm(shoreline_wgs84)
    records: list[dict[str, float | int | str]] = []
    spacing = shoreline.length / (STATION_COUNT - 1)
    for index in range(STATION_COUNT):
        station_id = f"E{index + 1:02d}"
        coast, nx, ny = _local_frame(shoreline, spacing * index)
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