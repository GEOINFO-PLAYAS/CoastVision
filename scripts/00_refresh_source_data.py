from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from coastvision.acquisition import (  # noqa: E402
    ELEVATION_PATH,
    MANIFEST_PATH,
    OPEN_METEO_RAW_PATH,
    OSM_RAW_PATH,
    SHORELINE_PATH,
    SOURCE_RECEIPT_PATH,
    atomic_write_bytes,
    atomic_write_json,
    build_elevation_profile,
    build_provenance_manifest,
    build_shoreline_geojson,
    parse_osm_way,
    request_elevations,
    request_osm,
    sha256_bytes,
    json_bytes,
    utc_now,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstruye las entradas activas OSM y DEM con trazabilidad.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Reconstruye desde data/raw sin realizar solicitudes de red.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = _arguments()
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "CoastVision-MVP/1.0 reproducible-academic-project"}
    )

    if arguments.offline:
        if not all(
            path.exists()
            for path in (OSM_RAW_PATH, OPEN_METEO_RAW_PATH, SOURCE_RECEIPT_PATH)
        ):
            raise FileNotFoundError("Faltan snapshots en data/raw para el modo offline.")
        osm_content = OSM_RAW_PATH.read_bytes()
        source_receipt = json.loads(SOURCE_RECEIPT_PATH.read_text(encoding="utf-8"))
        osm_retrieved_at = source_receipt["osm"]["requested_at"]
        osm_request_url = source_receipt["osm"]["request_url"]
    else:
        osm_content, osm_request_url, osm_retrieved_at = request_osm(session)

    osm_way = parse_osm_way(osm_content)
    shoreline = build_shoreline_geojson(
        osm_way,
        osm_retrieved_at,
        sha256_bytes(osm_content),
    )
    # Los puntos se derivan del payload validado en memoria. Ninguna entrada
    # activa se reemplaza si falla la segunda fuente o alguna validación.
    from shapely.geometry import LineString  # noqa: PLC0415
    from coastvision.geometry import elevation_query_points_for_shoreline  # noqa: PLC0415

    shoreline_line = LineString(shoreline["features"][0]["geometry"]["coordinates"])
    query_points = elevation_query_points_for_shoreline(shoreline_line)
    if arguments.offline:
        raw_elevation = json.loads(OPEN_METEO_RAW_PATH.read_text(encoding="utf-8"))
        response_payload = raw_elevation["response"]
        request_url = raw_elevation["request_url"]
        elevation_retrieved_at = raw_elevation["requested_at"]
    else:
        response_payload, request_url, elevation_retrieved_at = request_elevations(
            session,
            query_points,
        )

    raw_elevation = {
        "endpoint": "https://api.open-meteo.com/v1/elevation",
        "request_url": request_url,
        "requested_at": elevation_retrieved_at,
        "query_points": query_points,
        "response": response_payload,
    }

    elevation_profile = build_elevation_profile(
        query_points,
        response_payload.get("elevation", []),
        elevation_retrieved_at,
        request_url,
    )
    shoreline_sha256 = sha256_bytes(json_bytes(shoreline))
    elevation_profile["generated_from_shoreline_sha256"] = shoreline_sha256

    if arguments.offline:
        bundle_created_at = source_receipt["bundle_created_at"]
    else:
        bundle_created_at = utc_now()
        bundle_id = sha256_bytes(osm_content + json_bytes(raw_elevation))
        source_receipt = {
            "schema_version": 1,
            "bundle_id": bundle_id,
            "bundle_created_at": bundle_created_at,
            "osm": {
                "request_url": osm_request_url,
                "requested_at": osm_retrieved_at,
                "raw_sha256": sha256_bytes(osm_content),
            },
            "open_meteo": {
                "request_url": request_url,
                "requested_at": elevation_retrieved_at,
                "raw_wrapper_sha256": sha256_bytes(json_bytes(raw_elevation)),
            },
        }

    # Recién aquí el bundle completo está validado. Las escrituras individuales
    # son atómicas y el manifiesto se publica al final como sello del conjunto.
    atomic_write_bytes(OSM_RAW_PATH, osm_content)
    atomic_write_json(OPEN_METEO_RAW_PATH, raw_elevation)
    atomic_write_json(SOURCE_RECEIPT_PATH, source_receipt)
    atomic_write_json(SHORELINE_PATH, shoreline)
    atomic_write_json(ELEVATION_PATH, elevation_profile)
    manifest = build_provenance_manifest(bundle_created_at)
    manifest["bundle_id"] = source_receipt["bundle_id"]
    atomic_write_json(MANIFEST_PATH, manifest)

    summary = {
        "mode": "offline" if arguments.offline else "online",
        "osm_way": osm_way["way_id"],
        "osm_version": osm_way["version"],
        "shoreline_vertices": shoreline["features"][0]["properties"]["vertex_count"],
        "elevation_samples": len(elevation_profile["samples"]),
        "manifest": str(MANIFEST_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
