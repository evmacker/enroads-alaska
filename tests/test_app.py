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
        at.button_group[0].set_value(["custom"])
        at.run()
        assert not at.exception, at.exception
    return at


def test_app_renders_with_defaults():
    at = run()
    assert len(at.slider) == 15 and len(at.selectbox) == 0   # 15 visible scenario controls
    # visible:false inputs render no widget at all; the engine still gets their config default.
    labels = [w.label for w in list(at.slider) + list(at.selectbox)]
    assert "Investable cash (% revenue)" not in labels  # hidden: no KPI on the page uses it
    assert not any("supply case" in x for x in labels)
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


def _strategy_caption(at):
    """The one caption that names the selected strategy and quotes its note."""
    return [c.value for c in at.caption if c.value.startswith("**")][0]


def test_strategy_toggle_switches_the_blue_line():
    """Each button swaps the whole page — tiles, both charts and captions — to a strategy."""
    at = run()
    seen = {}
    for key in ("conservative", "all_in", "custom"):
        at.button_group[0].set_value([key])        # re-fetch the node on every pass
        at.run()
        assert not at.exception, at.exception
        seen[key] = _strategy_caption(at)
    assert "Conservative" in seen["conservative"]
    assert "All-In" in seen["all_in"]
    assert "Custom" in seen["custom"]
    assert len(set(seen.values())) == 3


def test_presets_say_that_moving_a_lever_switches_to_custom():
    at = run()
    at.button_group[0].set_value(["all_in"])
    at.run()
    assert "switches to Custom" in _strategy_caption(at)
    at.button_group[0].set_value(["custom"])
    at.run()
    assert "switches to Custom" not in _strategy_caption(at)


def test_toggle_defaults_to_custom():
    """Opening the page must still land on the workbook defaults the sidebar shows."""
    assert "Custom" in _strategy_caption(run())


def test_switching_strategy_changes_the_kpi_tiles():
    """The figures under each milestone year follow the toggle, not the sliders."""
    at = run()
    at.button_group[0].set_value(["conservative"])
    at.run()
    cons = " ".join(m.value for m in at.markdown)
    at.button_group[0].set_value(["all_in"])
    at.run()
    assert cons != " ".join(m.value for m in at.markdown)


def _levers(at):
    return {w.label: w.value for w in at.slider}


def test_picking_a_preset_fills_the_sidebar_with_its_own_values():
    at = run()
    assert _levers(at)["SAF share 2040"] == 60.0          # workbook default on open
    at.button_group[0].set_value(["all_in"])
    at.run()
    levers = _levers(at)
    assert levers["SAF share 2040"] == 90.0
    assert levers["Catalytic capital (% revenue)"] == 2.0
    assert levers["Partner-funded share of premium"] == 20.0


def test_conservative_fills_in_the_saf_share_it_solved_for():
    """Its 2030 share is derived, not chosen, and the sidebar shows the derived number."""
    at = run()
    at.button_group[0].set_value(["conservative"])
    at.run()
    levers = _levers(at)
    assert levers["SAF share 2030"] == pytest.approx(3.68, abs=0.01)
    assert levers["Catalytic capital (% revenue)"] == 0.0


def test_moving_a_lever_leaves_the_preset_and_runs_the_moved_value():
    """The callback that does this cannot be driven here — AppTest cannot re-read a
    single-select button group — so the state it leaves behind is restated instead."""
    at = run()
    at.button_group[0].set_value(["all_in"])
    at.run()
    at.button_group[0].set_value(["custom"])       # what _lever_touched sets
    at.slider[1].set_value(35.0)                   # SAF share 2040
    at.run()
    assert not at.exception, at.exception
    assert "Custom" in _strategy_caption(at)
    assert _levers(at)["SAF share 2040"] == 35.0


def test_the_lever_callback_is_wired_to_every_slider():
    """Guards the wiring the test above has to stub out."""
    source = Path(APP).read_text()
    assert source.count("on_change=_lever_touched") == 2      # pct and usd branches
    assert 'st.session_state.scenario = "custom"' in source


def test_the_tonnage_tile_can_contradict_the_intensity_tile():
    """Conservative meets its target in green while emitting more than 2025. Say so."""
    at = run()
    at.button_group[0].set_value(["conservative"])
    at.run()
    body = " ".join(m.value for m in at.markdown)
    assert "Meets target" in body                      # intensity verdict: green
    assert "+5.7% vs 2025" in body                     # tonnage sub-line: up
    assert any("growth outruns efficiency" in c.value for c in at.caption)


def test_no_contradiction_caption_when_a_pathway_really_is_decarbonising():
    """It must not nag All-In, whose tonnes actually fall."""
    at = run()
    at.button_group[0].set_value(["all_in"])
    at.run()
    assert not any("growth outruns efficiency" in c.value for c in at.caption)


def test_cost_per_tonne_abated_is_on_the_page():
    """The one metric no framing choice can move."""
    assert any("per tonne actually abated" in c.value for c in run().caption)


def test_chart_reveal_is_keyed_to_the_selected_strategy():
    """The keyframe name carries the strategy key — that is what replays the sweep."""
    at = run()
    assert "unfurl-custom" in " ".join(m.value for m in at.markdown if "@keyframes" in m.value)
    at.button_group[0].set_value(["all_in"])
    at.run()
    assert "unfurl-all_in" in " ".join(m.value for m in at.markdown if "@keyframes" in m.value)


def test_app_holds_no_business_logic():
    """Guard the 'no business logic in Streamlit' rule: the app runs the model once and draws it."""
    source = Path(APP).read_text()
    assert source.count("run_scenario(") == 1
    for banned in ("import pandas", "import numpy", "ScenarioResult("):
        assert banned not in source
