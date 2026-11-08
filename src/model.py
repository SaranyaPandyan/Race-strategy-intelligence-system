import os
import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

class LapTimeModel:
    def __init__(self):
        self.features = [
            "PreviousLapTime",
            "Previous3LapAvg",
            "TyreAge",
            "TyreAgeSquared",
            "CompoundCode",
            "Position",
            "LapNumber",
            "PitStop"
        ]
        self.pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", RandomForestRegressor(
                n_estimators=350,
                max_depth=14,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            ))
        ])
        self.fitted = False

    def fit(self, df):
        x = df[self.features]
        y = df["LapTimeSeconds"]
        mask = y.notna()
        self.pipeline.fit(x.loc[mask], y.loc[mask])
        self.fitted = True
        os.makedirs(os.path.join(os.getcwd(), "models"), exist_ok=True)
        joblib.dump(self.pipeline, os.path.join(os.getcwd(), "models", "race_lap_model.pkl"))

    def predict(self, row):
        if not self.fitted:
            raise RuntimeError("Model is not trained.")
        x = row[self.features]
        return float(self.pipeline.predict(x)[0])
