"""Funciones puras para enriquecer la exploración cartográfica del MVP."""

from __future__ import annotations

import math

from shapely.geometry import LineString
from shapely.ops import transform
from pyproj import Transformer


_WGS84_TO_UTM19S = Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True)
_UTM19S_TO_WGS84 = Transformer.from_crs("EPSG:32719", "EPSG:4326", always_xy=True)


def _resample_line(line: LineString, count: int) -> list[tuple[float, float]]:
    if count < 2:
        raise ValueError("count debe ser al menos 2.")
    if line.is_empty or line.length <= 0:
        raise ValueError("La línea no puede estar vacía.")
    return [
        (
            float(line.interpolate(line.length * index / (count - 1)).x),
            float(line.interpolate(line.length * index / (count - 1)).y),
        )
        for index in range(count)
    ]


def interpolate_shorelines(
    historical: LineString,
    current: LineString,
    progress: float,
    *,
    count: int = 150,
) -> LineString:
    """Interpola dos líneas con muestreo uniforme para una animación estable.

    El resultado es una comparación visual explícitamente demostrativa; no
    reemplaza una línea satelital anual ni una interpolación física del litoral.
    """
    if not math.isfinite(progress):
        raise ValueError("progress debe ser finito.")
    progress = min(1.0, max(0.0, float(progress)))
    # Interpolar en UTM 19S evita mezclar grados con metros y hace el avance
    # físicamente coherente. También se alinea la orientación de las líneas;
    # si una fue digitalizada al revés, interpolar por índice produce cruces.
    historical_utm = transform(_WGS84_TO_UTM19S.transform, historical)
    current_utm = transform(_WGS84_TO_UTM19S.transform, current)
    first = _resample_line(historical_utm, count)
    second_line = current_utm
    direct = math.hypot(
        historical_utm.coords[0][0] - current_utm.coords[0][0],
        historical_utm.coords[0][1] - current_utm.coords[0][1],
    )
    reverse = math.hypot(
        historical_utm.coords[0][0] - current_utm.coords[-1][0],
        historical_utm.coords[0][1] - current_utm.coords[-1][1],
    )
    if reverse < direct:
        second_line = LineString(list(current_utm.coords)[::-1])
    second = _resample_line(second_line, count)
    interpolated_utm = LineString(
        [
            (
                x_first + (x_second - x_first) * progress,
                y_first + (y_second - y_first) * progress,
            )
            for (x_first, y_first), (x_second, y_second) in zip(first, second)
        ]
    )
    return transform(_UTM19S_TO_WGS84.transform, interpolated_utm)


def shoreline_displacement_m(reference: LineString, candidate: LineString, *, count: int = 150) -> float:
    """Promedio de desplazamiento entre dos costas, expresado en metros."""
    reference_utm = transform(_WGS84_TO_UTM19S.transform, reference)
    candidate_utm = transform(_WGS84_TO_UTM19S.transform, candidate)
    first = _resample_line(reference_utm, count)
    second = _resample_line(candidate_utm, count)
    distances = [
        math.hypot(x_first - x_second, y_first - y_second)
        for (x_first, y_first), (x_second, y_second) in zip(first, second)
    ]
    return sum(distances) / len(distances)
