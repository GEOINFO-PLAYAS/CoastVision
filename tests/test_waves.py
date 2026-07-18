from pathlib import Path

from coastvision.waves import load_era5_wave_catalog, summarize_wave_catalog


def test_load_and_summarize_era5_catalog():
    events = load_era5_wave_catalog(
        Path(__file__).parents[1] / "data" / "events" / "oleaje_era5_cartagena.json"
    )
    summary = summarize_wave_catalog(events)
    assert summary["count"] == 6
    assert summary["max_date"] == "2017-03-10"
    assert summary["max_m"] == 2.558


def test_empty_wave_catalog_is_explicit():
    assert summarize_wave_catalog([]) == {
        "count": 0,
        "max_m": None,
        "mean_m": None,
        "max_date": None,
    }
