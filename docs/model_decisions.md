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
