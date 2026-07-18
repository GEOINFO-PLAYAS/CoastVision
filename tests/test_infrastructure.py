from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.infrastructure import (  # noqa: E402
    assess_infrastructure_risk,
    build_overpass_query,
    parse_overpass_infrastructure,
)


def test_query_contains_buildings_and_highways():
    query = build_overpass_query([-71.7, -33.6, -71.5, -33.4])
    assert 'way["building"]' in query
    assert 'way["highway"]' in query


def test_parse_overpass_building_and_road():
    payload = {"elements": [
        {"type": "way", "id": 1, "tags": {"building": "yes"}, "geometry": [
            {"lon": -71.6, "lat": -33.5}, {"lon": -71.5999, "lat": -33.5},
            {"lon": -71.5999, "lat": -33.5001}, {"lon": -71.6, "lat": -33.5001},
            {"lon": -71.6, "lat": -33.5},
        ]},
        {"type": "way", "id": 2, "tags": {"highway": "residential"}, "geometry": [
            {"lon": -71.6, "lat": -33.5}, {"lon": -71.59, "lat": -33.5},
        ]},
    ]}
    buildings, roads = parse_overpass_infrastructure(payload)
    assert len(buildings) == 1
    assert len(roads) == 1
    assert buildings.iloc[0]["osm_id"] == "way/1"


def test_parse_overpass_building_relation_members():
    ring = [
        {"lon": -71.6, "lat": -33.5},
        {"lon": -71.5999, "lat": -33.5},
        {"lon": -71.5999, "lat": -33.5001},
        {"lon": -71.6, "lat": -33.5001},
        {"lon": -71.6, "lat": -33.5},
    ]
    payload = {"elements": [{
        "type": "relation",
        "id": 3,
        "tags": {"building": "yes", "type": "multipolygon"},
        "members": [{"type": "way", "role": "outer", "geometry": ring}],
    }]}
    buildings, roads = parse_overpass_infrastructure(payload)
    assert len(buildings) == 1
    assert buildings.iloc[0]["osm_id"] == "relation/3"
    assert roads.empty


def test_risk_combines_distance_and_local_rate():
    shoreline = LineString([(-71.6, -33.51), (-71.6, -33.49)])
    building = Polygon([
        (-71.5999, -33.50005), (-71.5998, -33.50005),
        (-71.5998, -33.50015), (-71.5999, -33.50015), (-71.5999, -33.50005),
    ])
    road = LineString([(-71.5997, -33.501), (-71.5997, -33.499)])
    buildings = gpd.GeoDataFrame([{"osm_id": "way/1", "geometry": building}], crs=4326)
    roads = gpd.GeoDataFrame([{"osm_id": "way/2", "geometry": road}], crs=4326)
    rate_line = LineString([(-71.61, -33.5), (-71.59, -33.5)])
    rates = gpd.GeoDataFrame([
        {"transect_id": "T001", "lrr_m_per_year": 5.0, "geometry": rate_line}
    ], crs=4326)
    result = assess_infrastructure_risk(buildings, roads, shoreline, rates)
    assert result.buildings.iloc[0]["risk_level"] == "critico"
    assert result.roads.iloc[0]["erosion_rate_m_per_year"] == 5.0
    assert result.summary["road_segment_count"] == 1
