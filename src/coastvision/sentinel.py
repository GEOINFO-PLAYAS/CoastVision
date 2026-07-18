"""Sentinel-2 multitemporal, NDWI y extracción de línea de agua.

La serie objetivo es 2016--2026. Earth Search entrega COG L2A públicos desde
2017; para 2016 se cataloga L1C desde Copernicus Data Space (CDSE). Los assets
CDSE requieren una sesión/descarga autenticada, por lo que el catálogo lo
declara de forma explícita en vez de fingir que la escena fue procesada.
"""

from __future__ import annotations

import math
from calendar import monthrange
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import geopandas as gpd
import numpy as np
import requests
from pyproj import Transformer
from rasterio.features import rasterize, shapes
from rasterio.transform import array_bounds, from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling, transform_bounds
from rasterio.windows import Window
from scipy import ndimage
from shapely.geometry import GeometryCollection, LineString, MultiPoint, Point, Polygon, box, shape
from shapely.ops import nearest_points, unary_union


EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"
EARTH_SEARCH_V0_URL = "https://earth-search.aws.element84.com/v0/search"
CDSE_STAC_URL = "https://stac.dataspace.copernicus.eu/v1/search"
DEFAULT_YEARS = tuple(range(2016, 2027))
INVALID_SCL_CLASSES = {0, 1, 3, 8, 9, 10, 11}


@dataclass(frozen=True)
class SentinelScene:
    year: int
    item_id: str
    acquired_at: str
    cloud_cover_pct: float | None
    provider: str
    collection: str
    processing_level: str
    tile_code: str | None
    coverage_fraction: float
    green_asset: str
    nir_asset: str
    scl_asset: str | None
    product_asset: str | None
    requires_authentication: bool
    item_url: str | None
    data_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ShorelineExtraction:
    scene: SentinelScene
    shoreline_wgs84: LineString
    water_polygon_wgs84: Polygon
    ndwi: np.ndarray
    valid_mask: np.ndarray
    transform: Any
    raster_crs: str
    metadata: dict[str, Any]


def calculate_ndwi(
    green: np.ndarray,
    nir: np.ndarray,
    valid_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Calcula ``(B03-B08)/(B03+B08)`` y asigna NaN fuera de datos válidos."""
    if green.shape != nir.shape:
        raise ValueError("Las bandas verde y NIR deben tener la misma forma.")
    green = np.asarray(green, dtype=np.float32)
    nir = np.asarray(nir, dtype=np.float32)
    denominator = green + nir
    valid = np.isfinite(green) & np.isfinite(nir) & (denominator != 0)
    if valid_mask is not None:
        if valid_mask.shape != green.shape:
            raise ValueError("La máscara válida debe coincidir con las bandas.")
        valid &= valid_mask.astype(bool)
    result = np.full(green.shape, np.nan, dtype=np.float32)
    result[valid] = (green[valid] - nir[valid]) / denominator[valid]
    return result


def strict_majority(masks: Iterable[np.ndarray]) -> np.ndarray:
    """Mayoría estricta: con 2 escenas exige 2; con 4 exige 3."""
    masks = [np.asarray(mask, dtype=bool) for mask in masks]
    if not masks:
        raise ValueError("Se requiere al menos una máscara.")
    if any(mask.shape != masks[0].shape for mask in masks):
        raise ValueError("Las máscaras deben estar alineadas en la misma grilla.")
    votes = np.sum(masks, axis=0)
    return votes >= (len(masks) // 2 + 1)


def consensus_shoreline_extractions(
    extractions: Iterable[ShorelineExtraction],
    reference_shoreline_wgs84: LineString,
    *,
    min_scenes: int = 2,
    pixel_size_m: float = 10.0,
    max_reference_distance_m: float = 250.0,
) -> tuple[LineString, Polygon, dict[str, Any]]:
    """Combina varias máscaras NDWI en una línea costera de consenso.

    Cada escena se vectoriza primero con su propia grilla. Después las
    superficies de agua se llevan a una grilla métrica común (UTM 19S) y se
    conserva únicamente el voto mayoritario estricto. Esto reduce el ruido de
    oleaje de una captura puntual, siguiendo la idea multiescena de CoastSat,
    sin promediar coordenadas en grados.
    """
    valid = list(extractions)
    if not valid:
        raise ValueError("Se requiere al menos una extracción NDWI.")
    if min_scenes < 1 or len(valid) < min_scenes:
        raise ValueError(
            f"Solo hay {len(valid)} escenas válidas; se requieren al menos {min_scenes}."
        )
    if pixel_size_m <= 0:
        raise ValueError("pixel_size_m debe ser mayor que cero.")

    metric_polygons = [
        gpd.GeoSeries([item.water_polygon_wgs84], crs="EPSG:4326")
        .to_crs("EPSG:32719")
        .iloc[0]
        for item in valid
    ]
    union = unary_union(metric_polygons)
    if union.is_empty:
        raise ValueError("Las máscaras NDWI no contienen polígonos de agua.")
    west, south, east, north = union.bounds
    margin = pixel_size_m * 2.0
    west -= margin
    south -= margin
    east += margin
    north += margin
    width = max(1, int(math.ceil((east - west) / pixel_size_m)))
    height = max(1, int(math.ceil((north - south) / pixel_size_m)))
    if width * height > 4_000_000:
        raise ValueError("La grilla de consenso excede 4 millones de píxeles.")
    transform = from_origin(west, north, pixel_size_m, pixel_size_m)
    masks = [
        rasterize(
            [(polygon, 1)],
            out_shape=(height, width),
            transform=transform,
            fill=0,
            dtype="uint8",
        ).astype(bool)
        for polygon in metric_polygons
    ]
    consensus = strict_majority(masks)
    consensus = ndimage.binary_opening(consensus, structure=np.ones((3, 3), dtype=bool))
    consensus = ndimage.binary_closing(consensus, structure=np.ones((3, 3), dtype=bool))
    polygons = [
        shape(geometry)
        for geometry, value in shapes(
            consensus.astype(np.uint8), mask=consensus, transform=transform
        )
        if value == 1
    ]
    if not polygons:
        raise ValueError("El consenso multiescena quedó sin superficie de agua.")
    water_metric = max(polygons, key=lambda polygon: polygon.area).buffer(0)
    reference_metric = (
        gpd.GeoSeries([reference_shoreline_wgs84], crs="EPSG:4326")
        .to_crs("EPSG:32719")
        .iloc[0]
    )
    shoreline_metric = _guided_shoreline(
        water_metric.boundary,
        reference_metric,
        water_metric,
        search_distance_m=max_reference_distance_m,
        spacing_m=pixel_size_m,
    )
    shoreline = gpd.GeoSeries([shoreline_metric], crs="EPSG:32719").to_crs("EPSG:4326").iloc[0]
    water = gpd.GeoSeries([water_metric], crs="EPSG:32719").to_crs("EPSG:4326").iloc[0]
    areas = [float(polygon.area) for polygon in metric_polygons]
    mean_area = float(np.mean(areas))
    std_area = float(np.std(areas))
    return shoreline, water, {
        "method": "strict_majority_water_mask_utm19s",
        "scene_count": len(valid),
        "min_scenes": min_scenes,
        "pixel_size_m": pixel_size_m,
        "individual_water_area_m2": [round(area, 1) for area in areas],
        "water_area_mean_m2": round(mean_area, 1),
        "water_area_std_m2": round(std_area, 1),
        "water_area_cv_pct": round(std_area / mean_area * 100.0, 2) if mean_area else None,
    }


def consensus_shorelines_metric(
    shorelines_wgs84: Iterable[LineString],
    *,
    count: int = 150,
) -> LineString:
    """Calcula una línea mediana alineando progresivas en UTM 19S.

    Se usa después de corregir la marea de cada escena individual. Las líneas
    se orientan por sus extremos, se remuestrean por longitud y se toma la
    mediana de cada vértice; así no se vuelve a elegir una fecha representativa
    para esconder diferencias mareales entre escenas.
    """
    lines = list(shorelines_wgs84)
    if not lines:
        raise ValueError("Se requiere al menos una línea costera.")
    if count < 2:
        raise ValueError("count debe ser al menos 2.")
    metric = [
        gpd.GeoSeries([line], crs="EPSG:4326").to_crs("EPSG:32719").iloc[0]
        for line in lines
    ]
    reference = metric[0]
    samples = []
    for line in metric:
        distances = np.linspace(0.0, line.length, count)
        coords = [(point.x, point.y) for point in (line.interpolate(distance) for distance in distances)]
        direct = np.hypot(coords[0][0] - reference.coords[0][0], coords[0][1] - reference.coords[0][1])
        reverse = np.hypot(coords[-1][0] - reference.coords[0][0], coords[-1][1] - reference.coords[0][1])
        if reverse < direct:
            coords.reverse()
        samples.append(np.asarray(coords, dtype=float))
    median_coords = np.median(np.stack(samples, axis=0), axis=0)
    result = LineString(median_coords.tolist())
    return gpd.GeoSeries([result], crs="EPSG:32719").to_crs("EPSG:4326").iloc[0]


def _request_stac(
    url: str,
    collection: str,
    bbox_wgs84: list[float],
    year: int,
    *,
    start_month: int,
    end_month: int,
    limit: int = 100,
    timeout: int = 60,
) -> list[dict[str, Any]]:
    if not 1 <= start_month <= end_month <= 12:
        raise ValueError("La ventana mensual STAC debe cumplir 1 <= inicio <= fin <= 12.")
    end_day = monthrange(year, end_month)[1]
    payload = {
        "collections": [collection],
        "bbox": bbox_wgs84,
        "datetime": (
            f"{year}-{start_month:02d}-01T00:00:00Z/"
            f"{year}-{end_month:02d}-{end_day:02d}T23:59:59Z"
        ),
        "limit": limit,
    }
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return list(response.json().get("features", []))


def _coverage_fraction(item: dict[str, Any], bbox_wgs84: list[float]) -> float:
    aoi = box(*bbox_wgs84)
    footprint = shape(item["geometry"])
    if aoi.area == 0:
        return 0.0
    return max(0.0, min(1.0, footprint.intersection(aoi).area / aoi.area))


def _asset_href(item: dict[str, Any], *keys: str) -> str | None:
    assets = item.get("assets", {})
    for key in keys:
        asset = assets.get(key)
        if asset and asset.get("href"):
            return str(asset["href"])
    return None


def _item_self_url(item: dict[str, Any]) -> str | None:
    for link in item.get("links", []):
        if link.get("rel") == "self":
            return link.get("href")
    return None


def _public_sentinel_l1c_href(href: str | None) -> str | None:
    """Convierte el URI histórico S3 L1C en HTTPS público reproducible."""
    prefix = "s3://sentinel-s2-l1c/"
    if href and href.startswith(prefix):
        key = href[len(prefix):]
        return f"https://sentinel-s2-l1c.s3.eu-central-1.amazonaws.com/{key}"
    return href


def normalize_stac_item(
    item: dict[str, Any],
    year: int,
    bbox_wgs84: list[float],
    provider: str,
) -> SentinelScene:
    properties = item.get("properties", {})
    if provider == "earth-search":
        green = _asset_href(item, "green", "B03")
        nir = _asset_href(item, "nir", "B08")
        scl = _asset_href(item, "scl", "SCL")
        collection = str(item.get("collection") or "sentinel-2-l2a")
        level = "L2A"
        requires_authentication = False
        product = None
        status = "public_cog_ready"
    elif provider == "earth-search-l1c":
        green = _public_sentinel_l1c_href(_asset_href(item, "green", "B03"))
        nir = _public_sentinel_l1c_href(_asset_href(item, "nir", "B08"))
        scl = None
        collection = str(item.get("collection") or "sentinel-s2-l1c")
        level = "L1C"
        requires_authentication = False
        product = None
        status = "public_l1c_jp2_ready"
    elif provider == "copernicus-data-space":
        green = _asset_href(item, "B03", "green")
        nir = _asset_href(item, "B08", "nir")
        scl = _asset_href(item, "SCL", "scl")
        product = _asset_href(item, "Product", "product")
        collection = str(item.get("collection") or "sentinel-2-l1c")
        level = "L1C"
        requires_authentication = True
        status = "catalogued_auth_download_required"
    else:
        raise ValueError(f"Proveedor STAC no soportado: {provider}")
    if not green or not nir:
        raise ValueError(f"El item {item.get('id')} no expone B03/B08.")
    cloud = properties.get("eo:cloud_cover")
    tile = properties.get("grid:code") or properties.get("s2:mgrs_tile")
    return SentinelScene(
        year=year,
        item_id=str(item["id"]),
        acquired_at=str(properties.get("datetime") or properties.get("start_datetime")),
        cloud_cover_pct=float(cloud) if cloud is not None else None,
        provider=provider,
        collection=collection,
        processing_level=level,
        tile_code=str(tile) if tile else None,
        coverage_fraction=round(_coverage_fraction(item, bbox_wgs84), 6),
        green_asset=green,
        nir_asset=nir,
        scl_asset=scl,
        product_asset=product,
        requires_authentication=requires_authentication,
        item_url=_item_self_url(item),
        data_status=status,
    )


def _rank_scenes(scenes: list[SentinelScene]) -> list[SentinelScene]:
    # El mismo paso satelital aparece en dos teselas vecinas. Por fecha se
    # conserva la tesela que cubre mayor proporción del AOI.
    by_timestamp: dict[str, SentinelScene] = {}
    for scene in scenes:
        current = by_timestamp.get(scene.acquired_at)
        cloud = scene.cloud_cover_pct if scene.cloud_cover_pct is not None else 999.0
        rank = (scene.coverage_fraction, -cloud)
        current_rank = (
            (
                current.coverage_fraction,
                -(
                    current.cloud_cover_pct
                    if current.cloud_cover_pct is not None
                    else 999.0
                ),
            )
            if current else (-1.0, -999.0)
        )
        if current is None or rank > current_rank:
            by_timestamp[scene.acquired_at] = scene
    candidates = list(by_timestamp.values())
    full_coverage = [scene for scene in candidates if scene.coverage_fraction >= 0.98]
    if full_coverage:
        candidates = full_coverage
    return sorted(
        candidates,
        key=lambda scene: (
            scene.cloud_cover_pct if scene.cloud_cover_pct is not None else 999.0,
            -scene.coverage_fraction,
            scene.acquired_at,
        ),
    )


def query_sentinel_year(
    bbox_wgs84: list[float],
    year: int,
    *,
    start_month: int = 1,
    end_month: int = 3,
    max_cloud_pct: float = 20.0,
    max_scenes: int = 3,
) -> list[SentinelScene]:
    if year < 2016 or year > datetime.now(timezone.utc).year:
        raise ValueError("Año Sentinel fuera del intervalo disponible del proyecto.")
    if year == 2016:
        raw = _request_stac(
            EARTH_SEARCH_V0_URL,
            "sentinel-s2-l1c",
            bbox_wgs84,
            year,
            start_month=start_month,
            end_month=end_month,
        )
        provider = "earth-search-l1c"
    else:
        raw = _request_stac(
            EARTH_SEARCH_URL,
            "sentinel-2-l2a",
            bbox_wgs84,
            year,
            start_month=start_month,
            end_month=end_month,
        )
        provider = "earth-search"
    normalized: list[SentinelScene] = []
    above_cloud_limit: list[SentinelScene] = []
    for item in raw:
        try:
            scene = normalize_stac_item(item, year, bbox_wgs84, provider)
        except (KeyError, TypeError, ValueError):
            continue
        if scene.cloud_cover_pct is None or scene.cloud_cover_pct <= max_cloud_pct:
            normalized.append(scene)
        else:
            above_cloud_limit.append(scene)
    if year == 2016 and not normalized and above_cloud_limit:
        best = _rank_scenes(above_cloud_limit)[0]
        normalized = [replace(
            best,
            data_status="public_l1c_single_scene_cloud_fallback_requires_visual_qa",
        )]
    return _rank_scenes(normalized)[:max_scenes]


def build_multitemporal_catalog(
    bbox_wgs84: list[float],
    years: Iterable[int] = DEFAULT_YEARS,
    *,
    start_month: int = 1,
    end_month: int = 3,
    max_cloud_pct: float = 20.0,
    max_scenes_per_year: int = 3,
) -> dict[str, Any]:
    years = tuple(sorted(set(int(year) for year in years)))
    records: list[dict[str, Any]] = []
    missing: list[int] = []
    for year in years:
        scenes = query_sentinel_year(
            bbox_wgs84,
            year,
            start_month=start_month,
            end_month=end_month,
            max_cloud_pct=max_cloud_pct,
            max_scenes=max_scenes_per_year,
        )
        if not scenes:
            missing.append(year)
        records.extend(scene.to_dict() for scene in scenes)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "study_bbox_wgs84": bbox_wgs84,
        "years_requested": list(years),
        "seasonal_window": {"start_month": start_month, "end_month": end_month},
        "max_cloud_pct": max_cloud_pct,
        "max_scenes_per_year": max_scenes_per_year,
        "providers": {
            "2016": {
                "name": "Copernicus Data Space STAC",
                "url": CDSE_STAC_URL,
                "collection": "sentinel-2-l1c",
                "note": "L1C TOA; descarga autenticada requerida",
            },
            "2017-2026": {
                "name": "Element84 Earth Search",
                "url": EARTH_SEARCH_URL,
                "collection": "sentinel-2-l2a",
                "note": "L2A COG público con SCL",
            },
        },
        "scenes": records,
        "missing_years": missing,
        "catalog_complete": not missing and years == DEFAULT_YEARS,
        "catalogue_definition": "at_least_one_candidate_scene_per_requested_year",
        "processing_ready_years": sorted({
            int(record["year"])
            for record in records
            if not record["requires_authentication"]
        }),
        "authentication_required_years": sorted({
            int(record["year"])
            for record in records
            if record["requires_authentication"]
        }),
        "radiometric_warning": (
            "2016 L1C TOA no es radiométricamente idéntico a L2A 2017-2026; "
            "la comparación final debe reportar esta incertidumbre."
        ),
    }


def _window_for_bbox(dataset, bbox_wgs84: list[float]) -> Window:
    bounds = transform_bounds("EPSG:4326", dataset.crs, *bbox_wgs84, densify_pts=21)
    raw = dataset.window(*bounds)
    full = Window(0, 0, dataset.width, dataset.height)
    return raw.round_offsets().round_lengths().intersection(full)


def _read_aligned(dataset, target_crs, target_transform, height: int, width: int, resampling):
    with WarpedVRT(
        dataset,
        crs=target_crs,
        transform=target_transform,
        height=height,
        width=width,
        resampling=resampling,
    ) as vrt:
        return vrt.read(1, masked=True)


def _clean_water_mask(mask: np.ndarray, min_component_pixels: int = 80) -> np.ndarray:
    mask = ndimage.binary_opening(mask, structure=np.ones((3, 3), dtype=bool))
    mask = ndimage.binary_closing(mask, structure=np.ones((3, 3), dtype=bool))
    labels, count = ndimage.label(mask)
    if count == 0:
        raise ValueError("NDWI no identificó agua tras el filtrado.")
    sizes = np.bincount(labels.ravel())
    border_labels = np.concatenate(
        (labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1])
    )
    candidates = set(np.unique(border_labels)) - {0}
    candidates = {label for label in candidates if sizes[label] >= min_component_pixels}
    if not candidates:
        candidates = {
            int(label) for label in range(1, count + 1) if sizes[label] >= min_component_pixels
        }
    if not candidates:
        raise ValueError("Las componentes de agua son demasiado pequeñas.")
    winner = max(candidates, key=lambda label: sizes[label])
    return labels == winner


def _intersection_points(geometry, origin: Point) -> list[Point]:
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, Point):
        return [geometry]
    if isinstance(geometry, MultiPoint):
        return list(geometry.geoms)
    if isinstance(geometry, LineString):
        return [nearest_points(origin, geometry)[1]]
    if isinstance(geometry, GeometryCollection) or hasattr(geometry, "geoms"):
        points: list[Point] = []
        for part in geometry.geoms:
            points.extend(_intersection_points(part, origin))
        return points
    return []


def _guided_shoreline(
    boundary,
    reference: LineString,
    water_polygon,
    search_distance_m: float,
    spacing_m: float = 10.0,
) -> LineString:
    """Muestrea la costa sobre normales fijas para evitar bordes/loops espurios."""
    distances = list(np.arange(0.0, reference.length, spacing_m)) + [reference.length]
    selected: list[tuple[float, Point, float, float, float]] = []
    tangent_window = max(5.0, spacing_m)
    previous_position: float | None = None
    for distance in distances:
        origin = reference.interpolate(distance)
        before = reference.interpolate(max(0.0, distance - tangent_window))
        after = reference.interpolate(min(reference.length, distance + tangent_window))
        dx, dy = after.x - before.x, after.y - before.y
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        nx, ny = -dy / length, dx / length
        transect = LineString([
            (origin.x - nx * search_distance_m, origin.y - ny * search_distance_m),
            (origin.x + nx * search_distance_m, origin.y + ny * search_distance_m),
        ])
        candidates = _intersection_points(boundary.intersection(transect), origin)
        if candidates:
            oriented = []
            for candidate in candidates:
                sea_probe = Point(candidate.x - nx * spacing_m, candidate.y - ny * spacing_m)
                land_probe = Point(candidate.x + nx * spacing_m, candidate.y + ny * spacing_m)
                if water_polygon.covers(sea_probe) and not water_polygon.covers(land_probe):
                    oriented.append(candidate)
            candidates = oriented or candidates
            positioned = [
                (candidate, (candidate.x - origin.x) * nx + (candidate.y - origin.y) * ny)
                for candidate in candidates
            ]
            plausible = [item for item in positioned if -search_distance_m <= item[1] <= 60.0]
            positioned = plausible or positioned
            if previous_position is None:
                candidate, position = min(positioned, key=lambda item: abs(item[1]))
            else:
                candidate, position = min(
                    positioned,
                    key=lambda item: abs(item[1] - previous_position) + 0.08 * abs(item[1]),
                )
                if abs(position - previous_position) > 80.0:
                    continue
            previous_position = float(position)
            selected.append((distance, origin, nx, ny, float(position)))
    minimum = max(20, math.ceil(len(distances) * 0.60))
    if len(selected) < minimum:
        raise ValueError(
            f"Solo {len(selected)}/{len(distances)} transectos encontraron la costa NDWI; "
            f"se requieren al menos {minimum}."
        )
    positions = np.asarray([item[4] for item in selected], dtype=float)
    if len(positions) >= 5:
        positions = ndimage.median_filter(positions, size=5, mode="nearest")
        positions = ndimage.gaussian_filter1d(positions, sigma=1.0, mode="nearest")
    points = [
        (origin.x + nx * position, origin.y + ny * position)
        for (_, origin, nx, ny, _), position in zip(selected, positions)
    ]
    return LineString(points).simplify(2.0)


def _vectorize_shoreline(
    water_mask: np.ndarray,
    transform,
    raster_crs,
    reference_shoreline_wgs84: LineString,
    max_reference_distance_m: float,
) -> tuple[LineString, Polygon]:
    polygons = [
        shape(geometry)
        for geometry, value in shapes(
            water_mask.astype(np.uint8), mask=water_mask, transform=transform
        )
        if value == 1
    ]
    if not polygons:
        raise ValueError("No se pudo vectorizar la máscara de agua.")
    water = max(polygons, key=lambda polygon: polygon.area).buffer(0)
    reference = gpd.GeoSeries([reference_shoreline_wgs84], crs="EPSG:4326").to_crs(raster_crs).iloc[0]
    west, south, east, north = array_bounds(*water_mask.shape, transform)
    pixel = max(abs(transform.a), abs(transform.e))
    raster_edge = box(west, south, east, north).boundary.buffer(pixel * 1.5)
    boundary = water.boundary.difference(raster_edge)
    shoreline = _guided_shoreline(
        boundary,
        reference,
        water,
        search_distance_m=max_reference_distance_m,
        spacing_m=max(10.0, pixel),
    )

    shoreline_wgs84 = gpd.GeoSeries([shoreline], crs=raster_crs).to_crs("EPSG:4326").iloc[0]
    water_wgs84 = gpd.GeoSeries([water], crs=raster_crs).to_crs("EPSG:4326").iloc[0]
    coordinates = list(shoreline_wgs84.coords)
    if coordinates[0][1] < coordinates[-1][1]:
        shoreline_wgs84 = LineString(reversed(coordinates))
    return shoreline_wgs84, water_wgs84


def extract_ndwi_shoreline(
    scene: SentinelScene,
    bbox_wgs84: list[float],
    reference_shoreline_wgs84: LineString,
    *,
    ndwi_threshold: float = 0.0,
    max_reference_distance_m: float = 250.0,
) -> ShorelineExtraction:
    """Lee B03/B08, aplica SCL cuando existe y extrae una línea georreferenciada."""
    if scene.requires_authentication and scene.green_asset.startswith("s3://eodata"):
        raise PermissionError(
            "La escena CDSE está catalogada pero sus assets requieren autenticación. "
            "Descargue el producto o reemplace las URLs por rutas locales antes de procesar."
        )
    import rasterio

    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(scene.green_asset) as green_source:
            window = _window_for_bbox(green_source, bbox_wgs84)
            green = green_source.read(1, window=window, masked=True)
            transform = green_source.window_transform(window)
            crs = green_source.crs
            height, width = green.shape
            with rasterio.open(scene.nir_asset) as nir_source:
                nir = _read_aligned(
                    nir_source, crs, transform, height, width, Resampling.bilinear
                )
            scl = None
            if scene.scl_asset:
                with rasterio.open(scene.scl_asset) as scl_source:
                    scl = _read_aligned(
                        scl_source, crs, transform, height, width, Resampling.nearest
                    )

    valid = (~np.ma.getmaskarray(green)) & (~np.ma.getmaskarray(nir))
    valid &= np.asarray(green) > 0
    valid &= np.asarray(nir) > 0
    cloud_mask_status = "global_scene_metadata_only"
    if scl is not None:
        scl_values = np.asarray(scl)
        valid &= ~np.isin(scl_values, list(INVALID_SCL_CLASSES))
        valid &= ~np.ma.getmaskarray(scl)
        cloud_mask_status = "sentinel2_scene_classification_SCL"
    ndwi = calculate_ndwi(np.asarray(green), np.asarray(nir), valid)
    water_mask = valid & np.isfinite(ndwi) & (ndwi > ndwi_threshold)
    water_mask = _clean_water_mask(water_mask)
    shoreline, water_polygon = _vectorize_shoreline(
        water_mask,
        transform,
        crs,
        reference_shoreline_wgs84,
        max_reference_distance_m,
    )
    return ShorelineExtraction(
        scene=scene,
        shoreline_wgs84=shoreline,
        water_polygon_wgs84=water_polygon,
        ndwi=ndwi,
        valid_mask=valid,
        transform=transform,
        raster_crs=str(crs),
        metadata={
            "formula": "NDWI=(B03-B08)/(B03+B08)",
            "threshold": ndwi_threshold,
            "cloud_mask": cloud_mask_status,
            "valid_pixels": int(valid.sum()),
            "water_pixels": int(water_mask.sum()),
            "strict_reference_distance_m": max_reference_distance_m,
            "grid_alignment": "B08/SCL remuestreadas a la grilla B03",
            "shoreline_regularization": (
                "intersecciones con normales fijas cada 10 m, continuidad <=80 m, "
                "filtro mediana y suavizado gaussiano"
            ),
        },
    )


def load_cached_ndwi_shoreline(
    scene: SentinelScene,
    ndwi_path: str | Path,
    reference_shoreline_wgs84: LineString,
    *,
    ndwi_threshold: float = 0.0,
    max_reference_distance_m: float = 250.0,
) -> ShorelineExtraction:
    """Reconstruye la extracción desde un NDWI GeoTIFF previamente validado.

    Permite reanudar la serie sin volver a leer B03/B08/SCL remotos. El TIFF
    conserva grilla, CRS, ``item_id`` y umbral; cualquier incompatibilidad
    invalida el caché en vez de mezclar corridas distintas.
    """
    import rasterio

    ndwi_path = Path(ndwi_path)
    with rasterio.open(ndwi_path) as dataset:
        tags = dataset.tags()
        cached_item = tags.get("item_id")
        if cached_item and cached_item != scene.item_id:
            raise ValueError(
                f"El NDWI en caché pertenece a {cached_item}, no a {scene.item_id}."
            )
        cached_threshold = tags.get("threshold")
        if cached_threshold is not None and not np.isclose(
            float(cached_threshold), float(ndwi_threshold)
        ):
            raise ValueError(
                "El umbral del NDWI en caché no coincide con la corrida solicitada."
            )
        masked = dataset.read(1, masked=True)
        ndwi = np.asarray(masked, dtype=np.float32)
        valid = (~np.ma.getmaskarray(masked)) & np.isfinite(ndwi)
        transform = dataset.transform
        crs = dataset.crs

    water_mask = _clean_water_mask(valid & (ndwi > ndwi_threshold))
    shoreline, water_polygon = _vectorize_shoreline(
        water_mask,
        transform,
        crs,
        reference_shoreline_wgs84,
        max_reference_distance_m,
    )
    return ShorelineExtraction(
        scene=scene,
        shoreline_wgs84=shoreline,
        water_polygon_wgs84=water_polygon,
        ndwi=np.where(valid, ndwi, np.nan),
        valid_mask=valid,
        transform=transform,
        raster_crs=str(crs),
        metadata={
            "formula": "NDWI=(B03-B08)/(B03+B08)",
            "threshold": ndwi_threshold,
            "cloud_mask": "reused_from_cached_B03_B08_SCL_extraction",
            "valid_pixels": int(valid.sum()),
            "water_pixels": int(water_mask.sum()),
            "strict_reference_distance_m": max_reference_distance_m,
            "grid_alignment": "GeoTIFF NDWI georreferenciado de una corrida previa",
            "shoreline_regularization": (
                "intersecciones con normales fijas cada 10 m, continuidad <=80 m, "
                "filtro mediana y suavizado gaussiano"
            ),
            "cache_path": str(ndwi_path),
        },
    )
