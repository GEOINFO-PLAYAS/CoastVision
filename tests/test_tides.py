from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.tides import (
    correct_shoreline_to_msl,
    horizontal_tide_shift,
)


def _utm(geometry):
    return gpd.GeoSeries([geometry], crs="EPSG:4326").to_crs("EPSG:32719").iloc[0]


def test_horizontal_tide_shift_validates_slope():
    assert horizontal_tide_shift(1.0, 0.05) == pytest.approx(20.0)
    with pytest.raises(ValueError):
        horizontal_tide_shift(1.0, 0.0)


def test_positive_tide_is_corrected_seaward_using_land_reference():
    # Línea norte-sur; tierra al este, mar al oeste.
    shoreline = LineString([(-71.616, -33.502), (-71.616, -33.512)])
    land = Point(-71.610, -33.507)
    corrected, metadata = correct_shoreline_to_msl(
        shoreline,
        tide_height_m=1.0,
        beach_slope=0.05,
        land_reference_wgs84=land,
        acquired_at=datetime(2026, 2, 16, 14, 51, tzinfo=timezone.utc),
    )
    original_utm = _utm(shoreline)
    corrected_utm = _utm(corrected)
    # Se mueve ~20 m al oeste, es decir, en sentido contrario a la referencia de tierra.
    assert corrected_utm.centroid.x < original_utm.centroid.x
    assert corrected_utm.centroid.distance(original_utm.centroid) == pytest.approx(20.0, abs=0.2)
    assert metadata.horizontal_shift_m == 20.0
    assert metadata.direction_method == "land_reference"


def test_water_polygon_controls_direction_even_if_vertex_order_reverses():
    south_to_north = LineString([(-71.616, -33.512), (-71.616, -33.502)])
    # Caja occidental: el agua está al oeste de la línea.
    water = box(-71.625, -33.52, -71.616, -33.495)
    corrected, metadata = correct_shoreline_to_msl(
        south_to_north,
        tide_height_m=0.5,
        beach_slope=0.05,
        water_polygon_wgs84=water,
    )
    assert _utm(corrected).centroid.x < _utm(south_to_north).centroid.x
    assert metadata.direction_method == "water_polygon"


def test_direction_must_be_explicit():
    shoreline = LineString([(-71.616, -33.502), (-71.616, -33.512)])
    with pytest.raises(ValueError, match="lado tierra/mar"):
        correct_shoreline_to_msl(shoreline, 0.5, 0.05)
