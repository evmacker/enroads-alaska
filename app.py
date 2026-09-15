"""Alaska Airlines decarbonization explorer — presentation only.

All arithmetic lives in src/model. This file reads inputs, calls run_scenario once,
and draws the result.
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
import viz  # noqa: E402
from model import ScenarioInputs, load_data, run_scenario  # noqa: E402
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
        f"<div style='padding:.7rem .9rem;border:1px solid {viz.GRID};border-radius:10px;"
        f"background:#fff;height:100%'>"
        f"<div style='color:{viz.MUTED};font-size:.78rem;text-transform:uppercase;"
        f"letter-spacing:.04em'>{label}</div>"
        f"<div style='color:{colour};font-size:1.8rem;font-weight:650;line-height:1.25'>{value}</div>"
        f"<div style='color:{viz.MUTED};font-size:.82rem'>{icon}{sub}</div></div>",
        unsafe_allow_html=True)


# ---- inputs ----------------------------------------------------------------
with st.sidebar:
    st.subheader("Scenario")
    values = {}
    for group in GROUPS:
        with st.expander(group, expanded=group in ("SAF", "Money")):
            for key, s in SPEC.items():
                if s["group"] == group:
                    values[key] = control(key)
    st.caption("Defaults reproduce the source workbook. Model runs 2025→2040.")

result = run_scenario(ScenarioInputs(**values), DATA)
o30, p40, f40 = result.outcome_2030, result.physical_2040, result.financial_2040

# ---- headline ---------------------------------------------------------------
st.markdown("#### Alaska Airlines decarbonization pathway")
st.caption("A stripped-down En-ROADS for one airline: move the levers, see whether the "
           "2030 intensity target lands and whether 2040 net zero is affordable.")

a, b, c = st.columns(3)
with a:
    tile("2030 intensity reduction", f"{o30['reduction']:.1%}", o30["label"], o30["state"])
with b:
    tile("2040 physical residual", f"{p40['residual_emis']/1e6:,.2f} Mt",
         f"{p40['reduction_vs_2019']:.0%} intensity cut — closure brings this to zero")
with c:
    tile("Cash headroom after net zero", f"{f40['cash_headroom']:+.0%}", f40["label"], f40["state"])

st.divider()

# ---- 2030 -------------------------------------------------------------------
left, right = st.columns([1, 1])
with left:
    st.markdown("**2030 — does it land in the target band?**")
    st.plotly_chart(viz.target_band_2030(o30), width="stretch",
                    config={"displayModeBar": False})
    need = o30["required_saf_share"]
    st.caption(
        f"Effective SAF share {o30['effective_saf_share']:.1%} "
        f"({o30['market_capture']:.1%} of modeled US supply). "
        f"Hitting 10% needs {need['10%']:.1%} SAF, 14% needs {need['14%']:.1%}. "
        f"Net SAF premium {money(o30['net_saf_premium'])} "
        f"({o30['saf_cost_share_revenue']:.1%} of revenue).")
with right:
    st.markdown("**2040 — what is left after the physical levers?**")
    st.plotly_chart(viz.abatement_waterfall(p40), width="stretch",
                    config={"displayModeBar": False})
    st.caption(
        f"Physical levers leave {p40['residual_emis']/1e6:,.2f} Mt in 2040; carbon closure "
        f"neutralizes it at ${values['carbon_price']:,.0f}/t. Levers are attributed in a fixed "
        f"order ({', '.join(label for _, label in LEVER_ORDER)}), since overlapping levers make "
        "attribution order-dependent.")

# ---- 2040 money -------------------------------------------------------------
st.markdown("**2040 — can the pathway be funded from the investable-cash budget?**")
st.plotly_chart(viz.budget_bar(f40), width="stretch", config={"displayModeBar": False})
coverage = f40["closure_coverage"]
st.caption(
    f"Investable cash pool {money(f40['investable_pool'])} = revenue {money(f40['revenue'])} × "
    f"{values['investable_pct']:.1%}. Physical decarb spend {money(f40['physical_decarb_spend'])}, "
    f"carbon closure {money(f40['carbon_closure_cost'])} at ${values['carbon_price']:,.0f}/t. "
    f"Closure coverage {coverage:.2f}× "
    f"({'funded' if coverage >= 1 else 'unfunded'}). "
    f"For reference, 2025 operating cash flow was "
    f"{result.diagnostics['ocf_share_revenue_2025']:.1%} of revenue — and it also funds "
    "normal capex, debt service and working capital.")

# ---- discovery --------------------------------------------------------------
st.divider()
t1, t2, t3, t4 = st.tabs(["SAF supply vs demand", "Emissions pathway", "Annual table", "Model notes"])
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
with t2:
    st.plotly_chart(viz.emissions_pathway(result.pathway), width="stretch",
                    config={"displayModeBar": False})
    st.caption("Operational Scope 1 + market-based Scope 2. Scope 3 is excluded from the model.")
with t3:
    cols = ["year", "activity_index", "efficiency_index", "liquid_fuel_gal", "effective_saf_share",
            "saf_availability", "market_capture", "intensity", "reduction_vs_2019",
            "residual_emis", "revenue", "net_saf_premium", "investable_pool", "closure_cost"]
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
        "- **Catalytic capital** adds US SAF capacity after a 3-year lag. It never discounts "
        "the SAF price.\n"
        "- Waterfall levers are attributed in a fixed order "
        f"({', '.join(label for _, label in LEVER_ORDER)}); "
        "overlapping levers make attribution order-dependent.\n"
        f"- Not modeled: {', '.join(result.diagnostics['not_modeled'])}.")
    st.markdown("**Sources**")
    st.markdown("\n".join(f"- [{k}]({v})" for k, v in DATA["config"]["sources"].items()))
