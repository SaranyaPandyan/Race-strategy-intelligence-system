import os
import fastf1
import pandas as pd
import numpy as np

class RaceDataManager:
    def __init__(self):
        self.data = None
        self.engineered = None
        self.year = None
        self.event = None

    def load(self, year=2024, event="Monza"):
        cache = os.path.join(os.getcwd(), "data", "fastf1_cache")
        os.makedirs(cache, exist_ok=True)
        fastf1.Cache.enable_cache(cache)

        session = fastf1.get_session(year, event, "R")
        session.load(telemetry=False, weather=False, messages=False)

        laps = session.laps.copy()

        columns = [
            "Driver",
            "Team",
            "LapNumber",
            "LapTime",
            "Stint",
            "Compound",
            "TyreLife",
            "PitInTime",
            "PitOutTime",
            "Position",
            "TrackStatus"
        ]

        for col in columns:
            if col not in laps.columns:
                laps[col] = np.nan

        laps = laps[columns].copy()

        laps["LapTimeSeconds"] = laps["LapTime"].dt.total_seconds()
        laps["PitIn"] = laps["PitInTime"].notna().astype(int)
        laps["PitOut"] = laps["PitOutTime"].notna().astype(int)
        laps["Position"] = pd.to_numeric(laps["Position"], errors="coerce")
        laps["LapNumber"] = pd.to_numeric(laps["LapNumber"], errors="coerce")
        laps["TyreLife"] = pd.to_numeric(laps["TyreLife"], errors="coerce")

        laps = laps.dropna(
            subset=["Driver", "LapNumber", "LapTimeSeconds"]
        )

        laps = laps.sort_values(
            ["Driver", "LapNumber"]
        ).reset_index(drop=True)

        path = os.path.join(
            os.getcwd(),
            "data",
            f"{event.lower()}_{year}_race_data.csv"
        )

        laps.to_csv(path, index=False)

        self.year = year
        self.event = event

        return laps

    def set_data(self, data, engineered=None):
        self.data = data
        self.engineered = engineered

    def _check(self):
        if self.data is None or self.data.empty:
            raise RuntimeError("Race data is not loaded. Load a race first.")

    def driver_list(self):
        self._check()
        return sorted(
            self.data["Driver"].dropna().unique().tolist()
        )

    def summary(self):
        self._check()

        max_lap = int(self.data["LapNumber"].max())

        return {
            "total_laps": max_lap,
            "drivers": int(self.data["Driver"].nunique()),
            "teams": int(self.data["Team"].nunique()),
            "laps_recorded": int(len(self.data))
        }

    def overview(self):
        self._check()

        latest = (
            self.data
            .sort_values("LapNumber")
            .groupby("Driver", as_index=False)
            .tail(1)
        )

        max_lap = int(self.data["LapNumber"].max())
        latest_lap = int(latest["LapNumber"].max())

        track = "1"

        if not latest.empty and pd.notna(latest["TrackStatus"].iloc[0]):
            track = str(latest["TrackStatus"].iloc[0])

        return {
            "success": True,
            "year": int(self.year),
            "event": str(self.event),
            "circuit": str(self.event),
            "total_laps": max_lap,
            "current_lap": latest_lap,
            "progress": round(
                latest_lap / max_lap * 100,
                1
            ) if max_lap else 0,
            "track_status": track,
            "drivers": int(self.data["Driver"].nunique()),
            "teams": int(self.data["Team"].nunique())
        }

    def driver_table(self):
        self._check()

        rows = []

        for driver, g in self.data.groupby("Driver", sort=False):

            g = g.sort_values("LapNumber")
            last = g.iloc[-1]

            valid = g["LapTimeSeconds"].dropna()

            recent = g["LapTimeSeconds"].tail(3).mean()

            best = valid.min() if not valid.empty else np.nan
            avg = valid.mean() if not valid.empty else np.nan

            pit_stops = int(g["PitIn"].sum())

            rows.append({
                "driver": str(driver),
                "team": str(last["Team"]),
                "position": int(last["Position"])
                if pd.notna(last["Position"]) else None,
                "lap": int(last["LapNumber"]),
                "lap_time": round(
                    float(last["LapTimeSeconds"]),
                    3
                ),
                "best_lap": round(
                    float(best),
                    3
                ) if pd.notna(best) else None,
                "average_lap": round(
                    float(avg),
                    3
                ) if pd.notna(avg) else None,
                "recent_average": round(
                    float(recent),
                    3
                ) if pd.notna(recent) else None,
                "stint": int(last["Stint"])
                if pd.notna(last["Stint"]) else None,
                "compound": str(last["Compound"])
                if pd.notna(last["Compound"]) else "UNKNOWN",
                "tyre_age": int(last["TyreLife"])
                if pd.notna(last["TyreLife"]) else 0,
                "pit_stops": pit_stops
            })

        rows.sort(
            key=lambda x:
            x["position"]
            if x["position"] is not None
            else 999
        )

        for i, row in enumerate(rows, 1):
            if row["position"] is None:
                row["position"] = i

        return rows

    def driver_status(self, driver=None):
        self._check()

        drivers = self.driver_list()

        if driver not in drivers:
            driver = drivers[0]

        g = (
            self.data[
                self.data["Driver"] == driver
            ]
            .sort_values("LapNumber")
        )

        last = g.iloc[-1]

        valid = g["LapTimeSeconds"].dropna()

        recent = g["LapTimeSeconds"].tail(3).mean()

        best = valid.min()

        compound = (
            str(last["Compound"])
            if pd.notna(last["Compound"])
            else "UNKNOWN"
        )

        tyre_age = (
            int(last["TyreLife"])
            if pd.notna(last["TyreLife"])
            else 0
        )

        return {
            "success": True,
            "driver": str(driver),
            "team": str(last["Team"]),
            "position": int(last["Position"])
            if pd.notna(last["Position"]) else None,
            "lap": int(last["LapNumber"]),
            "lap_time": round(
                float(last["LapTimeSeconds"]),
                3
            ),
            "best_lap": round(
                float(best),
                3
            ),
            "recent_average": round(
                float(recent),
                3
            ),
            "stint": int(last["Stint"])
            if pd.notna(last["Stint"]) else None,
            "compound": compound,
            "tyre_age": tyre_age,
            "pit_stops": int(g["PitIn"].sum()),
            "track_status": str(last["TrackStatus"]),
            "total_laps": int(
                self.data["LapNumber"].max()
            )
        }

    def lap_history(self, driver=None):
        self._check()

        drivers = self.driver_list()

        if driver not in drivers:
            driver = drivers[0]

        g = (
            self.data[
                self.data["Driver"] == driver
            ]
            .sort_values("LapNumber")
        )

        return {
            "success": True,
            "driver": str(driver),
            "laps": [
                int(x)
                for x in g["LapNumber"]
            ],
            "lap_times": [
                round(float(x), 3)
                if pd.notna(x)
                else None
                for x in g["LapTimeSeconds"]
            ],
            "positions": [
                int(x)
                if pd.notna(x)
                else None
                for x in g["Position"]
            ],
            "tyre_age": [
                int(x)
                if pd.notna(x)
                else 0
                for x in g["TyreLife"]
            ],
            "compounds": [
                str(x)
                if pd.notna(x)
                else "UNKNOWN"
                for x in g["Compound"]
            ],
            "stints": [
                int(x)
                if pd.notna(x)
                else None
                for x in g["Stint"]
            ]
        }