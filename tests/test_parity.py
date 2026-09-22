"""Regression: the Python engine must reproduce the Excel workbook cell for cell."""
import dataclasses
from pathlib import Path

import openpyxl
import pytest

from model import load_data, default_inputs, run_scenario

WORKBOOK = Path(__file__).resolve().parents[1] / "data/raw/Alaska_Airlines_Model_Revenue_Anchored_v3.xlsx"

# Excel 'Model' sheet column -> engine pathway field.
COLUMNS = {
    "Business Activity Index": "activity_index",
    "Operational Efficiency Index": "efficiency_index",
    "Fleet Renewal Share": "fleet_share",
    "Fleet Fuel Factor": "fleet_factor",
    "Novel Propulsion Share": "propulsion_share",
    "Liquid Jet Fuel Gallons": "liquid_fuel_gal",
    "Target SAF Share": "target_saf_share",
    "Target SAF Gallons": "target_saf_gal",
    "U.S. SAF Availability": "saf_availability",
    "Market Capture Required": "market_capture",
    "SAF Supply Gap": "supply_gap_gal",
    "Effective SAF Share": "effective_saf_share",
    "Effective SAF Gallons": "effective_saf_gal",
    "Conventional Gallons": "conventional_gal",
    "Conventional Fuel $/gal": "jet_price",
    "SAF Market $/gal": "saf_market_price",
    "Alaska Net SAF $/gal": "net_saf_price",
    "Fuel Cost – No SAF": "fuel_cost_no_saf",
    "Fuel Cost – With SAF": "fuel_cost_with_saf",
    "Net Incremental SAF Cost": "net_saf_premium",
    "Corporate / Partner Contribution": "partner_contribution",
    "Projected Revenue": "revenue",
    "SAF Cost / Revenue": "saf_cost_share_revenue",
    "Carbon Mix Factor": "carbon_mix",
    "Aircraft GHG Intensity (MtCO2e / 1,000 RTM)": "intensity",
    "Reduction vs 2019": "reduction_vs_2019",
    "Aircraft Emissions (tCO2e)": "aircraft_emis",
    "Ground Electrification Share": "ground_share",
    "Vehicle Emissions (tCO2e)": "vehicle_emis",
    "Facility Heating Emissions (tCO2e)": "facility_emis",
    "Scope 2 Market Emissions (tCO2e)": "scope2_emis",
    "Operational Residual Emissions (tCO2e)": "residual_emis",
    "Carbon Closure Cost": "closure_cost",
}

# The workbook's cached post-2035 supply cells were last calculated with post-2035
# growth at 0%, so they are stale against its own 'SAF Supply' tab (2040: 4.69bn gal
# vs 2.91bn cached). test_stale_supply_cells_reproduce_at_zero_growth pins that
# reading instead; every other cell in those years still matches, because SAF supply
# is not binding in the default scenario.
STALE = {(y, f) for y in range(2036, 2041) for f in ("saf_availability", "market_capture")}


@pytest.fixture(scope="module")
def workbook_grid():
    ws = openpyxl.load_workbook(WORKBOOK, data_only=True)["Model"]
    header = [c.value for c in ws[1]]
    grid = {}
    for row in ws.iter_rows(min_row=2, max_row=17):
        year = row[0].value
        grid[year] = {header[i]: c.value for i, c in enumerate(row) if header[i]}
    return grid


# The workbook's own Inputs tab, stated here rather than inherited from the config.
#
# Parity is a claim about the ENGINE'S ARITHMETIC AT THE WORKBOOK'S INPUTS, not about the
# app's planning defaults. Those two were the same thing until the planning defaults had to
# diverge: several of them (a flat carbon price forever, a frozen carbon-removal market)
# are honest as parity fixtures and misleading as the first screen of a planning tool.
# Pinning the workbook's set here keeps the port verifiable while the app is free to open
# on defensible assumptions. Every value below is the workbook's, and none may change.
WORKBOOK_INPUTS = dict(
    saf_share_2030=0.10, saf_share_2040=0.60, saf_premium=1.00, partner_share=0.0,
    fleet_renewal=0.0, ground_elec=0.0, novel_propulsion=0.0,
    carbon_price=200, carbon_escalation=0.0, catalytic_pct=0.0,
    activity_adj=0.0, efficiency_adj=0.0, saf_supply_case="Base", post_2035_growth=0.10,
)


def workbook_inputs(data):
    return dataclasses.replace(default_inputs(data), **WORKBOOK_INPUTS)


@pytest.fixture(scope="module")
def result():
    data = load_data()
    return run_scenario(workbook_inputs(data), data)


def test_workbook_input_set_is_complete():
    """Every field the workbook fixes must be named above, so none can drift in silently."""
    data = load_data()
    fixed = set(WORKBOOK_INPUTS)
    free = {f.name for f in dataclasses.fields(default_inputs(data))} - fixed
    # Only inputs with no workbook counterpart may be left to the config default.
    assert free == {"investable_pct", "removal_growth"}, free


@pytest.mark.parametrize("year", range(2025, 2041))
def test_annual_pathway_matches_workbook(result, workbook_grid, year):
    engine = result.pathway.set_index("year").loc[year]
    for excel_col, field in COLUMNS.items():
        if (year, field) in STALE:
            continue
        expected = workbook_grid[year][excel_col]
        assert engine[field] == pytest.approx(expected, rel=1e-9, abs=1e-6), f"{year} {excel_col}"


def test_stale_supply_cells_reproduce_at_zero_growth(workbook_grid):
    """At 0% post-2035 growth the engine reproduces the workbook's stale cached cells exactly."""
    data = load_data()
    flat = dataclasses.replace(workbook_inputs(data), post_2035_growth=0.0)
    pathway = run_scenario(flat, data).pathway.set_index("year")
    for year in range(2036, 2041):
        row, cached = pathway.loc[year], workbook_grid[year]
        assert row["saf_availability"] == pytest.approx(cached["U.S. SAF Availability"], rel=1e-9)
        assert row["market_capture"] == pytest.approx(cached["Market Capture Required"], rel=1e-9)
    assert pathway.loc[2040, "saf_availability"] == pytest.approx(2_912_700_000, rel=1e-9)


def test_outcome_objects_match_workbook_outputs_tab(result):
    o30, p40, f40 = result.outcome_2030, result.physical_2040, result.financial_2040
    assert o30["reduction"] == pytest.approx(0.14688431763023047, rel=1e-9)
    assert o30["intensity"] == pytest.approx(1.1858307984939795, rel=1e-9)
    assert o30["required_saf_share"]["10%"] == pytest.approx(0.03679993652795671, rel=1e-9)
    assert o30["required_saf_share"]["14%"] == pytest.approx(0.09071993934893663, rel=1e-9)
    assert o30["net_saf_premium"] == pytest.approx(314640276.1818571, rel=1e-9)
    assert p40["residual_emis"] == pytest.approx(7117986.6076477375, rel=1e-9)
    assert p40["aircraft_emis"] == pytest.approx(7069104.989182192, rel=1e-9)
    assert f40["carbon_closure_cost"] == pytest.approx(1423597321.5295475, rel=1e-9)
    assert f40["net_saf_premium"] == pytest.approx(2646062337.4499702, rel=1e-9)
    assert f40["revenue"] == pytest.approx(20779978066.30524, rel=1e-9)
