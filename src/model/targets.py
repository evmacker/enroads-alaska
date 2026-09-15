"""Single source of truth for outcome classification."""

BAND = (0.10, 0.14)


def classify_2030(reduction, band=BAND):
    """Below / meets / exceeds Alaska's 10-14% intensity-reduction band. >14% is not a failure."""
    low, high = band
    if reduction < low:
        return dict(state="below", label=f"Below target ({reduction:.1%} vs {low:.0%} floor)")
    if reduction <= high:
        return dict(state="meets", label=f"Meets target ({reduction:.1%}, inside {low:.0%}-{high:.0%})")
    return dict(state="exceeds", label=f"Exceeds upper target ({reduction:.1%} vs {high:.0%})")


def classify_2040_finance(cash_headroom):
    """Feasible when the pathway fits inside the modeled investable-cash budget."""
    if cash_headroom >= 0.20:
        return dict(state="comfortable", label=f"Funded with {cash_headroom:.0%} budget left")
    if cash_headroom >= 0:
        return dict(state="tight", label=f"Just funded — {cash_headroom:.0%} budget left")
    return dict(state="infeasible", label=f"Over budget by {abs(cash_headroom):.0%}")
