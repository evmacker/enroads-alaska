# Model decisions

The engine is a port of `Alaska_Airlines_Model_Revenue_Anchored_v3.xlsx`. Decisions
carried over from the workbook are marked **(workbook)**; decisions made during the
port are marked **(new)**.

## Boundary
Operational Scope 1 (aircraft, vehicles, facility heating) plus market-based Scope 2.
Scope 3 is excluded. CORSIA compliance cost is not modeled.

## Structural choices

**Revenue is the financial anchor (workbook).** Projected revenue = 2025 revenue ×
business activity index. It is a scale and burden denominator, not a measure of cash
availability.

**Business activity (workbook).** FAA system ASM index × (1 + user adjustment)^years.
Alaska's own two-year history is too short to extrapolate.

**Operational efficiency (workbook).** EIA aircraft efficiency index × (1 + user
adjustment)^years. The fleet-renewal lever is *incremental beyond* this baseline, which
is why its default is 0% — anything else double-counts.

**SAF supply (workbook).** Published anchors, geometric interpolation, explicit
post-2035 growth. Never fitted to EPA history.

**SAF pricing (workbook).** Net SAF price = jet price × [1 + premium × (1 − partner
share)]. Partner support shifts who pays; it never changes physical SAF volumes.

**Catalytic capital (workbook).** A share of revenue, matured after a 3-year lag, and
converted to annual gallons at the DOE-implied capital intensity. It adds *supply*
only — it never discounts the SAF price.

**Carbon pricing (workbook).** One planning price applied to the 2040 residual.
CORSIA ($59/t) and durable removals ($200/t) address different obligations, so blending
them would be false precision. Both stay documented as context.

## The three outcomes

**2030 — target band (new framing).** Three states against Alaska's 10–14% intensity
reduction: `below`, `meets`, `exceeds`. Landing above 14% is *exceeding* the target,
not failing it. This lives in `src/model/targets.py` and nowhere else.

**2040 — physical residual (new framing).** Tonnes remaining after efficiency, fleet,
SAF, electrification and propulsion. This is deliberately **not** called net zero.
Carbon closure — residual × planning price × neutralization share — is what closes it,
and the waterfall draws purchased closure as a distinct patterned series so a bought
tonne never looks like an abated one.

Lever attribution in the waterfall runs in a fixed order (fleet renewal → novel
propulsion → ground electrification → SAF). Overlapping levers make attribution
order-dependent, so the order is part of the model definition, not a UI choice.

**Offset cost is priced every year (new).** The KPI grid reports, for both 2030 and 2040,
what it would cost to neutralize that year's residual at the planning price. Only 2040
closure is actually *charged* in the financial model — `closure_cost` stays 2040-only
because it is the workbook's own column and parity depends on it. The annual figure lives
in a separate `offset_cost` field so the two never get confused.

**Carbon market supply (new, presentational only).** Alaska's annual offset demand is
charted against the durable removal market, grown from its one observed volume
(1.88 Mt, Puro CORCX, Aug/Sep 2026) at an explicit user rate defaulting to 0%. There is
no published forward anchor for this market the way there is for SAF, so nothing is
fitted — the same reasoning that keeps SAF supply on published anchors rather than a
trend line. Carbon supply **never constrains the model**; it cannot change emissions or
cost, and a test enforces that. For scale, the whole voluntary market retired 202 Mt in
2025, so Alaska's 2040 residual alone is roughly 3.5% of it and about 3.8× the entire
observed durable removal market.

**Marginal abatement cost (new).** What a tonne costs, two ways:

```
SAF $/t abated   = jet price x premium x (1 - partner share) / tonnes avoided per gallon
breakeven premium = carbon price x tonnes avoided per gallon / (jet price x (1 - partner))
```

`tonnes avoided per gallon` is derived, not assumed: 2025 reported intensity is grossed
back up to a conventional-only basis (it already contains ~0.95% SAF), divided by 2025
operating fuel, and multiplied by the 80% lifecycle reduction. It comes to **0.00734
tCO2e per gallon**, implying ~9.2 kg/gal for conventional jet fuel — in line with
published lifecycle figures, which is a useful sanity check on the whole chain.

**The SAF share cancels out of this ratio.** Twice the SAF is twice the abatement at
twice the cost, so this is a *price*, not a quantity. Algebraically the activity index,
efficiency index, fleet factor and propulsion share all cancel too. Only three inputs
move it — jet fuel price, SAF premium, partner share — and `test_model.py` pins that
invariance against eight levers, because it is the property that makes the spread
chart readable.

At the workbook defaults SAF costs **$347/t in 2030 rising to $406/t in 2040** against a
$200/t carbon price, so **offsets are the cheaper tonne in every modeled year**. The
spread closes only below a ~49-58% SAF premium, above a ~$347-406/t carbon price, or with
partners funding ~50%+ of the premium. The CORSIA midpoint of $59/t widens the gap rather
than closing it.

**Ground electrification is negligible, and that is real.** Alaska's Scope 1 ground
vehicles are 0.13% of 2025 operational emissions and 0.28% of the 2040 residual. Full
100% electrification removes ~20,123 t — about $4M at $200/t — while one 5pp step on the
2040 SAF slider moves 543,777 t, roughly 27x more. The lever is kept because it is in the
workbook and the emissions are real, but its ceiling is stated in the slider help text and
pinned by a test so it cannot drift silently. It is a completeness lever, not a decision
lever.

**2040 — financial feasibility (new).** The headline KPI:

```
Investable Cash Pool     = Projected Revenue × Investable Cash % of Revenue
Cash Available           = max(0, Pool − Physical-Decarb Spend)
Closure Coverage         = Cash Available / Carbon Closure Cost
Cash Headroom After NZ   = (Pool − Physical-Decarb Spend − Closure Cost) / Pool
```

+25% means the pathway is funded with a quarter of the budget left; −30% means it costs
30% more than the modeled budget.

### Two honest caveats on the finance side

1. **Investable cash % of revenue is an assumption, not an observation.** The default is
   **3.0%**. Alaska's 2025 OCF/revenue was 8.4%, which the app shows as a reference — but
   OCF also funds normal capex (2025 capex was $1.6bn against $1.2bn OCF), debt service
   and working capital. Calling all of it investable would overstate the budget, so the
   share is an explicit, user-editable input.
2. **Physical-decarb spend is understated.** It currently covers the net SAF premium and
   catalytic capital. Incremental fleet, ground-equipment and propulsion capex are *not*
   modeled, so a scenario leaning on those levers looks cheaper than it is. This is the
   first gap to close if the demo becomes a product.

## Known workbook discrepancy
The workbook's cached `Model` sheet cells for US SAF availability and market capture in
2036–2040 were last calculated with post-2035 growth at 0%, so they disagree with its own
`SAF Supply` tab (2040: 2.91bn vs 4.69bn gallons). The engine follows the `SAF Supply`
logic. `tests/test_parity.py` pins both readings: the full grid matches at the workbook's
stated inputs, and a second test reproduces the stale cells exactly at 0% growth.

## Testing
- `tests/test_parity.py` — every `Model` sheet column, every year 2025–2040, against the
  workbook's own cached values (`rel=1e-9`).
- `tests/test_model.py` — sensitivity and invariants with no Excel counterpart: band
  classification, monotonic supply paths, the supply constraint binding, catalytic lag,
  each physical lever, the headroom identity, carbon-price linearity, determinism.
- `tests/test_app.py` — the Streamlit app renders, reacts to sliders, survives extreme
  slider positions, and contains no business logic.
