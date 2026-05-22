from pathlib import Path
import pandas as pd
import numpy as np

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 240)

# ============================================================
# LOAD
# ============================================================

ledger_path = Path("/workspaces/RoboTrader812/s4_deploy/trade_ledger.csv")

if not ledger_path.exists():
    raise FileNotFoundError(ledger_path)

df = pd.read_csv(ledger_path)

print(f"\nTrades loaded: {len(df)}")

required = [
    "time",
    "pnl",
    "ret_realized",
    "stake_lev",
]

for c in required:
    if c not in df.columns:
        raise ValueError(f"Missing required column: {c}")

df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)

# ============================================================
# BASELINE
# ============================================================

initial_equity = 1000.0

base_ret = df["ret_realized"].fillna(0.0).values

# ============================================================
# REALITY STRESS MODELS
# ============================================================

def apply_reality_model(
    returns,
    extra_fee_bps=0.0,
    latency_bps=0.0,
    spread_bps=0.0,
    volatility_slippage_factor=0.0,
    liquidity_random_std=0.0,
):

    stressed = returns.copy()

    # deterministic friction
    total_bps = (
        extra_fee_bps
        + latency_bps
        + spread_bps
    )

    stressed -= total_bps / 10000.0

    # volatility slippage
    stressed -= np.abs(stressed) * volatility_slippage_factor

    # random liquidity degradation
    if liquidity_random_std > 0:
        noise = np.random.normal(
            loc=0.0,
            scale=liquidity_random_std,
            size=len(stressed),
        )

        stressed -= np.abs(noise)

    eq = [initial_equity]

    for r in stressed:
        eq.append(eq[-1] * (1 + r))

    eq = np.array(eq)

    peak = np.maximum.accumulate(eq)

    dd = (eq - peak) / peak

    return {
        "final_equity": eq[-1],
        "cagr_multiple": eq[-1] / initial_equity,
        "max_drawdown": dd.min(),
        "mean_ret": stressed.mean(),
        "std_ret": stressed.std(),
        "winrate": (stressed > 0).mean(),
    }

# ============================================================
# SCENARIOS
# ============================================================

scenarios = {

    "BASELINE": {
        "extra_fee_bps": 0,
        "latency_bps": 0,
        "spread_bps": 0,
        "volatility_slippage_factor": 0,
        "liquidity_random_std": 0,
    },

    "LIGHT_FRICTION": {
        "extra_fee_bps": 2,
        "latency_bps": 1,
        "spread_bps": 2,
        "volatility_slippage_factor": 0.02,
        "liquidity_random_std": 0.0005,
    },

    "MEDIUM_FRICTION": {
        "extra_fee_bps": 5,
        "latency_bps": 3,
        "spread_bps": 5,
        "volatility_slippage_factor": 0.05,
        "liquidity_random_std": 0.001,
    },

    "HEAVY_FRICTION": {
        "extra_fee_bps": 10,
        "latency_bps": 5,
        "spread_bps": 10,
        "volatility_slippage_factor": 0.10,
        "liquidity_random_std": 0.002,
    },

    "EXTREME_FRICTION": {
        "extra_fee_bps": 20,
        "latency_bps": 10,
        "spread_bps": 20,
        "volatility_slippage_factor": 0.20,
        "liquidity_random_std": 0.004,
    },
}

# ============================================================
# RUN
# ============================================================

results = []

print("\n")
print("=" * 80)
print("REALITY MODELING")
print("=" * 80)

for name, params in scenarios.items():

    stats = apply_reality_model(base_ret, **params)

    row = {
        "scenario": name,
        **stats
    }

    results.append(row)

    print(f"""
SCENARIO               : {name}

Final Equity           : {stats["final_equity"]:,.2f}
Equity Multiple        : {stats["cagr_multiple"]:.2f}x
Max Drawdown           : {stats["max_drawdown"]:.4f}
Mean Return            : {stats["mean_ret"]:.6f}
Return Std             : {stats["std_ret"]:.6f}
Winrate                : {stats["winrate"]:.4f}
""")

# ============================================================
# SAVE
# ============================================================

out = pd.DataFrame(results)

out_path = Path("/workspaces/RoboTrader812/statistics/reality_modeling_report.csv")

out.to_csv(out_path, index=False)

print(f"\nSaved: {out_path}")
