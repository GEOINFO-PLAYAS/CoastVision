from __future__ import annotations

import pytest
from shapely.geometry import LineString

from coastvision.visual_features import interpolate_shorelines, shoreline_displacement_m


def test_interpolation_is_midpoint_and_resampled() -> None:
    first = LineString([(-71.62, -33.50), (-71.61, -33.50)])
    second = LineString([(-71.62, -33.49), (-71.61, -33.49)])

    result = interpolate_shorelines(first, second, 0.5, count=5)

    assert len(result.coords) == 5
    assert result.coords[0][1] == pytest.approx(-33.495, abs=1e-6)
    assert result.coords[-1][1] == pytest.approx(-33.495, abs=1e-6)
    assert shoreline_displacement_m(first, result) == pytest.approx(
        shoreline_displacement_m(result, second), rel=0.02
    )


def test_interpolation_clamps_progress_and_rejects_empty_lines() -> None:
    first = LineString([(-71.62, -33.50), (-71.61, -33.50)])
    second = LineString([(-71.61, -33.49), (-71.62, -33.49)])

    assert interpolate_shorelines(first, second, -1.0).coords[0] == pytest.approx(first.coords[0], abs=1e-6)
    assert interpolate_shorelines(first, second, 2.0).coords[0] == pytest.approx(second.coords[-1], abs=1e-6)
    with pytest.raises(ValueError, match="no puede estar vacía"):
        interpolate_shorelines(LineString(), second, 0.5)
