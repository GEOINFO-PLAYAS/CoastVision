"""Lectura reproducible del oleaje ERA5 de apoyo del proyecto compañero.

Los valores ERA5 se usan como contexto de oleaje, no como sustituto de la
correlación oficial SHOA/DMC. El módulo mantiene esa distinción explícita para
que la interfaz no presente una fuente auxiliar como una observación oficial.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WaveEvent:
    date: str
    significant_wave_height_m: float


def load_era5_wave_catalog(path: Path) -> list[WaveEvent]:
    """Carga un JSON ``fecha -> altura significativa`` y lo ordena por fecha."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("El catálogo ERA5 debe ser un objeto fecha -> altura.")
    events: list[WaveEvent] = []
    for date, height in payload.items():
        if not isinstance(date, str):
            raise ValueError("Cada fecha ERA5 debe ser texto ISO.")
        value = float(height)
        if value < 0:
            raise ValueError("La altura significativa no puede ser negativa.")
        events.append(WaveEvent(date=date, significant_wave_height_m=value))
    return sorted(events, key=lambda item: item.date)


def summarize_wave_catalog(events: list[WaveEvent]) -> dict[str, float | int | str | None]:
    """Devuelve métricas simples para mostrar el contexto de oleaje."""
    if not events:
        return {"count": 0, "max_m": None, "mean_m": None, "max_date": None}
    maximum = max(events, key=lambda item: item.significant_wave_height_m)
    return {
        "count": len(events),
        "max_m": maximum.significant_wave_height_m,
        "mean_m": sum(item.significant_wave_height_m for item in events) / len(events),
        "max_date": maximum.date,
    }
