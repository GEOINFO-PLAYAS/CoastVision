from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.acquisition import atomic_write_json  # noqa: E402
from coastvision.sentinel import build_multitemporal_catalog  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cataloga escenas Sentinel-2 estivales 2016-2026 para Playa Grande."
    )
    parser.add_argument("--buffer-m", type=float, default=500.0)
    parser.add_argument("--max-cloud", type=float, default=20.0)
    parser.add_argument("--scenes-per-year", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    if not 100 <= args.buffer_m <= 2_000:
        raise ValueError("El buffer del AOI debe estar entre 100 y 2.000 m.")
    shoreline_path = ROOT / "data" / "playa_grande_shoreline_osm.geojson"
    shoreline = gpd.read_file(shoreline_path).to_crs("EPSG:32719")
    aoi_wgs84 = gpd.GeoSeries(
        [shoreline.geometry.union_all().buffer(args.buffer_m).envelope],
        crs="EPSG:32719",
    ).to_crs("EPSG:4326").iloc[0]
    bbox = [round(value, 7) for value in aoi_wgs84.bounds]
    catalog = build_multitemporal_catalog(
        bbox,
        max_cloud_pct=args.max_cloud,
        max_scenes_per_year=args.scenes_per_year,
    )
    catalog["aoi_method"] = {
        "reference": str(shoreline_path.relative_to(ROOT)).replace("\\", "/"),
        "buffer_m": args.buffer_m,
        "method": "envolvente del buffer métrico UTM 19S de toda la línea de playa",
    }
    output = ROOT / "data" / "sentinel" / "catalog_2016_2026.json"
    atomic_write_json(output, catalog)
    print(json.dumps({
        "output": str(output),
        "bbox": bbox,
        "scene_count": len(catalog["scenes"]),
        "missing_years": catalog["missing_years"],
        "catalog_complete": catalog["catalog_complete"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

