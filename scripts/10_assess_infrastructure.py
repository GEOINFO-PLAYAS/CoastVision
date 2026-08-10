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
    parser.add_argument("--site", type=str, default="cartagena", help="Identificador del sitio/playa")
    parser.add_argument(
        "--buildings",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--roads",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--shorelines",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--rates",
        type=Path,
        default=None,
    )
    parser.add_argument("--horizon-years", type=int, default=30)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
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
    site = args.site
    
    # Resolve dynamic defaults based on --site
    if site == "cartagena":
        default_buildings = ROOT / "data/infrastructure/buildings_osm.geojson"
        default_roads = ROOT / "data/infrastructure/roads_osm.geojson"
        default_shorelines = ROOT / "outputs/multitemporal/shorelines_2016_2026_fes2014.geojson"
        default_rates = ROOT / "outputs/multitemporal/transect_rates.geojson"
        default_output = ROOT / "outputs/infrastructure_risk"
    else:
        default_buildings = ROOT / f"data/infrastructure/buildings_osm_{site}.geojson"
        default_roads = ROOT / f"data/infrastructure/roads_osm_{site}.geojson"
        default_shorelines = ROOT / f"outputs/{site}/multitemporal/shorelines_2016_2026_fes2014.geojson"
        default_rates = ROOT / f"outputs/{site}/multitemporal/transect_rates.geojson"
        default_output = ROOT / f"outputs/{site}/infrastructure_risk"

    buildings_path = args.buildings or default_buildings
    roads_path = args.roads or default_roads
    shorelines_path = args.shorelines or default_shorelines
    rates_path = args.rates or default_rates
    output_dir = args.output or default_output

    inputs = [buildings_path, roads_path, shorelines_path, rates_path]
    _require_files(inputs)

    buildings = gpd.read_file(buildings_path)
    roads = gpd.read_file(roads_path)
    shorelines = gpd.read_file(shorelines_path)
    rates = gpd.read_file(rates_path)
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

    output_dir.mkdir(parents=True, exist_ok=True)
    result.buildings.to_file(output_dir / "buildings_risk.geojson", driver="GeoJSON")
    result.roads.to_file(output_dir / "roads_risk.geojson", driver="GeoJSON")
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
    atomic_write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
