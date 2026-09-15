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
| **2040 physical** | How many tonnes remain after efficiency, fleet, SAF, electrification and propulsion? | abatement waterfall |
| **2040 financial** | What do SAF and offsets cost, as dollars and as a share of revenue? | KPI grid |

The page opens on a 2030 | 2040 KPI grid — six matching figures per milestone year
(intensity reduction, tonnes needing offset, SAF cost, offset cost, and each cost as a
share of projected revenue) — over a full-width intensity-reduction projection with the
2030 target band shaded. Below that sits the abatement waterfall, then a tab strip for
SAF supply vs demand, the carbon market, the emissions pathway, the annual table and the
model notes.

The investable-cash headroom KPI and its budget-bar chart are still in the engine
(`financial_2040`) and in `src/viz.py::budget_bar`, but are not currently on the page.

## Layout

```
data/raw/            source workbook
data/processed/      clean annual FAA / EIA / EPA / Alaska tables
scripts/build_data.py  deterministic rebuild of processed from raw
config/assumptions.yaml  defaults, bounds, labels, citations
src/model/core.py    run_scenario(inputs, data) -> ScenarioResult
src/model/emissions.py  intensity and residual emissions
src/model/saf.py     supply anchors, market capture, catalytic capital
src/model/finance.py revenue, SAF premium, closure cost, investable-cash headroom
src/model/targets.py outcome classification — the only place target logic lives
src/viz.py           chart builders
app.py               Streamlit UI only
tests/               workbook parity + sensitivity + app smoke tests
docs/                sources and model decisions
```

The engine imports nothing from Streamlit, and `app.py` calls `run_scenario` exactly
once per rerun and draws the result. `tests/test_app.py` enforces both.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q      # 55 tests
```

`tests/test_parity.py` reproduces every column of the workbook's `Model` sheet for every
year 2025–2040 at `rel=1e-9`, so the Python engine is a verified port rather than a
re-implementation. See `docs/model_decisions.md` for the one known workbook discrepancy
and the two honest caveats on the finance side.
