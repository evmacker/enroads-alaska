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

At the workbook inputs (flat premium) SAF costs **$347/t in 2030 rising to $406/t in 2040**
against a $200/t carbon price, so **offsets are the cheaper tonne in every modeled year**.
At the app defaults — premium falling 2%/yr, carbon price escalating 3.3%/yr — SAF falls to
$299/t in 2040 against $325/t, and **SAF becomes the cheaper tonne from 2038**. The
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

1. **Offsets are cheaper than SAF at the workbook inputs** — $200/t against $406/t. Cost
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
mechanisms were added so "invest early, save later" is expressible at all. Both are inert
at their defaults, which is what keeps `tests/test_parity.py` passing.

| Mechanism | Where | Effect |
|---|---|---|
| Catalytic buy-down | `saf.learning_factor()` | `SAF premium(t) = market premium(t) × (1 − r) ^ (cumulative CVC(t) / tranche)`, with `r` = 1% per $50M tranche deployed. Returns exactly 1.0 when nothing is invested |
| Carbon escalation | `finance.carbon_price_path()`, input `carbon_escalation` | The planning price grows in real terms as the cheapest credits are exhausted. Default 0% reproduces the workbook's single flat price |

**The exponent is money deployed, not years elapsed.** That is the point: the discount is
negligible while little has been spent and compounds as capital accumulates, so catalytic
capital is a real short-term cost buying a real long-term saving rather than a free lunch
that arrives on a timer. It scales exactly — doubling `catalytic_pct` doubles cumulative
spend and therefore squares the discount, which a test pins.

**It moves the SAF premium only, and this is load-bearing.** Discounting the carbon price
by the same factor — the first thing tried — leaves the ratio between the two prices fixed
at 1.622 no matter how much is invested, so it can scale total cost down but can *never*
change which tonne is cheaper. It is also not causally credible: Alaska funding SAF
capacity is no reason for the global credit price to fall. The two prices move for
different reasons, in opposite directions.

### The seven All-In assumptions

| Input | Value | Default | Why |
|---|---|---|---|
| `saf_share_2030` | 15% | 10% | Aggressive, still inside modeled US supply |
| `saf_share_2040` | 90% | 60% | Near-complete liquid-fuel substitution |
| `partner_share` | 20% | 0% | Corporate and book-and-claim partnerships carry a fifth of the premium |
| `catalytic_pct` | 2% | 0% | The early money — $5.52B cumulative by 2040, which buys the premium down to 33% of market. Abates zero tonnes directly, since supply never binds here |
| `fleet_renewal` | 20% | 0% | Marginal — capex unmodeled |
| `ground_elec` | 25% | 0% | Marginal — capex unmodeled, and the lever is 0.28% of the residual regardless |
| `novel_propulsion` | 5% | 0% | Marginal — capex unmodeled |
| `carbon_escalation` | 3.3% | 0% | A world assumption, so **Conservative carries the identical rate**. It is the rate that lifts $200/t to SAF's undiscounted $324/t by 2040 |

`saf_premium` and `carbon_price` are deliberately *not* overridden. An earlier version set
them by hand (0.50 and $100/t) as a proxy for "early investment drives prices down". Now
that the mechanisms above exist, asserting the endpoint as well would double-count the
same story. All-In pays for its price decline in cash and the model reports what that buys.

### What the All-In line does not claim
- It is not a forecast, a plan, or a least-cost solution.
- It does not show Alaska physically reaching net zero: 3.52 Mt of residual remains in
  2040 and is still bought, not abated.
- Its 25.9% market capture has Alaska alone consuming roughly a quarter of modeled US SAF
  production. The model permits this; nothing here defends it.

## Does delaying cost more? Reviewing the hypothesis

The hypothesis under test: **being conservative costs less to reach 2030, but more to
reach net zero by 2040.** Both strategies face the identical carbon world; they differ
only in SAF ambition and whether they deploy catalytic capital.

**Verdict: the first half holds. The second half does not.** An earlier version of this
model reported that All-In won by $6.48B. That finding was an artifact of two defects in
`saf.learning_factor()`, both since corrected:

1. **The buy-down was ~146× too strong.** It used an exponent of dollars/$50M. On the
   standard Wright's-law basis, Alaska's $5.52B buys **0.072 extra doublings** of
   cumulative US SAF output — a premium multiplier of ~0.99, against the 0.33 the old
   formula produced.
2. **Alaska booked 100% of a price decline it funded a quarter of.** Capacity built with
   its money serves the whole market.

Together those made catalytic capital worth **0.1%** off the premium — which is the
correct answer to the question that mechanism was asking, and the wrong question. A single
airline taking ~5% of US jet fuel cannot buy down a national commodity price. Catalytic
capital is therefore modeled as what it actually is: **a bilateral offtake**. Funding a
producer buys a cost-plus price on *your contracted volume* (`offtake_premium_ratio: 0.70`,
a 30% discount on the premium) while everything else still pays spot. The benefit is
volume-bound, never reaches fuel Alaska did not fund, and is structurally floored because
cost-plus still covers cost.

That mechanism is worth real money — All-In contracts 24% of its 2040 SAF and saves
about a quarter of its $5.52B outlay — but on its own it never repays the spend.

**What does flip the total is the market premium decline** (`saf_premium_decline`, 2%/yr
by default, new, not from the workbook). SAF gets cheaper every year while offsets get
dearer, so All-In's extra SAF replaces tonnes that would otherwise be bought at a rising
carbon price. The table uses the app defaults.

| | Conservative | All-In |
|---|---|---|
| 2030 intensity reduction | 10.0% | 20.8% |
| 2040 intensity reduction | 20.8% | 78.2% |
| 2040 residual | 12.65 Mt | 3.52 Mt |
| 2040 SAF price | $299/t | $222/t |
| **Cumulative to 2030** | **$14.41B** | $15.93B |
| **Cumulative to 2040** | $50.30B | **$49.38B** |
| Cumulative abatement vs BAU | 6.58 Mt | **65.35 Mt** |
| **Cost per tonne actually abated** | $371/t | **$283/t** |

**The hypothesis now holds at both dates.** Conservative is $1.52B cheaper to 2030; All-In
is $0.92B cheaper to 2040. The margin is thin and rests on the decline assumption: at a flat
premium (0%) Conservative wins both dates, $50.86B against $52.66B.

**One caveat that cuts the other way, and the model cannot express it.** There is no
balance sheet here: the full $5.52B of catalytic capital is expensed, and no asset is
booked against the capacity it bought. In reality that spend buys equity in operating
plants with residual value and an ongoing claim on output. So the CVC leg is charged at
full cost and credited only with the fuel discount it produces. Read $49.38B as an upper
bound on All-In's cost, not a settled figure.

### What survives, and what the tool should lead with

The cost comparison was never the strongest argument for acting early, and it is not the
one to make. This is:

> All-In keeps **65.35 Mt** out of the air for **$18.49B** of abatement spend — **$283 per
> tonne**. Conservative keeps **6.58 Mt** for **$2.44B** — **$371 per tonne**. Ten times
> the abatement, at 24% less per tonne.

That statement needs no carbon price, no escalation rate and no discounting, so no framing
choice can manufacture or destroy it. The app now leads with it. The honest summary of
this model is **"decarbonizing costs less per tonne, and less in total only if SAF keeps
getting cheaper"**.

### Two cautions that remain

1. **Framing still decides the total-cost winner.** The table above neutralises every
   year's residual. The model's own `closure_cost` column charges carbon only in 2040 — a
   workbook convention parity depends on — which compares sixteen years of SAF premium
   against one year of offsets and gives Conservative $6.56B against All-In's $14.12B. It
   is kept for parity, not because it is the right lens.
2. **Neither pathway can actually buy its residual.** See `docs/weaknesses.html` item 1.
   "Net zero 2040" in this tool means the residual was priced, not that it was procurable.

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
