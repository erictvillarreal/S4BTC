from pathlib import Path
import pandas as pd
import numpy as np

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 260)

# ============================================================
# LOAD
# ============================================================

ledger_path = Path("/workspaces/RoboTrader812/s4_deploy/trade_ledger.csv")
data_path   = Path("/workspaces/RoboTrader812/s4_deploy/data/BTCUSDT_labeled.csv")

ledger = pd.read_csv(ledger_path)
data   = pd.read_csv(data_path)

print(f"\nLedger trades : {len(ledger)}")
print(f"Dataset rows  : {len(data)}")

# ============================================================
# DATETIME
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
# BUILD REGIMES
# ============================================================

data = data.sort_values("open_time").reset_index(drop=True)

# 200 DMA
data["dma200"] = data["close"].rolling(200).mean()

data["above_200dma"] = np.where(
    data["close"] > data["dma200"],
    1,
    0
)

# Trend regime
ema50  = data["close"].ewm(span=50).mean()
ema200 = data["close"].ewm(span=200).mean()

data["trend_regime"] = np.select(
    [
        (data["close"] > ema200) & (ema50 > ema200),
        (data["close"] < ema200) & (ema50 < ema200),
        (data["close"] > ema200) & (ema50 < ema200),
        (data["close"] < ema200) & (ema50 > ema200),
    ],
    [
        "BULL_TREND",
        "BEAR_TREND",
        "BULL_WEAK",
        "BEAR_RALLY",
    ],
    default="UNKNOWN"
)

# ATR volatility quartiles
atr_q = pd.qcut(
    data["atr"],
    4,
    labels=[
        "Q1_LOW",
        "Q2_MEDLOW",
        "Q3_MEDHIGH",
        "Q4_HIGH",
    ]
)

data["vol_regime"] = atr_q.astype(str)

# ============================================================
# MERGE
# ============================================================

merge_cols = [
    "open_time",
    "trend_regime",
    "above_200dma",
    "vol_regime",
]

merged = pd.merge(
    ledger,
    data[merge_cols],
    left_on="time",
    right_on="open_time",
    how="left"
)

print(f"\nMissing regime rows: {merged['trend_regime'].isna().sum()}")

# ============================================================
# FILTER DEFINITIONS
# ============================================================

filters = {}

filters["BASELINE"] = merged.copy()

filters["NO_BEAR_RALLY"] = merged[
    merged["trend_regime"] != "BEAR_RALLY"
].copy()

filters["ONLY_BULL_TREND"] = merged[
    merged["trend_regime"] == "BULL_TREND"
].copy()

filters["ONLY_ABOVE_200DMA"] = merged[
    merged["above_200dma"] == 1
].copy()

filters["BULL_AND_HIGHVOL"] = merged[
    (merged["trend_regime"] == "BULL_TREND")
    &
    (merged["vol_regime"] == "Q4_HIGH")
].copy()

filters["COMBINED_FILTER"] = merged[
    (merged["trend_regime"] != "BEAR_RALLY")
    &
    (merged["above_200dma"] == 1)
].copy()

# ============================================================
# WALK SIMULATION
# ============================================================

results = []

for name, df in filters.items():

    rets = df["ret_realized"].astype(float).values

    if len(rets) == 0:
        continue

    equity = np.cumprod(1 + rets)

    peaks = np.maximum.accumulate(equity)

    dd = (equity - peaks) / peaks

    sharpe_like = (
        np.mean(rets)
        /
        (np.std(rets) + 1e-12)
    )

    wins = (rets > 0).mean()

    results.append({
        "scenario": name,
        "trades": len(df),
        "winrate": wins,
        "mean_return": np.mean(rets),
        "std_return": np.std(rets),
        "sharpe_like": sharpe_like,
        "final_multiple": equity[-1],
        "max_drawdown": dd.min(),
        "median_trade": np.median(rets),
        "ev_per_trade": np.mean(rets),
    })

# ============================================================
# RESULTS
# ============================================================

res = pd.DataFrame(results)

res = res.sort_values(
    "sharpe_like",
    ascending=False
)

print("\n============================================================")
print("INTEGRATED META REGIME WALK")
print("============================================================")

print(res)

# ============================================================
# BEST FILTER ANALYSIS
# ============================================================

best = res.iloc[0]

print("\n============================================================")
print("BEST FILTER")
print("============================================================")

for c in best.index:
    print(f"{c:20}: {best[c]}")

# ============================================================
# SAVE
# ============================================================

out_path = Path(
    "/workspaces/RoboTrader812/s4_enhancement/integrated_meta_walk_report.csv"
)

res.to_csv(out_path, index=False)

print("\n============================================================")
print("SAVED")
print("============================================================")
print(out_path)

