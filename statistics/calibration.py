from pathlib import Path
import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss

# ============================================================
# CONFIG
# ============================================================

report_path = Path("/workspaces/RoboTrader812/s4_deploy/walk_report.csv")

if not report_path.exists():
    raise FileNotFoundError(f"No existe: {report_path}")

out_dir = Path("/workspaces/RoboTrader812/statistics")
out_dir.mkdir(parents=True, exist_ok=True)

# ============================================================
# LOAD
# ============================================================

df = pd.read_csv(report_path)

required = ["p_up", "label"]

for c in required:
    if c not in df.columns:
        raise ValueError(f"Falta columna requerida: {c}")

df = df.dropna(subset=required).copy()

y_true = df["label"].astype(int).values
y_prob = df["p_up"].astype(float).values

# ============================================================
# METRICS
# ============================================================

brier = brier_score_loss(y_true, y_prob)

# Expected Calibration Error (ECE)
bins = np.linspace(0, 1, 11)
binids = np.digitize(y_prob, bins) - 1

ece = 0.0

for b in range(10):
    mask = binids == b

    if mask.sum() == 0:
        continue

    acc = y_true[mask].mean()
    conf = y_prob[mask].mean()

    ece += np.abs(acc - conf) * mask.mean()

# ============================================================
# RELIABILITY CURVE
# ============================================================

frac_pos, mean_pred = calibration_curve(
    y_true,
    y_prob,
    n_bins=10,
    strategy="uniform"
)

plt.figure(figsize=(8,6))

plt.plot(mean_pred, frac_pos, marker='o')
plt.plot([0,1], [0,1], linestyle='--')

plt.xlabel("Predicted Probability")
plt.ylabel("Observed Frequency")
plt.title("Reliability Diagram")

plt.savefig(out_dir / "reliability_curve.png", dpi=300)
plt.close()

# ============================================================
# PROBABILITY DISTRIBUTION
# ============================================================

plt.figure(figsize=(8,6))

plt.hist(y_prob, bins=30)

plt.xlabel("Predicted Probability")
plt.ylabel("Frequency")
plt.title("Probability Distribution")

plt.savefig(out_dir / "probability_distribution.png", dpi=300)
plt.close()

# ============================================================
# BIN TABLE
# ============================================================

rows = []

for b in range(10):
    lo = bins[b]
    hi = bins[b+1]

    mask = (y_prob >= lo) & (y_prob < hi)

    if mask.sum() == 0:
        continue

    rows.append({
        "bin_low": lo,
        "bin_high": hi,
        "count": int(mask.sum()),
        "avg_probability": float(y_prob[mask].mean()),
        "realized_frequency": float(y_true[mask].mean())
    })

table = pd.DataFrame(rows)

table.to_csv(out_dir / "calibration_bins.csv", index=False)

# ============================================================
# SUMMARY
# ============================================================

print("\n===================================================")
print("CALIBRATION REPORT")
print("===================================================")

print(f"Brier Score : {brier:.6f}")
print(f"ECE         : {ece:.6f}")

print("\nSaved:")
print(out_dir / "reliability_curve.png")
print(out_dir / "probability_distribution.png")
print(out_dir / "calibration_bins.csv")

