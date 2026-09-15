"""Scenario orchestration. Pure and deterministic — no Streamlit, no I/O beyond loading data."""
import dataclasses
from dataclasses import dataclass, asdict, fields
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

from . import emissions, finance, saf, targets

ROOT = Path(__file__).resolve().parents[2]
BASE_YEAR, TARGET_YEAR, NETZERO_YEAR = 2025, 2030, 2040


@dataclass(frozen=True)
class ScenarioInputs:
    saf_share_2030: float
    saf_share_2040: float
    saf_premium: float
    partner_share: float
    fleet_renewal: float
    ground_elec: float
    novel_propulsion: float
    carbon_price: float
    catalytic_pct: float
    investable_pct: float
    activity_adj: float
    efficiency_adj: float
    saf_supply_case: str
    post_2035_growth: float
    removal_growth: float


@lru_cache(maxsize=1)
def load_data(root: str = str(ROOT)) -> dict:
    """Processed tables + config, as one plain dict the model reads."""
    root = Path(root)
    cfg = yaml.safe_load((root / "config/assumptions.yaml").read_text())
    p = root / "data/processed"
    faa = pd.read_csv(p / "faa_activity.csv")
    eia = pd.read_csv(p / "eia_indices.csv")
    base = pd.read_csv(p / "alaska_base.csv").set_index("metric")["value"]
    carbon = pd.read_csv(p / "carbon_markets.csv")
    volume = carbon.set_index("instrument")["volume_tco2e"]
    return dict(
        config=cfg, anchors=cfg["anchors"],
        saf_history=pd.read_csv(p / "saf_history.csv"),
        carbon_markets=carbon,
        removal_volume=float(volume["Puro CORCX observed reference"]),
        removal_volume_year=2026,          # Puro CORCX observation window, Aug/Sep 2026
        voluntary_volume=float(volume["Broad voluntary carbon credits"]),
        voluntary_volume_year=2025,        # MSCI, 2025 retirements
        base_year=BASE_YEAR,
        faa_activity=dict(zip(faa.year, faa.activity_index)),
        eia_efficiency=dict(zip(eia.year, eia.efficiency_index)),
        eia_fuel_price=dict(zip(eia.year, eia.fuel_price_index)),
        base_fuel_gal=float(base["2025 Operating Aircraft Fuel"]),
        base_saf_share=float(base["2025 operating SAF share"]),
        intensity_2019=float(base["2019 GHG Intensity Baseline"]),
        intensity_2025=float(base["2025 GHG Intensity"]),
        implied_rtm=float(base["2025 implied RTM"]),
        jet_price_2025=float(base["2025 Into-plane Fuel Price"]),
        revenue_2025=float(base["2025 Total Operating Revenue"]),
        vehicle_emis=float(base["2025 Vehicle Scope 1 emissions"]),
        facility_emis=float(base["2025 Facility heating Scope 1 emissions"]),
        scope2_emis=float(base["2025 Scope 2 market-based emissions"]),
        ocf_2025=float(base["2025 Operating Cash Flow"]),
        tonnes_avoided_per_saf_gallon=_tonnes_avoided_per_saf_gallon(base, cfg["anchors"]),
    )


def _tonnes_avoided_per_saf_gallon(base, anchors):
    """CO2e a gallon of SAF avoids vs conventional jet fuel.

    2025 reported intensity already contains ~0.95% SAF, so it is grossed back up to a
    conventional-only basis before applying the lifecycle reduction.
    """
    reported = float(base["2025 GHG Intensity"]) * float(base["2025 implied RTM"]) / 1000
    conventional_basis = reported / float(base["2025 Operating Aircraft Fuel"]) / (
        1 - float(base["2025 operating SAF share"]) * anchors["saf_lifecycle_reduction"])
    return conventional_basis * anchors["saf_lifecycle_reduction"]


def default_inputs(data: dict) -> ScenarioInputs:
    spec = data["config"]["inputs"]
    return ScenarioInputs(**{f.name: spec[f.name]["default"] for f in fields(ScenarioInputs)})


@dataclass(frozen=True)
class ScenarioResult:
    pathway: pd.DataFrame          # annual, 2025-2040
    outcome_2030: dict
    physical_2040: dict
    financial_2040: dict
    milestones: dict            # {2030: {...}, 2040: {...}} — identical keys, for the KPI grid
    diagnostics: dict

    def year(self, y: int) -> dict:
        return self.pathway.set_index("year").loc[y].to_dict()


def run_scenario(inputs: ScenarioInputs, data: dict) -> ScenarioResult:
    a, years = data["anchors"], list(range(BASE_YEAR, NETZERO_YEAR + 1))
    horizon = NETZERO_YEAR - BASE_YEAR

    # Physical scale and revenue first — neither depends on SAF.
    rows = [emissions.physical_year(y, inputs, data, a, horizon) for y in years]
    revenue = {r["year"]: data["revenue_2025"] * r["activity_index"] for r in rows}

    # Catalytic capital matures into incremental US SAF capacity after a lag.
    invest, matured, extra_capacity = saf.catalytic_capacity(years, revenue, inputs.catalytic_pct, a)

    for r in rows:
        y = r["year"]
        r["revenue"] = revenue[y]
        r["catalytic_investment"] = invest[y]
        r["us_supply_base"] = saf.us_supply(y, inputs.saf_supply_case, inputs.post_2035_growth, a)
        r["saf_availability"] = r["us_supply_base"] + extra_capacity[y]

        r["target_saf_share"] = emissions.target_saf_share(
            y, data["base_saf_share"], inputs.saf_share_2030, inputs.saf_share_2040, BASE_YEAR)
        r["target_saf_gal"] = r["liquid_fuel_gal"] * r["target_saf_share"]
        r["supply_gap_gal"] = max(0.0, r["target_saf_gal"] - r["saf_availability"])
        r["market_capture"] = r["target_saf_gal"] / r["saf_availability"] if r["saf_availability"] else float("nan")
        r["effective_saf_share"] = (min(r["target_saf_share"], r["saf_availability"] / r["liquid_fuel_gal"])
                                    if r["liquid_fuel_gal"] else 0.0)
        r["effective_saf_gal"] = r["liquid_fuel_gal"] * r["effective_saf_share"]

        r.update(emissions.intensity_and_emissions(r, r["effective_saf_share"], a, data))
        r.update(finance.fuel_costs(r["liquid_fuel_gal"], r["effective_saf_gal"],
                                    data["jet_price_2025"] * data["eia_fuel_price"][y],
                                    inputs.saf_premium, inputs.partner_share))

        # Cost to neutralize this year's residual, priced every year for the KPI tiles.
        r["offset_cost"] = finance.closure_cost(r["residual_emis"], inputs.carbon_price,
                                                a["neutralization_share"])
        r["offset_share_revenue"] = r["offset_cost"] / r["revenue"]
        r["carbon_supply"] = finance.carbon_supply(y, data["removal_volume"],
                                                   data["removal_volume_year"], inputs.removal_growth)
        # closure_cost stays 2040-only: it is the workbook's own column and parity depends on it.
        r["closure_cost"] = r["offset_cost"] if y == NETZERO_YEAR else 0.0
        # Marginal abatement price: what a tonne costs via SAF vs via offsets.
        r["saf_cost_per_tonne"] = finance.saf_abatement_cost(
            r["jet_price"], inputs.saf_premium, inputs.partner_share,
            data["tonnes_avoided_per_saf_gallon"])
        r["carbon_price"] = inputs.carbon_price
        r["abatement_spread"] = r["saf_cost_per_tonne"] - inputs.carbon_price
        r["breakeven_premium"] = finance.breakeven_premium(
            inputs.carbon_price, r["jet_price"], inputs.partner_share,
            data["tonnes_avoided_per_saf_gallon"])
        r["physical_decarb_spend"] = r["net_saf_premium"] + r["catalytic_investment"]
        r.update(finance.headroom(r["revenue"], inputs.investable_pct,
                                  r["physical_decarb_spend"], r["closure_cost"]))
        r["saf_cost_share_revenue"] = r["net_saf_premium"] / r["revenue"]

    pathway = pd.DataFrame(rows)
    y30, y40 = (pathway.set_index("year").loc[y].to_dict() for y in (TARGET_YEAR, NETZERO_YEAR))
    band = tuple(data["config"]["meta"]["target_band"])

    outcome_2030 = dict(
        reduction=y30["reduction_vs_2019"], intensity=y30["intensity"], band=band,
        effective_saf_share=y30["effective_saf_share"],
        market_capture=y30["market_capture"], supply_gap_gal=y30["supply_gap_gal"],
        net_saf_premium=y30["net_saf_premium"],
        saf_cost_share_revenue=y30["saf_cost_share_revenue"],
        required_saf_share=_required_saf_shares(y30, data, a),
        **targets.classify_2030(y30["reduction_vs_2019"], band))

    physical_2040 = dict(
        residual_emis=y40["residual_emis"], aircraft_emis=y40["aircraft_emis"],
        vehicle_emis=y40["vehicle_emis"], facility_emis=y40["facility_emis"],
        scope2_emis=y40["scope2_emis"], intensity=y40["intensity"],
        reduction_vs_2019=y40["reduction_vs_2019"],
        effective_saf_share=y40["effective_saf_share"], market_capture=y40["market_capture"],
        supply_gap_gal=y40["supply_gap_gal"],
        abatement=_abatement_breakdown(inputs, data, a, horizon),
    )

    financial_2040 = dict(
        revenue=y40["revenue"], investable_pool=y40["investable_pool"],
        physical_decarb_spend=y40["physical_decarb_spend"],
        net_saf_premium=y40["net_saf_premium"], catalytic_investment=y40["catalytic_investment"],
        carbon_closure_cost=y40["closure_cost"],
        cash_available_for_closure=y40["cash_available_for_closure"],
        closure_coverage=y40["closure_coverage"], cash_headroom=y40["cash_headroom"],
        partner_contribution=y40["partner_contribution"],
        **targets.classify_2040_finance(y40["cash_headroom"]))

    milestones = {year: _milestone(row, band, year) for year, row in ((TARGET_YEAR, y30), (NETZERO_YEAR, y40))}

    diagnostics = dict(
        ocf_share_revenue_2025=data["ocf_2025"] / data["revenue_2025"],
        tonnes_avoided_per_saf_gallon=data["tonnes_avoided_per_saf_gallon"],
        cheaper_tonne_2040=("SAF" if y40["abatement_spread"] < 0 else "offsets"),
        saf_cost_per_tonne_2040=y40["saf_cost_per_tonne"],
        breakeven_premium_2040=y40["breakeven_premium"],
        matured_catalytic_2040=matured[NETZERO_YEAR],
        extra_capacity_2040=extra_capacity[NETZERO_YEAR],
        saf_supply_case=inputs.saf_supply_case,
        inputs=asdict(inputs),
        not_modeled=["fleet / ground / propulsion incremental capex",
                     "Scope 3 emissions", "CORSIA compliance cost"],
    )
    return ScenarioResult(pathway, outcome_2030, physical_2040, financial_2040, milestones, diagnostics)


def _milestone(row, band, year):
    """The same six KPI figures for any milestone year, so the UI can loop instead of branch.

    The 10-14% band is a 2030 target, so only the 2030 milestone carries a pass/fail
    state; 2040 reports its reduction against the same 2019 baseline without a verdict.
    """
    verdict = (targets.classify_2030(row["reduction_vs_2019"], band) if year == TARGET_YEAR
               else dict(state=None, label="vs 2019 baseline"))
    return dict(
        year=year, reduction=row["reduction_vs_2019"], intensity=row["intensity"],
        residual_emis=row["residual_emis"], revenue=row["revenue"],
        saf_cost=row["net_saf_premium"], saf_share_revenue=row["saf_cost_share_revenue"],
        offset_cost=row["offset_cost"], offset_share_revenue=row["offset_share_revenue"],
        effective_saf_share=row["effective_saf_share"], **verdict)


def _required_saf_shares(row, data, a):
    """Effective SAF share needed to hit each edge of the 2030 band, holding other levers fixed."""
    baseline_mix = 1 - data["base_saf_share"] * a["saf_lifecycle_reduction"]
    dry = data["intensity_2025"] / row["efficiency_index"] * row["fleet_factor"] * (1 - row["propulsion_share"])
    out = {}
    for tag, cut in (("10%", 0.10), ("14%", 0.14)):
        needed_mix = data["intensity_2019"] * (1 - cut) / dry * baseline_mix
        out[tag] = max(0.0, (1 - needed_mix) / a["saf_lifecycle_reduction"])
    return out


# Levers are attributed in this fixed order; attribution of overlapping levers is
# order-dependent, so the order is part of the model definition, not a UI choice.
LEVER_ORDER = [("fleet_renewal", "Fleet renewal"), ("novel_propulsion", "Novel propulsion"),
               ("ground_elec", "Ground electrification"), ("saf", "SAF")]


def _residual_2040(inputs, data, a, horizon, saf_on):
    row = emissions.physical_year(NETZERO_YEAR, inputs, data, a, horizon)
    share = 0.0
    if saf_on:
        target = emissions.target_saf_share(NETZERO_YEAR, data["base_saf_share"],
                                            inputs.saf_share_2030, inputs.saf_share_2040, BASE_YEAR)
        supply = saf.us_supply(NETZERO_YEAR, inputs.saf_supply_case, inputs.post_2035_growth, a)
        share = min(target, supply / row["liquid_fuel_gal"]) if row["liquid_fuel_gal"] else 0.0
    return emissions.intensity_and_emissions(row, share, a, data)["residual_emis"]


def _abatement_breakdown(inputs, data, a, horizon):
    """Cumulative 2040 abatement, lever by lever, from a no-lever counterfactual."""
    off = dataclasses.replace(inputs, fleet_renewal=0, novel_propulsion=0, ground_elec=0)
    steps, previous = [], _residual_2040(off, data, a, horizon, saf_on=False)
    baseline = previous
    for key, label in LEVER_ORDER:
        if key == "saf":
            off = dataclasses.replace(off, **{k: getattr(inputs, k) for k, _ in LEVER_ORDER[:-1]})
            current = _residual_2040(off, data, a, horizon, saf_on=True)
        else:
            off = dataclasses.replace(off, **{key: getattr(inputs, key)})
            current = _residual_2040(off, data, a, horizon, saf_on=False)
        steps.append((label, current - previous))
        previous = current
    return dict(baseline=baseline, steps=steps, residual=previous)
