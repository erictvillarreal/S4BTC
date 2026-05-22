from pathlib import Path
import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 240)

# ============================================================
# LOAD DATA
# ============================================================

data_path = Path("/workspaces/RoboTrader812/s4_deploy/data/BTCUSDT_labeled.csv")

if not data_path.exists():
    raise FileNotFoundError(data_path)

df = pd.read_csv(data_path)

print(f"\nDataset rows: {len(df)}")

# ============================================================
# TIME
# ============================================================

df["open_time"] = pd.to_datetime(df["open_time"], utc=True).dt.tz_localize(None)

# ============================================================
# FEATURES
# ============================================================

exclude = {
    "label",
    "open_time",
    "close_time",
}

features = [
    c for c in df.columns
    if c not in exclude
]

# numeric only
features = [
    c for c in features
    if pd.api.types.is_numeric_dtype(df[c])
]

print(f"\nFeatures used: {len(features)}")

# ============================================================
# CLEAN
# ============================================================

df = df.dropna(subset=["label"])

X = df[features].replace([np.inf, -np.inf], np.nan).fillna(0)
y = df["label"].astype(int)

# ============================================================
# WALK-FORWARD RANDOMIZED LABEL TEST
# ============================================================

window = 5000
step = 1000

results = []

print("\n")
print("=" * 80)
print("RANDOMIZED LABELS SANITY CHECK")
print("=" * 80)

for i in range(window, len(df) - step, step):

    tr_idx = slice(i - window, i)
    te_idx = slice(i, i + step)

    X_tr = X.iloc[tr_idx]
    y_tr = y.iloc[tr_idx]

    X_te = X.iloc[te_idx]
    y_te = y.iloc[te_idx]

    # ========================================================
    # RANDOMIZE LABELS ONLY IN TRAIN
    # ========================================================

    y_rand = np.random.permutation(y_tr.values)

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        random_state=42,
        n_jobs=-1,
    )

    model.fit(X_tr, y_rand)

    preds = model.predict(X_te)

    acc = accuracy_score(y_te, preds)
    p = precision_score(y_te, preds, zero_division=0)
    r = recall_score(y_te, preds, zero_division=0)
    f1 = f1_score(y_te, preds, zero_division=0)

    results.append({
        "slice": len(results),
        "acc": acc,
        "precision": p,
        "recall": r,
        "f1": f1,
    })

    print(
        f"Slice {len(results):02d} | "
        f"acc={acc:.4f} | "
        f"p={p:.4f} | "
        f"r={r:.4f} | "
        f"f1={f1:.4f}"
    )

# ============================================================
# SUMMARY
# ============================================================

res = pd.DataFrame(results)

print("\n")
print("=" * 80)
print("SUMMARY")
print("=" * 80)

print(f"""
Mean Accuracy     : {res["acc"].mean():.4f}
Mean Precision    : {res["precision"].mean():.4f}
Mean Recall       : {res["recall"].mean():.4f}
Mean F1           : {res["f1"].mean():.4f}
""")

# ============================================================
# SAVE
# ============================================================

out_path = Path("/workspaces/RoboTrader812/statistics/randomized_labels_report.csv")

res.to_csv(out_path, index=False)

print(f"Saved: {out_path}")
