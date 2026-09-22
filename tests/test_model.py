"""Sensitivity and invariant tests for logic that has no Excel counterpart."""
import dataclasses

import pytest

from model import (bau_reference, load_data, default_inputs, preset_inputs,
                   preset_scenarios, run_scenario)
from model import saf as saf_mod
from model.targets import classify_2030


@pytest.fixture(scope="module")
def data():
    return load_data()


def scenario(data, **overrides):
    return run_scenario(dataclasses.replace(default_inputs(data), **overrides), data)


# --- 2030 band classification -------------------------------------------------

@pytest.mark.parametrize("reduction, state", [
    (0.05, "below"), (0.0999, "below"), (0.10, "meets"), (0.14, "meets"), (0.20, "exceeds"),
    (0.09999999999999998, "meets"),   # solved-for floor, a float hair under
    (0.14000000000000001, "meets"),   # and the same at the top edge
])
def test_band_states(reduction, state):
    assert classify_2030(reduction)["state"] == state


def test_conservative_meets_the_floor_it_was_solved_for(data):
    """It lands 2.8e-17 under 10%; reporting that as a miss would be a rounding artefact."""
    outcome = preset_scenarios()["conservative"]["result"].outcome_2030
    assert outcome["state"] == "meets"
    assert "Meets target" in outcome["label"]


def test_more_saf_moves_2030_through_the_band(data):
    states = [scenario(data, saf_share_2030=s).outcome_2030["state"] for s in (0.0, 0.05, 0.30)]
    assert states == ["below", "meets", "exceeds"]


def test_required_saf_shares_are_self_consistent(data):
    """Dialing SAF to the computed requirement lands exactly on the band edge."""
    for tag, cut in (("10%", 0.10), ("14%", 0.14)):
        needed = scenario(data).outcome_2030["required_saf_share"][tag]
        assert scenario(data, saf_share_2030=needed).outcome_2030["reduction"] == pytest.approx(cut, abs=1e-9)


# --- SAF supply ---------------------------------------------------------------

def test_supply_paths_never_decline(data):
    for case in ("Base", "Conservative"):
        supply = scenario(data, saf_supply_case=case, post_2035_growth=0.0).pathway["us_supply_base"]
        assert (supply.diff().dropna() >= 0).all()


def test_conservative_supply_is_below_base(data):
    base = scenario(data, saf_supply_case="Base").pathway["us_supply_base"]
    cons = scenario(data, saf_supply_case="Conservative").pathway["us_supply_base"]
    assert (cons[1:] < base[1:]).all()


def test_supply_constraint_binds_and_opens_a_gap(data):
    """A SAF target the US market cannot supply is capped, and the shortfall is reported."""
    r = scenario(data, saf_share_2040=1.0, saf_supply_case="Conservative",
                 post_2035_growth=0.0, activity_adj=0.03)
    y40 = r.pathway.set_index("year").loc[2040]
    assert y40["effective_saf_share"] < y40["target_saf_share"]
    assert y40["supply_gap_gal"] > 0
    assert y40["effective_saf_gal"] == pytest.approx(y40["saf_availability"], rel=1e-9)


def test_catalytic_capital_adds_capacity_only_after_the_lag(data):
    r = scenario(data, catalytic_pct=0.02)
    plain = scenario(data).pathway.set_index("year")["saf_availability"]
    lifted = r.pathway.set_index("year")["saf_availability"]
    assert lifted.loc[2027] == pytest.approx(plain.loc[2027], rel=1e-12)   # within the 3-year lag
    assert lifted.loc[2040] > plain.loc[2040]


# --- physical levers ----------------------------------------------------------

@pytest.mark.parametrize("lever", ["fleet_renewal", "ground_elec", "novel_propulsion"])
def test_each_physical_lever_lowers_2040_residual(data, lever):
    assert scenario(data, **{lever: 0.5}).physical_2040["residual_emis"] < \
           scenario(data).physical_2040["residual_emis"]


def test_residual_is_the_sum_of_its_parts(data):
    p = scenario(data, ground_elec=0.4, fleet_renewal=0.3).physical_2040
    assert p["residual_emis"] == pytest.approx(
        p["aircraft_emis"] + p["vehicle_emis"] + p["facility_emis"] + p["scope2_emis"], rel=1e-12)


def test_physical_residual_is_not_zero_without_closure(data):
    """Physical levers alone never reach net zero — closure is what completes it."""
    assert scenario(data, saf_share_2040=1.0, fleet_renewal=1.0,
                    ground_elec=1.0, novel_propulsion=0.5).physical_2040["residual_emis"] > 0


# --- finance ------------------------------------------------------------------

def test_partner_support_shifts_cost_without_changing_physics(data):
    plain, helped = scenario(data), scenario(data, partner_share=0.5)
    assert helped.physical_2040["residual_emis"] == pytest.approx(
        plain.physical_2040["residual_emis"], rel=1e-12)
    assert helped.financial_2040["net_saf_premium"] < plain.financial_2040["net_saf_premium"]


def test_carbon_price_scales_closure_cost_linearly(data):
    a, b = (scenario(data, carbon_price=p).financial_2040["carbon_closure_cost"] for p in (100, 200))
    assert b == pytest.approx(2 * a, rel=1e-12)


def test_closure_cost_is_charged_in_2040_only(data):
    pathway = scenario(data).pathway.set_index("year")
    assert (pathway.loc[2025:2039, "closure_cost"] == 0).all()
    assert pathway.loc[2040, "closure_cost"] > 0


def test_model_is_deterministic(data):
    assert scenario(data).pathway.equals(scenario(data).pathway)


# --- offsets, carbon market and milestones ------------------------------------

def test_offset_cost_is_priced_every_year(data):
    """Unlike closure_cost (2040 only, for workbook parity), offsets are priced annually."""
    pathway = scenario(data).pathway.set_index("year")
    assert (pathway["offset_cost"] > 0).all()
    assert pathway.loc[2040, "offset_cost"] == pytest.approx(pathway.loc[2040, "closure_cost"])
    assert (pathway.loc[2025:2039, "closure_cost"] == 0).all()


def test_offset_cost_matches_residual_times_price(data):
    """Priced at THAT YEAR's carbon price, which escalates away from the 2025 anchor."""
    row = scenario(data, carbon_price=150).pathway.set_index("year").loc[2030]
    assert row["carbon_price"] > 150                      # escalation is on by default
    assert row["offset_cost"] == pytest.approx(row["residual_emis"] * row["carbon_price"], rel=1e-12)
    flat = scenario(data, carbon_price=150, carbon_escalation=0.0).pathway.set_index("year").loc[2030]
    assert flat["offset_cost"] == pytest.approx(flat["residual_emis"] * 150, rel=1e-12)
    assert row["offset_share_revenue"] == pytest.approx(row["offset_cost"] / row["revenue"], rel=1e-12)


def test_carbon_supply_is_flat_at_zero_growth(data):
    supply = scenario(data, removal_growth=0.0).pathway["carbon_supply"]
    assert supply.nunique() == 1
    assert supply.iloc[0] == pytest.approx(data["removal_volume"], rel=1e-12)


def test_carbon_supply_growth_compounds_from_the_observed_year(data):
    pathway = scenario(data, removal_growth=0.20).pathway.set_index("year")
    assert pathway.loc[2026, "carbon_supply"] == pytest.approx(data["removal_volume"], rel=1e-12)
    assert pathway.loc[2036, "carbon_supply"] == pytest.approx(
        data["removal_volume"] * 1.20 ** 10, rel=1e-12)


def test_carbon_supply_never_constrains_the_model(data):
    """The carbon chart is presentational — supply must not feed back into emissions or cost."""
    lean, rich = scenario(data, removal_growth=0.0), scenario(data, removal_growth=0.60)
    assert lean.physical_2040["residual_emis"] == pytest.approx(rich.physical_2040["residual_emis"])
    assert lean.financial_2040["carbon_closure_cost"] == pytest.approx(
        rich.financial_2040["carbon_closure_cost"])


def test_milestones_expose_identical_keys_for_both_years(data):
    m = scenario(data).milestones
    assert set(m) == {2030, 2040}
    assert set(m[2030]) == set(m[2040])


def test_only_2030_carries_a_band_verdict(data):
    """The 10-14% band is a 2030 target; 2040 must not inherit its pass/fail state."""
    m = scenario(data).milestones
    assert m[2030]["state"] in {"below", "meets", "exceeds"}
    assert m[2040]["state"] is None


def test_milestone_figures_agree_with_the_pathway(data):
    r = scenario(data, carbon_price=125, saf_premium=0.5)
    for year, m in r.milestones.items():
        row = r.pathway.set_index("year").loc[year]
        assert m["saf_cost"] == pytest.approx(row["net_saf_premium"], rel=1e-12)
        assert m["offset_cost"] == pytest.approx(row["offset_cost"], rel=1e-12)
        assert m["residual_emis"] == pytest.approx(row["residual_emis"], rel=1e-12)


# --- marginal abatement cost: SAF vs carbon credits ---------------------------

def _cost_per_tonne_2040(data, **overrides):
    """Measured, not read off the model: cost / (emissions avoided vs a no-SAF run)."""
    with_saf = scenario(data, **overrides).pathway.set_index("year").loc[2040]
    without = scenario(data, saf_share_2030=0.0, saf_share_2040=0.0,
                       **overrides).pathway.set_index("year").loc[2040]
    return with_saf["net_saf_premium"] / (without["aircraft_emis"] - with_saf["aircraft_emis"])


def test_reported_saf_cost_per_tonne_matches_measured_abatement(data):
    reported = scenario(data).pathway.set_index("year").loc[2040, "saf_cost_per_tonne"]
    assert reported == pytest.approx(_cost_per_tonne_2040(data), rel=1e-9)


@pytest.mark.parametrize("lever, value", [
    ("saf_share_2040", 0.25), ("saf_share_2040", 0.95),   # the share cancels out
    ("efficiency_adj", 0.02), ("fleet_renewal", 1.0), ("novel_propulsion", 0.5),
    ("activity_adj", 0.03), ("ground_elec", 1.0),
])
def test_saf_cost_per_tonne_is_invariant_to_quantity_levers(data, lever, value):
    """It is a price, not a total: quantity levers cannot move it.

    catalytic_pct is deliberately absent — since the learning curve was added it is a
    price lever, which the next test pins.
    """
    base = scenario(data).pathway.set_index("year").loc[2040, "saf_cost_per_tonne"]
    moved = scenario(data, **{lever: value}).pathway.set_index("year").loc[2040, "saf_cost_per_tonne"]
    assert moved == pytest.approx(base, rel=1e-12)


@pytest.mark.parametrize("lever, value, factor", [
    ("saf_premium", 0.5, 0.5),        # half the premium, half the cost per tonne
    ("partner_share", 0.5, 0.5),      # partners cover half, Alaska pays half
])
def test_price_levers_scale_saf_cost_per_tonne(data, lever, value, factor):
    base = scenario(data).pathway.set_index("year").loc[2040, "saf_cost_per_tonne"]
    moved = scenario(data, **{lever: value}).pathway.set_index("year").loc[2040, "saf_cost_per_tonne"]
    assert moved == pytest.approx(base * factor, rel=1e-12)


def test_catalytic_capital_buys_a_price_on_the_volume_it_funded(data):
    """The offtake: capital cuts the premium on contracted gallons, not on the market."""
    off = scenario(data, catalytic_pct=0.0).pathway.set_index("year")
    on = scenario(data, catalytic_pct=0.02).pathway.set_index("year")
    assert (off["offtake_share"] == 0.0).all()                 # inert when nothing is spent
    assert (off["effective_saf_premium"] == off["market_saf_premium"]).all()
    assert on.loc[2040, "offtake_share"] > 0.2
    assert on.loc[2040, "saf_cost_per_tonne"] < off.loc[2040, "saf_cost_per_tonne"]


def test_the_discount_never_reaches_fuel_alaska_did_not_fund(data):
    """Blended premium is exactly the volume-weighted mix of contracted and spot."""
    a, on = data["anchors"], scenario(data, catalytic_pct=0.02).pathway.set_index("year")
    for year in (2030, 2040):
        r = on.loc[year]
        expected = r["market_saf_premium"] * (1 - r["offtake_share"] * (1 - a["offtake_premium_ratio"]))
        assert r["effective_saf_premium"] == pytest.approx(expected, rel=1e-12)


def test_the_offtake_ratio_is_a_structural_floor(data):
    """Cost-plus still covers cost: no amount of capital drives the premium below it."""
    ratio = data["anchors"]["offtake_premium_ratio"]
    for pct in (0.02, 0.05):
        p = scenario(data, catalytic_pct=pct).pathway
        assert (p["effective_saf_premium"] >= ratio * p["market_saf_premium"] - 1e-12).all()
    assert saf_mod.contracted_premium(1.0, 1.0, data["anchors"]) == pytest.approx(ratio)
    assert saf_mod.contracted_premium(1.0, 0.0, data["anchors"]) == 1.0


def test_you_cannot_contract_more_than_you_burn(data):
    """Offtake share is capped at 1.0 however much capacity the capital builds."""
    assert saf_mod.offtake_share(5e9, 1e9) == 1.0
    assert saf_mod.offtake_share(0.0, 1e9) == 0.0
    assert saf_mod.offtake_share(1e9, 0.0) == 0.0
    assert (scenario(data, catalytic_pct=0.05).pathway["offtake_share"] <= 1.0).all()


def test_saf_premium_declines_from_its_default(data):
    """The market premium now falls by default; 0% is the workbook fixture, not the default."""
    p = scenario(data).pathway.set_index("year")["market_saf_premium"]
    assert p.loc[2025] == pytest.approx(1.0)
    assert p.loc[2040] == pytest.approx(0.98 ** 15, rel=1e-12)
    flat = scenario(data, saf_premium_decline=0.0).pathway["market_saf_premium"]
    assert (flat == 1.0).all()


def test_carbon_price_escalates_from_its_default(data):
    """The planning price now grows by default; 0% is the workbook fixture, not the default."""
    rising = scenario(data).pathway.set_index("year")["carbon_price"]
    assert rising.loc[2025] == pytest.approx(200)
    assert rising.loc[2040] > rising.loc[2025]
    flat = scenario(data, carbon_escalation=0.0).pathway.set_index("year")["carbon_price"]
    assert flat.nunique() == 1 and flat.iloc[0] == 200


def test_at_a_flat_premium_offsets_stay_the_cheaper_tonne(data):
    """Without market learning, the offtake discount alone never gets SAF under the carbon price."""
    r = scenario(data, catalytic_pct=0.02, saf_premium_decline=0.0).pathway.set_index("year")
    assert r.loc[2040, "saf_cost_per_tonne"] > r.loc[2040, "carbon_price"]


def test_saf_cost_per_tonne_tracks_the_jet_fuel_price(data):
    """Across years the line moves only with the EIA fuel price and the premium decline."""
    pathway = scenario(data).pathway
    ratio = pathway["saf_cost_per_tonne"] / (pathway["jet_price"] * pathway["market_saf_premium"])
    assert ratio.nunique() == 1 or ratio.std() < 1e-9


def test_breakeven_premium_actually_breaks_even(data):
    """Setting the premium to the reported breakeven equalizes the two prices."""
    flat = dict(saf_premium_decline=0.0)   # breakeven is the 2040 premium, not the 2025 one
    breakeven = scenario(data, **flat).pathway.set_index("year").loc[2040, "breakeven_premium"]
    row = scenario(data, saf_premium=breakeven, **flat).pathway.set_index("year").loc[2040]
    assert row["saf_cost_per_tonne"] == pytest.approx(row["carbon_price"], rel=1e-9)
    assert row["abatement_spread"] == pytest.approx(0.0, abs=1e-9)


def test_saf_becomes_the_cheaper_tonne_late_in_the_decade(data):
    """Documents the finding: a 2%/yr premium decline gets SAF under offsets from 2038.

    At a flat 100% premium, carbon credits undercut SAF every year.
    """
    p = scenario(data).pathway.set_index("year")
    assert scenario(data).diagnostics["cheaper_tonne_2040"] == "SAF"
    assert (p.loc[:2037, "abatement_spread"] > 0).all()
    assert (p.loc[2038:, "abatement_spread"] < 0).all()
    assert (scenario(data, saf_premium_decline=0.0).pathway["abatement_spread"] > 0).all()


def test_a_high_enough_carbon_price_flips_the_spread(data):
    flipped = scenario(data, carbon_price=500)
    assert flipped.diagnostics["cheaper_tonne_2040"] == "SAF"
    assert (flipped.pathway["abatement_spread"] < 0).all()


# --- ground electrification is real but tiny ----------------------------------

def test_ground_electrification_ceiling_is_negligible(data):
    """Pins the finding so it cannot drift silently: the whole lever is <0.3% of residual."""
    none = scenario(data, ground_elec=0.0).physical_2040["residual_emis"]
    full = scenario(data, ground_elec=1.0).physical_2040["residual_emis"]
    removed = none - full
    assert 0 < removed / none < 0.003
    assert removed == pytest.approx(20_123, rel=0.01)


def test_one_saf_step_outweighs_the_entire_ground_lever(data):
    ground = (scenario(data, ground_elec=0.0).physical_2040["residual_emis"]
              - scenario(data, ground_elec=1.0).physical_2040["residual_emis"])
    saf_step = (scenario(data, saf_share_2040=0.60).physical_2040["residual_emis"]
                - scenario(data, saf_share_2040=0.65).physical_2040["residual_emis"])
    assert saf_step > 20 * ground


# --- business-as-usual reference line -----------------------------------------

def test_bau_does_not_move_when_any_control_moves(data):
    """The whole point of the reference line: it is fixed while the scenario is not."""
    before = bau_reference()["pathway"].reduction_vs_2019.tolist()
    for lever, value in [("saf_share_2030", 0.45), ("saf_share_2040", 0.95),
                         ("fleet_renewal", 1.0), ("ground_elec", 1.0),
                         ("novel_propulsion", 0.5), ("activity_adj", 0.03),
                         ("efficiency_adj", 0.02), ("catalytic_pct", 0.05),
                         ("saf_premium", 0.1), ("partner_share", 0.9),
                         ("carbon_price", 500), ("saf_supply_case", "Conservative"),
                         ("post_2035_growth", 0.0), ("removal_growth", 0.6)]:
        scenario(data, **{lever: value})                       # move the scenario
        assert bau_reference()["pathway"].reduction_vs_2019.tolist() == before, lever


def test_bau_is_efficiency_only(data):
    """BAU intensity is exactly the 2025 intensity deflated by the EIA efficiency index."""
    pathway = bau_reference()["pathway"]
    full = scenario(data, saf_share_2030=data["base_saf_share"],
                    saf_share_2040=data["base_saf_share"]).pathway.set_index("year")
    for year in (2030, 2040):
        expected = 1 - (data["intensity_2025"] / full.loc[year, "efficiency_index"]) / data["intensity_2019"]
        actual = pathway.set_index("year").loc[year, "reduction_vs_2019"]
        assert actual == pytest.approx(expected, rel=1e-12)


def test_bau_falls_short_of_the_2030_floor(data):
    """Documents the reference line's point: industry efficiency alone misses the target."""
    bau = bau_reference()
    assert bau["reduction_2030"] == pytest.approx(0.0798, abs=5e-4)
    assert bau["reduction_2030"] < 0.10


def test_scenario_beats_bau_at_default_settings(data):
    assert scenario(data).outcome_2030["reduction"] > bau_reference()["reduction_2030"]


def test_milestones_carry_absolute_tonnes_not_just_intensity(data):
    """Intensity is a ratio; the atmosphere sees tonnes. Both must reach the UI."""
    cons = preset_scenarios()["conservative"]["result"]
    m30 = cons.milestones[2030]
    assert m30["state"] == "meets"                      # intensity target: met
    assert m30["residual_vs_base"] > 0                  # and yet emissions are up
    assert m30["absolute_state"] == "below"             # which the tile must render as bad
    allin = preset_scenarios()["all_in"]["result"].milestones[2030]
    assert allin["residual_vs_base"] < 0 and allin["absolute_state"] == "meets"


def test_cost_per_tonne_abated_favours_the_pathway_that_actually_abates(data):
    """Framing-independent metric: All-In loses on total cost and wins on this."""
    from model import abatement_economics
    out = {n: abatement_economics(run_scenario(preset_inputs(n, data), data).pathway)
           for n in ("conservative", "all_in")}
    assert out["all_in"]["cost_per_tonne_abated"] < out["conservative"]["cost_per_tonne_abated"]
    assert out["all_in"]["cumulative_abated_vs_bau"] > 5 * out["conservative"]["cumulative_abated_vs_bau"]


# --- the delay hypothesis -----------------------------------------------------
#
# "Being conservative costs less to reach 2030, but more to reach net zero by 2040."
# These pin the answer docs/model_decisions.md reports, so the prose cannot drift.

def _annual(data, name, **world):
    import dataclasses as dc
    return run_scenario(dc.replace(preset_inputs(name, data), **world), data) \
        .pathway.set_index("year")["annual_cost"]


def test_conservative_is_cheaper_to_reach_2030(data):
    """First half of the hypothesis: delay genuinely is cheaper in the short run."""
    assert _annual(data, "conservative").loc[:2030].sum() < \
           _annual(data, "all_in").loc[:2030].sum()


def test_all_in_is_cheaper_by_2040(data):
    """Second half HOLDS, but only because the market premium declines.

    With SAF 2%/yr cheaper, All-In's extra SAF replaces offsets that keep getting dearer.
    The catalytic spend itself still does not repay (next test); at a flat premium
    Conservative stays cheaper at both dates.
    """
    cons, allin = _annual(data, "conservative").sum(), _annual(data, "all_in").sum()
    assert allin < cons
    flat = dict(saf_premium_decline=0.0)
    assert _annual(data, "all_in", **flat).sum() > _annual(data, "conservative", **flat).sum()


def test_the_offtake_saves_real_money_and_still_does_not_pay_for_itself(data):
    """The honest shape of the CVC bet, and the reason it reads as a cost.

    The discount is worth about a quarter of the outlay in premium savings. The model
    charges the whole outlay as expense and books no asset against it - there is no
    balance sheet here - so deploying capital still raises total cost even though the
    price it buys is real.
    """
    import dataclasses as dc
    allin = preset_inputs("all_in", data)
    on = run_scenario(allin, data).pathway
    off = run_scenario(dc.replace(allin, catalytic_pct=0.0), data).pathway
    saved = off["net_saf_premium"].sum() - on["net_saf_premium"].sum()
    spent = on["catalytic_investment"].sum()
    assert saved > 1e9                             # over a billion off the premium leg
    assert 0.15 < saved / spent < 0.40             # but only a fraction of the outlay
    assert on["annual_cost"].sum() > off["annual_cost"].sum()


def test_all_in_buys_far_more_abatement_per_dollar(data):
    """The claim that DOES survive every correction and every framing.

    All-In loses on total cost and wins decisively on what the money buys: roughly ten
    times the cumulative abatement at a materially lower cost per tonne. This needs no
    carbon-price forecast, so no escalation assumption can manufacture or destroy it.
    """
    bau = bau_reference()["pathway"].set_index("year")["residual_emis"].sum()
    out = {}
    for name in ("conservative", "all_in"):
        p = run_scenario(preset_inputs(name, data), data).pathway
        spend = (p["net_saf_premium"] + p["catalytic_investment"]).sum()
        out[name] = (bau - p["residual_emis"].sum(), spend)
    (c_ab, c_sp), (a_ab, a_sp) = out["conservative"], out["all_in"]
    assert a_ab > 5 * c_ab                          # far more tonnes
    assert a_sp / a_ab < c_sp / c_ab                # at a lower price per tonne


def test_more_catalytic_capital_is_not_always_better(data):
    """The lever has an interior optimum — beyond it the spend outruns the saving."""
    best = _annual(data, "all_in").sum()
    assert _annual(data, "all_in", catalytic_pct=0.05).sum() > best


# --- the three reference pathways on the projection toggle --------------------
#
# These encode scenario definitions asserted from outside the workbook (see the
# `references` block in config/assumptions.yaml). The tests below pin the claims the
# UI makes about them, so the prose and the arithmetic cannot drift apart.

def test_every_preset_is_fixed_while_the_sidebar_moves(data):
    """Presets are fixed strategies: the sidebar drives Custom only, never these."""
    before = {k: v["result"].pathway.reduction_vs_2019.tolist()
              for k, v in preset_scenarios().items()}
    for lever, value in [("saf_share_2030", 0.45), ("saf_share_2040", 0.95),
                         ("fleet_renewal", 1.0), ("novel_propulsion", 0.5),
                         ("saf_premium", 0.1), ("partner_share", 0.9),
                         ("carbon_price", 500), ("catalytic_pct", 0.05)]:
        scenario(data, **{lever: value})
        after = {k: v["result"].pathway.reduction_vs_2019.tolist()
                 for k, v in preset_scenarios().items()}
        assert after == before, lever


def _red(scn, year):
    return scn["result"].pathway.set_index("year").loc[year, "reduction_vs_2019"]


def test_presets_are_ordered_by_ambition(data):
    p = preset_scenarios()
    assert (bau_reference()["reduction_2040"] < _red(p["conservative"], 2040)
            < _red(p["all_in"], 2040))


def test_conservative_lands_exactly_on_the_2030_floor(data):
    """'Reaching 2030' is the band floor, solved by the model, not a chosen number."""
    floor = data["config"]["meta"]["target_band"][0]
    assert _red(preset_scenarios()["conservative"], 2030) == pytest.approx(floor, abs=5e-4)


def test_conservative_saf_ramp_is_one_straight_line(data):
    """The asserted rule: the 2025-2030 SAF slope simply continues to 2040."""
    from model.core import _conservative_saf_ramp
    ramp = _conservative_saf_ramp(data)
    s25, s30, s40 = data["base_saf_share"], ramp["saf_share_2030"], ramp["saf_share_2040"]
    assert (s40 - s30) / 10 == pytest.approx((s30 - s25) / 5, rel=1e-12)


def test_all_in_makes_saf_the_cheaper_tonne(data):
    """The All-In note claims the premium cut flips SAF below the carbon price by 2040."""
    over = data["config"]["references"]["all_in"]["overrides"]
    y40 = scenario(data, **over).pathway.set_index("year").loc[2040]
    assert y40["saf_cost_per_tonne"] < y40["carbon_price"]


def test_all_in_buys_its_price_decline_rather_than_asserting_it(data):
    """All-In spends real money up front; the cheaper SAF price is the return on it."""
    over = dict(data["config"]["references"]["all_in"]["overrides"])
    assert over["catalytic_pct"] > 0 and "saf_premium" not in over
    spent = scenario(data, **over).pathway
    free = scenario(data, **{**over, "catalytic_pct": 0.0}).pathway
    assert spent.catalytic_investment.sum() > 1e9
    s40 = spent.set_index("year").loc[2040]
    f40 = free.set_index("year").loc[2040]
    assert s40["saf_cost_per_tonne"] < f40["saf_cost_per_tonne"]    # the payoff
    assert s40["residual_emis"] == pytest.approx(f40["residual_emis"], rel=1e-12)  # no tonnes


def test_catalytic_capital_abates_no_tonnes_when_supply_does_not_bind(data):
    """Unconstrained, this lever still removes zero tonnes — it only makes them cheaper.

    Before the learning curve this was pure dead-weight. It now buys a price decline
    instead, so the emissions claim survives but the 'pure cost' half of it does not.
    """
    off, on = scenario(data, catalytic_pct=0.0), scenario(data, catalytic_pct=0.02)
    assert (on.pathway["supply_gap_gal"] == 0).all()           # supply never binds here
    assert on.physical_2040["residual_emis"] == pytest.approx(
        off.physical_2040["residual_emis"], rel=1e-12)         # not one tonne abated
    assert on.pathway.set_index("year").loc[2040, "market_capture"] < \
        off.pathway.set_index("year").loc[2040, "market_capture"]
    assert on.pathway.set_index("year").loc[2040, "saf_cost_per_tonne"] < \
        off.pathway.set_index("year").loc[2040, "saf_cost_per_tonne"]


def test_catalytic_capital_does_abate_when_supply_binds(data):
    bind = dict(saf_share_2040=1.0, saf_supply_case="Conservative",
                post_2035_growth=0.01, activity_adj=0.03)
    off = scenario(data, catalytic_pct=0.0, **bind)
    on = scenario(data, catalytic_pct=0.02, **bind)
    assert off.pathway.set_index("year").loc[2040, "supply_gap_gal"] > 0
    assert on.physical_2040["residual_emis"] < off.physical_2040["residual_emis"]
