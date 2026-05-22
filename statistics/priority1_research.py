from pathlib import Path
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    brier_score_loss,
    log_loss
)

# ============================================================
# PATHS
# ============================================================

CALIB_PATH = Path("/workspaces/RoboTrader812/s4_deploy/calibration_predictions.csv")

if not CALIB_PATH.exists():
    raise FileNotFoundError(
        f"No existe calibration_predictions.csv:\n{CALIB_PATH}"
    )

OUT_DIR = Path("/workspaces/RoboTrader812/statistics")
OUT_DIR.mkdir(exist_ok=True)

# ============================================================
# LOAD
# ============================================================

df = pd.read_csv(CALIB_PATH)

required = ["y_true", "p_up"]

for c in required:
    if c not in df.columns:
        raise ValueError(f"Falta columna requerida: {c}")

df = df.dropna(subset=["y_true", "p_up"]).copy()

df["y_true"] = df["y_true"].astype(int)
df["p_up"]   = df["p_up"].astype(float)

df["p_up"] = np.clip(df["p_up"], 1e-6, 1 - 1e-6)

print("=" * 60)
print("CALIBRATION DATA")
print("=" * 60)
print(f"Rows: {len(df):,}")
print()

# ============================================================
# METRICS
# ============================================================

brier = brier_score_loss(df["y_true"], df["p_up"])
lloss = log_loss(df["y_true"], df["p_up"])

print("=" * 60)
print("PROBABILISTIC METRICS")
print("=" * 60)
print(f"Brier Score : {brier:.6f}")
print(f"Log Loss    : {lloss:.6f}")
print()

# ============================================================
# CALIBRATION CURVE
# ============================================================

prob_true, prob_pred = calibration_curve(
    df["y_true"],
    df["p_up"],
    n_bins=10,
    strategy="quantile"
)

ece = np.mean(np.abs(prob_true - prob_pred))

print(f"ECE (Expected Calibration Error): {ece:.6f}")
print()

calib_table = pd.DataFrame({
    "predicted_prob": prob_pred,
    "realized_freq": prob_true,
    "abs_gap": np.abs(prob_true - prob_pred)
})

print("=" * 60)
print("CALIBRATION TABLE")
print("=" * 60)
print(calib_table.round(4))
print()

# ============================================================
# SAVE TABLE
# ============================================================

calib_csv = OUT_DIR / "calibration_table.csv"
calib_table.to_csv(calib_csv, index=False)

# ============================================================
# RELIABILITY DIAGRAM
# ============================================================

plt.figure(figsize=(8,8))

plt.plot(
    [0,1],
    [0,1],
    linestyle="--"
)

plt.plot(
    prob_pred,
    prob_true,
    marker="o"
)

plt.xlabel("Predicted Probability")
plt.ylabel("Observed Frequency")
plt.title("Reliability Diagram")

plt.tight_layout()

plot_path = OUT_DIR / "reliability_diagram.png"

plt.savefig(plot_path, dpi=300)

# ============================================================
# SHARPNESS
# ============================================================

plt.figure(figsize=(10,5))

plt.hist(
    df["p_up"],
    bins=30
)

plt.xlabel("Predicted Probability")
plt.ylabel("Count")
plt.title("Probability Sharpness")

plt.tight_layout()

sharp_path = OUT_DIR / "probability_sharpness.png"

plt.savefig(sharp_path, dpi=300)

# ============================================================
# CONFIDENCE ANALYSIS
# ============================================================

df["confidence"] = np.abs(df["p_up"] - 0.5)

bins = pd.qcut(df["confidence"], q=10, duplicates="drop")

conf_stats = (
    df.groupby(bins)
    .agg(
        avg_confidence=("confidence", "mean"),
        realized_winrate=("y_true", "mean"),
        avg_probability=("p_up", "mean"),
        count=("y_true", "count")
    )
    .reset_index(drop=True)
)

print("=" * 60)
print("CONFIDENCE ANALYSIS")
print("=" * 60)
print(conf_stats.round(4))
print()

conf_csv = OUT_DIR / "confidence_analysis.csv"
conf_stats.to_csv(conf_csv, index=False)

# ============================================================
# SUMMARY
# ============================================================

print("=" * 60)
print("SUMMARY")
print("=" * 60)

print(f"Brier Score     : {brier:.6f}")
print(f"Log Loss        : {lloss:.6f}")
print(f"ECE             : {ece:.6f}")

print()
print(f"Saved: {calib_csv}")
print(f"Saved: {plot_path}")
print(f"Saved: {sharp_path}")
print(f"Saved: {conf_csv}")
