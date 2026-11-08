from flask import Flask, render_template, jsonify, request
from src.data_loader import RaceDataManager
from src.feature_engineering import build_features
from src.model import LapTimeModel
from src.strategy_engine import StrategyEngine

app = Flask(__name__)
manager = RaceDataManager()
model = LapTimeModel()
strategy_engine = StrategyEngine()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.post("/api/load-race")
def load_race():
    payload = request.get_json(silent=True) or {}
    year = int(payload.get("year", 2024))
    event = payload.get("event", "Monza")
    try:
        df = manager.load(year, event)
        engineered = build_features(df)
        model.fit(engineered)
        manager.set_data(df, engineered)
        return jsonify({
            "success": True,
            "year": year,
            "event": event,
            "drivers": manager.driver_list(),
            "summary": manager.summary()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.get("/api/overview")
def overview():
    try:
        return jsonify(manager.overview())
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.get("/api/drivers")
def drivers():
    try:
        return jsonify({"success": True, "drivers": manager.driver_table()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.get("/api/race-status")
def race_status():
    driver = request.args.get("driver")
    try:
        return jsonify(manager.driver_status(driver))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.get("/api/lap-history")
def lap_history():
    driver = request.args.get("driver")
    try:
        return jsonify(manager.lap_history(driver))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.get("/api/strategy")
def strategy():
    driver = request.args.get("driver")
    try:
        status = manager.driver_status(driver)
        result = strategy_engine.analyze(manager.data, driver, status, model)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
