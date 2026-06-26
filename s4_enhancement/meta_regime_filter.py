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
# DATETIME ALIGNMENT
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
# BUILD MARKET REGIMES
# ============================================================

# 200 DMA
data["dma_200"] = data["close"].rolling(200).mean()

# Trend strength
data["ema_50"] = data["close"].ewm(span=50).mean()

# ATR %
data["atr_pct"] = data["atr"] / data["close"]

# Volatility quartiles
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

# Trend regime
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
    "atr_pct",
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

rets = merged["ret_realized"].astype(float)

baseline_mean = rets.mean()
baseline_std  = rets.std()

baseline_sharpe = baseline_mean / baseline_std

baseline_equity = (1 + rets).cumprod()

baseline_final = baseline_equity.iloc[-1]

baseline_dd = (
    baseline_equity /
    baseline_equity.cummax() - 1
).min()

print("\n============================================================")
print("BASELINE")
print("============================================================")

print(f"Trades          : {len(rets)}")
print(f"Mean Return     : {baseline_mean:.6f}")
print(f"Std Return      : {baseline_std:.6f}")
print(f"Sharpe-like     : {baseline_sharpe:.6f}")
print(f"Final Multiple  : {baseline_final:.2f}x")
print(f"Max Drawdown    : {baseline_dd:.4f}")

# ============================================================
# META FILTER TESTS
# ============================================================

filters = {
    "REMOVE_BEAR_RALLY":
        merged["trend_regime"] != "BEAR_RALLY",

    "ONLY_BULL_TREND":
        merged["trend_regime"] == "BULL_TREND",

    "ONLY_ABOVE_200DMA":
        merged["close"] > merged["dma_200"],

    "REMOVE_LOW_VOL":
        merged["vol_q"] != "LOW_VOL",

    "BULL_AND_HIGHVOL":
        (
            (merged["trend_regime"] == "BULL_TREND")
            &
            (merged["vol_q"].isin(["MIDHIGH_VOL", "HIGH_VOL"]))
        ),

    "BEST_REGIMES_ONLY":
        (
            (merged["trend_regime"].isin([
                "BULL_TREND",
                "BEAR_TREND"
            ]))
            &
            (merged["vol_q"] != "LOW_VOL")
        )
}

results = []

print("\n============================================================")
print("META REGIME FILTER RESULTS")
print("============================================================")

for name, mask in filters.items():

    sub = merged[mask].copy()

    if len(sub) < 50:
        continue

    r = sub["ret_realized"].astype(float)

    mean_r = r.mean()
    std_r  = r.std()

    sharpe = mean_r / std_r if std_r > 0 else np.nan

    eq = (1 + r).cumprod()

    final_mult = eq.iloc[-1]

    dd = (
        eq /
        eq.cummax() - 1
    ).min()

    wr = (r > 0).mean()

    out = {
        "filter": name,
        "trades": len(sub),
        "winrate": wr,
        "mean_ret": mean_r,
        "std_ret": std_r,
        "sharpe_like": sharpe,
        "final_multiple": final_mult,
        "max_drawdown": dd
    }

    results.append(out)

    print(f"\n{name}")
    print("-" * 60)

    print(f"Trades           : {len(sub)}")
    print(f"Winrate          : {wr:.4f}")
    print(f"Mean Return      : {mean_r:.6f}")
    print(f"Std Return       : {std_r:.6f}")
    print(f"Sharpe-like      : {sharpe:.6f}")
    print(f"Final Multiple   : {final_mult:.2f}x")
    print(f"Max Drawdown     : {dd:.4f}")

# ============================================================
# SAVE
# ============================================================

res = pd.DataFrame(results)

save_path = "/workspaces/RoboTrader812/s4_enhancement/meta_regime_filter_report.csv"

res.to_csv(save_path, index=False)

print("\n============================================================")
print("SAVED")
print("============================================================")
print(save_path)
