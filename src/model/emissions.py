"""Physical pathway: activity, efficiency, fuel, SAF blend, GHG intensity, residual emissions."""


def _ramp(endpoint_2040, years_from_base, horizon):
    """Linear ramp of a 2040 endpoint lever, clamped to [0, 1]."""
    return min(1.0, max(0.0, endpoint_2040 * years_from_base / horizon))


def target_saf_share(year, base_share, s2030, s2040, base_year=2025):
    if year <= 2030:
        share = base_share + (s2030 - base_share) * ((year - base_year) / (2030 - base_year))
    else:
        share = s2030 + (s2040 - s2030) * ((year - 2030) / (2040 - 2030))
    return min(1.0, max(0.0, share))


def physical_year(year, i, b, a, horizon):
    """Everything physical for one year, before SAF supply constraint is applied."""
    n = year - b["base_year"]
    activity = b["faa_activity"][year] * (1 + i.activity_adj) ** n
    efficiency = b["eia_efficiency"][year] * (1 + i.efficiency_adj) ** n
    fleet_share = _ramp(i.fleet_renewal, n, horizon)
    fleet_factor = 1 - fleet_share * a["fleet_fuel_advantage"]
    propulsion = _ramp(i.novel_propulsion, n, horizon)
    liquid_fuel = b["base_fuel_gal"] * activity / efficiency * fleet_factor * (1 - propulsion)
    return dict(year=year, activity_index=activity, efficiency_index=efficiency,
                fleet_share=fleet_share, fleet_factor=fleet_factor,
                propulsion_share=propulsion, liquid_fuel_gal=liquid_fuel,
                ground_share=_ramp(i.ground_elec, n, horizon))


def intensity_and_emissions(row, effective_saf_share, a, b):
    """GHG intensity (t/1,000 RTM) and operational residual emissions (tCO2e)."""
    carbon_mix = 1 - effective_saf_share * a["saf_lifecycle_reduction"]
    baseline_mix = 1 - b["base_saf_share"] * a["saf_lifecycle_reduction"]
    intensity = (b["intensity_2025"] / row["efficiency_index"] * row["fleet_factor"]
                 * (carbon_mix / baseline_mix) * (1 - row["propulsion_share"]))
    aircraft = intensity * b["implied_rtm"] * row["activity_index"] / 1000
    vehicle = b["vehicle_emis"] * row["activity_index"] * (1 - row["ground_share"])
    facility = b["facility_emis"] * row["activity_index"]
    scope2 = b["scope2_emis"] * row["activity_index"]
    return dict(carbon_mix=carbon_mix, intensity=intensity,
                reduction_vs_2019=1 - intensity / b["intensity_2019"],
                aircraft_emis=aircraft, vehicle_emis=vehicle, facility_emis=facility,
                scope2_emis=scope2, residual_emis=aircraft + vehicle + facility + scope2)
