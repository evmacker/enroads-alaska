"""US SAF supply: published anchors, explicit post-2035 growth, catalytic capacity."""
import math


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


def learning_factor(cum_baseline_gal, cum_added_gal, capture_share, a):
    """How far catalytic capital walks the SAF premium down, on the standard basis.

        factor = floor + (1 - floor) * (1 - LR) ** (doublings * capture_share)
        doublings = log2((baseline + added) / baseline)

    NEW, not in the workbook. Three things this gets right that a naive decay does not:

    1. WRIGHT'S LAW, NOT DOLLARS. Experience curves are quoted per DOUBLING of cumulative
       output, so the exponent is the extra doublings the money buys. An earlier version
       used dollars/$50M, which for Alaska's $5.52B implied ~10.5 doublings of US SAF
       production against the 0.07 it actually funds - a 146x overstatement.
    2. A FLOOR. SAF has a cost of production. Without `floor` the curve decays to zero and
       enough capital makes SAF cheaper than fossil jet, which cannot happen.
    3. CAPTURE. Capacity built with Alaska's money serves the whole market, so Alaska
       captures a share of the decline proportional to what it actually buys - not all of
       it. Awarding the full benefit to the funder is what made spending look free.

    Returns exactly 1.0 when nothing has been invested, which is what keeps workbook parity.
    The affine form also returns exactly 1.0 at zero doublings for ANY floor value.
    """
    if cum_added_gal <= 0 or cum_baseline_gal <= 0:
        return 1.0
    doublings = math.log2((cum_baseline_gal + cum_added_gal) / cum_baseline_gal)
    captured = doublings * min(1.0, max(0.0, capture_share))
    floor = a["saf_premium_floor_ratio"]
    return floor + (1 - floor) * (1 - a["saf_learning_rate"]) ** captured
