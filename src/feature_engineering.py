import pandas as pd
import numpy as np

COMPOUND_CODES = {
    "SOFT": 0,
    "MEDIUM": 1,
    "HARD": 2,
    "INTERMEDIATE": 3,
    "WET": 4
}

def build_features(df):
    x = df.copy()
    x = x.sort_values(["Driver", "LapNumber"]).reset_index(drop=True)
    x["PreviousLapTime"] = x.groupby("Driver")["LapTimeSeconds"].shift(1)
    x["Previous3LapAvg"] = x.groupby("Driver")["LapTimeSeconds"].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean()
    )
    x["TyreAge"] = pd.to_numeric(x["TyreLife"], errors="coerce").fillna(0)
    x["TyreAgeSquared"] = x["TyreAge"] ** 2
    x["CompoundCode"] = x["Compound"].map(COMPOUND_CODES).fillna(1)
    x["Position"] = pd.to_numeric(x["Position"], errors="coerce").fillna(20)
    x["LapNumber"] = pd.to_numeric(x["LapNumber"], errors="coerce").fillna(0)
    x["PitStop"] = x["PitIn"].fillna(0).astype(int)
    x["TrackStatusCode"] = x["TrackStatus"].astype(str).str.extract(r"(\d+)")[0].fillna("1").astype(float)
    x["PreviousLapTime"] = x["PreviousLapTime"].fillna(x["LapTimeSeconds"].median())
    x["Previous3LapAvg"] = x["Previous3LapAvg"].fillna(x["LapTimeSeconds"].median())
    return x
