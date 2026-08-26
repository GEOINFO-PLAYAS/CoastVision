"""Ejecuta la integración strandline sobre outputs ya construidos."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.strandline import run_strandline  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Integra strandline al pipeline de CoastVision.")
    parser.add_argument("--strandline-bin", default=os.environ.get("STRANDLINE_BIN"))
    parser.add_argument("--site", default="cartagena")
    parser.add_argument("--transects", type=Path, default=None)
    parser.add_argument("--shorelines", type=Path, default=None)
    parser.add_argument("--native-rates", type=Path, default=None)
    parser.add_argument("--along-dist", type=float, default=25.0)
    parser.add_argument("--min-valid", type=int, default=3)
    args = parser.parse_args()
    if not args.strandline_bin:
        parser.error("indica --strandline-bin o define STRANDLINE_BIN")
    if args.site == "cartagena":
        base = ROOT / "outputs" / "multitemporal"
    else:
        base = ROOT / "outputs" / args.site / "multitemporal"
    transects = args.transects or base / "transects.geojson"
    shorelines = args.shorelines or base / "shorelines_2016_2026_fes2014.geojson"
    native_rates = args.native_rates or base / "transect_rates.csv"
    for path in (transects, shorelines):
        if not path.is_file():
            raise FileNotFoundError(f"Falta el output requerido: {path}")
    result = run_strandline(
        binary=args.strandline_bin,
        transects_geojson=transects,
        shorelines_geojson=shorelines,
        output_dir=base / "strandline",
        native_rates_csv=native_rates if native_rates.is_file() else None,
        along_dist_m=args.along_dist,
        min_valid=args.min_valid,
    )
    print(result.to_dict())


if __name__ == "__main__":
    main()
