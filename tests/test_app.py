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
        # AppTest cannot re-read a single-select button group: its `indices` property
        # iterates the widget value, which comes back as a bare string after a run. Only
        # the harness is affected, not the app, so restate the default before rerunning.
        at.button_group[0].set_value(["bau"])
        at.run()
        assert not at.exception, at.exception
    return at


def test_app_renders_with_defaults():
    at = run()
    assert len(at.slider) == 14 and len(at.selectbox) == 0   # 14 visible scenario controls
    # visible:false inputs render no widget at all; the engine still gets their config default.
    labels = [w.label for w in list(at.slider) + list(at.selectbox)]
    assert not any("Investable cash" in x or "supply case" in x for x in labels)
    assert "Carbon planning price ($/t)" in labels
    assert len(at.button_group) == 1 and len(at.button_group[0].options) == 3
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
    assert len(at.tabs) == 6          # SAF, carbon, cost/tonne, pathway, table, notes
    assert len(at.dataframe) == 1


def test_kpi_grid_shows_both_milestone_years():
    """Twelve tiles: six figures for 2030 and the same six for 2040."""
    body = " ".join(m.value for m in run().markdown)
    assert body.count("Carbon emissions needing offset") == 2
    assert body.count("Total cost to invest in SAF") == 2
    assert body.count("Share of revenue to offsets") == 2
    assert "2030 intensity reduction" in body and "2040 intensity reduction" in body


@pytest.mark.parametrize("index, value", [(0, 50.0), (1, 100.0), (7, 5.0), (8, 3.0), (11, 500.0)])
def test_extreme_slider_positions_do_not_break_the_app(index, value):
    run({index: value})


def _reference_caption(at):
    return [c.value for c in at.caption if "by 2030 and" in c.value][0]


def test_reference_toggle_switches_the_comparison_line():
    """Each of the three buttons redraws the chart against a different fixed pathway."""
    at = run()
    seen = {}
    for key in ("bau", "conservative", "all_in"):
        at.button_group[0].set_value([key])        # re-fetch the node on every pass
        at.run()
        assert not at.exception, at.exception
        seen[key] = _reference_caption(at)
    assert "Business as usual" in seen["bau"]
    assert "Conservative" in seen["conservative"]
    assert "All-In" in seen["all_in"]
    assert len(set(seen.values())) == 3


def test_toggle_defaults_to_business_as_usual():
    """Opening the page must look exactly like it did before the toggle existed."""
    assert "Business as usual" in _reference_caption(run())


def test_chart_reveal_is_keyed_to_the_selected_reference():
    """The keyframe name carries the reference key — that is what replays the sweep."""
    at = run()
    assert "unfurl-bau" in " ".join(m.value for m in at.markdown if "@keyframes" in m.value)
    at.button_group[0].set_value(["all_in"])
    at.run()
    assert "unfurl-all_in" in " ".join(m.value for m in at.markdown if "@keyframes" in m.value)


def test_app_holds_no_business_logic():
    """Guard the 'no business logic in Streamlit' rule: the app runs the model once and draws it."""
    source = Path(APP).read_text()
    assert source.count("run_scenario(") == 1
    for banned in ("import pandas", "import numpy", "ScenarioResult("):
        assert banned not in source
