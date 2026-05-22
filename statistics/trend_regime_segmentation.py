from pathlib import Path
import pandas as pd
import numpy as np

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 220)

# ============================================================
# LOAD
# ============================================================

ledger_path = Path("/workspaces/RoboTrader812/s4_deploy/trade_ledger.csv")
data_path   = Path("/workspaces/RoboTrader812/s4_deploy/data/BTCUSDT_labeled.csv")

ledger = pd.read_csv(ledger_path)
data   = pd.read_csv(data_path)

print(f"\nLedger trades: {len(ledger)}")
print(f"Dataset rows : {len(data)}")

# ============================================================
# TIME NORMALIZATION
# ============================================================

ledger["time"] = pd.to_datetime(
    ledger["time"],
    utc=True
).dt.tz_localize(None)

data["open_time"] = pd.to_datetime(
    data["open_time"],
    utc=True
).dt.tz_localize(None)

# ============================================================
# REQUIRED
# ============================================================

required = [
    "open_time",
    "close",
]

for c in required:
    if c not in data.columns:
        raise ValueError(f"Dataset missing: {c}")

# ============================================================
# TREND FEATURES
# ============================================================

data = data.sort_values("open_time").copy()

# 50 EMA
data["ema50"] = data["close"].ewm(span=50).mean()

# 200 SMA
data["sma200"] = data["close"].rolling(200).mean()

# distance from 200DMA
data["dist_200"] = (
    (data["close"] - data["sma200"]) / data["sma200"]
)

# trend slope
data["ema50_slope"] = data["ema50"].pct_change(10)

# ============================================================
# TREND REGIMES
# ============================================================

conditions = [
    (data["close"] > data["sma200"]) & (data["ema50_slope"] > 0),
    (data["close"] > data["sma200"]) & (data["ema50_slope"] <= 0),
    (data["close"] <= data["sma200"]) & (data["ema50_slope"] > 0),
    (data["close"] <= data["sma200"]) & (data["ema50_slope"] <= 0),
]

choices = [
    "BULL_TREND",
    "BULL_WEAK",
    "BEAR_RALLY",
    "BEAR_TREND",
]

data["trend_regime"] = np.select(
    conditions,
    choices,
    default="UNKNOWN"
)

# ============================================================
# MERGE
# ============================================================

merge_cols = [
    "open_time",
    "close",
    "sma200",
    "dist_200",
    "trend_regime",
]

merged = pd.merge(
    ledger,
    data[merge_cols],
    left_on="time",
    right_on="open_time",
    how="left"
)

print("\nMissing trend rows:", merged["trend_regime"].isna().sum())

# ============================================================
# RETURNS
# ============================================================

merged["ret"] = merged["ret_realized"]

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
# TREND REPORT
# ============================================================

print("\n")
print("=" * 70)
print("TREND REGIMES")
print("=" * 70)

trend_report = summarize("trend_regime")

print(trend_report)

# ============================================================
# ABOVE / BELOW 200DMA
# ============================================================

merged["above_200dma"] = np.where(
    merged["close"] > merged["sma200"],
    "ABOVE_200DMA",
    "BELOW_200DMA"
)

print("\n")
print("=" * 70)
print("200 DMA REGIME")
print("=" * 70)

dma_report = summarize("above_200dma")

print(dma_report)

# ============================================================
# SAVE
# ============================================================

trend_path = Path("/workspaces/RoboTrader812/statistics/trend_regime_report.csv")
dma_path   = Path("/workspaces/RoboTrader812/statistics/dma200_report.csv")

trend_report.to_csv(trend_path)
dma_report.to_csv(dma_path)

print(f"\nSaved: {trend_path}")
print(f"Saved: {dma_path}")

