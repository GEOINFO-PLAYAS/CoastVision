from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.acquisition import atomic_write_json, sha256_file  # noqa: E402
from coastvision.infrastructure import (  # noqa: E402
    OVERPASS_URL,
    download_overpass_snapshot,
    parse_overpass_infrastructure,
    save_overpass_snapshot,
)


def main() -> None:
    reference = gpd.read_file(ROOT / "data/playa_grande_shoreline_osm.geojson").to_crs(32719)
    aoi = gpd.GeoSeries(
        [reference.geometry.union_all().buffer(500).envelope], crs=32719
    ).to_crs(4326).iloc[0]
    bbox = [round(value, 7) for value in aoi.bounds]
    payload = download_overpass_snapshot(bbox)
    raw_path = ROOT / "data/raw/osm_infrastructure_playa_grande.json"
    save_overpass_snapshot(payload, raw_path)
    buildings, roads = parse_overpass_infrastructure(payload)
    clip_geometry = gpd.GeoDataFrame(
        [{"geometry": aoi}], geometry="geometry", crs=4326
    )
    if not buildings.empty:
        buildings = gpd.clip(buildings, clip_geometry)
    if not roads.empty:
        roads = gpd.clip(roads, clip_geometry)
    output = ROOT / "data/infrastructure"
    output.mkdir(parents=True, exist_ok=True)
    building_path = output / "buildings_osm.geojson"
    road_path = output / "roads_osm.geojson"
    buildings.to_file(building_path, driver="GeoJSON")
    roads.to_file(road_path, driver="GeoJSON")
    receipt = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "OpenStreetMap Overpass",
        "endpoint": OVERPASS_URL,
        "bbox": bbox,
        "raw": str(raw_path),
        "raw_sha256": sha256_file(raw_path),
        "buildings": len(buildings),
        "road_segments": len(roads),
        "buildings_sha256": sha256_file(building_path),
        "roads_sha256": sha256_file(road_path),
        "clip_method": "AOI envelope from 500 m UTM buffer around full reference shoreline",
    }
    atomic_write_json(output / "source_receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
