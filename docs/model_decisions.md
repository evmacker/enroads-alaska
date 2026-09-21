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

**Business-as-usual reference (new).** The projection chart carries a fixed dashed line:
FAA activity and EIA efficiency as published, SAF flat at its 2025 share, and every
Alaska-specific lever off. It is computed from a hard-coded input set, not the user's, so
it does not move when the controls move — a test asserts that across all fourteen
controls. The price and supply inputs it inherits from the config defaults provably
cannot touch intensity, which a second test pins.

BAU reaches **7.98% by 2030** and **15.18% by 2040**. That is the reference line's point:
industry efficiency alone lands *below* the 10% target floor, so the gap between the two
lines is exactly what Alaska's own levers are buying. BAU intensity reduces to
`2025 intensity / EIA efficiency index`, since a flat SAF share leaves the carbon-mix term
at 1.

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

## Reference pathways on the projection chart

The projection chart compares the live scenario against one of three fixed reference
pathways, chosen with a toggle. **These are scenario definitions asserted from outside
`Alaska_Airlines_Model_Revenue_Anchored_v3.xlsx`.** The workbook holds one parameter set,
not scenarios. The numbers therefore live in the `references` block of
`config/assumptions.yaml`, beside the inputs they set rather than inside chart code, and
`tests/test_model.py` pins every claim the UI makes about them.

How much of each line is derived from the model versus asserted here:

| Reference | Derived | Asserted |
|---|---|---|
| Business as usual | All of it — FAA activity and EIA efficiency as published, SAF held flat at its 2025 share, none of Alaska's levers | Nothing |
| Conservative | The 2030 SAF share (3.68%) is solved by `_required_saf_shares` against the published 10% band floor | One rule: the 2025→2030 SAF slope continues unchanged to 2040, which makes the whole ramp a single straight line |
| All-In | Nothing | Nine input values |

### Why All-In is a stated assumption set, not an optimization

"The most cost-effective route to net zero" is not computable here, and a naive optimizer
would draw an actively misleading line, for two reasons:

1. **Offsets are cheaper than SAF at default assumptions** — $200/t against $406/t. Cost
   minimization therefore drives SAF to zero and buys the entire residual: $3.23B total
   against $17.13B for the default scenario, at a 2040 intensity reduction of 15.2% —
   identical to business as usual. The cheapest route to "net zero" is to decarbonize
   nothing and purchase the whole residual.
2. **Three of the five physical levers have zero modeled cost.** Fleet renewal, ground
   electrification and novel propulsion carry no capex (see the caveats above), so an
   optimizer maxes them out for free. Adding fleet renewal at 50% and ground
   electrification at 100% makes a scenario *cheaper* ($7.90B vs $8.57B) while abating
   more — an artifact of the missing capex, not a finding.

So All-In states its assumptions rather than solving for them, and moves the three
zero-cost levers only marginally, precisely because maxing a free lever flatters the
result.

### Two new price mechanisms (NEW, not in the workbook)

The workbook has one flat carbon price and no link between investment and cost. Two
mechanisms were added so that "invest early, save later" is expressible at all. Both are
inert at their defaults, which is what keeps `tests/test_parity.py` passing.

| Mechanism | Where | Effect |
|---|---|---|
| Catalytic learning curve | `saf.learning_factor()`, anchor `catalytic_learning_rate: 1.0` | After the existing 3-year maturation lag, the SAF premium falls by `catalytic_pct × learning_rate` per year, compounding. At 2% of revenue that is 2%/yr. Returns exactly 1.0 when nothing is invested |
| Carbon price escalation | `finance.carbon_price_path()`, input `carbon_escalation` | The planning price grows in real terms as the cheapest credits are exhausted. Default 0% reproduces the workbook's single flat price |

**The learning curve moves the SAF premium only, and this is load-bearing.** Discounting
the carbon price by the same factor — the first thing tried — leaves the ratio between
the two prices fixed at 1.622 no matter how much is invested, so it can scale total cost
down but can *never* change which tonne is cheaper. It is also not causally credible:
Alaska funding SAF capacity is no reason for the global credit price to fall. The two
prices therefore move for different reasons and in opposite directions.

### The seven All-In assumptions

| Input | Value | Default | Why |
|---|---|---|---|
| `saf_share_2030` | 15% | 10% | Aggressive, still inside modeled US supply |
| `saf_share_2040` | 90% | 60% | Near-complete liquid-fuel substitution |
| `partner_share` | 20% | 0% | Corporate and book-and-claim partnerships carry a fifth of the premium |
| `catalytic_pct` | 2% | 0% | The early money. Abates zero tonnes directly — supply never binds here — and instead buys a 2%/yr compounding decline in the SAF premium |
| `fleet_renewal` | 20% | 0% | Marginal — capex unmodeled |
| `ground_elec` | 25% | 0% | Marginal — capex unmodeled, and the lever is 0.28% of the residual regardless |
| `novel_propulsion` | 5% | 0% | Marginal — capex unmodeled |
| `carbon_escalation` | 3.3% | 0% | A world assumption, so **Conservative carries the identical rate**. It is the rate that lifts $200/t to SAF's own $324/t by 2040 |

`saf_premium` and `carbon_price` are deliberately *not* overridden any more. An earlier
version set them by hand (0.50 and $100/t) as a proxy for "early investment drives prices
down". Now that the two mechanisms above exist, asserting the endpoint as well would
double-count the same story. All-In therefore pays for its price decline in cash and the
model reports what that buys.

### What the All-In line does not claim
- It is not a forecast, a plan, or a least-cost solution.
- It does not show Alaska physically reaching net zero: 3.52 Mt of residual remains in
  2040 and is still bought, not abated.
- Its 25.9% market capture has Alaska alone consuming roughly a quarter of modeled US SAF
  production. The model permits this; nothing here defends it.

## Does delaying cost more? Reviewing the hypothesis

The hypothesis under test: **being conservative costs less to reach 2030, but more to
reach net zero by 2040.** Conservative and All-In face the identical carbon world (3.3%
escalation); they differ only in SAF ambition and whether they invest early.

First, an identity that decides the whole question. Total cost to neutralise a fixed
quantity of emissions `T`, of which `A` is abated physically, is

```
cost = T × carbon_price + A × (saf_price − carbon_price)
```

So abating more only costs less when **SAF is the cheaper tonne**. Before the two
mechanisms were added it never was ($324/t against $200/t), and total cost rose
monotonically with SAF — $6.84B at 10% SAF to $18.26B at 90%. The hypothesis was not
merely false, it was unreachable.

With learning and escalation pulling the prices apart, SAF crosses below carbon before
2040 ($255/t against $325/t) and the picture changes:

| | Conservative | All-In |
|---|---|---|
| 2030 intensity reduction | 10.0% | 20.8% |
| 2040 intensity reduction | 20.8% | 78.2% |
| 2040 residual | 12.65 Mt | 3.52 Mt |
| 2040 SAF price | $406/t | $255/t |
| **Cost to 2030** (spend + offsets) | **$14.44B** | $16.05B |
| Cumulative spend to 2040 | $3.00B | $20.40B |
| Cumulative offsets to 2040 | $47.86B | $30.88B |
| **Cost to 2040** (net zero every year) | **$50.86B** | $51.28B |

**The verdict: the first half holds, the second half very nearly does.** Conservative is
$1.61B cheaper to 2030, exactly as hypothesised. By 2040 that lead has been ground down
to $0.42B — under 1% — because All-In's cheaper tonnes progressively offset its higher
spend. On *annual* cost in 2040 All-In is already ahead by $0.69B/yr; it simply runs out
of horizon before repaying the head start.

Where it tips outright:

| Carbon escalation | Catalytic 2% | Catalytic 3% |
|---|---|---|
| 3.3% | Conservative by $0.43B | Conservative by $2.01B |
| 4.0% | **All-In by $0.95B** | Conservative by $0.64B |
| 5.0% | **All-In by $3.10B** | **All-In by $1.52B** |
| 6.0% | **All-In by $5.50B** | **All-In by $3.92B** |

So the hypothesis is true for carbon escalation at or above roughly 4%/yr, and at 5% the
cumulative crossover lands inside the horizon, in 2038. Two cautions on reading this:

1. **More investment is not better.** Catalytic capital at 3% loses to 2% at every
   escalation rate: the extra spend outruns the extra saving. The lever has an interior
   optimum, which is worth knowing before treating it as a dial to max out.
2. **The framing does a lot of work.** The table above neutralises every year's residual.
   The model's own `closure_cost` column charges carbon only in 2040 (a workbook
   convention parity depends on), which compares sixteen years of SAF premium against one
   year of offsets and hands Conservative a $7.11B-to-$21.54B win. That framing is
   structurally biased against acting early; it is kept for parity, not because it is the
   right lens for this question.

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
  slider positions, switches between the three reference pathways, and contains no
  business logic.
