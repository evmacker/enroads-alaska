"""The app must run end to end and stay free of business logic."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def run(overrides=None):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    for index, value in (overrides or {}).items():
        at.slider[index].set_value(value)
    if overrides:
        at.run()
        assert not at.exception, at.exception
    return at


def test_app_renders_with_defaults():
    at = run()
    assert len(at.slider) == 14 and len(at.selectbox) == 1   # 15 scenario controls
    assert any("Alaska Airlines decarbonization pathway" in m.value for m in at.markdown)


def test_headline_reflects_the_scenario():
    at = run()
    headline = " ".join(m.value for m in at.markdown)
    assert "14.7%" in headline          # default 2030 reduction
    assert "Exceeds upper target" in headline


def test_moving_a_slider_changes_the_headline():
    """Dropping 2030 SAF to zero must flip the 2030 outcome to 'below'."""
    at = run({0: 0.0})
    assert "Below target" in " ".join(m.value for m in at.markdown)


def test_all_tabs_and_charts_render():
    at = run()
    assert len(at.tabs) == 5          # SAF, carbon, pathway, table, notes
    assert len(at.dataframe) == 1


def test_kpi_grid_shows_both_milestone_years():
    """Twelve tiles: six figures for 2030 and the same six for 2040."""
    body = " ".join(m.value for m in run().markdown)
    assert body.count("Carbon emissions needing offset") == 2
    assert body.count("Total cost to invest in SAF") == 2
    assert body.count("Share of revenue to offsets") == 2
    assert "2030 intensity reduction" in body and "2040 intensity reduction" in body


@pytest.mark.parametrize("index, value", [(0, 50.0), (1, 100.0), (7, 500.0), (9, 10.0), (10, 3.0)])
def test_extreme_slider_positions_do_not_break_the_app(index, value):
    run({index: value})


def test_app_holds_no_business_logic():
    """Guard the 'no business logic in Streamlit' rule: the app runs the model once and draws it."""
    source = Path(APP).read_text()
    assert source.count("run_scenario(") == 1
    for banned in ("import pandas", "import numpy", "ScenarioResult("):
        assert banned not in source
