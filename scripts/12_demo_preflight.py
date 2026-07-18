from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _check_port(host: str = "127.0.0.1", port: int = 8501) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    expected_years = set(range(2016, 2027))
    pipeline_path = ROOT / "outputs/multitemporal/pipeline_summary.json"
    fes_path = ROOT / "outputs/fes2014_validation.json"
    infrastructure_path = ROOT / "outputs/infrastructure_risk/summary.json"
    requirements_path = ROOT / "outputs/requirement_status.json"
    app_path = ROOT / "app.py"

    pipeline = _load_json(pipeline_path)
    fes = _load_json(fes_path)
    infrastructure = _load_json(infrastructure_path)
    requirements = _load_json(requirements_path)
    app_source = app_path.read_text(encoding="utf-8") if app_path.is_file() else ""

    map_labels = (
        "Leyenda",
        "Norte",
        "Fuente/autor",
        "CRS/Proyección",
        "Fecha",
        "control_scale=True",
        "cv-map-title",
    )
    checks = [
        {
            "id": "app_source",
            "required_for_demo": True,
            "passed": app_path.is_file(),
            "evidence": "app.py",
        },
        {
            "id": "base_geodata",
            "required_for_demo": True,
            "passed": all(
                (ROOT / path).is_file()
                for path in (
                    "data/playa_grande_shoreline_osm.geojson",
                    "data/elevation_profile_open_meteo.json",
                    "data/provenance_manifest.json",
                )
            ),
            "evidence": "data/playa_grande_shoreline_osm.geojson + DEM + manifiesto",
        },
        {
            "id": "seven_map_elements",
            "required_for_demo": True,
            "passed": all(label in app_source for label in map_labels),
            "evidence": "app.py:add_cartographic_elements",
        },
        {
            "id": "sentinel_ndwi_real",
            "required_for_demo": True,
            "passed": set(pipeline.get("extracted_ndwi_years", [])) == expected_years,
            "evidence": str(pipeline_path.relative_to(ROOT)).replace("\\", "/"),
        },
        {
            "id": "fes_numeric_and_corrected",
            "required_for_demo": True,
            "passed": bool(fes.get("numeric_prediction_validated"))
            and set(pipeline.get("fes2014_corrected_years", [])) == expected_years
            and int(pipeline.get("tide_model", {}).get("numeric_prediction_count", 0)) >= 11,
            "evidence": "outputs/fes2014_validation.json + outputs/multitemporal/tide_corrections.csv",
        },
        {
            "id": "dsas_equivalent_executed",
            "required_for_demo": True,
            "passed": pipeline.get("change_analysis", {}).get("status") == "OK"
            and (ROOT / "outputs/multitemporal/transect_rates.csv").is_file(),
            "evidence": "outputs/multitemporal/transect_rates.csv",
        },
        {
            "id": "infrastructure_screening",
            "required_for_demo": True,
            "passed": infrastructure.get("decision_status")
            == "SCREENING_REQUIRES_FIELD_VALIDATION",
            "evidence": str(infrastructure_path.relative_to(ROOT)).replace("\\", "/"),
        },
        {
            "id": "semaphore_connected_to_pipeline",
            "required_for_demo": True,
            "passed": all(
                (ROOT / path).is_file()
                for path in (
                    "src/coastvision/scientific.py",
                    "outputs/infrastructure_risk/buildings_risk.geojson",
                    "outputs/infrastructure_risk/roads_risk.geojson",
                )
            )
            and "scientific_bundle = load_scientific_bundle()" in app_source
            and "assessment = assess_nearest_infrastructure(" in app_source
            and "scientific_pipeline_ready(" in app_source,
            "evidence": "app.py + src/coastvision/scientific.py + outputs/infrastructure_risk/*.geojson",
        },
        {
            "id": "storm_correlation_executed",
            "required_for_demo": True,
            "passed": pipeline.get("storm_correlation", {}).get("status") == "OK"
            and (ROOT / "outputs/multitemporal/storm_correlation.json").is_file(),
            "evidence": "outputs/multitemporal/storm_correlation.json",
            "note": (
                "La correlación exigida está ejecutada; su interpretación sigue exploratoria hasta "
                "certificar la cobertura completa del catálogo oficial SHOA/DMC."
            ),
        },
        {
            "id": "streamlit_port_8501",
            "required_for_demo": False,
            "passed": _check_port(),
            "evidence": "tcp://127.0.0.1:8501",
            "note": "Si falla, iniciar con python scripts/run_mvp.py.",
        },
    ]

    demo_ready = all(
        item["passed"] for item in checks if item["required_for_demo"]
    )
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "demo_ready": demo_ready,
        "scientific_requirements_complete": bool(requirements.get("strict_completion")),
        "passed_checks": sum(bool(item["passed"]) for item in checks),
        "total_checks": len(checks),
        "checks": checks,
        "interpretation": (
            "DEMO_READY_WITH_EXPLICIT_SCIENTIFIC_LIMITATIONS"
            if demo_ready and not requirements.get("strict_completion")
            else "FULLY_COMPLETE"
            if demo_ready
            else "DEMO_NOT_READY"
        ),
    }
    output = ROOT / "outputs/demo_preflight.json"
    _write_json(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not demo_ready:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
