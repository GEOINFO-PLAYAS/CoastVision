from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from coastvision.acquisition import MANIFEST_PATH, sha256_file  # noqa: E402
from coastvision.geometry import DEFAULT_RETREAT_RATE, build_demo_layers  # noqa: E402


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta un escenario verificable de CoastVision.")
    parser.add_argument("--year", type=int, default=2035, choices=range(2026, 2041))
    parser.add_argument("--retreat-rate", type=float, default=DEFAULT_RETREAT_RATE)
    return parser.parse_args()


def main() -> None:
    arguments = _arguments()
    if not 0.0 <= arguments.retreat_rate <= 10.0:
        raise ValueError("La tasa de retroceso debe estar entre 0 y 10 m/año.")
    output_dir = PROJECT_ROOT / "outputs" / "coastvision_mvp"
    output_dir.mkdir(parents=True, exist_ok=True)
    layers = build_demo_layers(
        year=arguments.year,
        retreat_rate=arguments.retreat_rate,
    )

    layers["shorelines"].to_file(output_dir / "lineas_costa.geojson", driver="GeoJSON")
    layers["risk_bands"].to_file(output_dir / "franjas_riesgo.geojson", driver="GeoJSON")
    layers["impact_zone"].to_file(output_dir / "zona_alcanzada.geojson", driver="GeoJSON")
    layers["risk_boundaries"].to_file(
        output_dir / "limites_comparacion.geojson",
        driver="GeoJSON",
    )
    layers["buildings"].to_file(output_dir / "predios_demo.geojson", driver="GeoJSON")
    layers["study_area"].to_file(output_dir / "area_estudio.geojson", driver="GeoJSON")
    layers["stations"].to_file(output_dir / "estaciones_medicion.geojson", driver="GeoJSON")
    layers["transects"].to_file(output_dir / "transectos.geojson", driver="GeoJSON")
    layers["elevation_samples"].to_file(
        output_dir / "muestras_elevacion.geojson",
        driver="GeoJSON",
    )
    layers["elevation_profile"].to_csv(output_dir / "perfil_elevacion.csv", index=False)
    provenance = layers.get("provenance", {})
    (output_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    source_hashes = {
        item["path"]: item["sha256"] for item in provenance.get("active_inputs", [])
    }
    summary = {
        "schema_version": 1,
        "pipeline_version": "coastvision-mvp-1.1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "scenario_year": layers["year"],
        "retreat_rate_m_year": layers["retreat_rate"],
        "accumulated_retreat_m": layers["retreat_m"],
        "metric_crs": "EPSG:32719",
        "map_crs": "EPSG:4326",
        "area_metrics": layers["area_metrics"],
        "coverage": layers["coverage"],
        "building_counts": layers["counts"],
        "source_bundle_id": provenance.get("bundle_id"),
        "source_hashes": source_hashes,
        "provenance_file": "provenance.json",
        "provenance_manifest_sha256": (
            sha256_file(MANIFEST_PATH) if MANIFEST_PATH.exists() else None
        ),
        "status": "DEMO_DATA_NOT_FOR_OPERATIONAL_DECISIONS",
    }
    (output_dir / "resumen.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
