"""Train the regression model from CSV and save as pickle.

Updated features (v2):
  study_hours, sleep_hours, screen_time, sports_hours,
  other_activities, attendance, previous_marks  →  final_score

Removed: mobile_usage, tv_hours, gaming_hours, social_media_hours,
         assignment_completion (internal_marks was never a model feature).
"""
import os
import pickle
import numpy as np
import pandas as pd
import json
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.dummy import DummyRegressor

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(BASE_DIR, "data", "students.csv")
MODEL_PATH = os.path.join(BASE_DIR, "model", "model.pkl")

FEATURES = [
    "study_hours", "sleep_hours", "screen_time",
    "sports_hours", "other_activities", "attendance", "previous_marks",
]
TARGET = "final_score"


def _generate_dataset(n: int = 1500, seed: int = 42) -> pd.DataFrame:
    """Synthesise a realistic student dataset using the new feature schema."""
    rng = np.random.default_rng(seed)

    study      = rng.uniform(0, 10, n)
    sleep      = rng.uniform(4, 11, n)
    screen     = rng.uniform(0, 10, n)
    sports     = rng.uniform(0, 4,  n)
    other_act  = rng.uniform(0, 6,  n)
    attendance = rng.uniform(40, 100, n)
    prev       = rng.uniform(40, 100, n)

    # Optimal sleep ~7.5 h; deviations in either direction cost marks
    sleep_score = -np.abs(sleep - 7.5) * 2.0

    score = (
        28
        + study      * 4.5    # most important driver
        + sleep_score          # rest quality
        - screen     * 1.8    # screen time hurts focus
        + sports     * 1.4    # physical activity helps
        - other_act  * 0.7    # time lost to other commitments
        + attendance * 0.19   # being present matters
        + prev       * 0.26   # past performance is a strong predictor
        + rng.normal(0, 3, n) # realistic noise
    )
    score = np.clip(score, 0, 100)

    return pd.DataFrame({
        "study_hours":      study.round(1),
        "sleep_hours":      sleep.round(1),
        "screen_time":      screen.round(1),
        "sports_hours":     sports.round(1),
        "other_activities": other_act.round(1),
        "attendance":       attendance.round(1),
        "previous_marks":   prev.round(1),
        "final_score":      score.round(1),
    })


def train_and_save():
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(DATA_PATH),  exist_ok=True)

    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
        # If the CSV is stale (old feature schema), regenerate it
        missing = [c for c in FEATURES + [TARGET] if c not in df.columns]
        if missing:
            print(f"CSV missing columns {missing} — regenerating dataset.")
            df = _generate_dataset()
            df.to_csv(DATA_PATH, index=False)
    else:
        print("No CSV found — generating synthetic dataset.")
        df = _generate_dataset()
        df.to_csv(DATA_PATH, index=False)

    X = df[FEATURES].values
    y = df[TARGET].values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(
        n_estimators=160, max_depth=12, random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    baseline = DummyRegressor(strategy="mean").fit(X_train, y_train)
    base_pred = baseline.predict(X_test)
    metrics = {
        "dataset_rows": int(len(df)), "dataset_kind": "synthetic" if os.path.basename(DATA_PATH) == "students.csv" else "unknown",
        "train_rows": int(len(X_train)), "test_rows": int(len(X_test)), "target": TARGET,
        "features": FEATURES, "split": "80/20 random holdout; random_state=42",
        "model": {"mae": round(float(mean_absolute_error(y_test, pred)), 4), "rmse": round(float(np.sqrt(mean_squared_error(y_test, pred))), 4), "r2": round(float(r2_score(y_test, pred)), 4)},
        "mean_baseline": {"mae": round(float(mean_absolute_error(y_test, base_pred)), 4), "rmse": round(float(np.sqrt(mean_squared_error(y_test, base_pred))), 4), "r2": round(float(r2_score(y_test, base_pred)), 4)},
        "feature_importance": {key: round(float(value), 5) for key, value in zip(FEATURES, model.feature_importances_)},
        "warning": "The bundled CSV is synthetic and generated from a formula. These metrics do not establish real-world predictive performance."
    }
    print(json.dumps(metrics, indent=2))

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    with open(os.path.join(os.path.dirname(MODEL_PATH), "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Model saved → {MODEL_PATH}")


if __name__ == "__main__":
    train_and_save()
