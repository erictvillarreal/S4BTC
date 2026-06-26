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
# REGIME FEATURES
# ============================================================

data["dma_200"] = data["close"].rolling(200).mean()

data["ema_50"] = data["close"].ewm(
    span=50,
    adjust=False
).mean()

data["atr_pct"] = data["atr"] / data["close"]

data["vol_q"] = pd.qcut(
    data["atr_pct"],
    4,
    labels=[
        "LOW_VOL",
        "MIDLOW_VOL",
        "MIDHIGH_VOL",
        "HIGH_VOL"
    ]
)

conditions = [
    (data["close"] > data["ema_50"]) & (data["close"] > data["dma_200"]),
    (data["close"] < data["ema_50"]) & (data["close"] < data["dma_200"]),
    (data["close"] > data["dma_200"]) & (data["close"] < data["ema_50"]),
    (data["close"] < data["dma_200"]) & (data["close"] > data["ema_50"])
]

choices = [
    "BULL_TREND",
    "BEAR_TREND",
    "BULL_WEAK",
    "BEAR_RALLY"
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
    "trend_regime",
    "vol_q",
    "close",
    "dma_200"
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
# BASELINE
# ============================================================

def compute_stats(df, label):

    r = df["ret_realized"].astype(float)

    eq = (1 + r).cumprod()

    dd = (
        eq /
        eq.cummax() - 1
    ).min()

    mean_r = r.mean()
    std_r  = r.std()

    sharpe = mean_r / std_r if std_r > 0 else np.nan

    out = {
        "scenario": label,
        "trades": len(df),
        "winrate": (r > 0).mean(),
        "mean_ret": mean_r,
        "std_ret": std_r,
        "sharpe_like": sharpe,
        "final_multiple": eq.iloc[-1],
        "max_drawdown": dd,
        "ev_per_trade": r.mean(),
        "median_trade": r.median()
    }

    return out

results = []

baseline = compute_stats(
    merged,
    "BASELINE"
)

results.append(baseline)

# ============================================================
# META FILTERS
# ============================================================

filters = {
    "FILTER_1_REMOVE_BEAR_RALLY":
        merged["trend_regime"] != "BEAR_RALLY",

    "FILTER_2_ONLY_ABOVE_200DMA":
        merged["close"] > merged["dma_200"],

    "FILTER_3_BULL_HIGHVOL":
        (
            (merged["trend_regime"] == "BULL_TREND")
            &
            (
                merged["vol_q"].isin([
                    "MIDHIGH_VOL",
                    "HIGH_VOL"
                ])
            )
        ),

    "FILTER_4_COMBINED":
        (
            (merged["trend_regime"] != "BEAR_RALLY")
            &
            (merged["close"] > merged["dma_200"])
            &
            (
                merged["vol_q"] != "LOW_VOL"
            )
        )
}

for name, mask in filters.items():

    sub = merged[mask].copy()

    if len(sub) < 50:
        continue

    res = compute_stats(sub, name)

    results.append(res)

# ============================================================
# RESULTS
# ============================================================

res = pd.DataFrame(results)

print("\n============================================================")
print("META FILTER WALK RESULTS")
print("============================================================")

print(
    res.sort_values(
        "sharpe_like",
        ascending=False
    )
)

# ============================================================
# SAVE
# ============================================================

save_path = "/workspaces/RoboTrader812/s4_enhancement/meta_filtered_walk_report.csv"

res.to_csv(save_path, index=False)

print("\n============================================================")
print("SAVED")
print("============================================================")
print(save_path)
