import numpy as np
import pandas as pd

COMPOUNDS = ["SOFT", "MEDIUM", "HARD"]

class StrategyEngine:
    def _compound_data(self, data, compound):
        return data[
            data["Compound"].astype(str).str.upper() == compound
        ].copy()

    def _compound_base(self, compound, data):
        g = self._compound_data(data, compound)
        values = g["LapTimeSeconds"].dropna()

        if len(values) == 0:
            values = data["LapTimeSeconds"].dropna()

        if len(values) == 0:
            return 90.0

        return float(values.quantile(0.25))

    def _degradation(self, compound, data):
        g = self._compound_data(data, compound)
        g = g.dropna(subset=["LapTimeSeconds", "TyreLife"])

        if len(g) < 8:
            return 0.055

        grouped = (
            g.groupby("TyreLife")["LapTimeSeconds"]
            .median()
            .reset_index()
        )

        if len(grouped) < 4:
            return 0.055

        slope = np.polyfit(
            grouped["TyreLife"],
            grouped["LapTimeSeconds"],
            1
        )[0]

        return float(np.clip(slope, 0.01, 0.20))

    def _pit_loss(self, data):
        return 21.5

    def _compound_options(self, current):
        if current == "SOFT":
            return ["MEDIUM", "HARD"]
        if current == "MEDIUM":
            return ["HARD", "SOFT"]
        return ["MEDIUM", "SOFT"]

    def _simulate_stint(
        self,
        compound,
        tyre_age,
        laps,
        data
    ):
        base = self._compound_base(compound, data)
        degradation = self._degradation(compound, data)

        total = 0.0

        for age in range(tyre_age, tyre_age + laps):
            total += base + degradation * age

        return total

    def _simulate_strategy(
        self,
        current_compound,
        current_age,
        remaining_laps,
        pit_laps,
        compounds,
        data
    ):
        if remaining_laps <= 0:
            return 0.0

        total = 0.0
        current_lap_offset = 0
        tyre_age = current_age
        compound_index = 0

        for pit_lap in pit_laps:
            stint_laps = pit_lap - current_lap_offset

            if stint_laps > 0:
                total += self._simulate_stint(
                    compounds[compound_index],
                    tyre_age,
                    stint_laps,
                    data
                )

                current_lap_offset = pit_lap
                tyre_age = 0

            total += self._pit_loss(data)

            compound_index += 1

            if compound_index >= len(compounds):
                break

        remaining = remaining_laps - current_lap_offset

        if remaining > 0:
            total += self._simulate_stint(
                compounds[min(compound_index, len(compounds) - 1)],
                tyre_age,
                remaining,
                data
            )

        return float(total)

    def _strategy_plans(
        self,
        current_lap,
        total_laps,
        current_compound,
        current_age,
        data
    ):
        remaining = max(0, total_laps - current_lap)

        if remaining <= 0:
            return [
                {
                    "name": "Finish Current Stint",
                    "pit_laps": [],
                    "compounds": [current_compound]
                }
            ]

        earliest = current_lap + 3
        latest = total_laps - 2

        if latest < earliest:
            return [
                {
                    "name": "Stay Out To Finish",
                    "pit_laps": [],
                    "compounds": [current_compound]
                }
            ]

        middle = int((earliest + latest) / 2)

        alternatives = self._compound_options(current_compound)

        first = alternatives[0]
        second = alternatives[1]

        plans = [
            {
                "name": "Stay Out → " + first,
                "pit_laps": [middle],
                "compounds": [current_compound, first]
            },
            {
                "name": "Early Pit → " + first + " → " + second,
                "pit_laps": [
                    earliest,
                    min(earliest + 15, latest)
                ],
                "compounds": [
                    current_compound,
                    first,
                    second
                ]
            },
            {
                "name": "Late Pit → " + first,
                "pit_laps": [latest],
                "compounds": [current_compound, first]
            },
            {
                "name": "Stay Out To Finish",
                "pit_laps": [],
                "compounds": [current_compound]
            }
        ]

        return plans

    def _decision(
        self,
        current_age,
        degradation,
        remaining,
        current_pace,
        baseline,
        best_time,
        stay_time,
        pit_time
    ):
        degradation_pressure = degradation * max(current_age, 1)

        pace_delta = max(0.0, current_pace - baseline)

        pit_advantage = stay_time - pit_time

        if remaining <= 3:
            decision = "STAY OUT"
        elif pit_advantage > 2.0 and (
            current_age >= 10 or
            degradation_pressure > 0.8 or
            pace_delta > 0.5
        ):
            decision = "PIT NOW"
        elif pit_advantage > 0:
            decision = "PIT SOON"
        else:
            decision = "STAY OUT"

        return decision

    def analyze(self, data, driver, status, model):
        g = (
            data[data["Driver"] == driver]
            .sort_values("LapNumber")
            .copy()
        )

        if g.empty:
            raise ValueError("Driver data not found.")

        total_laps = int(data["LapNumber"].max())
        current_lap = int(status["lap"])
        remaining = max(0, total_laps - current_lap)

        current_compound = str(
            status["compound"]
        ).upper()

        current_age = int(
            status.get("tyre_age", 0)
        )

        recent_values = (
            g["LapTimeSeconds"]
            .dropna()
            .tail(5)
        )

        current_pace = (
            float(recent_values.mean())
            if len(recent_values)
            else float(
                data["LapTimeSeconds"].median()
            )
        )

        baseline = self._compound_base(
            current_compound,
            data
        )

        degradation = self._degradation(
            current_compound,
            data
        )

        plans = self._strategy_plans(
            current_lap,
            total_laps,
            current_compound,
            current_age,
            data
        )

        candidates = []

        for plan in plans:
            predicted = self._simulate_strategy(
                current_compound,
                current_age,
                remaining,
                plan["pit_laps"],
                plan["compounds"],
                data
            )

            candidates.append({
                "name": plan["name"],
                "pit_laps": plan["pit_laps"],
                "compounds": plan["compounds"],
                "predicted_remaining_time": round(
                    predicted,
                    2
                )
            })

        candidates.sort(
            key=lambda x:
            x["predicted_remaining_time"]
        )

        best = candidates[0]

        stay_plan = next(
            (
                x for x in candidates
                if x["name"] == "Stay Out To Finish"
            ),
            candidates[-1]
        )

        pit_plan = min(
            (
                x for x in candidates
                if len(x["pit_laps"]) > 0
            ),
            key=lambda x:
            x["predicted_remaining_time"],
            default=stay_plan
        )

        decision = self._decision(
            current_age,
            degradation,
            remaining,
            current_pace,
            baseline,
            best["predicted_remaining_time"],
            stay_plan["predicted_remaining_time"],
            pit_plan["predicted_remaining_time"]
        )

        if decision == "PIT NOW":
            recommended = pit_plan
        elif decision == "PIT SOON":
            recommended = pit_plan
        else:
            recommended = stay_plan

        gap = abs(
            candidates[1]["predicted_remaining_time"]
            - candidates[0]["predicted_remaining_time"]
        ) if len(candidates) > 1 else 0

        confidence = float(
            np.clip(
                68 + gap * 3,
                55,
                96
            )
        )

        if current_age < 8:
            tyre_risk = "LOW"
        elif current_age < 16:
            tyre_risk = "MEDIUM"
        else:
            tyre_risk = "HIGH"

        if degradation > 0.10:
            tyre_risk = "HIGH"

        pit_start = max(
            current_lap + 2,
            current_lap + 5
        )

        pit_end = min(
            total_laps - 2,
            current_lap + 18
        )

        if pit_end < pit_start:
            pit_end = pit_start

        if decision == "PIT NOW":
            pit_window = [
                current_lap,
                current_lap + 2
            ]
        else:
            pit_window = [
                pit_start,
                pit_end
            ]

        if decision == "PIT NOW":
            reason = (
                "Tyre degradation and remaining race distance "
                "make a pit stop strategically favourable."
            )
        elif decision == "PIT SOON":
            reason = (
                "Current tyres remain usable, but degradation "
                "indicates an approaching pit window."
            )
        else:
            reason = (
                "Current tyre pace remains competitive and the "
                "pit-stop time loss outweighs the immediate benefit."
            )

        return {
            "success": True,
            "driver": str(driver),
            "decision": decision,
            "recommendation": recommended["name"],
            "reason": reason,
            "confidence": round(confidence, 1),
            "pit_window": pit_window,
            "recommended_pit_laps": recommended["pit_laps"],
            "remaining_laps": remaining,
            "current_lap": current_lap,
            "total_laps": total_laps,
            "current_compound": current_compound,
            "tyre_age": current_age,
            "tyre_risk": tyre_risk,
            "current_pace": round(current_pace, 3),
            "compound_baseline": round(baseline, 3),
            "tyre_degradation_per_lap": round(
                degradation,
                4
            ),
            "pit_stop_loss": self._pit_loss(data),
            "current_stint_average": round(
                float(
                    g.tail(8)["LapTimeSeconds"].mean()
                ),
                3
            ),
            "stay_out_time": round(
                stay_plan["predicted_remaining_time"],
                2
            ),
            "best_pit_time": round(
                pit_plan["predicted_remaining_time"],
                2
            ),
            "alternatives": candidates
        }