from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.acquisition import atomic_write_json  # noqa: E402
from coastvision.tides import predict_tide_fes2014, validate_fes2014_directory  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida el modelo externo FES2014b.")
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument(
        "--predict",
        action="store_true",
        help="Además ejecuta una predicción real; la primera carga puede tardar varios minutos.",
    )
    return parser.parse_args()


def main() -> None:
    args = arguments()
    model_dir = args.model_dir or os.environ.get("TIDE_MODEL_DIR")
    try:
        result = validate_fes2014_directory(model_dir)
    except Exception as exc:
        result = {
            "model": "FES2014b ocean_tide",
            "valid": False,
            "validation_scope": "constituent_filenames_and_hdf5_headers",
            "numeric_prediction_validated": False,
            "error": str(exc),
        }
    # El recibo se versiona: conserva la evidencia técnica, pero no una ruta
    # personal que dejaría el artefacto atado a este equipo.
    if "ocean_tide_directory" in result:
        result["ocean_tide_directory"] = "${TIDE_MODEL_DIR}/fes2014/ocean_tide"
    result["model_location_policy"] = "external_unversioned_via_TIDE_MODEL_DIR"
    prediction_failed = False
    if args.predict and result["valid"]:
        acquired_at = datetime(2017, 3, 30, 14, 51, 21, tzinfo=timezone.utc)
        try:
            tide_height = predict_tide_fes2014(
                -33.508, -71.616, acquired_at, model_dir=model_dir
            )
            result["sample_prediction"] = {
                "latitude": -33.508,
                "longitude": -71.616,
                "acquired_at_utc": acquired_at.isoformat(),
                "tide_height_m": tide_height,
            }
            result["numeric_prediction_validated"] = True
            result["prediction_status"] = "validated"
        except Exception as exc:
            prediction_failed = True
            result["numeric_prediction_validated"] = False
            result["prediction_status"] = "failed"
            result["prediction_error"] = str(exc)
    output = ROOT / "outputs/fes2014_validation.json"
    atomic_write_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["valid"]:
        raise SystemExit(2)
    if prediction_failed:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
