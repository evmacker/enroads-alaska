"""Chart builders. Palette is the validated default instance, light surface only
(the app pins base="light"), so every colour below is checked against #fcfcfb.
Validator: 3 categorical slots, all-pairs, light — all checks pass; aqua carries a
contrast WARN, so it is always direct-labelled and mirrored in the annual table.
"""
import plotly.graph_objects as go

SERIES = {"blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a"}
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
INK, MUTED, GRID, BAND, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#cde2fb", "#fcfcfb"

STATE_COLOR = {"below": STATUS["critical"], "meets": STATUS["good"], "exceeds": SERIES["blue"],
               "infeasible": STATUS["critical"], "tight": STATUS["warning"], "comfortable": STATUS["good"]}
STATE_ICON = {"below": "✕", "meets": "✓", "exceeds": "▲",
              "infeasible": "✕", "tight": "!", "comfortable": "✓"}

MT, BN = 1e6, 1e9


def _frame(fig, height, xtitle=None, ytitle=None, legend=False):
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8), plot_bgcolor=SURFACE,
        paper_bgcolor="rgba(0,0,0,0)", font=dict(color=INK, size=13), bargap=0.3,
        hoverlabel=dict(bgcolor=SURFACE, font_size=13, bordercolor=GRID),
        showlegend=legend, legend=dict(orientation="h", y=1.14, x=0, traceorder="normal",
                                       font=dict(color=MUTED), title=None))
    fig.update_xaxes(title=xtitle, gridcolor=GRID, zeroline=False, linecolor=GRID,
                     title_font=dict(color=MUTED, size=12), tickfont=dict(color=MUTED))
    fig.update_yaxes(title=ytitle, gridcolor=GRID, zeroline=False, linecolor=GRID,
                     title_font=dict(color=MUTED, size=12), tickfont=dict(color=MUTED))
    return fig


def intensity_projection(pathway, outcome, bau=None, target_year=2030):
    """Intensity reduction vs 2019 across the pathway, with the 2030 target band shaded.

    `bau` is a fixed business-as-usual reference that ignores the scenario controls, so
    the gap between the two lines is what Alaska's own levers are actually buying.
    """
    low, high = outcome["band"]
    colour = STATE_COLOR[outcome["state"]]
    reduction = outcome["reduction"]
    fig = go.Figure()
    fig.add_hrect(y0=low, y1=high, fillcolor=BAND, opacity=1, line_width=0, layer="below",
                  annotation_text="2030 target band 10-14%", annotation_position="top left",
                  annotation_font=dict(color=MUTED, size=11))
    if bau is not None:
        ref = bau["pathway"]
        fig.add_trace(go.Scatter(
            x=ref.year, y=ref.reduction_vs_2019, mode="lines",
            name="Business as usual (published baselines only)",
            line=dict(color=MUTED, width=1.5, dash="dash"),
            hovertemplate="%{x}: %{y:.1%} below 2019<extra>Business as usual</extra>"))
        end = ref.iloc[-1]
        fig.add_annotation(x=end.year, y=end.reduction_vs_2019, text="business as usual",
                           showarrow=False, xanchor="right", yshift=-14,
                           font=dict(color=MUTED, size=11))
    fig.add_trace(go.Scatter(
        x=pathway.year, y=pathway.reduction_vs_2019, mode="lines", name="Modeled scenario",
        line=dict(color=SERIES["blue"], width=2),
        hovertemplate="%{x}: %{y:.1%} below 2019<extra>Modeled</extra>"))
    fig.add_trace(go.Scatter(
        x=[target_year], y=[reduction], mode="markers", name=f"{target_year} outcome",
        marker=dict(color=colour, size=12, line=dict(color=SURFACE, width=2)),
        hovertemplate=f"{target_year}: %{{y:.1%}} below 2019<extra></extra>"))
    fig.add_annotation(x=target_year, y=reduction, text=f"<b>{reduction:.1%}</b>", showarrow=False,
                       yshift=20, font=dict(color=INK, size=14))
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    return _frame(fig, 330, ytitle="Intensity reduction vs 2019", legend=bau is not None)


def abatement_waterfall(physical):
    """2040 tonnes: physical levers cut emissions; carbon closure pays for the rest.

    The two are drawn as different traces on purpose — cutting a tonne and buying a
    tonne are not the same act, and the model refuses to call the residual 'net zero'.
    """
    ab, residual = physical["abatement"], physical["residual_emis"]
    labels = ["2040 unabated"] + [s[0] for s in ab["steps"]] + ["Physical residual"]
    values = [ab["baseline"] / MT] + [s[1] / MT for s in ab["steps"]] + [0]
    fig = go.Figure(go.Waterfall(
        x=labels, y=values, measure=["absolute"] + ["relative"] * len(ab["steps"]) + ["total"],
        name="Physical abatement", orientation="v",
        decreasing=dict(marker=dict(color=SERIES["aqua"])),
        increasing=dict(marker=dict(color=SERIES["orange"])),
        totals=dict(marker=dict(color=SERIES["blue"])),
        connector=dict(line=dict(color=GRID, width=1)),
        texttemplate="%{delta:.2f}", textposition="outside", textfont=dict(color=MUTED, size=11),
        hovertemplate="%{x}<br>%{y:.2f} MtCO2e<extra></extra>"))
    fig.add_trace(go.Bar(
        x=["Carbon closure"], y=[residual / MT], name="Carbon closure (purchased → net zero)",
        marker=dict(color=SERIES["orange"], pattern=dict(shape="/", fgcolor=SURFACE, size=5)),
        text=[f"−{residual/MT:.2f}"], textposition="outside", textfont=dict(color=MUTED, size=11),
        hovertemplate=f"Carbon closure<br>{residual:,.0f} tCO2e neutralized<extra></extra>"))
    fig.update_xaxes(tickangle=-25, tickfont=dict(size=11))
    fig.update_yaxes(range=[0, ab["baseline"] / MT * 1.12])   # headroom for outside labels
    return _frame(fig, 340, ytitle="MtCO2e in 2040", legend=True)


def budget_bar(fin):
    """2040 spend against the investable-cash pool."""
    pool = fin["investable_pool"] / BN
    parts = [("Physical decarb spend", fin["physical_decarb_spend"] / BN, SERIES["blue"]),
             ("Carbon closure", fin["carbon_closure_cost"] / BN, SERIES["orange"])]
    fig = go.Figure()
    for name, value, colour in parts:
        fig.add_trace(go.Bar(
            x=[value], y=[""], name=name, orientation="h", width=0.34,
            marker=dict(color=colour, line=dict(color=SURFACE, width=2)),
            hovertemplate=f"{name}: $%{{x:.2f}}B<extra></extra>"))
    fig.add_vline(x=pool, line=dict(color=INK, width=2, dash="dot"),
                  annotation_text=f"investable cash ${pool:,.2f}B", annotation_position="bottom right",
                  annotation_font=dict(color=INK, size=12))
    fig.update_layout(barmode="stack")
    fig.update_xaxes(tickprefix="$", ticksuffix="B", tickformat=".1f", rangemode="tozero")
    fig.update_yaxes(showgrid=False)
    return _frame(fig, 185, legend=True)


def saf_supply_chart(pathway, history):
    """US SAF supply against what this scenario asks Alaska to secure."""
    full_year = history[history.status == "Full year"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=full_year.year, y=full_year.epa_gallons / BN, name="EPA actual (US)", mode="lines+markers",
        line=dict(color=SERIES["aqua"], width=2), marker=dict(size=8),
        hovertemplate="%{y:.3f}B gal<extra>EPA actual</extra>"))
    fig.add_trace(go.Scatter(
        x=pathway.year, y=pathway.saf_availability / BN, name="US supply (modeled)", mode="lines",
        line=dict(color=SERIES["blue"], width=2),
        hovertemplate="%{y:.2f}B gal<extra>US supply</extra>"))
    fig.add_trace(go.Scatter(
        x=pathway.year, y=pathway.target_saf_gal / BN, name="Alaska requirement", mode="lines",
        line=dict(color=SERIES["orange"], width=2),
        hovertemplate="%{y:.2f}B gal<extra>Alaska requirement</extra>"))
    peak = full_year.iloc[-1]
    fig.add_annotation(x=peak.year, y=peak.epa_gallons / BN, text="EPA actual", showarrow=False,
                       yshift=16, xshift=-10, font=dict(color=MUTED, size=11))
    fig.update_yaxes(ticksuffix="B", tickformat=".1f", rangemode="tozero")
    return _frame(fig, 310, ytitle="Gallons per year", legend=True)


def emissions_pathway(pathway):
    fig = go.Figure(go.Scatter(
        x=pathway.year, y=pathway.residual_emis / MT, mode="lines",
        line=dict(color=SERIES["blue"], width=2), fill="tozeroy", fillcolor="rgba(42,120,214,0.10)",
        hovertemplate="%{x}: %{y:.2f} MtCO2e<extra></extra>"))
    fig.add_vline(x=2030, line=dict(color=MUTED, width=1, dash="dot"),
                  annotation_text="2030 target year", annotation_position="top left",
                  annotation_font=dict(color=MUTED, size=11))
    fig.update_yaxes(tickformat=".1f", rangemode="tozero")
    return _frame(fig, 310, ytitle="MtCO2e per year (operational residual)")


def carbon_market_chart(pathway, data):
    """Alaska's annual offset demand against observed carbon-market supply.

    Supply here is one observed volume grown at an explicit user rate — there is no
    published forward anchor for durable removals, so nothing is fitted or implied.
    """
    import math

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pathway.year, y=pathway.residual_emis / MT, name="Alaska offset demand", mode="lines",
        line=dict(color=SERIES["orange"], width=2),
        hovertemplate="%{y:.2f} Mt needing offset<extra>Alaska</extra>"))
    fig.add_trace(go.Scatter(
        x=pathway.year, y=pathway.carbon_supply / MT, name="Durable removal supply", mode="lines",
        line=dict(color=SERIES["blue"], width=2),
        hovertemplate="%{y:.2f} Mt available<extra>Durable removals</extra>"))
    crossover = _crossover_year(pathway)
    if crossover:
        fig.add_vline(x=crossover, line=dict(color=MUTED, width=1, dash="dot"),
                      annotation_text=f"break-even {crossover}", annotation_position="bottom right",
                      annotation_font=dict(color=INK, size=11))
    # Log scale with an explicit range: supply spans two orders of magnitude across the
    # growth slider, and autorange on a log axis mis-scales badly.
    lo = min(pathway.residual_emis.min(), pathway.carbon_supply.min()) / MT
    hi = max(pathway.residual_emis.max(), pathway.carbon_supply.max()) / MT
    fig.update_yaxes(type="log", range=[math.log10(lo * 0.55), math.log10(hi * 1.8)],
                     dtick="D2", ticksuffix=" Mt")
    return _frame(fig, 310, ytitle="MtCO2e per year (log scale)", legend=True)


def _crossover_year(pathway):
    """First year durable removal supply covers Alaska's offset demand, if it ever does."""
    covered = pathway[pathway.carbon_supply >= pathway.residual_emis]
    return int(covered.year.iloc[0]) if len(covered) else None


def abatement_cost_chart(pathway):
    """The price of a tonne, two ways: bought as SAF, or bought as a carbon credit.

    The SAF line is a marginal price, not a total — it does not move with how much SAF
    the scenario buys. Only the jet fuel price, the SAF premium and the partner-funded
    share move it, which is what makes the spread against the carbon price readable.
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pathway.year, y=pathway.saf_cost_per_tonne, name="SAF, $/t abated", mode="lines",
        line=dict(color=SERIES["orange"], width=2),
        hovertemplate="SAF: $%{y:,.0f}/t abated<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=pathway.year, y=pathway.carbon_price, name="Carbon credit, $/t", mode="lines",
        line=dict(color=SERIES["blue"], width=2), fill="tonexty", fillcolor="rgba(82,81,78,0.10)",
        hovertemplate="Carbon: $%{y:,.0f}/t<extra></extra>"))

    crossing = _abatement_crossover(pathway)
    if crossing:
        fig.add_vline(x=crossing, line=dict(color=MUTED, width=1, dash="dot"),
                      annotation_text=f"SAF becomes cheaper, {crossing}",
                      annotation_position="top left", annotation_font=dict(color=INK, size=11))
    else:
        last = pathway.iloc[-1]
        cheaper = "SAF" if last.abatement_spread < 0 else "offsets"
        fig.add_annotation(
            x=last.year, y=(last.saf_cost_per_tonne + last.carbon_price) / 2,
            text=f"<b>${abs(last.abatement_spread):,.0f}/t</b><br>{cheaper} cheaper",
            showarrow=False, xanchor="right", xshift=-10, font=dict(color=INK, size=12),
            bgcolor=SURFACE, borderpad=3)
    fig.update_yaxes(tickprefix="$", ticksuffix="/t", rangemode="tozero")
    return _frame(fig, 310, ytitle="Cost per tonne of CO2e", legend=True)


def _abatement_crossover(pathway):
    """First year a tonne abated by SAF costs no more than a tonne of offsets."""
    cheaper = pathway[pathway.abatement_spread <= 0]
    return int(cheaper.year.iloc[0]) if len(cheaper) else None
