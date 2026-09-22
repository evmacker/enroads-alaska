# Alaska Airlines decarbonization explorer

A stripped-down En-ROADS for one airline. A small deterministic model engine under a
very simple interface: move a few levers, see whether the 2030 intensity target lands
and whether 2040 net zero is affordable.

```bash
pip install -r requirements-dev.txt   # requirements.txt alone is enough to run the app
streamlit run app.py
```

## The three outcomes

| | Question | Where |
|---|---|---|
| **2030** | Does intensity reduction vs 2019 land in Alaska's 10–14% band? | KPI grid + projection chart |
| **vs a reference** | What do Alaska's own levers buy over business as usual, a conservative path, or an all-in one? | three-way toggle on the projection |
| **2040 physical** | How many tonnes remain after efficiency, fleet, SAF, electrification and propulsion? | abatement waterfall |
| **2040 financial** | What do SAF and offsets cost, as dollars and as a share of revenue? | KPI grid |

The page opens on a 2030 | 2040 KPI grid — six matching figures per milestone year
(intensity reduction, tonnes needing offset, SAF cost, offset cost, and each cost as a
share of projected revenue) — over a full-width intensity-reduction projection with the
2030 target band shaded. A three-button toggle picks the strategy — Conservative, All-In or
Custom — and drives the whole panel: the KPI tiles, both charts and the captions. The
strategy is always the blue line; business as usual sits behind it in grey dashes and
never moves. The right-hand chart pairs tonnes still needing offset against that year's
cost, per year rather than cumulative. Below that sits the abatement waterfall, then a tab strip for SAF supply vs demand, the carbon market, the emissions
pathway, the annual table and the model notes.

The three reference pathways are **scenario definitions asserted from outside the
workbook**, not workbook data. They live in the `references` block of
`config/assumptions.yaml`; `docs/model_decisions.md` sets out what each one derives and
what it asserts, and why All-In is a stated assumption set rather than a least-cost
solution.

Three price mechanisms make "invest early, save later" expressible: the market SAF premium
falls 2%/yr with industry learning, catalytic capital discounts the premium on the volume it
funds, and the carbon planning price escalates in real terms. All are inert at the workbook's
inputs, so parity is untouched. `docs/model_decisions.md` uses them to review the hypothesis
that **delaying is cheaper to 2030 but dearer to reach net zero by 2040**. At the defaults it
holds, narrowly: Conservative is $1.52B cheaper to 2030, All-In $0.92B cheaper to 2040
($49.38B vs $50.30B). At a flat premium Conservative wins both dates. The sturdier result is
the abatement comparison: All-In keeps 65.4 Mt out of the air at $283/t against
Conservative's 6.6 Mt at $371/t — ten times the abatement, 24% less per tonne.

## Layout

```
data/raw/            source workbook
data/processed/      clean annual FAA / EIA / EPA / Alaska tables
scripts/build_data.py  deterministic rebuild of processed from raw
config/assumptions.yaml  defaults, bounds, labels, citations
src/model/core.py    run_scenario(inputs, data) -> ScenarioResult
src/model/emissions.py  intensity and residual emissions
src/model/saf.py     supply anchors, market capture, catalytic capital
src/model/finance.py SAF premium, carbon price, closure cost
src/model/targets.py outcome classification — the only place target logic lives
src/viz.py           chart builders
app.py               Streamlit UI only
tests/               workbook parity + sensitivity + app smoke tests
docs/                sources and model decisions
```

The engine imports nothing from Streamlit, and `app.py` calls `run_scenario` exactly
once per rerun and draws the result. `tests/test_app.py` enforces both.

## Documentation

| Document | Covers |
|---|---|
| `docs/variables.html` | Every input, anchor and derived quantity, and the order they depend on each other |
| `docs/weaknesses.html` | Where the model breaks — the assumptions most likely to be wrong, worst first |
| `docs/model_decisions.md` | Decisions carried from the workbook vs made during the port, and the delay-hypothesis review |
| `docs/sources.md` | Citations for every published anchor |

The two HTML documents are standalone — open them in a browser, they are not part of the app.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q      # 115 tests
```

`tests/test_parity.py` reproduces every column of the workbook's `Model` sheet for every
year 2025–2040 at `rel=1e-9`, so the Python engine is a verified port rather than a
re-implementation. See `docs/model_decisions.md` for the one known workbook discrepancy
and the two honest caveats on the finance side.
