from pathlib import Path
import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import f1_score

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 260)

# ============================================================
# LOAD
# ============================================================

data_path = Path("/workspaces/RoboTrader812/s4_deploy/data/BTCUSDT_labeled.csv")

if not data_path.exists():
    raise FileNotFoundError(data_path)

df = pd.read_csv(data_path)

print(f"\nDataset rows: {len(df)}")

# ============================================================
# TIME
# ============================================================

if "open_time" in df.columns:
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True).dt.tz_localize(None)

# ============================================================
# TARGET
# ============================================================

target_col = "label"

if target_col not in df.columns:
    raise ValueError("Missing label column")

# ============================================================
# FEATURE SELECTION
# ============================================================

exclude_cols = {
    "label",
    "open_time",
    "close_time",
    "target",
    "future_return",
}

features = []

for c in df.columns:
    if c in exclude_cols:
        continue

    if pd.api.types.is_numeric_dtype(df[c]):
        features.append(c)

print(f"\nFeatures used: {len(features)}")

X = df[features].replace([np.inf, -np.inf], np.nan).fillna(0)
y = df[target_col].astype(int)

# ============================================================
# WALKFORWARD FEATURE STABILITY
# ============================================================

window = 5000
step = 2000

results = []

i = 0
slice_id = 1

while i + window + step < len(df):

    train_idx = slice(i, i + window)
    test_idx  = slice(i + window, i + window + step)

    X_train = X.iloc[train_idx]
    y_train = y.iloc[train_idx]

    X_test = X.iloc[test_idx]
    y_test = y.iloc[test_idx]

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    preds = model.predict(X_test)

    f1 = f1_score(y_test, preds, zero_division=0)

    perm = permutation_importance(
        model,
        X_test,
        y_test,
        n_repeats=5,
        random_state=42,
        n_jobs=-1
    )

    imp = perm.importances_mean

    for feat, val in zip(features, imp):
        results.append({
            "slice": slice_id,
            "feature": feat,
            "importance": val,
            "f1": f1
        })

    print(f"Slice {slice_id:02d} | F1={f1:.4f}")

    i += step
    slice_id += 1

# ============================================================
# AGGREGATE
# ============================================================

res = pd.DataFrame(results)

summary = (
    res.groupby("feature")
    .agg(
        mean_importance=("importance", "mean"),
        std_importance=("importance", "std"),
        max_importance=("importance", "max"),
        min_importance=("importance", "min"),
    )
    .sort_values("mean_importance", ascending=False)
)

summary["stability_ratio"] = (
    summary["std_importance"] /
    (summary["mean_importance"].abs() + 1e-9)
)

print("\n")
print("=" * 90)
print("FEATURE SIGNIFICANCE / STABILITY")
print("=" * 90)

print(summary.head(25))

# ============================================================
# FLAGS
# ============================================================

unstable = summary[summary["stability_ratio"] > 1.0]

print("\n")
print("=" * 90)
print("UNSTABLE FEATURES")
print("=" * 90)

if len(unstable) == 0:
    print("No highly unstable features detected.")
else:
    print(unstable.sort_values("stability_ratio", ascending=False).head(20))

# ============================================================
# SAVE
# ============================================================

out1 = "/workspaces/RoboTrader812/statistics/feature_significance_full.csv"
out2 = "/workspaces/RoboTrader812/statistics/feature_significance_summary.csv"

res.to_csv(out1, index=False)
summary.to_csv(out2)

print(f"\nSaved: {out1}")
print(f"Saved: {out2}")

