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
from model import default_inputs, load_data, reference_pathways, run_scenario  # noqa: E402
from model.core import LEVER_ORDER  # noqa: E402

st.set_page_config(page_title="Alaska Airlines decarbonization", page_icon="✈️", layout="wide")
DATA = load_data()
SPEC = DATA["config"]["inputs"]
GROUPS = ["SAF", "Operations", "Money", "Baselines"]


def control(key):
    s = SPEC[key]
    if s["fmt"] == "choice":
        return st.selectbox(s["label"], s["options"], help=s["help"])
    if s["fmt"] == "pct":
        v = st.slider(s["label"], s["min"] * 100, s["max"] * 100, s["default"] * 100,
                      s["step"] * 100, format="%.1f%%", help=s["help"])
        return v / 100
    return st.slider(s["label"], float(s["min"]), float(s["max"]), float(s["default"]),
                     float(s["step"]), format="$%.0f", help=s["help"])


def money(x):
    return f"${x/1e9:,.2f}B" if abs(x) >= 1e9 else f"${x/1e6:,.0f}M"


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
          "residual after physical levers", None)],
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
    st.caption("Defaults reproduce the source workbook. Model runs 2025→2040.")

inputs = dataclasses.replace(default_inputs(DATA), **values)
result = run_scenario(inputs, DATA)
o30, p40, f40 = result.outcome_2030, result.physical_2040, result.financial_2040

# ---- headline ---------------------------------------------------------------
st.markdown("#### Alaska Airlines decarbonization pathway")
st.caption("A stripped-down En-ROADS for one airline: move the levers, see whether the "
           "2030 intensity target lands and whether 2040 net zero is affordable.")

left, right = st.columns(2, gap="medium")
for column, year in ((left, 2030), (right, 2040)):
    with column:
        st.markdown(f"<div style='text-align:center;font-size:1.1rem;font-weight:650;"
                    f"padding-bottom:.45rem'>{year}</div>", unsafe_allow_html=True)
        milestone_tiles(result.milestones[year])

st.markdown("")
REFS = reference_pathways()
picker, _ = st.columns([2, 3])
with picker:
    choice = st.segmented_control("Compare against", options=list(REFS), default="bau",
                                  format_func=lambda k: REFS[k]["label"], key="reference")
ref = REFS[choice or "bau"]          # segmented_control returns None when deselected

# Gentle left-to-right reveal. The keyframe name carries the reference key, so choosing a
# different line changes animation-name and the browser replays the sweep. fill-mode stays
# at its default, so the clip is gone once it lands and never interferes with hover.
st.markdown(
    f"<style>@keyframes unfurl-{ref['key']}{{from{{clip-path:inset(0 100% 0 0)}}"
    f"to{{clip-path:inset(0 0 0 0)}}}}"
    f".st-key-projection [data-testid='stPlotlyChart']"
    f"{{animation:unfurl-{ref['key']} 900ms ease-out}}</style>", unsafe_allow_html=True)
with st.container(key="projection"):
    st.plotly_chart(viz.intensity_projection(result.pathway, o30, ref), width="stretch",
                    config={"displayModeBar": False})

need = o30["required_saf_share"]
st.caption(
    f"**{ref['label']}** — {ref['note']} It reaches {ref['reduction_2030']:.1%} by 2030 and "
    f"{ref['reduction_2040']:.1%} by 2040; the gap to the blue line is what your own sidebar "
    f"levers buy on top of it. "
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
        "- **Catalytic capital abates no tonnes unless SAF supply binds — but it does cut "
        "the price.** It adds US capacity after a 3-year lag, and after the same lag it "
        "walks the SAF premium down by `catalytic_pct × learning rate` per year, "
        "compounding. So in an unconstrained scenario it still removes exactly zero "
        "tonnes; what it buys is a cheaper tonne later. That trade is the whole "
        "short-term-cost-for-long-term-saving question, and whether it repays depends on "
        "how fast the carbon price escalates beside it.\n"
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
