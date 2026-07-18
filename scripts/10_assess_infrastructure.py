from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.acquisition import atomic_write_json, sha256_file  # noqa: E402
from coastvision.infrastructure import assess_infrastructure_risk  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cruza edificios y caminos OSM con tasas LRR costeras locales."
    )
    parser.add_argument(
        "--buildings",
        type=Path,
        default=ROOT / "data/infrastructure/buildings_osm.geojson",
    )
    parser.add_argument(
        "--roads",
        type=Path,
        default=ROOT / "data/infrastructure/roads_osm.geojson",
    )
    parser.add_argument(
        "--shorelines",
        type=Path,
        default=ROOT / "outputs/multitemporal/shorelines_2016_2026_fes2014.geojson",
    )
    parser.add_argument(
        "--rates",
        type=Path,
        default=ROOT / "outputs/multitemporal/transect_rates.geojson",
    )
    parser.add_argument("--horizon-years", type=int, default=30)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/infrastructure_risk",
    )
    return parser.parse_args()


def _require_files(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        joined = "\n - ".join(missing)
        raise FileNotFoundError(
            "Faltan insumos. Ejecute primero scripts/08_refresh_osm_infrastructure.py "
            f"y scripts/07_process_multitemporal.py:\n - {joined}"
        )


def main() -> None:
    args = arguments()
    inputs = [args.buildings, args.roads, args.shorelines, args.rates]
    _require_files(inputs)

    buildings = gpd.read_file(args.buildings)
    roads = gpd.read_file(args.roads)
    shorelines = gpd.read_file(args.shorelines)
    rates = gpd.read_file(args.rates)
    for name, layer in (
        ("buildings", buildings),
        ("roads", roads),
        ("shorelines", shorelines),
        ("rates", rates),
    ):
        if layer.crs is None:
            raise ValueError(f"La capa {name} no declara CRS.")
    buildings = buildings.to_crs(4326)
    roads = roads.to_crs(4326)
    shorelines = shorelines.to_crs(4326)
    if shorelines.empty:
        raise ValueError("El archivo de líneas costeras está vacío.")
    if "year" not in shorelines.columns:
        raise ValueError("Las líneas costeras deben incluir la columna year.")

    shorelines["year"] = shorelines["year"].astype(int)
    latest_year = int(shorelines["year"].max())
    latest = shorelines.loc[shorelines["year"] == latest_year].geometry.union_all()
    result = assess_infrastructure_risk(
        buildings,
        roads,
        latest,
        rates,
        rate_column="lrr_m_per_year",
        horizon_years=args.horizon_years,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    result.buildings.to_file(args.output / "buildings_risk.geojson", driver="GeoJSON")
    result.roads.to_file(args.output / "roads_risk.geojson", driver="GeoJSON")
    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "shoreline_year": latest_year,
        "method": (
            "distancia métrica a la línea más reciente + LRR del transecto más cercano; "
            "LRR positivo significa retroceso tierra adentro"
        ),
        "inputs": [
            {"path": str(path), "sha256": sha256_file(path)} for path in inputs
        ],
        **result.summary,
        "decision_status": "SCREENING_REQUIRES_FIELD_VALIDATION",
    }
    atomic_write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
