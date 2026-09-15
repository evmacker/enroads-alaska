"""Revenue anchor, SAF premium, carbon closure cost, investable-cash headroom."""


def fuel_costs(liquid_gal, saf_gal, jet_price, premium, partner_share):
    """Net SAF premium borne by Alaska, and the share shifted to third parties."""
    net_saf_price = jet_price * (1 + premium * (1 - partner_share))
    conventional_gal = liquid_gal - saf_gal
    cost_no_saf = liquid_gal * jet_price
    cost_with_saf = conventional_gal * jet_price + saf_gal * net_saf_price
    return dict(jet_price=jet_price, saf_market_price=jet_price * (1 + premium),
                net_saf_price=net_saf_price, conventional_gal=conventional_gal,
                fuel_cost_no_saf=cost_no_saf, fuel_cost_with_saf=cost_with_saf,
                net_saf_premium=cost_with_saf - cost_no_saf,
                partner_contribution=saf_gal * jet_price * premium * partner_share)


def closure_cost(residual_emis, carbon_price, neutralization_share):
    return residual_emis * carbon_price * neutralization_share


def carbon_supply(year, observed_volume, observed_year, growth):
    """Durable removal supply grown from its one observed volume.

    There is no published forward anchor for this market the way there is for SAF, so
    growth is an explicit user input defaulting to 0% rather than a fitted trend.
    """
    if year <= observed_year:
        return observed_volume
    return observed_volume * (1 + growth) ** (year - observed_year)


def headroom(revenue, investable_pct, physical_spend, closure):
    """Can the modeled pathway be funded from the stated investable-cash budget?"""
    pool = revenue * investable_pct
    available = max(0.0, pool - physical_spend)
    return dict(investable_pool=pool, physical_decarb_spend=physical_spend,
                carbon_closure_cost=closure,
                cash_available_for_closure=available,
                closure_coverage=(available / closure) if closure > 0 else float("inf"),
                cash_headroom=((pool - physical_spend - closure) / pool) if pool > 0 else float("-inf"))
