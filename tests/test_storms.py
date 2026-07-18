from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.storms import (  # noqa: E402
    aggregate_position_anomalies,
    correlate_storms,
    tag_observations_with_storms,
)


def _events():
    return pd.DataFrame({
        "event_id": ["E1"],
        "start_date": pd.to_datetime(["2020-03-10"], utc=True),
        "end_date": pd.to_datetime(["2020-03-12"], utc=True),
        "affects_cartagena": [True],
    })


def test_temporal_join_honours_window():
    observations = pd.DataFrame({"acquired_at": ["2020-03-08T12:00:00Z", "2020-03-20T12:00:00Z"]})
    tagged = tag_observations_with_storms(observations, _events(), window_days=3)
    assert tagged["official_storm_event"].tolist() == [1, 0]
    assert tagged.loc[0, "official_event_ids"] == "E1"


def test_anomaly_removes_linear_trend():
    data = pd.DataFrame({
        "acquired_at": ["2018-01-01", "2019-01-01", "2020-01-01", "2021-01-01"],
        "position_m": [0.0, 2.0, 4.0, 6.0],
    })
    result = aggregate_position_anomalies(data)
    assert result["position_anomaly_m"].abs().max() < 0.01


def test_anomaly_accepts_mixed_iso_precision():
    data = pd.DataFrame({
        "acquired_at": [
            "2016-02-04T14:42:56Z",
            "2017-03-10T14:51:18.458000Z",
            "2018-03-15T14:52:18.040000Z",
        ],
        "position_m": [0.0, 1.0, 2.0],
    })
    result = aggregate_position_anomalies(data)
    assert len(result) == 3
    assert result["position_anomaly_m"].notna().all()


def test_point_biserial_and_insufficient_state():
    enough = pd.DataFrame({
        "position_anomaly_m": [-2.0, -1.0, 0.0, 4.0, 5.0, 6.0],
        "official_storm_event": [0, 0, 0, 1, 1, 1],
    })
    result = correlate_storms(enough)
    assert result["status"] == "OK"
    assert result["correlation_r"] > 0.9
    insufficient = correlate_storms(enough.iloc[:3])
    assert insufficient["status"] == "INSUFFICIENT_DATA"


def test_point_biserial_rejects_single_event_or_constant_response():
    single_event = pd.DataFrame({
        "position_anomaly_m": [-2.0, -1.0, 0.0, 1.0, 2.0],
        "official_storm_event": [0, 0, 0, 0, 1],
    })
    assert correlate_storms(single_event)["status"] == "INSUFFICIENT_DATA"
    constant = pd.DataFrame({
        "position_anomaly_m": [1.0] * 6,
        "official_storm_event": [0, 0, 0, 1, 1, 1],
    })
    assert correlate_storms(constant)["status"] == "INSUFFICIENT_DATA"
