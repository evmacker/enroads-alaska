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


def learning_factor(year, catalytic_pct, a, base_year):
    """Compounding price decline bought by sustained catalytic investment.

    The workbook has no such mechanism: this is an explicit assumption that early
    money buys cheaper SAF later, so investing before it pays off still pays off by
    2040. It starts after the same maturation lag the capacity effect uses, and
    compounds once per year thereafter.

    It moves the SAF premium only. Alaska funding SAF capacity is not a reason for the
    global carbon credit price to fall, and discounting both by the same factor would
    leave their ratio fixed - which can never change which tonne is cheaper.

    Returns exactly 1.0 when nothing is invested, which is what keeps workbook parity.
    """
    if catalytic_pct <= 0:
        return 1.0
    years_active = max(0, year - base_year - a["catalytic_lag_years"])
    rate = min(1.0, catalytic_pct * a["catalytic_learning_rate"])
    return (1 - rate) ** years_active
