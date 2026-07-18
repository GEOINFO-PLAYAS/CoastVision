from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

from src.coastvision.change_analysis import (
    UTM_19S,
    WGS84,
    analyze_shoreline_change,
    build_fixed_transects,
)


BASE_X = 300_000.0
BASE_Y = 6_300_000.0
BASE_YEAR = 2016
BASELINE_UTM = LineString([(BASE_X, BASE_Y), (BASE_X, BASE_Y + 1_000.0)])


def _annual_shorelines(
    years: list[int],
    *,
    rate_m_per_year: float = 2.0,
    reverse_coordinates: bool = False,
) -> gpd.GeoDataFrame:
    records = []
    for year in years:
        # La línea base va de sur a norte: su normal izquierda apunta al
        # oeste. Por ello x decreciente produce posición/retroceso positivo.
        x = BASE_X - rate_m_per_year * (year - BASE_YEAR)
        coordinates = [(x, BASE_Y - 100.0), (x, BASE_Y + 1_100.0)]
        if reverse_coordinates:
            coordinates.reverse()
        records.append({"year": year, "geometry": LineString(coordinates)})
    return gpd.GeoDataFrame(records, geometry="geometry", crs=UTM_19S)


def _analyse(shorelines: gpd.GeoDataFrame):
    return analyze_shoreline_change(
        BASELINE_UTM,
        shorelines,
        baseline_crs=UTM_19S,
        target_crs=UTM_19S,
        spacing_m=250.0,
        seaward_m=60.0,
        landward_m=60.0,
        positive_side="left",
    )


def test_known_rate_calculates_nsm_epr_lrr_r2_and_ci95() -> None:
    result = _analyse(_annual_shorelines([2016, 2021, 2026]))

    assert len(result.transects) == 5
    assert len(result.intersections) == 15
    assert result.intersections["intersection_found"].all()
    assert isinstance(result.metrics_table, pd.DataFrame)
    assert "geometry" not in result.metrics_table.columns

    metrics = result.metrics
    np.testing.assert_allclose(metrics["nsm_m"], 20.0, atol=1e-9)
    np.testing.assert_allclose(metrics["epr_m_per_year"], 2.0, atol=1e-9)
    np.testing.assert_allclose(metrics["lrr_m_per_year"], 2.0, atol=1e-9)
    np.testing.assert_allclose(metrics["lrr_r2"], 1.0, atol=1e-12)
    np.testing.assert_allclose(metrics["lrr_standard_error_m_per_year"], 0.0, atol=1e-10)
    np.testing.assert_allclose(metrics["lrr_ci95_low_m_per_year"], 2.0, atol=1e-9)
    np.testing.assert_allclose(metrics["lrr_ci95_high_m_per_year"], 2.0, atol=1e-9)
    assert set(metrics["analysis_status"]) == {"ok"}
    assert set(metrics["uncertainty_method"]) == {"student_t_95"}
    assert metrics["sign_convention"].str.contains("positivo=retroceso").all()


def test_input_year_order_and_shoreline_coordinate_order_do_not_change_metrics() -> None:
    chronological = _analyse(_annual_shorelines([2016, 2021, 2026]))
    reversed_input = _analyse(
        _annual_shorelines(
            [2026, 2021, 2016],
            reverse_coordinates=True,
        )
    )

    columns = [
        "transect_id",
        "first_year",
        "last_year",
        "nsm_m",
        "epr_m_per_year",
        "lrr_m_per_year",
        "lrr_r2",
    ]
    expected = chronological.metrics[columns].sort_values("transect_id").reset_index(drop=True)
    actual = reversed_input.metrics[columns].sort_values("transect_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected)


def test_single_year_is_reported_as_insufficient_without_inventing_rates() -> None:
    result = _analyse(_annual_shorelines([2020]))
    metrics = result.metrics

    assert (metrics["n_observations"] == 1).all()
    assert set(metrics["analysis_status"]) == {"insufficient_observations"}
    for column in (
        "nsm_m",
        "epr_m_per_year",
        "lrr_m_per_year",
        "lrr_r2",
        "lrr_standard_error_m_per_year",
        "lrr_ci95_low_m_per_year",
        "lrr_ci95_high_m_per_year",
    ):
        assert metrics[column].isna().all(), column


def test_two_years_calculate_rates_but_not_regression_uncertainty() -> None:
    result = _analyse(_annual_shorelines([2016, 2026]))
    metrics = result.metrics

    np.testing.assert_allclose(metrics["nsm_m"], 20.0, atol=1e-9)
    np.testing.assert_allclose(metrics["epr_m_per_year"], 2.0, atol=1e-9)
    np.testing.assert_allclose(metrics["lrr_m_per_year"], 2.0, atol=1e-9)
    assert set(metrics["analysis_status"]) == {"ok_without_lrr_uncertainty"}
    assert metrics["lrr_standard_error_m_per_year"].isna().all()
    assert metrics["lrr_ci95_low_m_per_year"].isna().all()
    assert metrics["lrr_ci95_high_m_per_year"].isna().all()


def test_wgs84_inputs_are_projected_to_utm19s_and_outputs_support_wgs84() -> None:
    baseline_wgs84 = gpd.GeoSeries([BASELINE_UTM], crs=UTM_19S).to_crs(WGS84).iloc[0]
    shorelines_wgs84 = _annual_shorelines([2016, 2021, 2026]).to_crs(WGS84)
    result = analyze_shoreline_change(
        baseline_wgs84,
        shorelines_wgs84,
        baseline_crs=WGS84,
        target_crs=UTM_19S,
        spacing_m=250.0,
        seaward_m=60.0,
        landward_m=60.0,
    )

    assert result.transects.crs.to_epsg() == 32719
    assert result.intersections.crs.to_epsg() == 32719
    assert result.metrics.crs.to_epsg() == 32719
    assert result.transects_wgs84.crs.to_epsg() == 4326
    assert result.intersections_wgs84.crs.to_epsg() == 4326
    assert result.metrics_wgs84.crs.to_epsg() == 4326
    np.testing.assert_allclose(result.metrics["lrr_m_per_year"], 2.0, atol=1e-5)


def test_transect_parameters_and_metric_crs_are_validated() -> None:
    with pytest.raises(ValueError, match="spacing_m"):
        build_fixed_transects(BASELINE_UTM, spacing_m=0, baseline_crs=UTM_19S)
    with pytest.raises(ValueError, match="proyectado"):
        build_fixed_transects(
            BASELINE_UTM,
            baseline_crs=UTM_19S,
            target_crs=WGS84,
        )
    with pytest.raises(ValueError, match="positive_side"):
        build_fixed_transects(
            BASELINE_UTM,
            baseline_crs=UTM_19S,
            positive_side="up",  # type: ignore[arg-type]
        )
