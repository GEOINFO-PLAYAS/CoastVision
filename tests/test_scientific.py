from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.scientific import (
    assess_nearest_infrastructure,
    scientific_pipeline_ready,
)


def test_scientific_pipeline_requires_complete_chain() -> None:
    pipeline = {
        "extracted_ndwi_years": list(range(2016, 2027)),
        "fes2014_corrected_years": list(range(2016, 2027)),
        "satellite_tide_change_complete_2016_2026": True,
        "change_analysis": {"status": "OK", "valid_lrr_count": 38},
    }
    ready, problems = scientific_pipeline_ready(
        pipeline,
        {"building_count": 1},
        shorelines_exist=True,
        rates_exist=True,
        buildings_exist=True,
        roads_exist=True,
    )
    assert ready
    assert problems == []

    pipeline["fes2014_corrected_years"] = [2017, 2026]
    ready, problems = scientific_pipeline_ready(
        pipeline,
        {"building_count": 1},
        shorelines_exist=True,
        rates_exist=True,
        buildings_exist=True,
        roads_exist=True,
    )
    assert not ready
    assert "2016-2026" in problems[0]


def test_nearest_assessment_preserves_pipeline_classification(tmp_path) -> None:
    building_path = tmp_path / "buildings.geojson"
    road_path = tmp_path / "roads.geojson"
    buildings = gpd.GeoDataFrame(
        [
            {
                "osm_id": "way/1",
                "name": "Edificio prueba",
                "feature_type": "building",
                "nearest_transect_id": "T010",
                "erosion_rate_m_per_year": 1.5,
                "distance_to_shoreline_m": 9.0,
                "years_to_impact": 6.0,
                "risk_level": "critico",
                "risk_explanation": "Impacto estimado en menos de 10 años",
                "horizon_years": 30,
                "geometry": Polygon(
                    [(-71.6161, -33.5081), (-71.6160, -33.5081), (-71.6160, -33.5080),
                     (-71.6161, -33.5080), (-71.6161, -33.5081)]
                ),
            }
        ],
        crs=4326,
    )
    roads = gpd.GeoDataFrame(
        [
            {
                "osm_id": "way/2",
                "feature_type": "road",
                "nearest_transect_id": "T020",
                "erosion_rate_m_per_year": -0.5,
                "distance_to_shoreline_m": 200.0,
                "years_to_impact": None,
                "risk_level": "bajo",
                "risk_explanation": "Sin avance erosivo positivo medido",
                "horizon_years": 30,
                "geometry": LineString([(-71.61, -33.50), (-71.609, -33.50)]),
            }
        ],
        crs=4326,
    )
    buildings.to_file(building_path, driver="GeoJSON")
    roads.to_file(road_path, driver="GeoJSON")

    result = assess_nearest_infrastructure(-33.50805, -71.61605, building_path, road_path)
    assert result.osm_id == "way/1"
    assert result.risk_level == "critico"
    assert result.risk_label == "Crítico"
    assert result.erosion_rate_m_per_year == 1.5
    assert result.evidence_source == "pipeline_fes2014_lrr_osm"
