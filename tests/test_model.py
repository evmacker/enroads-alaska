"""Sensitivity and invariant tests for logic that has no Excel counterpart."""
import dataclasses

import pytest

from model import bau_reference, load_data, default_inputs, run_scenario
from model.targets import classify_2030, classify_2040_finance


@pytest.fixture(scope="module")
def data():
    return load_data()


def scenario(data, **overrides):
    return run_scenario(dataclasses.replace(default_inputs(data), **overrides), data)


# --- 2030 band classification -------------------------------------------------

@pytest.mark.parametrize("reduction, state", [
    (0.05, "below"), (0.0999, "below"), (0.10, "meets"), (0.14, "meets"), (0.20, "exceeds"),
])
def test_band_states(reduction, state):
    assert classify_2030(reduction)["state"] == state


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

def test_headroom_identity(data):
    f = scenario(data, investable_pct=0.05).financial_2040
    assert f["cash_headroom"] == pytest.approx(
        (f["investable_pool"] - f["physical_decarb_spend"] - f["carbon_closure_cost"])
        / f["investable_pool"], rel=1e-12)
    assert f["investable_pool"] == pytest.approx(f["revenue"] * 0.05, rel=1e-12)


def test_bigger_budget_buys_headroom(data):
    headrooms = [scenario(data, investable_pct=p).financial_2040["cash_headroom"]
                 for p in (0.02, 0.05, 0.10)]
    assert headrooms == sorted(headrooms)


def test_partner_support_shifts_cost_without_changing_physics(data):
    plain, helped = scenario(data), scenario(data, partner_share=0.5)
    assert helped.physical_2040["residual_emis"] == pytest.approx(
        plain.physical_2040["residual_emis"], rel=1e-12)
    assert helped.financial_2040["net_saf_premium"] < plain.financial_2040["net_saf_premium"]
    assert helped.financial_2040["cash_headroom"] > plain.financial_2040["cash_headroom"]


def test_carbon_price_scales_closure_cost_linearly(data):
    a, b = (scenario(data, carbon_price=p).financial_2040["carbon_closure_cost"] for p in (100, 200))
    assert b == pytest.approx(2 * a, rel=1e-12)


def test_closure_cost_is_charged_in_2040_only(data):
    pathway = scenario(data).pathway.set_index("year")
    assert (pathway.loc[2025:2039, "closure_cost"] == 0).all()
    assert pathway.loc[2040, "closure_cost"] > 0


@pytest.mark.parametrize("headroom, state", [(0.25, "comfortable"), (0.05, "tight"), (-0.3, "infeasible")])
def test_financial_states(headroom, state):
    assert classify_2040_finance(headroom)["state"] == state


def test_default_scenario_is_unaffordable_on_the_default_budget(data):
    """Documents the headline finding: the default pathway costs far more than 3% of revenue."""
    f = scenario(data).financial_2040
    assert f["state"] == "infeasible"
    assert f["cash_available_for_closure"] == 0.0


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
    row = scenario(data, carbon_price=150).pathway.set_index("year").loc[2030]
    assert row["offset_cost"] == pytest.approx(row["residual_emis"] * 150, rel=1e-12)
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
    ("activity_adj", 0.03), ("ground_elec", 1.0), ("catalytic_pct", 0.02),
])
def test_saf_cost_per_tonne_is_invariant_to_quantity_levers(data, lever, value):
    """It is a price, not a total: only fuel price, premium and partner share move it."""
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


def test_saf_cost_per_tonne_tracks_the_jet_fuel_price(data):
    """The only reason the line moves across years is the EIA fuel price index."""
    pathway = scenario(data).pathway
    ratio = pathway["saf_cost_per_tonne"] / pathway["jet_price"]
    assert ratio.nunique() == 1 or ratio.std() < 1e-9


def test_breakeven_premium_actually_breaks_even(data):
    """Setting the premium to the reported breakeven equalizes the two prices."""
    breakeven = scenario(data).pathway.set_index("year").loc[2040, "breakeven_premium"]
    row = scenario(data, saf_premium=breakeven).pathway.set_index("year").loc[2040]
    assert row["saf_cost_per_tonne"] == pytest.approx(row["carbon_price"], rel=1e-9)
    assert row["abatement_spread"] == pytest.approx(0.0, abs=1e-9)


def test_default_scenario_makes_offsets_the_cheaper_tonne(data):
    """Documents the finding: at a 100% premium, carbon credits undercut SAF every year."""
    r = scenario(data)
    assert r.diagnostics["cheaper_tonne_2040"] == "offsets"
    assert (r.pathway["abatement_spread"] > 0).all()


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
