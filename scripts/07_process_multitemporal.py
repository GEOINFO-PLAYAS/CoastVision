from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import LineString, Point


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.acquisition import atomic_write_json  # noqa: E402
from coastvision.change_analysis import analyze_shoreline_change  # noqa: E402
from coastvision.sentinel import (  # noqa: E402
    SentinelScene,
    consensus_shoreline_extractions,
    consensus_shorelines_metric,
    extract_ndwi_shoreline,
    load_cached_ndwi_shoreline,
)
from coastvision.storms import (  # noqa: E402
    aggregate_position_anomalies,
    correlate_storms,
    load_storm_events,
    tag_observations_with_storms,
)
from coastvision.tides import (  # noqa: E402
    correct_shoreline_to_msl,
    predict_tides_fes2014,
    validate_fes2014_directory,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrae NDWI por año, corrige FES2014 y calcula tasas tipo DSAS."
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=list(range(2016, 2027)),
        help="Años a procesar; por defecto 2016..2026.",
    )
    parser.add_argument("--catalog", type=Path, default=ROOT / "data/sentinel/catalog_2016_2026.json")
    parser.add_argument("--tide-model-dir", type=Path, default=None)
    parser.add_argument(
        "--local-assets",
        type=Path,
        default=None,
        help="JSON opcional {item_id:{green,nir,scl}} para assets descargados, incluido 2016.",
    )
    parser.add_argument("--ndwi-threshold", type=float, default=0.0)
    parser.add_argument(
        "--resume-cache",
        action="store_true",
        help="Reutiliza NDWI GeoTIFF compatibles y conserva el avance entre reintentos.",
    )
    parser.add_argument(
        "--max-scenes-per-year",
        type=int,
        default=3,
        help="Máximo de escenas NDWI candidatas a combinar por año.",
    )
    parser.add_argument(
        "--min-scenes-consensus",
        type=int,
        default=2,
        help="Escenas mínimas para activar consenso estricto; con una sola se deja fallback explícito.",
    )
    parser.add_argument("--beach-slope", type=float, default=0.05)
    parser.add_argument(
        "--storm-events",
        type=Path,
        default=ROOT / "data/events/marejadas_oficiales_armada.csv",
        help="Catálogo de avisos oficiales SHOA/Armada/DMC con fechas verificables.",
    )
    parser.add_argument(
        "--storm-window-days",
        type=int,
        default=3,
        help="Ventana antes/después del aviso para asociar una escena (días).",
    )
    parser.add_argument(
        "--storm-catalog-metadata",
        type=Path,
        default=ROOT / "data/events/catalog_metadata.json",
        help="Metadatos de cobertura y completitud del catálogo oficial.",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/multitemporal")
    return parser.parse_args()


def _load_local_assets(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("--local-assets debe ser un objeto JSON por item_id.")
    return payload


def _localize_scene(scene: SentinelScene, mapping: dict[str, dict[str, str]]) -> SentinelScene:
    assets = mapping.get(scene.item_id)
    if not assets:
        return scene
    def resolve_asset(value: str) -> Path:
        path = Path(value).expanduser()
        return (path if path.is_absolute() else ROOT / path).resolve()

    green_path = resolve_asset(assets["green"])
    nir_path = resolve_asset(assets["nir"])
    scl = assets.get("scl")
    scl_path = resolve_asset(scl) if scl else None
    if not green_path.is_file() or not nir_path.is_file() or (
        scl_path is not None and not scl_path.is_file()
    ):
        raise FileNotFoundError(f"Assets locales incompletos para {scene.item_id}")
    return replace(
        scene,
        green_asset=str(green_path),
        nir_asset=str(nir_path),
        scl_asset=str(scl_path) if scl_path else None,
        requires_authentication=False,
        data_status="local_assets_ready",
    )


def _write_ndwi(extraction, output: Path) -> None:
    data = np.where(np.isfinite(extraction.ndwi), extraction.ndwi, -9999.0).astype("float32")
    with rasterio.open(
        output,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs=extraction.raster_crs,
        transform=extraction.transform,
        nodata=-9999.0,
        compress="deflate",
    ) as dataset:
        dataset.write(data, 1)
        dataset.update_tags(
            formula="NDWI=(B03-B08)/(B03+B08)",
            item_id=extraction.scene.item_id,
            threshold=extraction.metadata["threshold"],
        )


def _clear_generated_outputs(output: Path) -> list[str]:
    """Evita mezclar artefactos de una corrida anterior con una parcial nueva."""
    patterns = (
        "ndwi_*.tif",
        "water_*.geojson",
        "shorelines_raw_ndwi.geojson",
        "shorelines_2016_2026_fes2014.geojson",
        "tide_corrections.csv",
        "transects.geojson",
        "transect_intersections.geojson",
        "transect_intersections.csv",
        "transect_rates.geojson",
        "transect_rates.csv",
        "storm_scene_join.csv",
        "storm_correlation.json",
        "pipeline_summary.json",
    )
    removed: list[str] = []
    for pattern in patterns:
        for path in output.glob(pattern):
            if path.is_file():
                path.unlink()
                removed.append(path.name)
    return sorted(set(removed))


def _north_to_south(line: LineString) -> LineString:
    coordinates = list(line.coords)
    return LineString(reversed(coordinates)) if coordinates[0][1] < coordinates[-1][1] else line


def _land_reference(line_wgs84: LineString, offset_m: float = 300.0) -> Point:
    """Crea un respaldo terrestre al lado izquierdo de la costa norte-sur."""
    line = gpd.GeoSeries([line_wgs84], crs=4326).to_crs(32719).iloc[0]
    distance = line.length / 2
    window = min(20.0, line.length / 4)
    before = line.interpolate(max(0.0, distance - window))
    after = line.interpolate(min(line.length, distance + window))
    dx, dy = after.x - before.x, after.y - before.y
    length = float(np.hypot(dx, dy))
    if length == 0:
        raise ValueError("La referencia costera no permite calcular una normal terrestre.")
    midpoint = line.interpolate(distance)
    land_metric = Point(
        midpoint.x - dy / length * offset_m,
        midpoint.y + dx / length * offset_m,
    )
    return gpd.GeoSeries([land_metric], crs=32719).to_crs(4326).iloc[0]


def main() -> None:
    args = arguments()
    requested_years = sorted(set(args.years))
    if any(year < 2016 or year > 2026 for year in requested_years):
        raise ValueError("Este proyecto exige el intervalo 2016-2026.")
    if not -1 <= args.ndwi_threshold <= 1:
        raise ValueError("El umbral NDWI debe estar entre -1 y 1.")
    if args.max_scenes_per_year < 1:
        raise ValueError("--max-scenes-per-year debe ser al menos 1.")
    if args.min_scenes_consensus < 1 or args.min_scenes_consensus > args.max_scenes_per_year:
        raise ValueError("--min-scenes-consensus debe estar entre 1 y --max-scenes-per-year.")

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    bbox = catalog["study_bbox_wgs84"]
    scenes_by_year: dict[int, list[SentinelScene]] = {}
    for record in catalog["scenes"]:
        scene = SentinelScene(**record)
        scenes_by_year.setdefault(scene.year, []).append(scene)
    local_assets = _load_local_assets(args.local_assets)
    reference_gdf = gpd.read_file(ROOT / "data/playa_grande_shoreline_osm.geojson")
    reference_line = _north_to_south(reference_gdf.geometry.iloc[0])
    land_reference = _land_reference(reference_line)
    center_metric = gpd.GeoSeries([reference_line], crs="EPSG:4326").to_crs(32719).iloc[0].centroid
    center = gpd.GeoSeries([center_metric], crs=32719).to_crs(4326).iloc[0]

    args.output.mkdir(parents=True, exist_ok=True)
    removed_previous_outputs = (
        [] if args.resume_cache else _clear_generated_outputs(args.output)
    )

    model_dir = args.tide_model_dir or os.environ.get("TIDE_MODEL_DIR")
    tide_validation: dict = {
        "configured": False,
        "valid": False,
        "reason": "TIDE_MODEL_DIR no configurado; se generarán solo líneas NDWI crudas.",
    }
    tide_ready = False
    if model_dir:
        try:
            tide_validation = {
                "configured": True,
                **validate_fes2014_directory(model_dir),
                "numeric_prediction_validated": False,
            }
            tide_ready = bool(tide_validation["valid"])
        except Exception as exc:
            tide_validation = {
                "configured": True,
                "valid": False,
                "reason": str(exc),
                "numeric_prediction_validated": False,
            }

    raw_records: list[dict] = []
    corrected_records: list[dict] = []
    tide_rows: list[dict] = []
    tide_failures: list[dict] = []
    blocked: list[dict] = []
    scene_attempts: list[dict] = []
    scene_receipts: list[dict] = []
    tide_groups: list[dict] = []
    analysis_result: dict = {
        "status": "NOT_RUN",
        "reason": "Se requieren al menos dos líneas corregidas con FES2014.",
    }
    storm_result: dict = {
        "status": "NOT_RUN",
        "reason": "Se requieren al menos dos líneas corregidas y un catálogo oficial.",
    }

    for year in requested_years:
        candidates = scenes_by_year.get(year, [])
        if not candidates:
            blocked.append({"year": year, "reason": "no_scene_in_catalog"})
            continue

        successful: list[tuple[SentinelScene, object]] = []
        failed_attempts: list[dict] = []
        for candidate in candidates[: args.max_scenes_per_year]:
            try:
                localized = _localize_scene(candidate, local_assets)
                if localized.requires_authentication:
                    raise PermissionError("cdse_authenticated_download_required")
                cached_ndwi = args.output / f"ndwi_{year}_{localized.item_id}.tif"
                if args.resume_cache and cached_ndwi.is_file():
                    candidate_extraction = load_cached_ndwi_shoreline(
                        localized,
                        cached_ndwi,
                        reference_line,
                        ndwi_threshold=args.ndwi_threshold,
                    )
                    attempt_status = "candidate_cache_success"
                else:
                    candidate_extraction = extract_ndwi_shoreline(
                        localized,
                        bbox,
                        reference_line,
                        ndwi_threshold=args.ndwi_threshold,
                    )
                    attempt_status = "candidate_success"
                successful.append((localized, candidate_extraction))
                scene_attempts.append({
                    "year": year,
                    "item_id": localized.item_id,
                    "status": attempt_status,
                })
            except Exception as exc:
                attempt = {
                    "year": year,
                    "item_id": candidate.item_id,
                    "status": "failed",
                    "reason": str(exc),
                }
                failed_attempts.append(attempt)
                scene_attempts.append(attempt)

        if not successful:
            blocked.append({
                "year": year,
                "reason": "all_catalogued_scenes_failed",
                "attempts": failed_attempts,
            })
            continue

        scenes_ok = [scene for scene, _ in successful]
        extractions_ok = [extraction for _, extraction in successful]
        if len(successful) >= args.min_scenes_consensus:
            shoreline, water_polygon, consensus_metadata = consensus_shoreline_extractions(
                extractions_ok,
                reference_line,
                min_scenes=args.min_scenes_consensus,
            )
        else:
            shoreline = extractions_ok[0].shoreline_wgs84
            water_polygon = extractions_ok[0].water_polygon_wgs84
            consensus_metadata = {
                "method": "single_scene_fallback",
                "scene_count": 1,
                "min_scenes": args.min_scenes_consensus,
                "reason": "No hubo suficientes escenas válidas para consenso estricto.",
            }
        representative_idx = len(scenes_ok) // 2
        representative_scene = sorted(scenes_ok, key=lambda item: item.acquired_at)[representative_idx]
        scene_ids = [scene.item_id for scene in scenes_ok]
        consensus_item_id = "consensus:" + ",".join(scene_ids)
        for extraction in extractions_ok:
            _write_ndwi(
                extraction,
                args.output / f"ndwi_{year}_{extraction.scene.item_id}.tif",
            )
        water = gpd.GeoDataFrame(
            [{
                "year": year,
                "item_id": consensus_item_id,
                "scene_count": len(scenes_ok),
                "consensus_method": consensus_metadata["method"],
                "geometry": water_polygon,
            }],
            crs="EPSG:4326",
        )
        water.to_file(args.output / f"water_{year}.geojson", driver="GeoJSON")
        common = {
            "year": year,
            "acquired_at": representative_scene.acquired_at,
            "item_id": consensus_item_id,
            "scene_ids": scene_ids,
            "scene_count": len(scenes_ok),
            "consensus_method": consensus_metadata["method"],
            "cloud_cover_pct": representative_scene.cloud_cover_pct,
            "processing_level": representative_scene.processing_level,
            "ndwi_threshold": args.ndwi_threshold,
            "source": "Sentinel-2",
        }
        raw_records.append({**common, "data_status": "raw_ndwi_consensus_waterline", "consensus": consensus_metadata, "geometry": shoreline})
        scene_receipts.extend(
            {
                **scene.to_dict(),
                "extraction": extraction.metadata,
                "consensus": consensus_metadata,
            }
            for scene, extraction in successful
        )

        if tide_ready:
            tide_groups.append({
                "year": year,
                "common": common,
                "consensus_item_id": consensus_item_id,
                "successful": successful,
            })

    if tide_ready and tide_groups:
        flat_scenes = [
            (group, scene, extraction)
            for group in tide_groups
            for scene, extraction in group["successful"]
        ]
        scene_dates = [
            datetime.fromisoformat(scene.acquired_at.replace("Z", "+00:00"))
            for _, scene, _ in flat_scenes
        ]
        try:
            tide_heights = predict_tides_fes2014(
                center.y,
                center.x,
                scene_dates,
                model_dir=model_dir,
            )
            tide_by_item = {
                scene.item_id: (acquired_at, tide_height)
                for (_, scene, _), acquired_at, tide_height in zip(
                    flat_scenes, scene_dates, tide_heights
                )
            }
            for group in tide_groups:
                corrected_lines = []
                scene_corrections = []
                successful = group["successful"]
                for scene, extraction in successful:
                    acquired_at, tide_height = tide_by_item[scene.item_id]
                    corrected_scene, correction = correct_shoreline_to_msl(
                        extraction.shoreline_wgs84,
                        tide_height,
                        args.beach_slope,
                        water_polygon_wgs84=extraction.water_polygon_wgs84,
                        land_reference_wgs84=land_reference,
                        acquired_at=acquired_at,
                    )
                    corrected_lines.append(corrected_scene)
                    scene_corrections.append({
                        "year": group["year"],
                        "item_id": scene.item_id,
                        "scene_count": len(successful),
                        "consensus_group": group["consensus_item_id"],
                        "tide_correction_mode": "per_scene_before_metric_median",
                        "prediction_mode": "single_spatial_interpolation_vectorized_times",
                        "reference_latitude": round(float(center.y), 7),
                        "reference_longitude": round(float(center.x), 7),
                        "horizontal_shift_slope_0_03_m": round(tide_height / 0.03, 3),
                        "horizontal_shift_slope_0_08_m": round(tide_height / 0.08, 3),
                        **correction.to_dict(),
                    })
                corrected = (
                    consensus_shorelines_metric(corrected_lines)
                    if len(corrected_lines) >= args.min_scenes_consensus
                    else corrected_lines[0]
                )
                corrected_records.append({
                    **group["common"],
                    "data_status": "tide_corrected_fes2014_msl_scene_consensus",
                    "tide_correction_mode": (
                        "per_scene_before_metric_median"
                        if len(corrected_lines) >= args.min_scenes_consensus
                        else "single_scene_fallback"
                    ),
                    "geometry": corrected,
                })
                tide_rows.extend(scene_corrections)
        except Exception as exc:
            tide_failures.append({
                "year": "all_requested_years",
                "item_id": "vectorized_fes2014_batch",
                "reason": str(exc),
            })

    if raw_records:
        gpd.GeoDataFrame(raw_records, crs="EPSG:4326").to_file(
            args.output / "shorelines_raw_ndwi.geojson", driver="GeoJSON"
        )
    if corrected_records:
        corrected_gdf = gpd.GeoDataFrame(corrected_records, crs="EPSG:4326")
        corrected_gdf.to_file(args.output / "shorelines_2016_2026_fes2014.geojson", driver="GeoJSON")
        pd.DataFrame(tide_rows).to_csv(args.output / "tide_corrections.csv", index=False)
        if len(corrected_gdf["year"].unique()) >= 2:
            try:
                analysis = analyze_shoreline_change(
                    reference_line,
                    corrected_gdf,
                    spacing_m=50,
                    seaward_m=100,
                    landward_m=300,
                    positive_side="left",
                )
                analysis.transects_wgs84.to_file(
                    args.output / "transects.geojson", driver="GeoJSON"
                )
                analysis.intersections_wgs84.to_file(
                    args.output / "transect_intersections.geojson", driver="GeoJSON"
                )
                analysis.metrics_wgs84.to_file(
                    args.output / "transect_rates.geojson", driver="GeoJSON"
                )
                pd.DataFrame(
                    analysis.intersections.drop(columns=analysis.intersections.geometry.name)
                ).to_csv(args.output / "transect_intersections.csv", index=False)
                analysis.metrics_table.to_csv(args.output / "transect_rates.csv", index=False)
                analysis_result = {
                    "status": "OK",
                    "method": "fixed_transects_NSM_EPR_LRR",
                    "transect_count": int(len(analysis.transects)),
                    "intersection_count": int(analysis.intersections["intersection_found"].sum()),
                    "valid_lrr_count": int(analysis.metrics["lrr_m_per_year"].notna().sum()),
                    "sign_convention": "positive=landward_retreat; negative=seaward_accretion",
                }

                if args.storm_events.is_file():
                    try:
                        acquisition_dates = corrected_gdf[["year", "acquired_at"]].drop_duplicates("year")
                        position_observations = pd.DataFrame(
                            analysis.intersections.drop(columns=analysis.intersections.geometry.name)
                        ).merge(acquisition_dates, on="year", how="left", validate="many_to_one")
                        anomalies = aggregate_position_anomalies(position_observations)
                        events = load_storm_events(args.storm_events)
                        tagged = tag_observations_with_storms(
                            anomalies,
                            events,
                            window_days=args.storm_window_days,
                        )
                        correlation = correlate_storms(tagged)
                        tagged.to_csv(args.output / "storm_scene_join.csv", index=False)
                        event_years = sorted(
                            events.loc[events["affects_cartagena"], "start_date"].dt.year.unique()
                        )
                        missing_event_years = sorted(set(requested_years) - set(event_years))
                        catalog_metadata = (
                            json.loads(args.storm_catalog_metadata.read_text(encoding="utf-8"))
                            if args.storm_catalog_metadata.is_file()
                            else {"catalog_complete": False, "coverage_status": "metadata_missing"}
                        )
                        storm_result = {
                            **correlation,
                            "catalog_path": str(args.storm_events),
                            "catalog_metadata_path": str(args.storm_catalog_metadata),
                            "catalog_scope": catalog_metadata.get(
                                "coverage_status", "partial_verified_official_notices"
                            ),
                            "event_years_with_records": [int(year) for year in event_years],
                            "years_without_verified_records": [
                                int(year) for year in missing_event_years
                            ],
                            "catalog_complete": bool(
                                catalog_metadata.get("catalog_complete", False)
                            ),
                            "decision_status": (
                                "ANALYTICAL_RESULT_READY"
                                if correlation.get("status") == "OK"
                                and catalog_metadata.get("catalog_complete", False)
                                else "EXPLORATORY_NOT_VALID_FOR_DECISIONS"
                            ),
                            "note": (
                                "La correlación se calcula, pero no se considera requisito "
                                "cerrado hasta completar el inventario oficial SHOA/DMC 2016-2026."
                            ),
                        }
                        atomic_write_json(
                            args.output / "storm_correlation.json", storm_result
                        )
                    except Exception as exc:
                        storm_result = {"status": "FAILED", "reason": str(exc)}
                else:
                    storm_result = {
                        "status": "NOT_RUN",
                        "reason": f"No existe el catálogo oficial: {args.storm_events}",
                    }
            except Exception as exc:
                analysis_result = {"status": "FAILED", "reason": str(exc)}

    extracted_years = sorted({record["year"] for record in raw_records})
    corrected_years = sorted({record["year"] for record in corrected_records})
    tide_validation["numeric_prediction_validated"] = bool(corrected_records)
    tide_validation["numeric_prediction_count"] = len(tide_rows)
    tide_validation["corrected_annual_count"] = len(corrected_records)
    tide_validation["prediction_mode"] = "single_spatial_interpolation_vectorized_times"
    series_complete = (
        corrected_years == requested_years
        and requested_years == list(range(2016, 2027))
        and analysis_result.get("status") == "OK"
    )
    storm_complete = (
        storm_result.get("status") == "OK"
        and storm_result.get("catalog_complete") is True
    )
    complete = series_complete and storm_complete
    summary = {
        "schema_version": 1,
        "requested_years": requested_years,
        "extracted_ndwi_years": extracted_years,
        "fes2014_corrected_years": corrected_years,
        "blocked": blocked,
        "tide_failures": tide_failures,
        "tide_model": tide_validation,
        "annual_scene_method": "strict_majority_consensus_with_single_scene_fallback",
        "tide_correction_method": "per_scene_fes2014_then_metric_median_when_consensus_available",
        "max_scenes_per_year": args.max_scenes_per_year,
        "min_scenes_consensus": args.min_scenes_consensus,
        "resume_cache_enabled": bool(args.resume_cache),
        "scene_attempts": scene_attempts,
        "scene_receipts": scene_receipts,
        "change_analysis": analysis_result,
        "storm_correlation": storm_result,
        "removed_previous_outputs": removed_previous_outputs,
        "radiometric_warning": (
            "2016 usa L1C TOA mientras 2017-2026 usa L2A; la incertidumbre "
            "radiométrica debe acompañar la interpretación final."
        ),
        "satellite_tide_change_complete_2016_2026": series_complete,
        "storm_requirement_complete": storm_complete,
        "pipeline_complete_2016_2026": complete,
        "status": "COMPLETE" if complete else "PARTIAL_DO_NOT_USE_FOR_DECISIONS",
    }
    atomic_write_json(args.output / "pipeline_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
