from pathlib import Path
import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    brier_score_loss,
    log_loss,
    f1_score
)

from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 260)

# ============================================================
# LOAD
# ============================================================

preds_path = Path("/workspaces/RoboTrader812/s4_deploy/calibration_predictions.csv")

if not preds_path.exists():
    raise FileNotFoundError(
        f"No existe calibration_predictions.csv en:\n{preds_path}\n\n"
        "Necesitas primero exportar probabilidades del walk-forward."
    )

df = pd.read_csv(preds_path)

required = ["y_true", "p_up"]

for c in required:
    if c not in df.columns:
        raise ValueError(f"Missing column: {c}")

df = df.dropna(subset=required).copy()

y = df["y_true"].astype(int).values
p_raw = np.clip(df["p_up"].astype(float).values, 1e-6, 1 - 1e-6)

print(f"\nRows loaded: {len(df)}")

# ============================================================
# BASE METRICS
# ============================================================

base_brier = brier_score_loss(y, p_raw)
base_logloss = log_loss(y, p_raw)

preds_raw = (p_raw >= 0.5).astype(int)
base_f1 = f1_score(y, preds_raw, zero_division=0)

print("\n============================================================")
print("RAW MODEL")
print("============================================================")

print(f"Brier Score : {base_brier:.6f}")
print(f"Log Loss    : {base_logloss:.6f}")
print(f"F1 Score    : {base_f1:.6f}")

# ============================================================
# TIME SERIES SPLIT RECALIBRATION
# ============================================================

tscv = TimeSeriesSplit(n_splits=5)

iso_preds = np.zeros(len(df))
platt_preds = np.zeros(len(df))

for fold, (tr_idx, te_idx) in enumerate(tscv.split(p_raw), 1):

    X_tr = p_raw[tr_idx]
    y_tr = y[tr_idx]

    X_te = p_raw[te_idx]

    # -------------------------
    # ISOTONIC
    # -------------------------

    iso = IsotonicRegression(out_of_bounds="clip")

    iso.fit(X_tr, y_tr)

    iso_preds[te_idx] = iso.predict(X_te)

    # -------------------------
    # PLATT
    # -------------------------

    lr = LogisticRegression()

    lr.fit(X_tr.reshape(-1, 1), y_tr)

    platt_preds[te_idx] = lr.predict_proba(
        X_te.reshape(-1, 1)
    )[:, 1]

    print(f"Fold {fold} completed")

# ============================================================
# METRICS
# ============================================================

def evaluate(name, probs):

    probs = np.clip(probs, 1e-6, 1 - 1e-6)

    brier = brier_score_loss(y, probs)
    ll = log_loss(y, probs)

    preds = (probs >= 0.5).astype(int)

    f1 = f1_score(y, preds, zero_division=0)

    return {
        "model": name,
        "brier": brier,
        "logloss": ll,
        "f1": f1
    }

results = pd.DataFrame([
    evaluate("RAW", p_raw),
    evaluate("ISOTONIC", iso_preds),
    evaluate("PLATT", platt_preds)
])

print("\n============================================================")
print("RECALIBRATION RESULTS")
print("============================================================")
print(results)

# ============================================================
# RELIABILITY DIAGRAM
# ============================================================

fig, ax = plt.subplots(figsize=(8, 8))

models = {
    "RAW": p_raw,
    "ISOTONIC": iso_preds,
    "PLATT": platt_preds
}

for name, probs in models.items():

    frac_pos, mean_pred = calibration_curve(
        y,
        probs,
        n_bins=10,
        strategy="quantile"
    )

    ax.plot(mean_pred, frac_pos, marker="o", label=name)

ax.plot([0, 1], [0, 1], linestyle="--")

ax.set_title("Reliability Diagram")
ax.set_xlabel("Predicted Probability")
ax.set_ylabel("Observed Frequency")
ax.legend()

plt.tight_layout()

plot_path = "/workspaces/RoboTrader812/s4_enhancement/reliability_recalibration.png"

plt.savefig(plot_path, dpi=300)

# ============================================================
# SAVE OUTPUTS
# ============================================================

out = pd.DataFrame({
    "y_true": y,
    "p_raw": p_raw,
    "p_isotonic": iso_preds,
    "p_platt": platt_preds
})

csv_preds = "/workspaces/RoboTrader812/s4_enhancement/recalibrated_predictions.csv"
csv_metrics = "/workspaces/RoboTrader812/s4_enhancement/recalibration_metrics.csv"

out.to_csv(csv_preds, index=False)
results.to_csv(csv_metrics, index=False)

print("\n============================================================")
print("FILES SAVED")
print("============================================================")
print(csv_preds)
print(csv_metrics)
print(plot_path)
