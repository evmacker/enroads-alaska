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


def target_band_2030(outcome):
    """Where the scenario lands against the 10–14% reduction band."""
    low, high = outcome["band"]
    reduction, colour = outcome["reduction"], STATE_COLOR[outcome["state"]]
    top = max(high, reduction) * 1.4
    fig = go.Figure()
    fig.add_vrect(x0=low, x1=high, fillcolor=BAND, opacity=1, line_width=0, layer="below",
                  annotation_text="target band", annotation_position="top left",
                  annotation_font=dict(color=MUTED, size=11))
    fig.add_trace(go.Bar(
        x=[reduction], y=[""], orientation="h", marker=dict(color=colour), width=0.3,
        hovertemplate="Reduction vs 2019: %{x:.1%}<extra></extra>"))
    fig.add_annotation(x=reduction, y=0, text=f"<b>{reduction:.1%}</b>", showarrow=False,
                       xanchor="left", xshift=8, font=dict(color=INK, size=15))
    fig.update_xaxes(range=[0, top], tickformat=".0%")
    fig.update_yaxes(showgrid=False)
    return _frame(fig, 150, xtitle="Intensity reduction vs 2019  ·  Alaska target 10–14%")


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
