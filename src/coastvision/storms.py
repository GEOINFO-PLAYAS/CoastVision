"""Unión temporal y correlación con avisos oficiales de marejadas."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


REQUIRED_EVENT_COLUMNS = {
    "event_id", "start_date", "end_date", "source_agency", "source_url",
    "affects_cartagena",
}


def load_storm_events(path: str | Path) -> pd.DataFrame:
    events = pd.read_csv(path)
    missing = REQUIRED_EVENT_COLUMNS - set(events.columns)
    if missing:
        raise ValueError(f"Faltan columnas de eventos: {', '.join(sorted(missing))}")
    events = events.copy()
    events["start_date"] = pd.to_datetime(events["start_date"], utc=True)
    events["end_date"] = pd.to_datetime(events["end_date"], utc=True)
    if (events["end_date"] < events["start_date"]).any():
        raise ValueError("Un evento termina antes de comenzar.")
    events["affects_cartagena"] = (
        events["affects_cartagena"].astype(str).str.lower().map({"true": True, "false": False})
    )
    if events["affects_cartagena"].isna().any():
        raise ValueError("affects_cartagena debe ser true/false.")
    return events.sort_values("start_date").reset_index(drop=True)


def tag_observations_with_storms(
    observations: pd.DataFrame,
    events: pd.DataFrame,
    *,
    date_column: str = "acquired_at",
    window_days: int = 3,
) -> pd.DataFrame:
    """Marca escenas dentro o cerca de un aviso que afectó Cartagena."""
    if date_column not in observations.columns:
        raise ValueError(f"Falta la fecha de observación '{date_column}'.")
    if window_days < 0:
        raise ValueError("window_days no puede ser negativo.")
    tagged = observations.copy()
    tagged[date_column] = pd.to_datetime(
        tagged[date_column], format="mixed", utc=True
    )
    relevant = events.loc[events["affects_cartagena"]].copy()
    event_ids: list[str] = []
    flags: list[int] = []
    nearest_days: list[float] = []
    counts: list[int] = []
    padding = pd.Timedelta(days=window_days)
    for acquired_at in tagged[date_column]:
        matches = relevant.loc[
            (relevant["start_date"] - padding <= acquired_at)
            & (relevant["end_date"] + padding >= acquired_at)
        ]
        flags.append(int(not matches.empty))
        counts.append(len(matches))
        event_ids.append(";".join(matches["event_id"].astype(str)))
        if relevant.empty:
            nearest_days.append(np.nan)
        else:
            distance = relevant.apply(
                lambda row: 0.0
                if row["start_date"] <= acquired_at <= row["end_date"]
                else min(
                    abs((acquired_at - row["start_date"]).total_seconds()),
                    abs((acquired_at - row["end_date"]).total_seconds()),
                ) / 86_400,
                axis=1,
            )
            nearest_days.append(float(distance.min()))
    tagged["official_storm_event"] = flags
    tagged["official_event_count"] = counts
    tagged["official_event_ids"] = event_ids
    tagged["nearest_official_event_days"] = nearest_days
    tagged["storm_join_window_days"] = window_days
    return tagged


def aggregate_position_anomalies(
    observations: pd.DataFrame,
    *,
    date_column: str = "acquired_at",
    position_column: str = "position_m",
) -> pd.DataFrame:
    """Agrega transectos por fecha y remueve la tendencia lineal de largo plazo."""
    required = {date_column, position_column}
    if not required.issubset(observations.columns):
        raise ValueError(f"Faltan columnas: {', '.join(sorted(required - set(observations.columns)))}")
    data = observations.copy()
    data[date_column] = pd.to_datetime(
        data[date_column], format="mixed", utc=True
    )
    data[position_column] = pd.to_numeric(data[position_column], errors="coerce")
    grouped = (
        data.dropna(subset=[position_column])
        .groupby(date_column, as_index=False)[position_column]
        .median()
        .sort_values(date_column)
    )
    if len(grouped) < 3:
        grouped["position_trend_m"] = np.nan
        grouped["position_anomaly_m"] = np.nan
        return grouped
    epoch = grouped[date_column].min()
    years = (grouped[date_column] - epoch).dt.total_seconds().to_numpy() / (365.2425 * 86_400)
    positions = grouped[position_column].to_numpy(dtype=float)
    slope, intercept = np.polyfit(years, positions, 1)
    trend = slope * years + intercept
    grouped["position_trend_m"] = trend
    grouped["position_anomaly_m"] = positions - trend
    grouped.attrs["trend_m_per_year"] = float(slope)
    return grouped


def correlate_storms(
    tagged_observations: pd.DataFrame,
    *,
    response_column: str = "position_anomaly_m",
    event_column: str = "official_storm_event",
) -> dict[str, Any]:
    """Calcula correlación punto-biserial, con controles de suficiencia."""
    required = {response_column, event_column}
    if not required.issubset(tagged_observations.columns):
        raise ValueError(f"Faltan columnas: {', '.join(sorted(required - set(tagged_observations.columns)))}")
    data = tagged_observations[[response_column, event_column]].dropna().copy()
    data[event_column] = pd.to_numeric(data[event_column], errors="coerce")
    data = data.dropna()
    classes = sorted(data[event_column].unique().tolist())
    base = {
        "method": "point_biserial",
        "response": response_column,
        "event_indicator": event_column,
        "n": int(len(data)),
        "n_event": int((data[event_column] == 1).sum()),
        "n_no_event": int((data[event_column] == 0).sum()),
        "correlation_r": None,
        "p_value": None,
        "interpretation": "association_not_causation",
    }
    if (
        len(data) < 5
        or classes != [0, 1]
        or base["n_event"] < 2
        or base["n_no_event"] < 2
        or data[response_column].nunique() < 2
    ):
        return {**base, "status": "INSUFFICIENT_DATA"}
    result = stats.pointbiserialr(
        data[event_column].to_numpy(dtype=int), data[response_column].to_numpy(dtype=float)
    )
    statistic = float(result.statistic)
    p_value = float(result.pvalue)
    if not np.isfinite(statistic) or not np.isfinite(p_value):
        return {**base, "status": "INVALID_NUMERICAL_RESULT"}
    return {
        **base,
        "correlation_r": statistic,
        "p_value": p_value,
        "status": "OK",
    }
