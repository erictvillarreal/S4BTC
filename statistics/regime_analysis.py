import pandas as pd
import numpy as np
from pathlib import Path

# =========================================================
# LOAD DATA
# =========================================================
ledger_path = Path("/workspaces/RoboTrader812/s4_deploy/trade_ledger.csv")

if not ledger_path.exists():
    raise FileNotFoundError(f"Missing ledger: {ledger_path}")

df = pd.read_csv(ledger_path)

# =========================================================
# BASIC CLEANING
# =========================================================
df = df.dropna()

# Expect columns:
# pnl, open_time, price, atr, close, maybe direction etc.

# =========================================================
# REGIME FEATURES
# =========================================================

# --- Volatility regime (ATR quantiles)
df["vol_regime"] = pd.qcut(df["atr"], 4, labels=["low", "mid_low", "mid_high", "high"])

# --- Trend proxy (price momentum)
df["price_roll"] = df["close"].pct_change(10).fillna(0)

df["trend_regime"] = np.where(
    df["price_roll"] > 0.01, "uptrend",
    np.where(df["price_roll"] < -0.01, "downtrend", "range")
)

# --- 200DMA regime
df["dma200"] = df["close"].rolling(200).mean()
df["dma_regime"] = np.where(df["close"] > df["dma200"], "above_200dma", "below_200dma")

# =========================================================
# PNL ASSUMPTION
# =========================================================
# expected columns from ledger:
# pnl per trade

if "pnl" not in df.columns:
    raise ValueError("Ledger must include pnl column per trade")

# =========================================================
# REGIME ANALYSIS FUNCTION
# =========================================================
def summarize(group):
    return pd.Series({
        "trades": len(group),
        "win_rate": (group["pnl"] > 0).mean(),
        "avg_pnl": group["pnl"].mean(),
        "total_pnl": group["pnl"].sum()
    })

# =========================================================
# ANALYSIS TABLES
# =========================================================
vol_stats = df.groupby("vol_regime").apply(summarize)
trend_stats = df.groupby("trend_regime").apply(summarize)
dma_stats = df.groupby("dma_regime").apply(summarize)

print("\n================ VOL REGIME ================\n")
print(vol_stats)

print("\n================ TREND REGIME ================\n")
print(trend_stats)

print("\n================ DMA REGIME ================\n")
print(dma_stats)

# =========================================================
# SAVE OUTPUTS
# =========================================================
out_dir = Path("statistics")
out_dir.mkdir(exist_ok=True)

vol_stats.to_csv(out_dir / "regime_vol.csv")
trend_stats.to_csv(out_dir / "regime_trend.csv")
dma_stats.to_csv(out_dir / "regime_dma.csv")

print("\nSaved regime analysis in /statistics/")
