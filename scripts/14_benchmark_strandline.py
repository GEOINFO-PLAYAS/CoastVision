"""Benchmark reproducible: análisis nativo de CoastVision versus strandline."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.change_analysis import analyze_shoreline_change  # noqa: E402
from coastvision.geometry import get_site_paths  # noqa: E402
from coastvision.strandline import run_strandline  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara tiempos de CoastVision y strandline.")
    parser.add_argument("--strandline-bin", default=os.environ.get("STRANDLINE_BIN"))
    parser.add_argument("--site", default="cartagena")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--along-dist", type=float, default=25.0)
    parser.add_argument("--min-valid", type=int, default=3)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if not args.strandline_bin:
        parser.error("indica --strandline-bin o define STRANDLINE_BIN")
    if args.runs < 1:
        parser.error("--runs debe ser al menos 1")
    if args.site == "cartagena":
        base = ROOT / "outputs" / "multitemporal"
    else:
        base = ROOT / "outputs" / args.site / "multitemporal"
    shoreline_path, _, _ = get_site_paths(args.site)
    shorelines_path = base / "shorelines_2016_2026_fes2014.geojson"
    transects_path = base / "transects.geojson"
    shorelines = gpd.read_file(shorelines_path)
    reference = gpd.read_file(shoreline_path).geometry.iloc[0]
    native_times: list[float] = []
    rust_times: list[float] = []
    last_result = None
    for _ in range(args.runs):
        started = time.perf_counter()
        analyze_shoreline_change(
            reference,
            shorelines,
            spacing_m=50,
            seaward_m=100,
            landward_m=300,
            positive_side="left",
        )
        native_times.append(time.perf_counter() - started)
        with tempfile.TemporaryDirectory(prefix="coastvision-strandline-") as temp:
            started = time.perf_counter()
            last_result = run_strandline(
                binary=args.strandline_bin,
                transects_geojson=transects_path,
                shorelines_geojson=shorelines_path,
                output_dir=Path(temp),
                native_rates_csv=base / "transect_rates.csv",
                along_dist_m=args.along_dist,
                min_valid=args.min_valid,
            )
            rust_times.append(time.perf_counter() - started)
    output = args.output or base / "strandline" / "benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "site": args.site,
        "runs": args.runs,
        "same_inputs": {
            "transects": str(transects_path),
            "shorelines": str(shorelines_path),
        },
        "python_coastvision_seconds": native_times,
        "strandline_end_to_end_seconds": rust_times,
        "python_median_seconds": sorted(native_times)[len(native_times) // 2],
        "strandline_median_seconds": sorted(rust_times)[len(rust_times) // 2],
        "strandline_result": last_result.to_dict() if last_result else None,
        "note": "Los tiempos incluyen conversión de formatos en el adaptador Rust.",
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
