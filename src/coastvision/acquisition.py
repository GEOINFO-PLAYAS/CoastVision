from __future__ import annotations

import hashlib
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from pyproj import Transformer
from shapely.geometry import LineString


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"

OSM_WAY_ID = 300607261
OSM_PAGE_URL = f"https://www.openstreetmap.org/way/{OSM_WAY_ID}"
OSM_API_URL = f"https://api.openstreetmap.org/api/0.6/way/{OSM_WAY_ID}/full"
OPEN_METEO_ENDPOINT = "https://api.open-meteo.com/v1/elevation"
OPEN_METEO_DOCS_URL = "https://open-meteo.com/en/docs/elevation-api"

OSM_RAW_PATH = RAW_DIR / f"osm_way_{OSM_WAY_ID}.xml"
OPEN_METEO_RAW_PATH = RAW_DIR / "open_meteo_elevation_response.json"
SOURCE_RECEIPT_PATH = RAW_DIR / "source_receipt.json"
SHORELINE_PATH = DATA_DIR / "playa_grande_shoreline_osm.geojson"
ELEVATION_PATH = DATA_DIR / "elevation_profile_open_meteo.json"
MANIFEST_PATH = DATA_DIR / "provenance_manifest.json"

NORTH_ANCHOR = (-71.6214046, -33.5017252)
SOUTH_ANCHOR = (-71.6105658, -33.5150018)
EXPECTED_STATION_COUNT = 11
EXPECTED_OFFSETS_M = (50, 150, 250)

_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    _atomic_write_bytes(path, json_bytes(payload))


def atomic_write_bytes(path: Path, content: bytes) -> None:
    _atomic_write_bytes(path, content)


def _anchor_index(
    coordinates: list[tuple[float, float]],
    anchor: tuple[float, float],
    tolerance: float = 5e-4,
) -> int:
    distances = [
        abs(longitude - anchor[0]) + abs(latitude - anchor[1])
        for longitude, latitude in coordinates
    ]
    index = min(range(len(distances)), key=distances.__getitem__)
    if distances[index] > tolerance:
        raise ValueError(f"No se encontró el ancla OSM {anchor} dentro de la tolerancia.")
    return index


def _cyclic_path(
    coordinates: list[tuple[float, float]],
    start_index: int,
    end_index: int,
    step: int,
) -> list[tuple[float, float]]:
    path = [coordinates[start_index]]
    index = start_index
    for _ in range(len(coordinates)):
        if index == end_index:
            return path
        index = (index + step) % len(coordinates)
        path.append(coordinates[index])
    raise ValueError("No fue posible recorrer el anillo OSM entre las anclas.")


def select_marine_arc(
    polygon_coordinates: Iterable[tuple[float, float]],
    north_anchor: tuple[float, float] = NORTH_ANCHOR,
    south_anchor: tuple[float, float] = SOUTH_ANCHOR,
) -> list[tuple[float, float]]:
    """Extrae el arco occidental del polígono de playa y lo orienta norte-sur."""
    coordinates = list(polygon_coordinates)
    if len(coordinates) > 1 and coordinates[0] == coordinates[-1]:
        coordinates = coordinates[:-1]
    if len(coordinates) < 4:
        raise ValueError("El way OSM no contiene un anillo de playa utilizable.")

    north_index = _anchor_index(coordinates, north_anchor)
    south_index = _anchor_index(coordinates, south_anchor)
    forward = _cyclic_path(coordinates, north_index, south_index, 1)
    backward = _cyclic_path(coordinates, north_index, south_index, -1)

    # Las anclas dividen el polígono en dos recorridos. El arco marino auditado
    # de Playa Grande mide cerca de 1,87 km; el borde interior supera 2 km. Se
    # exige que solo uno caiga en el rango aceptado para no cambiar de lado en
    # silencio si OSM modifica el polígono.
    candidates = []
    for path in (forward, backward):
        projected_path = LineString(
            [_TO_UTM.transform(*coordinate) for coordinate in path]
        )
        if 1_800 <= projected_path.length <= 1_950:
            candidates.append((path, projected_path))
    if len(candidates) != 1:
        lengths = [
            round(
                LineString([_TO_UTM.transform(*coordinate) for coordinate in path]).length,
                1,
            )
            for path in (forward, backward)
        ]
        raise ValueError(
            "La selección del arco marino quedó ambigua; "
            f"longitudes candidatas: {lengths} m."
        )
    marine, projected = candidates[0]
    if marine[0][1] <= marine[-1][1]:
        raise ValueError("El borde marino debe quedar orientado desde el norte hacia el sur.")

    if not 60 <= len(marine) <= 90:
        raise ValueError(f"Cantidad inesperada de vértices del borde marino: {len(marine)}.")
    if not 1_800 <= projected.length <= 1_950:
        raise ValueError(f"Longitud inesperada del borde marino: {projected.length:.1f} m.")
    if not projected.is_simple:
        raise ValueError("El borde marino extraído contiene autointersecciones.")
    return marine


def parse_osm_way(xml_content: bytes, way_id: int = OSM_WAY_ID) -> dict[str, Any]:
    root = ET.fromstring(xml_content)
    nodes = {
        int(node.attrib["id"]): (float(node.attrib["lon"]), float(node.attrib["lat"]))
        for node in root.findall("node")
    }
    way = next(
        (item for item in root.findall("way") if int(item.attrib["id"]) == way_id),
        None,
    )
    if way is None:
        raise ValueError(f"La respuesta OSM no contiene el way {way_id}.")

    node_refs = [int(item.attrib["ref"]) for item in way.findall("nd")]
    missing = [node_ref for node_ref in node_refs if node_ref not in nodes]
    if missing:
        raise ValueError(f"Faltan {len(missing)} nodos referenciados por el way OSM.")
    coordinates = [nodes[node_ref] for node_ref in node_refs]
    tags = {item.attrib["k"]: item.attrib["v"] for item in way.findall("tag")}
    if tags.get("natural") != "beach":
        raise ValueError("El way OSM esperado ya no está etiquetado como natural=beach.")
    if coordinates[0] != coordinates[-1]:
        raise ValueError("El way OSM de playa dejó de ser un polígono cerrado.")

    return {
        "way_id": way_id,
        "version": int(way.attrib.get("version", "0")),
        "timestamp": way.attrib.get("timestamp"),
        "changeset": int(way.attrib.get("changeset", "0")),
        "tags": tags,
        "node_refs": node_refs,
        "coordinates": coordinates,
    }


def build_shoreline_geojson(
    osm_way: dict[str, Any],
    retrieved_at: str,
    raw_sha256: str,
) -> dict[str, Any]:
    marine_arc = select_marine_arc(osm_way["coordinates"])
    return {
        "type": "FeatureCollection",
        "name": "playa_grande_shoreline_osm",
        "metadata": {
            "source": "OpenStreetMap",
            "source_url": OSM_PAGE_URL,
            "source_api_url": OSM_API_URL,
            "way_id": OSM_WAY_ID,
            "way_version": osm_way["version"],
            "way_timestamp": osm_way["timestamp"],
            "changeset": osm_way["changeset"],
            "tags": osm_way["tags"],
            "retrieved_at": retrieved_at,
            "observation_date": None,
            "scenario_base_year": 2026,
            "raw_snapshot": str(OSM_RAW_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "raw_sha256": raw_sha256,
            "license": "ODbL",
            "extraction_method": (
                "Dos anclas auditadas dividen el polígono en dos recorridos. Se conserva "
                "el único arco simple cuya longitud UTM 19S está entre 1,80 y 1,95 km; "
                "el otro recorrido interior supera 2 km. La línea se orienta de norte a "
                "sur para que la normal izquierda apunte a tierra."
            ),
            "description": (
                "Borde marino derivado del polígono OSM natural=beach de Playa Grande. "
                "Es una referencia espacial del escenario base, no una línea de agua "
                "observada en 2026."
            ),
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "Borde marino de Playa Grande",
                    "role": "referencia_espacial_escenario_base",
                    "source": f"Arco occidental derivado de OSM way {OSM_WAY_ID}",
                    "vertex_count": len(marine_arc),
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[longitude, latitude] for longitude, latitude in marine_arc],
                },
            }
        ],
    }


def build_elevation_profile(
    query_points: list[dict[str, Any]],
    elevations: list[float | int | None],
    retrieved_at: str,
    request_url: str,
) -> dict[str, Any]:
    if len(query_points) != EXPECTED_STATION_COUNT * len(EXPECTED_OFFSETS_M):
        raise ValueError(f"Se esperaban 33 puntos DEM y se recibieron {len(query_points)}.")
    if len(elevations) != len(query_points):
        raise ValueError("Open-Meteo devolvió una cantidad distinta de elevaciones.")
    if any(value is None for value in elevations):
        raise ValueError("Open-Meteo devolvió una o más cotas nulas.")

    expected_pairs = {
        (f"E{station:02d}", offset)
        for station in range(1, EXPECTED_STATION_COUNT + 1)
        for offset in EXPECTED_OFFSETS_M
    }
    actual_pairs = {
        (str(point["station_id"]), int(point["offset_m"])) for point in query_points
    }
    if actual_pairs != expected_pairs:
        raise ValueError("Los puntos DEM no cubren exactamente E01-E11 × 50/150/250 m.")

    samples = []
    for point, elevation in zip(query_points, elevations, strict=True):
        samples.append(
            {
                "station_id": str(point["station_id"]),
                "offset_m": int(point["offset_m"]),
                "latitude": float(point["latitude"]),
                "longitude": float(point["longitude"]),
                "elevation_m": float(elevation),
            }
        )
    return {
        "source": "Copernicus DEM GLO-90 vía Open-Meteo",
        "data_product": "Copernicus DEM 2021 GLO-90",
        "provider": "Open-Meteo Elevation API",
        "source_url": OPEN_METEO_DOCS_URL,
        "api_endpoint": OPEN_METEO_ENDPOINT,
        "request_url": request_url,
        "retrieved_at": retrieved_at,
        "resolution_m": 90,
        "horizontal_crs": "EPSG:4326 (WGS84)",
        "vertical_reference": "EGM2008, según documentación del proveedor",
        "query_design": {
            "station_count": EXPECTED_STATION_COUNT,
            "station_spacing": "equidistante por progresiva a lo largo del borde",
            "offsets_landward_m": list(EXPECTED_OFFSETS_M),
            "offset_definition": "distancia medida a lo largo de cada transecto local",
        },
        "caveat": (
            "Orientación regional a 90 m; no usar para niveles de inundación finos, "
            "topografía predial ni decisiones de diseño u obras."
        ),
        "samples": samples,
    }


def _file_record(path: Path, **metadata: Any) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "sha256": sha256_file(path),
        **metadata,
    }


def build_provenance_manifest(generated_at: str) -> dict[str, Any]:
    shoreline_payload = json.loads(SHORELINE_PATH.read_text(encoding="utf-8"))
    elevation_payload = json.loads(ELEVATION_PATH.read_text(encoding="utf-8"))
    shoreline_metadata = shoreline_payload["metadata"]
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "active_inputs": [
            _file_record(
                SHORELINE_PATH,
                role="borde_marino_referencia",
                source="OpenStreetMap",
                source_url=OSM_PAGE_URL,
                source_api_url=OSM_API_URL,
                source_version=shoreline_metadata.get("way_version"),
                source_timestamp=shoreline_metadata.get("way_timestamp"),
                license="ODbL",
                status="active",
            ),
            _file_record(
                ELEVATION_PATH,
                role="cotas_dem_transectos",
                source="Copernicus DEM GLO-90 vía Open-Meteo",
                source_url=OPEN_METEO_DOCS_URL,
                request_url=elevation_payload.get("request_url"),
                resolution_m=90,
                status="active",
            ),
            _file_record(
                DATA_DIR / "knowledge_base.json",
                role="corpus_local_rag",
                source="Fuentes y reglas documentadas del proyecto",
                status="active",
            ),
        ],
        "raw_snapshots": [
            _file_record(OSM_RAW_PATH, source_url=OSM_API_URL),
            _file_record(
                OPEN_METEO_RAW_PATH,
                source_url=OPEN_METEO_ENDPOINT,
                request_url=elevation_payload.get("request_url"),
            ),
            _file_record(SOURCE_RECEIPT_PATH, role="recibo_de_adquisicion"),
        ],
        "generated_or_assumed_layers": [
            {
                "layer": "líneas 2017 y futura",
                "method": "offset geométrico con tasa lineal demostrativa",
                "not_observed": True,
            },
            {
                "layer": "franjas de riesgo",
                "method": "umbrales demostrativos de 25 m y 60 m desde la línea proyectada",
                "not_regulatory": True,
            },
            {
                "layer": "predios_demo",
                "method": "polígonos sintéticos para probar la clasificación",
                "not_cadastral": True,
            },
        ],
        "excluded_legacy_inputs": [
            "data/green.tif",
            "data/nir.tif",
            "data/dem.tif",
            "data/linea_costa.geojson",
            "data/zonas_costeras.gpkg",
        ],
        "reproducibility": {
            "refresh_online": "python scripts/00_refresh_source_data.py",
            "rebuild_offline": "python scripts/00_refresh_source_data.py --offline",
            "export": "python scripts/04_build_coastvision_mvp.py",
            "test": "python -m pytest -q",
        },
    }


def request_osm(
    session: requests.Session,
    timeout_s: int = 30,
) -> tuple[bytes, str, str]:
    response = session.get(OSM_API_URL, timeout=timeout_s)
    response.raise_for_status()
    return response.content, response.url, utc_now()


def request_elevations(
    session: requests.Session,
    query_points: list[dict[str, Any]],
    timeout_s: int = 30,
) -> tuple[dict[str, Any], str, str]:
    params = {
        "latitude": ",".join(str(point["latitude"]) for point in query_points),
        "longitude": ",".join(str(point["longitude"]) for point in query_points),
    }
    response = session.get(OPEN_METEO_ENDPOINT, params=params, timeout=timeout_s)
    response.raise_for_status()
    return response.json(), response.url, utc_now()
