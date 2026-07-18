from __future__ import annotations

import math
import json
import sys
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.acquisition import (
    ELEVATION_PATH,
    MANIFEST_PATH,
    OPEN_METEO_RAW_PATH,
    OSM_RAW_PATH,
    SHORELINE_PATH,
    SOURCE_RECEIPT_PATH,
    build_elevation_profile,
    build_shoreline_geojson,
    parse_osm_way,
    sha256_bytes,
    sha256_file,
)
from coastvision.geometry import (
    build_demo_layers,
    elevation_query_points,
    evaluate_location,
)
from coastvision.rag import answer_with_optional_llm, retrieve


@lru_cache(maxsize=None)
def _e06_point_at_offset(offset_m: float) -> tuple[float, float, Point]:
    layers = build_demo_layers(year=2026, retreat_rate=1.5)
    station = (
        layers["stations"]
        .to_crs("EPSG:32719")
        .query("station_id == 'E06'")
        .geometry.iloc[0]
    )
    sample_50 = (
        layers["elevation_samples"]
        .to_crs("EPSG:32719")
        .query("station_id == 'E06' and offset_m == 50")
        .geometry.iloc[0]
    )
    point = Point(
        station.x + (sample_50.x - station.x) * offset_m / 50.0,
        station.y + (sample_50.y - station.y) * offset_m / 50.0,
    )
    point_wgs84 = gpd.GeoSeries([point], crs="EPSG:32719").to_crs("EPSG:4326").iloc[0]
    return point_wgs84.y, point_wgs84.x, point


def test_network_covers_full_playa_grande() -> None:
    layers = build_demo_layers(year=2035, retreat_rate=1.5)
    coverage = layers["coverage"]

    assert 1_800 <= coverage["length_m"] <= 1_950
    assert coverage["lat_max"] - coverage["lat_min"] > 0.012
    assert coverage["station_count"] == 11
    assert 170 <= coverage["spacing_m"] <= 200
    assert len(layers["stations"]) == 11
    assert len(layers["transects"]) == 11


def test_transects_cross_the_reference_shoreline() -> None:
    layers = build_demo_layers(year=2035, retreat_rate=1.5)
    current = (
        layers["shorelines"]
        .query("type == 'actual'")
        .to_crs("EPSG:32719")
        .geometry.iloc[0]
    )
    transects = layers["transects"].to_crs("EPSG:32719")

    assert all(math.isclose(line.length, 310.0, abs_tol=0.2) for line in transects.geometry)
    # El viaje UTM -> WGS84 -> UTM puede separar el vértice por fracciones de milímetro.
    assert all(line.distance(current) < 0.02 for line in transects.geometry)


def test_risk_bands_and_study_area_are_valid() -> None:
    layers = build_demo_layers(year=2035, retreat_rate=1.5)
    bands = layers["risk_bands"].to_crs("EPSG:32719")

    assert layers["study_area"].geometry.iloc[0].is_valid
    assert layers["impact_zone"].geometry.iloc[0].is_valid
    assert not layers["impact_zone"].geometry.iloc[0].is_empty
    assert all(geometry.is_valid and not geometry.is_empty for geometry in bands.geometry)
    assert set(bands["nivel"]) == {"critico", "precaucion", "bajo"}
    for first_index in range(len(bands)):
        for second_index in range(first_index + 1, len(bands)):
            overlap = bands.geometry.iloc[first_index].intersection(
                bands.geometry.iloc[second_index]
            )
            assert overlap.area < 0.05


def test_elevation_profile_is_complete_and_attributed() -> None:
    layers = build_demo_layers(year=2035, retreat_rate=1.5)
    samples = layers["elevation_samples"]
    profile = layers["elevation_profile"]

    assert len(samples) == 33
    assert samples["elevation_m"].notna().all()
    assert profile[["elevation_50m", "elevation_150m", "elevation_250m"]].notna().all().all()
    assert layers["coverage"]["elevation_resolution_m"] == 90
    assert "Copernicus" in layers["coverage"]["elevation_source"]


def test_click_evaluation_separates_distance_and_elevation() -> None:
    layers = build_demo_layers(year=2035, retreat_rate=1.5)
    samples = layers["elevation_samples"]
    near_point = samples.query("station_id == 'E06' and offset_m == 50").iloc[0]
    far_point = samples.query("station_id == 'E06' and offset_m == 150").iloc[0]

    near = evaluate_location(near_point.geometry.y, near_point.geometry.x, year=2035)
    far = evaluate_location(far_point.geometry.y, far_point.geometry.x, year=2035)

    assert near.level in {"critico", "precaucion"}
    assert far.level == "bajo"
    assert near.distance_m < far.distance_m
    assert far.nearest_station_id == "E06"
    assert far.elevation_m == float(far_point["elevation_m"])
    assert far.elevation_resolution_m == 90


def test_projected_line_moves_about_configured_retreat() -> None:
    layers = build_demo_layers(year=2035, retreat_rate=1.5)
    lines = layers["shorelines"].to_crs("EPSG:32719")
    current = lines.query("type == 'actual'").geometry.iloc[0]
    projected = lines.query("type == 'proyectada'").geometry.iloc[0]
    distances = [
        current.interpolate(current.length * fraction / 10).distance(projected)
        for fraction in range(11)
    ]

    assert layers["retreat_m"] == 13.5
    assert all(12.5 <= distance <= 14.5 for distance in distances)


def test_fixed_locations_worsen_as_year_advances() -> None:
    expected = {
        35: ["precaucion", "critico", "critico"],
        45: ["precaucion", "precaucion", "critico"],
        68: ["bajo", "precaucion", "precaucion"],
        80: ["bajo", "bajo", "precaucion"],
    }
    years = [2026, 2035, 2040]

    for offset_m, expected_levels in expected.items():
        lat, lon, _ = _e06_point_at_offset(offset_m)
        actual = [evaluate_location(lat, lon, year, 1.5).level for year in years]
        assert actual == expected_levels


def test_reached_location_stays_critical_for_all_rates() -> None:
    lat, lon, _ = _e06_point_at_offset(5)
    severity = {"bajo": 0, "precaucion": 1, "critico": 2}

    for retreat_rate in (0.5, 1.5, 3.0):
        assessments = [
            evaluate_location(lat, lon, year, retreat_rate)
            for year in (2026, 2030, 2035, 2040)
        ]
        assert all(item.level == "critico" for item in assessments)
        assert [severity[item.level] for item in assessments] == sorted(
            severity[item.level] for item in assessments
        )
    extreme = evaluate_location(lat, lon, 2040, 3.0)
    assert extreme.reached_by_projection
    assert extreme.signed_margin_m < 0


def test_visible_band_matches_click_classification() -> None:
    for retreat_rate in (0.5, 1.5, 3.0):
        for year in (2026, 2030, 2035, 2040):
            layers = build_demo_layers(year, retreat_rate)
            bands = layers["risk_bands"].to_crs("EPSG:32719")
            for offset_m in (5, 15, 35, 45, 68, 80, 120):
                lat, lon, point = _e06_point_at_offset(offset_m)
                visible_levels = [
                    row["nivel"]
                    for _, row in bands.iterrows()
                    if row.geometry.buffer(0.03).covers(point)
                ]
                assessment = evaluate_location(lat, lon, year, retreat_rate)
                assert visible_levels == [assessment.level]


def test_red_growth_matches_area_reached_and_green_shrinks() -> None:
    base = build_demo_layers(2026, 1.5)
    base_red = base["area_metrics"]["critical_area_m2"]
    base_green = base["area_metrics"]["low_area_m2"]

    for year in (2035, 2040):
        layers = build_demo_layers(year, 1.5)
        reached = layers["area_metrics"]["impact_area_m2"]
        red_growth = layers["area_metrics"]["critical_area_m2"] - base_red
        green_loss = base_green - layers["area_metrics"]["low_area_m2"]
        assert math.isclose(red_growth, reached, rel_tol=0.03)
        assert math.isclose(green_loss, reached, rel_tol=0.03)


def test_historical_line_does_not_move_with_future_rate() -> None:
    slow = build_demo_layers(2040, 0.5)["shorelines"].to_crs("EPSG:32719")
    fast = build_demo_layers(2040, 3.0)["shorelines"].to_crs("EPSG:32719")
    slow_historical = slow.query("type == 'historica'").geometry.iloc[0]
    fast_historical = fast.query("type == 'historica'").geometry.iloc[0]

    assert slow_historical.hausdorff_distance(fast_historical) < 0.02


def test_all_year_rate_combinations_are_topologically_consistent() -> None:
    reference_total_area = None
    for retreat_rate in (0.5, 1.5, 3.0):
        for year in (2026, 2030, 2035, 2040):
            layers = build_demo_layers(year, retreat_rate)
            bands = layers["risk_bands"].to_crs("EPSG:32719")
            lines = layers["shorelines"].to_crs("EPSG:32719")
            current = lines.query("type == 'actual'").geometry.iloc[0]
            projected = lines.query("type == 'proyectada'").geometry.iloc[0]
            expected_retreat = (year - 2026) * retreat_rate

            assert all(geometry.is_valid and not geometry.is_empty for geometry in bands.geometry)
            total_area = sum(geometry.area for geometry in bands.geometry)
            if reference_total_area is None:
                reference_total_area = total_area
            assert math.isclose(total_area, reference_total_area, rel_tol=0.002)

            for first_index in range(len(bands)):
                for second_index in range(first_index + 1, len(bands)):
                    assert (
                        bands.geometry.iloc[first_index]
                        .intersection(bands.geometry.iloc[second_index])
                        .area
                        < 0.05
                    )

            assert projected.is_valid
            assert projected.is_simple

            if math.isclose(expected_retreat, 0.0):
                assert current.hausdorff_distance(projected) < 0.02
                continue

            # Muestreo denso y con vértices: evita que un pliegue localizado en
            # un extremo pase inadvertido entre deciles de una playa de 1,87 km.
            current_samples = [Point(coordinate) for coordinate in current.coords]
            current_samples.extend(
                current.interpolate(distance_m)
                for distance_m in range(0, int(current.length) + 1, 5)
            )
            projected_samples = [Point(coordinate) for coordinate in projected.coords]
            projected_samples.extend(
                projected.interpolate(distance_m)
                for distance_m in range(0, int(projected.length) + 1, 5)
            )
            current_to_projected = [
                point.distance(projected) for point in current_samples
            ]
            projected_to_current = [
                point.distance(current) for point in projected_samples
            ]

            # En uniones cóncavas el offset simple puede quedar algo más lejos
            # de un vértice base, pero nunca debe plegarse ni acercarse de nuevo.
            assert min(current_to_projected) >= expected_retreat * 0.98
            assert max(current_to_projected) <= expected_retreat * 1.15 + 0.05
            allowed_offset_error = max(0.25, expected_retreat * 0.02)
            assert all(
                math.isclose(
                    distance,
                    expected_retreat,
                    abs_tol=allowed_offset_error,
                )
                for distance in projected_to_current
            )


def test_rag_returns_ranked_evidence() -> None:
    results = retrieve("¿Qué herramienta extrae líneas de costa desde Sentinel?")
    assert len(results) == 3
    assert results[0]["title"] == "CoastSat"
    assert results[0]["score"] >= results[1]["score"]


def test_osm_snapshot_rebuilds_the_active_marine_arc() -> None:
    receipt = json.loads(SOURCE_RECEIPT_PATH.read_text(encoding="utf-8"))
    raw_osm = OSM_RAW_PATH.read_bytes()
    osm_way = parse_osm_way(raw_osm)
    rebuilt = build_shoreline_geojson(
        osm_way,
        receipt["osm"]["requested_at"],
        sha256_bytes(raw_osm),
    )
    active = json.loads(SHORELINE_PATH.read_text(encoding="utf-8"))
    coordinates = rebuilt["features"][0]["geometry"]["coordinates"]

    assert osm_way["tags"]["natural"] == "beach"
    assert osm_way["version"] >= 1
    assert len(coordinates) == 69
    assert coordinates[0][1] > coordinates[-1][1]
    assert rebuilt == active


def test_elevation_queries_match_the_active_11_by_3_grid() -> None:
    active = json.loads(ELEVATION_PATH.read_text(encoding="utf-8"))
    queries = elevation_query_points()
    active_coordinates = [
        {
            "station_id": item["station_id"],
            "offset_m": item["offset_m"],
            "latitude": item["latitude"],
            "longitude": item["longitude"],
        }
        for item in active["samples"]
    ]

    assert len(queries) == 33
    assert queries == active_coordinates
    assert {item["station_id"] for item in queries} == {
        f"E{index:02d}" for index in range(1, 12)
    }
    assert {item["offset_m"] for item in queries} == {50, 150, 250}


def test_raw_elevation_snapshot_rebuilds_the_active_profile() -> None:
    raw = json.loads(OPEN_METEO_RAW_PATH.read_text(encoding="utf-8"))
    active = json.loads(ELEVATION_PATH.read_text(encoding="utf-8"))
    shoreline_sha256 = sha256_file(SHORELINE_PATH)
    rebuilt = build_elevation_profile(
        raw["query_points"],
        raw["response"]["elevation"],
        raw["requested_at"],
        raw["request_url"],
    )
    rebuilt["generated_from_shoreline_sha256"] = shoreline_sha256

    assert rebuilt == active
    with pytest.raises(ValueError, match="cantidad distinta"):
        build_elevation_profile(
            raw["query_points"],
            raw["response"]["elevation"][:-1],
            raw["requested_at"],
            raw["request_url"],
        )


def test_provenance_manifest_hashes_match_every_snapshot_and_active_input() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["bundle_id"]
    for item in manifest["active_inputs"] + manifest["raw_snapshots"]:
        assert sha256_file(ROOT / item["path"]) == item["sha256"]


def test_local_rag_fallback_never_requires_an_external_llm() -> None:
    contexts = retrieve("¿Qué datos son demostrativos?")
    answer, mode = answer_with_optional_llm(
        "¿Qué datos son demostrativos?",
        contexts,
        allow_llm=False,
    )

    assert "Respuesta basada en evidencia local" in answer
    assert "TF-IDF" in mode
