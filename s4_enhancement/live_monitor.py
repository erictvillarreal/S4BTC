from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 260)

# ============================================================
# LOAD LIVE LEDGER
# ============================================================

LEDGER = Path("/workspaces/RoboTrader812/s4_deploy/logs/trade_ledger.csv")

OUTDIR = Path("/workspaces/RoboTrader812/s4_enhancement/live_metrics")
OUTDIR.mkdir(parents=True, exist_ok=True)

OUTFILE = OUTDIR / "daily_live_monitor.csv"

# ============================================================
# LOAD
# ============================================================

df = pd.read_csv(LEDGER)

print("\n============================================================")
print("S4 LIVE MONITOR")
print("============================================================")

print(f"\nTrades loaded: {len(df)}")

# ============================================================
# BASIC CLEANING
# ============================================================

df["ts"] = pd.to_datetime(df["ts"], errors="coerce")

df["pnl_simulated"] = pd.to_numeric(df["pnl_simulated"], errors="coerce")
df["ev"] = pd.to_numeric(df["ev"], errors="coerce")
df["equity_after"] = pd.to_numeric(df["equity_after"], errors="coerce")

df = df.dropna(subset=["pnl_simulated"])

# ============================================================
# CORE METRICS
# ============================================================

realized_ev = df["pnl_simulated"].mean()

expected_ev = df["ev"].mean()

ev_decay = realized_ev - expected_ev

winrate = (df["pnl_simulated"] > 0).mean()

std_pnl = df["pnl_simulated"].std()

sharpe_like = realized_ev / std_pnl if std_pnl > 0 else np.nan

# ============================================================
# DRAWDOWN
# ============================================================

equity = df["equity_after"].ffill()

rolling_peak = equity.cummax()

drawdown = equity / rolling_peak - 1

max_drawdown = drawdown.min()

# ============================================================
# CALIBRATION DRIFT
# ============================================================

df["predicted_win"] = (df["p_up"] >= 0.5).astype(int)

df["actual_win"] = (df["pnl_simulated"] > 0).astype(int)

calibration_gap = (
    df["predicted_win"].mean()
    -
    df["actual_win"].mean()
)

# ============================================================
# REGIME PERSISTENCE PROXY
# ============================================================

rolling_ev = df["pnl_simulated"].rolling(10).mean()

regime_persistence = (
    rolling_ev.iloc[-1] > 0
    if len(rolling_ev.dropna()) > 0
    else False
)

# ============================================================
# REPORT
# ============================================================

report = {
    "timestamp_utc": datetime.utcnow(),

    "trades": len(df),

    "expected_ev": expected_ev,
    "realized_ev": realized_ev,
    "ev_decay": ev_decay,

    "winrate": winrate,

    "std_pnl": std_pnl,
    "sharpe_like": sharpe_like,

    "max_drawdown": max_drawdown,

    "calibration_gap": calibration_gap,

    "regime_persistence_positive": regime_persistence
}

R = pd.DataFrame([report])

# ============================================================
# SAVE
# ============================================================

if OUTFILE.exists():
    OLD = pd.read_csv(OUTFILE)
    R = pd.concat([OLD, R], ignore_index=True)

R.to_csv(OUTFILE, index=False)

# ============================================================
# PRINT
# ============================================================

print("\n============================================================")
print("LIVE EDGE REPORT")
print("============================================================")

for k, v in report.items():
    print(f"{k:<35}: {v}")

print("\n============================================================")
print("SAVED")
print("============================================================")

print(OUTFILE)
