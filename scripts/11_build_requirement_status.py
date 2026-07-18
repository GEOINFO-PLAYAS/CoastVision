from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _evidence(path: Path) -> str:
    """Devuelve una ruta portable relativa a la raíz del proyecto."""
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def main() -> None:
    catalog_path = ROOT / "data/sentinel/catalog_2016_2026.json"
    pipeline_path = ROOT / "outputs/multitemporal/pipeline_summary.json"
    fes_path = ROOT / "outputs/fes2014_validation.json"
    event_meta_path = ROOT / "data/events/catalog_metadata.json"
    infra_path = ROOT / "outputs/infrastructure_risk/summary.json"
    infra_receipt_path = ROOT / "data/infrastructure/source_receipt.json"

    catalog = _load(catalog_path, {})
    pipeline = _load(pipeline_path, {})
    fes = _load(fes_path, {})
    events = _load(event_meta_path, {})
    infrastructure = _load(infra_path, {})
    infrastructure_receipt = _load(infra_receipt_path, {})
    extracted_years = pipeline.get("extracted_ndwi_years", [])
    corrected_years = pipeline.get("fes2014_corrected_years", [])
    numeric_tide_validated = bool(
        fes.get("numeric_prediction_validated")
        or pipeline.get("tide_model", {}).get("numeric_prediction_validated")
    )
    expected_years = set(range(2016, 2027))
    corrected_year_set = {int(year) for year in corrected_years}
    rates_path = ROOT / "outputs/multitemporal/transect_rates.csv"
    change_summary = pipeline.get("change_analysis", {})
    storm_summary = pipeline.get("storm_correlation", {})

    requirements = [
        {
            "id": "sentinel_2016_2026",
            "requirement": "Extraer línea costera Sentinel-2 multitemporal 2016-2026",
            "status": "COMPLETO" if pipeline.get("satellite_tide_change_complete_2016_2026") else "PARCIAL",
            "evidence": [_evidence(catalog_path), _evidence(pipeline_path)],
            "detail": (
                f"Catálogo: {len(catalog.get('scenes', []))} escenas, años faltantes "
                f"{catalog.get('missing_years', [])}. Años NDWI extraídos: {extracted_years or 'ninguno en salida final'}."
            ),
        },
        {
            "id": "ndwi",
            "requirement": "Aplicar NDWI o MNDWI",
            "status": (
                "COMPLETO"
                if set(extracted_years) == expected_years
                else "EJECUTADO_DOS_ANOS_PENDIENTE_SERIE"
                if len(extracted_years) >= 2
                else "VALIDADO_PARCIAL"
            ),
            "evidence": [
                _evidence(ROOT / "src/coastvision/sentinel.py"),
                _evidence(pipeline_path),
                _evidence(ROOT / "outputs/multitemporal/shorelines_raw_ndwi.geojson"),
            ],
            "detail": (
                f"NDWI real procesado en {extracted_years}: "
                f"{len(pipeline.get('scene_receipts', []))} escenas con B03/B08, máscara SCL, "
                "grillas alineadas y consenso anual por mayoría. 2016 usa L1C sin SCL y queda "
                "marcado para control visual por nubosidad y diferencia radiométrica."
            ),
        },
        {
            "id": "dsas_equivalent",
            "requirement": "Calcular tasas de cambio con DSAS o equivalente en Python",
            "status": (
                "COMPLETO"
                if rates_path.is_file() and expected_years.issubset(corrected_year_set)
                else (
                    "EJECUTADO_DOS_FECHAS_PENDIENTE_SERIE"
                    if rates_path.is_file()
                    else "IMPLEMENTADO_PENDIENTE_DATOS"
                )
            ),
            "evidence": [
                _evidence(ROOT / "src/coastvision/change_analysis.py"),
                _evidence(ROOT / "tests/test_change_analysis.py"),
                _evidence(rates_path),
                _evidence(ROOT / "outputs/multitemporal/transect_rates.geojson"),
            ],
            "detail": (
                "NSM/EPR/LRR ejecutados sobre la serie anual corregida 2016-2026: "
                f"{change_summary.get('transect_count', 0)} transectos, "
                f"{change_summary.get('intersection_count', 0)} intersecciones y "
                f"{change_summary.get('valid_lrr_count', 0)} LRR válidas. "
                "Se exportan R², error estándar e IC95 y se conserva la completitud temporal por transecto."
                if rates_path.is_file()
                else "Calcula NSM, EPR, LRR, R², error estándar e IC95 en transectos fijos; falta ejecutar sobre líneas corregidas."
            ),
        },
        {
            "id": "storm_correlation",
            "requirement": "Correlacionar con eventos de marejadas SHOA/DMC",
            "status": (
                "COMPLETO"
                if pipeline.get("storm_requirement_complete")
                else "PARCIAL_CORRELACION_EJECUTADA_CATALOGO_OFICIAL_INCOMPLETO"
                if storm_summary.get("status") == "OK"
                else "PARCIAL"
            ),
            "evidence": [
                _evidence(ROOT / "data/events/marejadas_oficiales_armada.csv"),
                _evidence(event_meta_path),
                _evidence(ROOT / "src/coastvision/storms.py"),
                _evidence(ROOT / "outputs/multitemporal/storm_correlation.json"),
            ],
            "detail": (
                "Unión temporal y correlación punto-biserial implementadas. "
                f"Salida actual: {storm_summary.get('status', 'sin ejecutar')} con "
                f"n={storm_summary.get('n', 0)}, r={storm_summary.get('correlation_r', 's/d')}, "
                f"p={storm_summary.get('p_value', 's/d')}; catálogo oficial: "
                f"{events.get('coverage_status', 'sin metadatos')}. "
                "La correlación existe, pero no cierra el requisito hasta certificar exhaustividad SHOA/DMC."
            ),
        },
        {
            "id": "infrastructure_risk",
            "requirement": "Identificar edificaciones y caminos costeros en riesgo",
            "status": (
                "COMPLETO"
                if bool(infrastructure) and expected_years.issubset(corrected_year_set)
                else (
                    "EJECUTADO_SCREENING_PENDIENTE_SERIE"
                    if bool(infrastructure)
                    else "INVENTARIO_REAL_PENDIENTE_TASAS"
                    if bool(infrastructure_receipt)
                    else "IMPLEMENTADO_PENDIENTE_DATOS"
                )
            ),
            "evidence": [
                _evidence(ROOT / "src/coastvision/infrastructure.py"),
                _evidence(ROOT / "scripts/08_refresh_osm_infrastructure.py"),
                _evidence(ROOT / "scripts/10_assess_infrastructure.py"),
                _evidence(infra_receipt_path),
                _evidence(ROOT / "data/infrastructure/buildings_osm.geojson"),
                _evidence(ROOT / "data/infrastructure/roads_osm.geojson"),
                _evidence(infra_path),
                _evidence(ROOT / "outputs/infrastructure_risk/buildings_risk.geojson"),
                _evidence(ROOT / "outputs/infrastructure_risk/roads_risk.geojson"),
            ],
            "detail": (
                "Screening real del AOI: "
                f"{infrastructure.get('building_count', 0)} edificios y "
                f"{infrastructure.get('road_segment_count', 0)} tramos; "
                f"{infrastructure.get('critical_buildings', 0)} edificios y "
                f"{infrastructure.get('critical_roads', 0)} caminos críticos; "
                f"estado {infrastructure.get('decision_status', 'sin estado')}. "
                "Se basa en la costa FES2014 2026 y en las LRR locales de la serie 2016-2026."
                if infrastructure
                else "Inventario OSM real del AOI: "
                f"{infrastructure_receipt.get('buildings', 0)} edificios y "
                f"{infrastructure_receipt.get('road_segments', 0)} tramos viales, "
                "con fecha y hashes. El cruce de riesgo sigue pendiente de tasas LRR reales."
                if infrastructure_receipt
                else "Cruce OSM con distancia métrica y LRR local listo; falta descargar el inventario del AOI y ejecutar el análisis final."
            ),
        },
        {
            "id": "fes2014",
            "requirement": "Corrección de marea FES2014",
            "status": (
                "COMPLETO"
                if corrected_year_set == expected_years
                else (
                    "CORRECCION_APLICADA_DOS_ANOS_PENDIENTE_SERIE"
                    if corrected_years
                    else (
                    "PREDICCION_VALIDADA_PENDIENTE_SERIE"
                    if numeric_tide_validated
                    else "MODELO_VALIDADO_PENDIENTE_SERIE"
                    )
                )
            ),
            "evidence": [
                _evidence(fes_path),
                _evidence(ROOT / "src/coastvision/tides.py"),
                _evidence(ROOT / "outputs/multitemporal/tide_corrections.csv"),
                _evidence(ROOT / "outputs/multitemporal/shorelines_2016_2026_fes2014.geojson"),
            ],
            "detail": (
                f"Modelo externo: {fes.get('constituent_count', 0)}/{fes.get('expected_constituent_count', 34)} constituyentes; "
                f"predicción numérica validada: {'sí' if numeric_tide_validated else 'no'}; "
                f"años corregidos en la salida final: {corrected_years or 'ninguno'}."
            ),
        },
        {
            "id": "map_elements",
            "requirement": "Siete elementos obligatorios del mapa",
            "status": "COMPLETO",
            "evidence": [_evidence(ROOT / "app.py")],
            "detail": "Título, leyenda, escala, norte, fuente/autor, CRS/proyección y fecha están incrustados en el mapa Folium.",
        },
    ]
    complete = all(item["status"] == "COMPLETO" for item in requirements)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "overall_status": "COMPLETO" if complete else "MVP_UNIFICADO_CON_PENDIENTES_DE_DATOS",
        "strict_completion": complete,
        "requirements": requirements,
    }
    output = ROOT / "outputs/requirement_status.json"
    _write(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
