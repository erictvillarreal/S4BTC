from pathlib import Path
import pandas as pd
import numpy as np

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

# ============================================================
# LOAD FILES
# ============================================================

ledger_path = Path("/workspaces/RoboTrader812/s4_deploy/trade_ledger.csv")
data_path   = Path("/workspaces/RoboTrader812/s4_deploy/data/BTCUSDT_labeled.csv")

ledger = pd.read_csv(ledger_path)
data   = pd.read_csv(data_path)

print(f"\nLedger trades: {len(ledger)}")
print(f"Dataset rows : {len(data)}")

# ============================================================
# NORMALIZE TIMES
# ============================================================

ledger["time"] = pd.to_datetime(ledger["time"], utc=True).dt.tz_localize(None)
data["open_time"] = pd.to_datetime(data["open_time"], utc=True).dt.tz_localize(None)

# ============================================================
# REQUIRED COLS
# ============================================================

required = [
    "open_time",
    "close",
    "atr",
]

for c in required:
    if c not in data.columns:
        raise ValueError(f"Dataset missing column: {c}")

# ============================================================
# MERGE MARKET CONTEXT
# ============================================================

merge_cols = ["open_time", "close", "atr"]

merged = pd.merge(
    ledger,
    data[merge_cols],
    left_on="time",
    right_on="open_time",
    how="left"
)

print("\nMissing merged ATR rows:", merged["atr"].isna().sum())

# ============================================================
# RETURNS
# ============================================================

if "ret_realized" not in merged.columns:
    raise ValueError("Missing ret_realized in ledger")

merged["ret"] = merged["ret_realized"]

# ============================================================
# ATR REGIME
# ============================================================

merged["atr_ratio"] = merged["atr"] / merged["close"]

merged["vol_q"] = pd.qcut(
    merged["atr_ratio"],
    4,
    labels=["Q1_LOW", "Q2_MEDLOW", "Q3_MEDHIGH", "Q4_HIGH"]
)

# ============================================================
# WIN FLAG
# ============================================================

merged["win"] = (merged["ret"] > 0).astype(int)

# ============================================================
# SUMMARY FUNCTION
# ============================================================

def summarize(group_col):

    out = (
        merged.groupby(group_col)
        .agg(
            trades=("ret", "count"),
            winrate=("win", "mean"),
            avg_ret=("ret", "mean"),
            median_ret=("ret", "median"),
            total_ret=("ret", "sum"),
            std_ret=("ret", "std"),
        )
        .sort_values("total_ret", ascending=False)
    )

    out["winrate"] *= 100

    return out

# ============================================================
# REPORT
# ============================================================

print("\n")
print("=" * 60)
print("VOLATILITY REGIMES")
print("=" * 60)

vol_report = summarize("vol_q")

print(vol_report)

# ============================================================
# SAVE
# ============================================================

save_path = Path("/workspaces/RoboTrader812/statistics/regime_volatility.csv")

vol_report.to_csv(save_path)

print(f"\nSaved: {save_path}")

