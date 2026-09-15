"""Rebuild data/processed/*.csv from the source workbook. Deterministic; no app logic."""
import pandas as pd, pathlib

RAW = pathlib.Path("data/raw/Alaska_Airlines_Model_Revenue_Anchored_v3.xlsx")
OUT = pathlib.Path("data/processed")

def main():
    faa = pd.read_excel(RAW, "FAA Forecast", skiprows=2, usecols="A:C").dropna(subset=["Year"])
    faa = faa.rename(columns={"Year": "year", "Activity Index (2025=1)": "activity_index"})
    faa[["year", "activity_index"]].astype({"year": int}).to_csv(OUT / "faa_activity.csv", index=False)

    eia = pd.read_excel(RAW, "EIA_AEO").dropna(subset=["Year"])
    eia = eia[pd.to_numeric(eia["Year"], errors="coerce").notna()]
    eia.columns = [str(c).strip() for c in eia.columns]
    eia = eia.rename(columns={"Year": "year", "Efficiency Index": "efficiency_index",
                              "Fuel Price Index:": "fuel_price_index"})
    eia[["year", "efficiency_index", "fuel_price_index"]].astype({"year": int}).to_csv(
        OUT / "eia_indices.csv", index=False)

    saf = pd.read_excel(RAW, "SAF Supply", skiprows=2, usecols="A:C").dropna(subset=["Year"])
    saf = saf.rename(columns={"Year": "year", "EPA Actual / YTD SAF (gal)": "epa_gallons",
                              "Actual Status": "status"}).dropna(subset=["epa_gallons"])
    saf.astype({"year": int}).to_csv(OUT / "saf_history.csv", index=False)

    carbon = pd.read_excel(RAW, "Carbon Markets", skiprows=2, usecols="A:H").dropna(
        subset=["Market / Instrument"])
    carbon = carbon.rename(columns={
        "Market / Instrument": "instrument", "Reference Price": "price", "Units": "units",
        "Availability / Volume": "volume_tco2e", "Timeframe": "timeframe",
        "How we use it": "use", "Status": "status", "Source URL": "source"})
    carbon.to_csv(OUT / "carbon_markets.csv", index=False)

    base = pd.read_excel(RAW, "Alaska Base", usecols="A:E").dropna(subset=["Metric"])
    base.rename(columns={"Metric": "metric", "Year": "year", "Value": "value",
                         "Units": "units", "Source": "source"}).to_csv(
        OUT / "alaska_base.csv", index=False)
    print("wrote", *[p.name for p in sorted(OUT.glob("*.csv"))])

if __name__ == "__main__":
    main()
