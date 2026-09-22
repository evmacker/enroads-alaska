"""Alaska Airlines decarbonization explorer — presentation only.

All arithmetic lives in src/model. This file reads inputs, calls run_scenario once,
and draws the result.
"""
import dataclasses
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
import viz  # noqa: E402
from model import (abatement_economics, bau_reference, default_inputs,  # noqa: E402
                   load_data, preset_inputs, preset_scenarios, run_scenario)
from model.core import LEVER_ORDER, SCENARIO_ORDER  # noqa: E402

st.set_page_config(page_title="Alaska Airlines decarbonization", page_icon="✈️", layout="wide")
DATA = load_data()
SPEC = DATA["config"]["inputs"]
GROUPS = ["SAF", "Operations", "Money", "Baselines"]
REFS = DATA["config"]["references"]


LEVERS = [k for k, s in SPEC.items() if s.get("visible", True) and s["fmt"] != "choice"]


def _shown(key, raw):
    """Sliders hold percentages as 0-100, everything else at face value."""
    return float(raw) * 100 if SPEC[key]["fmt"] == "pct" else float(raw)


for _k in LEVERS:                      # seed once, before any widget reads it
    if f"in_{_k}" not in st.session_state:
        st.session_state[f"in_{_k}"] = _shown(_k, SPEC[_k]["default"])


def _lever_touched():
    """Moving any lever means you have left the preset behind."""
    st.session_state.scenario = "custom"


def _strategy_picked():
    """Picking a preset pushes its own values back into the sidebar."""
    name = st.session_state.get("scenario")
    if not name or name == "custom":
        return
    chosen = dataclasses.asdict(preset_inputs(name, DATA))
    for key in LEVERS:
        st.session_state[f"in_{key}"] = _shown(key, chosen[key])


def control(key):
    s, state = SPEC[key], f"in_{key}"
    if s["fmt"] == "choice":
        return st.selectbox(s["label"], s["options"], help=s["help"])
    if s["fmt"] == "pct":
        return st.slider(s["label"], s["min"] * 100, s["max"] * 100, step=s["step"] * 100,
                         format="%.1f%%", help=s["help"], key=state,
                         on_change=_lever_touched) / 100
    return st.slider(s["label"], float(s["min"]), float(s["max"]), step=float(s["step"]),
                     format="$%.0f", help=s["help"], key=state, on_change=_lever_touched)


def money(x):
    return f"${x/1e9:,.2f}B" if abs(x) >= 1e9 else f"${x/1e6:,.0f}M"


def md_money(x):
    r"""Same figure, safe for st.caption: two bare $ in one markdown block become LaTeX."""
    return money(x).replace("$", r"\$")


def tile(label, value, sub, state=None):
    colour = viz.STATE_COLOR.get(state, viz.INK)
    icon = f"{viz.STATE_ICON[state]} " if state else ""
    st.markdown(
        f"<div style='padding:.55rem .75rem;border:1px solid {viz.GRID};border-radius:9px;"
        f"background:#fff;height:100%;min-height:5.4rem'>"
        f"<div style='color:{viz.MUTED};font-size:.72rem;line-height:1.3'>{label}</div>"
        f"<div style='color:{colour};font-size:1.45rem;font-weight:650;line-height:1.35'>{value}</div>"
        f"<div style='color:{viz.MUTED};font-size:.72rem;line-height:1.3'>{icon}{sub}</div></div>",
        unsafe_allow_html=True)


def milestone_tiles(m):
    """The six KPI figures for one milestone year, in the 3x2 grid from the layout spec."""
    rows = [
        [(f"{m['year']} intensity reduction", f"{m['reduction']:.1%}", m["label"], m["state"]),
         ("Carbon emissions needing offset", f"{m['residual_emis']/1e6:,.2f} Mt",
          (f"{m['residual_vs_base']:+.1%} vs 2025" if m["residual_vs_base"] is not None
           else "residual after physical levers"), m["absolute_state"])],
        [("Total cost to invest in SAF", money(m["saf_cost"]),
          "net premium after partner support", None),
         ("Total cost to buy carbon offsets", money(m["offset_cost"]),
          f"at ${m['carbon_price']:,.0f}/t", None)],
        [("Share of proj. revenue to SAF", f"{m['saf_share_revenue']:.1%}",
          f"of {money(m['revenue'])} revenue", None),
         ("Share of revenue to offsets", f"{m['offset_share_revenue']:.1%}",
          f"of {money(m['revenue'])} revenue", None)],
    ]
    for row in rows:
        for column, args in zip(st.columns(2), row):
            with column:
                tile(*args)


# ---- inputs ----------------------------------------------------------------
with st.sidebar:
    st.subheader("Scenario")
    values = {}
    for group in GROUPS:
        keys = [k for k, s in SPEC.items() if s["group"] == group and s.get("visible", True)]
        if not keys:
            continue
        with st.expander(group, expanded=group in ("SAF", "Money")):
            for key in keys:
                values[key] = control(key)
    st.caption("These are the selected strategy's own values. Move any of them and the "
               "strategy switches to Custom. Model runs 2025→2040.")

custom_inputs = dataclasses.replace(default_inputs(DATA), **values)
SCENARIOS = {**preset_scenarios(),
             "custom": dict(key="custom", label=REFS["custom"]["label"],
                            note=REFS["custom"]["note"], inputs=custom_inputs,
                            result=run_scenario(custom_inputs, DATA))}

# ---- headline ---------------------------------------------------------------
st.markdown("#### Alaska Airlines decarbonization pathway")
st.caption("A stripped-down En-ROADS for one airline: pick a strategy, see whether the "
           "2030 intensity target lands and what the 2040 bill looks like.")

picker, _ = st.columns([2, 3])
with picker:
    choice = st.segmented_control("Strategy", options=list(SCENARIO_ORDER), default="custom",
                                  format_func=lambda k: SCENARIOS[k]["label"], key="scenario",
                                  on_change=_strategy_picked)
scn = SCENARIOS[choice or "custom"]     # segmented_control returns None when deselected
inputs, result = scn["inputs"], scn["result"]
o30, p40, f40 = result.outcome_2030, result.physical_2040, result.financial_2040

left, right = st.columns(2, gap="medium")
for column, year in ((left, 2030), (right, 2040)):
    with column:
        st.markdown(f"<div style='text-align:center;font-size:1.1rem;font-weight:650;"
                    f"padding-bottom:.45rem'>{year}</div>", unsafe_allow_html=True)
        milestone_tiles(result.milestones[year])
        ms = result.milestones[year]
        if ms["state"] in ("meets", "exceeds") and (ms["residual_vs_base"] or 0) > 0.005:
            st.caption(f":orange[Meets the intensity target and still emits "
                       f"{ms['residual_vs_base']:+.1%} more carbon than 2025 — "
                       f"growth outruns efficiency.]")

st.markdown("")
BAU = bau_reference()

# Gentle left-to-right reveal. The keyframe name carries the strategy key, so switching
# strategy changes animation-name and the browser replays the sweep. fill-mode stays at
# its default, so the clip is gone once it lands and never interferes with hover.
st.markdown(
    f"<style>@keyframes unfurl-{scn['key']}{{from{{clip-path:inset(0 100% 0 0)}}"
    f"to{{clip-path:inset(0 0 0 0)}}}}"
    f".st-key-projection [data-testid='stPlotlyChart'],"
    f".st-key-cost [data-testid='stPlotlyChart']"
    f"{{animation:unfurl-{scn['key']} 900ms ease-out}}</style>", unsafe_allow_html=True)

chart_left, chart_right = st.columns(2, gap="medium")
with chart_left:
    with st.container(key="projection"):
        st.plotly_chart(viz.intensity_projection(result.pathway, o30, BAU, scn["label"]),
                        width="stretch", config={"displayModeBar": False})
with chart_right:
    with st.container(key="cost"):
        st.plotly_chart(viz.offset_and_cost(result.pathway, scn["label"]),
                        width="stretch", config={"displayModeBar": False})

econ = abatement_economics(result.pathway)
st.caption(
    f"**{scn['label']}** — {scn['note']}"
    + ("" if scn["key"] == "custom" else
       " *The sidebar shows this strategy's values; moving any of them switches to Custom.*"))
st.caption(
    f"Over 2025–2040 this pathway keeps **{econ['cumulative_abated_vs_bau']/1e6:,.1f} Mt** out "
    f"of the air versus business as usual, for **{md_money(econ['abatement_spend'])}** of "
    f"abatement spend — **\\${econ['cost_per_tonne_abated']:,.0f} per tonne actually abated**. "
    f"That needs no carbon price and no discounting, so unlike the totals it cannot be moved "
    f"by a framing choice.")

need = o30["required_saf_share"]
y30, y40 = (result.pathway.set_index("year").loc[y] for y in (2030, 2040))
st.caption(
    f"Left: intensity reduction vs 2019, against a business-as-usual line that never moves "
    f"({BAU['reduction_2030']:.1%} by 2030, {BAU['reduction_2040']:.1%} by 2040). "
    f"Right: tonnes still needing offset against what each year costs — premium borne plus "
    f"capital deployed plus residual bought — "
    f"${y30['annual_cost']/1e9:,.2f}B in 2030 rising to ${y40['annual_cost']/1e9:,.2f}B in "
    f"2040, never cumulative. "
    f"2030 effective SAF share {o30['effective_saf_share']:.1%} "
    f"({o30['market_capture']:.1%} of modeled US supply). Hitting 10% needs "
    f"{need['10%']:.1%} SAF, 14% needs {need['14%']:.1%}. Offset cost assumes the full "
    f"residual is neutralized at that year's planning price "
    f"(${result.milestones[2030]['carbon_price']:,.0f}/t in 2030, "
    f"${p40['carbon_price']:,.0f}/t in 2040) — in the model only 2040 closure is actually "
    "charged; the 2030 figure is what it would cost today.")

st.divider()
st.markdown("**2040 — what is left after the physical levers?**")
st.plotly_chart(viz.abatement_waterfall(p40), width="stretch", config={"displayModeBar": False})
st.caption(
    f"Physical levers leave {p40['residual_emis']/1e6:,.2f} Mt in 2040; carbon closure "
    f"neutralizes it at ${p40['carbon_price']:,.0f}/t. Levers are attributed in a fixed "
    f"order ({', '.join(label for _, label in LEVER_ORDER)}), since overlapping levers make "
    "attribution order-dependent.")

# ---- discovery --------------------------------------------------------------
st.divider()
t1, tc, tp, t2, t3, t4 = st.tabs(["SAF supply vs demand", "Carbon market", "Cost per tonne",
                                  "Emissions pathway", "Annual table", "Model notes"])
with t1:
    st.plotly_chart(viz.saf_supply_chart(result.pathway, DATA["saf_history"]),
                    width="stretch", config={"displayModeBar": False})
    gap = p40["supply_gap_gal"]
    st.caption("EPA RFS full-year actuals through 2025 (2026 is a partial-year cut and is "
               "excluded); forward supply follows published anchors "
               "(2030 probable production, Rystad 2035 case) plus explicit growth. "
               + (f"This scenario is short {gap/1e6:,.0f}M gallons in 2040, so the "
                  "effective SAF share is capped below the target."
                  if gap > 0 else "This scenario stays inside modeled US supply."))
with tc:
    st.plotly_chart(viz.carbon_market_chart(result.pathway, DATA), width="stretch",
                    config={"displayModeBar": False})
    crossover = viz._crossover_year(result.pathway)
    st.caption(
        f"Alaska's 2040 residual of {p40['residual_emis']/1e6:,.2f} Mt against a durable removal "
        f"market observed at {DATA['removal_volume']/1e6:,.2f} Mt "
        f"({DATA['removal_volume_year']}) and a whole voluntary market of "
        f"{DATA['voluntary_volume']/1e6:,.0f} Mt retired in {DATA['voluntary_volume_year']}. "
        + (f"At the selected growth rate the removal market covers Alaska from {crossover}."
           if crossover else
           "At the selected growth rate the durable removal market never covers Alaska alone — "
           "raise 'durable removal market growth' in the sidebar to find the rate that would.")
        + " Log scale. This chart is presentational: carbon supply never constrains the model.")

with tp:
    st.plotly_chart(viz.abatement_cost_chart(result.pathway), width="stretch",
                    config={"displayModeBar": False})
    y40 = result.pathway.set_index("year").loc[2040]
    crossing = viz._abatement_crossover(result.pathway)
    st.caption(
        f"A tonne abated by SAF costs ${y40['saf_cost_per_tonne']:,.0f} in 2040 against "
        f"${y40['carbon_price']:,.0f} for a carbon credit — "
        + (f"SAF is the cheaper tonne from {crossing}."
           if crossing else
           f"offsets are cheaper by ${abs(y40['abatement_spread']):,.0f}/t in every modeled year.")
        + f" The SAF line is a *price*, not a quantity: it does not move with how much SAF you "
          f"buy, or with efficiency, fleet, propulsion or activity. Only three things move it — "
          f"the jet fuel price, the SAF premium, and the partner-funded share. So SAF becomes the "
          f"cheaper tonne in 2040 below a {y40['breakeven_premium']:.0%} premium, or above a "
          f"${y40['saf_cost_per_tonne']:,.0f}/t carbon price. For reference the CORSIA midpoint is "
          f"$59/t, which widens the gap rather than closing it.")

with t2:
    st.plotly_chart(viz.emissions_pathway(result.pathway), width="stretch",
                    config={"displayModeBar": False})
    st.caption("Operational Scope 1 + market-based Scope 2. Scope 3 is excluded from the model.")
with t3:
    cols = ["year", "activity_index", "efficiency_index", "liquid_fuel_gal", "effective_saf_share",
            "saf_availability", "market_capture", "intensity", "reduction_vs_2019",
            "residual_emis", "revenue", "net_saf_premium", "offset_cost", "carbon_supply",
            "saf_cost_per_tonne", "abatement_spread", "breakeven_premium",
            "investable_pool", "closure_cost"]
    st.dataframe(result.pathway[cols], width="stretch", hide_index=True, height=440)
    st.download_button("Download pathway CSV", result.pathway.to_csv(index=False),
                       "alaska_pathway.csv", "text/csv")
with t4:
    st.markdown(
        "- **2030 outcome** is Alaska's 10–14% intensity reduction vs 2019. Above 14% is "
        "*exceeding* the target, not failing it.\n"
        "- **2040 physical residual** is what remains after efficiency, fleet, SAF, "
        "electrification and propulsion. Carbon closure — residual × planning price × "
        "neutralization share — is what takes it to zero.\n"
        "- **Investable cash** is an explicit budget assumption, not observed free cash flow. "
        "Physical decarb spend currently covers the net SAF premium and catalytic capital; "
        "incremental fleet, ground and propulsion capex are **not** modeled, so the spend "
        "side is understated.\n"
        "- **Catalytic capital buys a contract, not a market price.** It funds capacity "
        "that comes online after a 3-year lag, and Alaska then prices that volume "
        "cost-plus while the rest of its SAF pays spot — so the discount is bounded by "
        "how much of its own fuel it funded, and never reaches fuel it did not. An "
        "earlier version instead walked the whole national SAF price down and let Alaska "
        "keep the benefit; on a standard learning curve that was worth 0.1%, because one "
        "airline taking ~5% of US jet fuel cannot move a commodity price. It still abates "
        "zero tonnes directly unless supply binds.\n"
        "- **The CVC line reads as a cost because there is no balance sheet.** The "
        "premium saving is real — about a quarter of the outlay — but the model expenses "
        "the whole investment and books no asset against the capacity it bought, so "
        "deploying capital always raises total cost here.\n"
        "- **Post-2035 SAF growth of 0% is a stress test, not a neutral default.** It "
        "asserts US production flatlines for five years. ~1%/yr is the conservative floor.\n"
        "- **Ground electrification barely moves the result, and that is real, not a bug.** "
        "Alaska's ground vehicles are 0.28% of the 2040 operational residual; 100% "
        "electrification removes ~20k t, about $4M at $200/t. One 5pp step on the 2040 SAF "
        "slider moves 27x more.\n"
        "- Waterfall levers are attributed in a fixed order "
        f"({', '.join(label for _, label in LEVER_ORDER)}); "
        "overlapping levers make attribution order-dependent.\n"
        f"- Not modeled: {', '.join(result.diagnostics['not_modeled'])}.")
    st.markdown("**Sources**")
    st.markdown("\n".join(f"- [{k}]({v})" for k, v in DATA["config"]["sources"].items()))
