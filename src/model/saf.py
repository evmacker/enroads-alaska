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
