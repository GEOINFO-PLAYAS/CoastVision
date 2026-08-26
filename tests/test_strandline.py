from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coastvision.strandline import prepare_inputs, run_strandline


def _write_geojson(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "transect_id": "T001",
                    "chainage_m": 0,
                    "baseline_x": 500000,
                    "baseline_y": 6300000,
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-70.0, -33.0], [-70.0, -32.99]],
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_shorelines(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"year": 2020, "acquired_at": "2020-02-01T00:00:00Z"},
                "geometry": {"type": "LineString", "coordinates": [[-70.01, -33.0], [-70.01, -32.99]]},
            },
            {
                "type": "Feature",
                "properties": {"year": 2021, "acquired_at": "2021-02-01T00:00:00Z"},
                "geometry": {"type": "LineString", "coordinates": [[-70.011, -33.0], [-70.011, -32.99]]},
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_fake_engine(path: Path) -> None:
    path.write_text(
        """import csv, pathlib, sys
args = sys.argv[1:]
if args == ['--version']:
    print('strandline 0.1.0-test')
    raise SystemExit(0)
def value(flag):
    return pathlib.Path(args[args.index(flag) + 1])
if 'intersect' in args:
    out = value('--output')
    out.write_text('transect,shoreline_id,chainage_m\\nT001,Y2020,10\\nT001,Y2021,9\\n')
elif 'rates' in args:
    out = value('--output')
    out.write_text('transect,n_valid,years,NSM_m,SCE_m,EPR_m_yr,LRR_m_yr,LRR_r2,LRR_ci95,WLR_m_yr,WLR_ci95\\nT001,2,1,1,1,1,1,0.5,0.2,1,0.2\\n')
else:
    raise SystemExit(2)
""",
        encoding="utf-8",
    )


def test_prepare_inputs_converts_orientation_and_dates(tmp_path: Path) -> None:
    transects = tmp_path / "transects.geojson"
    shorelines = tmp_path / "shorelines.geojson"
    _write_geojson(transects)
    _write_shorelines(shorelines)
    result = prepare_inputs(transects, shorelines, tmp_path / "inputs")
    assert result["metadata"]["transect_count"] == 1
    assert result["metadata"]["shoreline_count"] == 2
    assert "2020-02-01" in Path(result["dates_csv"]).read_text(encoding="utf-8")
    assert "origin_e" in Path(result["transects_csv"]).read_text(encoding="utf-8")


def test_run_strandline_normalises_output_and_records_comparison(tmp_path: Path) -> None:
    transects = tmp_path / "transects.geojson"
    shorelines = tmp_path / "shorelines.geojson"
    native = tmp_path / "native.csv"
    fake = tmp_path / "fake_engine.py"
    _write_geojson(transects)
    _write_shorelines(shorelines)
    _write_fake_engine(fake)
    native.write_text("transect_id,lrr_m_per_year\nT001,-1.1\n", encoding="utf-8")
    result = run_strandline(
        binary=[sys.executable, fake],
        transects_geojson=transects,
        shorelines_geojson=shorelines,
        output_dir=tmp_path / "run",
        native_rates_csv=native,
    )
    assert result.status == "OK"
    assert result.intersection_count == 2
    assert result.rate_count == 1
    assert result.comparison["status"] == "OK"
    rows = Path(result.rates_coastvision).read_text(encoding="utf-8")
    assert "lrr_m_per_year" in rows
    assert "-1.000000" in rows
    manifest = json.loads(Path(result.manifest).read_text(encoding="utf-8"))
    assert manifest["engine"] == "strandline"
    assert manifest["contract"]["crs"] == "EPSG:32719"
