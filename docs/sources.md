# Sources

Every number in `data/processed/` traces to one of these. `scripts/build_data.py`
rebuilds the processed tables from `data/raw/` deterministically.

## Alaska Air Group
| Item | Source |
|---|---|
| 2019 GHG intensity baseline (1.39 t/1,000 RTM) | Alaska sustainability report |
| 2025 GHG intensity (1.33), fuel, SAF, Scope 1/2 emissions | 2025 Impact Report |
| 2025 revenue, ASMs, into-plane fuel price, capex, OCF, liquidity | 2025 10-K |
| 2026 capex guidance, aircraft commitments | 2026 Q1 / Q2 10-Q |

## External
| Series | Source |
|---|---|
| System ASM activity index 2025–2040 | [FAA Aerospace Forecast FY2026–2046, Table A-2](https://www.faa.gov/data_research/aviation/aerospace_forecasts/FY_2026-2046_Full_Forecast_Document_Tables.pdf) — annual values geometrically interpolated between published anchor years |
| Aircraft efficiency index, jet fuel price index | [EIA Annual Energy Outlook](https://www.eia.gov/outlooks/aeo/) |
| Historical US renewable jet fuel volumes | [EPA RFS RIN generation](https://www.epa.gov/fuels-registration-reporting-and-compliance-help/spreadsheet-rin-generation-and-renewable-fuel-0) |
| US SAF probable production 2030 (2.049bn gal) | [Peer-reviewed estimate](https://www.sciencedirect.com/science/article/pii/S0961953425009274) |
| US SAF announced capacity 2030 (3bn gal, upper reference only) | [DOE SAF Liftoff](https://www.energy.gov/articles/us-department-energy-releases-new-report-pathways-commercial-liftoff-sustainable-aviation) |
| US SAF 2035 base / conservative (190k / 110k bpd) | [Rystad Energy](https://www.rystadenergy.com/news/booming-biofuels-us-diesel-sustainable-aviation-fuel) |
| CORSIA reference price ($59/t midpoint, context only) | [MSCI](https://www.msci.com/research-and-insights/paper/corsia-costs-and-implications-for-the-airline-industry) |
| Durable removal planning benchmark ($200/t) | [Nasdaq / Puro](https://www.nasdaq.com/products/european-markets/carbon-removal-platform) |

## Notes on data handling
- The 2026 EPA figure is a **partial-year** cut. It is stored but excluded from charts
  and never annualized into a forward path.
- SAF forward supply is **not** fitted to EPA history — the market is too nonlinear.
  It interpolates geometrically between published anchors, then grows at an explicit
  user rate after 2035.
- DOE announced capacity is an upper reference, never treated as realized production.
