"""Sensitivity and invariant tests for logic that has no Excel counterpart."""
import dataclasses

import pytest

from model import load_data, default_inputs, run_scenario
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
