from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from rasterio.transform import from_origin
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.sentinel import (  # noqa: E402
    ShorelineExtraction,
    SentinelScene,
    consensus_shoreline_extractions,
    consensus_shorelines_metric,
    _rank_scenes,
    _request_stac,
    calculate_ndwi,
    normalize_stac_item,
    strict_majority,
)


def _scene(item_id: str, cloud: float) -> SentinelScene:
    return SentinelScene(
        year=2020,
        item_id=item_id,
        acquired_at="2020-02-01T14:50:00Z",
        cloud_cover_pct=cloud,
        provider="earth-search",
        collection="sentinel-2-l2a",
        processing_level="L2A",
        tile_code="19HBC",
        coverage_fraction=1.0,
        green_asset="green.tif",
        nir_asset="nir.tif",
        scl_asset="scl.tif",
        product_asset=None,
        requires_authentication=False,
        item_url=None,
        data_status="public_cog_ready",
    )


def test_ndwi_formula_and_invalid_pixels():
    green = np.array([[6.0, 1.0], [0.0, 3.0]], dtype=np.float32)
    nir = np.array([[2.0, 3.0], [0.0, 1.0]], dtype=np.float32)
    valid = np.array([[True, True], [True, False]])
    result = calculate_ndwi(green, nir, valid)
    assert result[0, 0] == pytest.approx(0.5)
    assert result[0, 1] == pytest.approx(-0.5)
    assert np.isnan(result[1, 0])
    assert np.isnan(result[1, 1])


def test_strict_majority_rejects_ties():
    one = np.array([[True, False], [True, False]])
    two = np.array([[False, True], [True, False]])
    result = strict_majority([one, two])
    assert result.tolist() == [[False, False], [True, False]]


def test_strict_majority_requires_aligned_grids():
    with pytest.raises(ValueError, match="alineadas"):
        strict_majority([np.ones((2, 2)), np.ones((3, 2))])


def test_scene_ranking_preserves_zero_cloud_cover():
    selected = _rank_scenes([_scene("cloud-zero", 0.0), _scene("cloud-two", 2.0)])
    assert [scene.item_id for scene in selected] == ["cloud-zero"]


def test_stac_february_uses_calendar_month_end(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"features": []}

    def fake_post(url, json, timeout):
        captured.update(json)
        return Response()

    monkeypatch.setattr("coastvision.sentinel.requests.post", fake_post)
    _request_stac(
        "https://example.test/stac",
        "sentinel-test",
        [-71.7, -33.6, -71.5, -33.4],
        2024,
        start_month=1,
        end_month=2,
    )
    assert captured["datetime"].endswith("2024-02-29T23:59:59Z")


def test_normalize_earth_search_item_uses_public_l2a_assets():
    item = {
        "id": "scene-2019",
        "collection": "sentinel-2-l2a",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-72, -34], [-71, -34], [-71, -33], [-72, -33], [-72, -34]]],
        },
        "properties": {
            "datetime": "2019-02-01T14:50:00Z",
            "eo:cloud_cover": 2.5,
            "s2:mgrs_tile": "19HBC",
        },
        "assets": {
            "green": {"href": "https://example/B03.tif"},
            "nir": {"href": "https://example/B08.tif"},
            "scl": {"href": "https://example/SCL.tif"},
        },
        "links": [{"rel": "self", "href": "https://example/item.json"}],
    }
    scene = normalize_stac_item(item, 2019, [-71.7, -33.6, -71.5, -33.4], "earth-search")
    assert scene.processing_level == "L2A"
    assert scene.requires_authentication is False
    assert scene.scl_asset.endswith("SCL.tif")
    assert scene.data_status == "public_cog_ready"


def test_normalize_cdse_marks_2016_auth_requirement():
    item = {
        "id": "scene-2016",
        "collection": "sentinel-2-l1c",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-72, -34], [-71, -34], [-71, -33], [-72, -33], [-72, -34]]],
        },
        "properties": {"datetime": "2016-02-14T14:51:22Z", "eo:cloud_cover": 0.0},
        "assets": {
            "B03": {"href": "s3://eodata/example/B03.jp2"},
            "B08": {"href": "s3://eodata/example/B08.jp2"},
            "Product": {"href": "https://zipper.example/product"},
        },
    }
    scene = normalize_stac_item(
        item, 2016, [-71.7, -33.6, -71.5, -33.4], "copernicus-data-space"
    )
    assert scene.processing_level == "L1C"
    assert scene.requires_authentication is True
    assert scene.data_status == "catalogued_auth_download_required"


def test_normalize_public_earth_search_l1c_converts_s3_to_https():
    item = {
        "id": "scene-2016-public",
        "collection": "sentinel-s2-l1c",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-72, -34], [-71, -34], [-71, -33], [-72, -33], [-72, -34]]],
        },
        "properties": {"datetime": "2016-02-04T14:42:56Z", "eo:cloud_cover": 35.42},
        "assets": {
            "B03": {"href": "s3://sentinel-s2-l1c/tiles/19/H/BC/2016/2/4/0/B03.jp2"},
            "B08": {"href": "s3://sentinel-s2-l1c/tiles/19/H/BC/2016/2/4/0/B08.jp2"},
        },
    }
    scene = normalize_stac_item(
        item, 2016, [-71.7, -33.6, -71.5, -33.4], "earth-search-l1c"
    )
    assert scene.processing_level == "L1C"
    assert scene.requires_authentication is False
    assert scene.green_asset.startswith("https://sentinel-s2-l1c.s3.eu-central-1.amazonaws.com/")
    assert scene.scl_asset is None


def test_consensus_uses_strict_majority_in_metric_grid():
    reference = LineString([(-71.61, -33.49), (-71.61, -33.50)])
    water_a = Polygon([
        (-71.64, -33.49), (-71.6102, -33.49),
        (-71.6102, -33.50), (-71.64, -33.50), (-71.64, -33.49),
    ])
    water_b = Polygon([
        (-71.64, -33.49), (-71.6105, -33.49),
        (-71.6105, -33.50), (-71.64, -33.50), (-71.64, -33.49),
    ])
    base = dict(
        shoreline_wgs84=reference,
        ndwi=np.ones((2, 2), dtype=np.float32),
        valid_mask=np.ones((2, 2), dtype=bool),
        transform=from_origin(0, 0, 10, 10),
        raster_crs="EPSG:32719",
        metadata={},
    )
    first = ShorelineExtraction(scene=_scene("scene-a", 1.0), water_polygon_wgs84=water_a, **base)
    second = ShorelineExtraction(scene=_scene("scene-b", 2.0), water_polygon_wgs84=water_b, **base)

    line, water, metadata = consensus_shoreline_extractions(
        [first, second], reference, min_scenes=2, pixel_size_m=10.0
    )

    assert line.geom_type == "LineString"
    assert not line.is_empty
    assert water.area > 0
    assert metadata["method"] == "strict_majority_water_mask_utm19s"
    assert metadata["scene_count"] == 2
    assert metadata["water_area_cv_pct"] is not None


def test_metric_median_aligns_reversed_corrected_lines():
    first = LineString([
        (-71.62, -33.49), (-71.619, -33.495), (-71.618, -33.50)
    ])
    second = LineString([
        (-71.618, -33.50), (-71.6191, -33.495), (-71.6202, -33.49)
    ])
    result = consensus_shorelines_metric([first, second], count=7)
    assert result.geom_type == "LineString"
    assert len(result.coords) == 7
    assert result.coords[0][1] == pytest.approx(-33.49, abs=2e-4)
    assert result.coords[-1][1] == pytest.approx(-33.50, abs=2e-4)
