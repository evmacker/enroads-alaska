"""US SAF supply: published anchors, explicit post-2035 growth, catalytic capacity."""


def us_supply(year, case, post_2035_growth, a):
    """Selected-case US SAF production (gallons/yr). Geometric between published anchors."""
    y0, v0 = 2025, a["saf_2025_actual"]
    if year <= y0:
        return v0
    if case == "Conservative":
        v35 = a["saf_2035_conservative"]
        if year <= 2035:
            return v0 * (v35 / v0) ** ((year - y0) / 10)
        return v35 * (1 + post_2035_growth) ** (year - 2035)
    v30, v35 = a["saf_2030_probable"], a["saf_2035_base"]
    if year <= 2030:
        return v0 * (v30 / v0) ** ((year - y0) / 5)
    if year <= 2035:
        return v30 * (v35 / v30) ** ((year - 2030) / 5)
    return v35 * (1 + post_2035_growth) ** (year - 2035)


def catalytic_capacity(years, revenue, catalytic_pct, a):
    """Investment (=% of revenue) matures after a lag, then converts to annual gallons."""
    invest = {y: revenue[y] * catalytic_pct for y in years}
    matured, capacity = {}, {}
    for y in years:
        m = 0.0 if y < years[0] + a["catalytic_lag_years"] else sum(
            v for yy, v in invest.items() if yy <= y - a["catalytic_lag_years"])
        matured[y] = m
        capacity[y] = m / a["saf_capital_intensity"]
    return invest, matured, capacity


def offtake_share(funded_capacity_gal, saf_gal):
    """Share of Alaska's SAF that comes out of capacity its own capital built.

    You can only contract what you actually burn, so this is capped at 1.0. Capacity is
    already lagged by catalytic_lag_years, so nothing is contracted before it is built.
    """
    if saf_gal <= 0 or funded_capacity_gal <= 0:
        return 0.0
    return min(1.0, funded_capacity_gal / saf_gal)


def contracted_premium(market_premium, share, a):
    """Blended premium: contracted volume prices cost-plus, the rest pays market.

        premium = market x (1 - share x (1 - offtake_ratio))

    NEW, not in the workbook. This replaces an earlier market-wide learning curve, which
    asked Alaska's balance sheet to move a NATIONAL commodity price and then let it keep
    the benefit. On the standard Wright's-law basis that mechanism was worth 0.1% - a
    single airline consuming ~5% of US jet fuel cannot buy down the price of a commodity
    it is a minority consumer of.

    What capital can do is bilateral, which is how SAF offtakes actually work: funding a
    producer buys a contractual price on YOUR contracted volume - cost-plus, or equity
    with preferential pricing - while everything else still pays spot. So the benefit is
    volume-bound, it never touches fuel Alaska did not fund, and it is structurally
    floored: the blended premium can never fall below market x offtake_ratio, because
    cost-plus still has to cover cost.

    Returns the market premium untouched when nothing is contracted, which holds parity.
    """
    return market_premium * (1 - share * (1 - a["offtake_premium_ratio"]))
