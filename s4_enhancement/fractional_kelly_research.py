from pathlib import Path
import pandas as pd
import numpy as np

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 260)

# ============================================================
# LOAD
# ============================================================

ledger_path = Path("/workspaces/RoboTrader812/s4_deploy/trade_ledger.csv")

if not ledger_path.exists():
    raise FileNotFoundError(ledger_path)

df = pd.read_csv(ledger_path)

print(f"\nTrades loaded: {len(df)}")

# ============================================================
# RETURNS
# ============================================================

rets = df["ret_realized"].astype(float).values

wins = rets[rets > 0]
loss = np.abs(rets[rets < 0])

p = len(wins) / len(rets)
q = 1 - p

avg_win = wins.mean()
avg_loss = loss.mean()

b = avg_win / avg_loss

kelly_full = (b * p - q) / b

print("\n============================================================")
print("BASE STATISTICS")
print("============================================================")

print(f"Winrate              : {p:.4f}")
print(f"Avg Win              : {avg_win:.6f}")
print(f"Avg Loss             : {avg_loss:.6f}")
print(f"Payoff Ratio (b)     : {b:.4f}")
print(f"Full Kelly Fraction  : {kelly_full:.4f}")

# ============================================================
# KELLY FRACTIONS
# ============================================================

fractions = {
    "0.10_KELLY": 0.10 * kelly_full,
    "0.25_KELLY": 0.25 * kelly_full,
    "0.50_KELLY": 0.50 * kelly_full,
    "0.75_KELLY": 0.75 * kelly_full,
    "1.00_KELLY": 1.00 * kelly_full,
}

results = []

# ============================================================
# SIMULATE
# ============================================================

for name, frac in fractions.items():

    equity = 1.0
    curve = [equity]

    for r in rets:

        position_ret = frac * r

        equity *= (1 + position_ret)

        curve.append(equity)

    curve = np.array(curve)

    peaks = np.maximum.accumulate(curve)

    dd = (curve - peaks) / peaks

    final_multiple = curve[-1]

    cagr_like = (final_multiple ** (1 / max(len(rets)/365, 1e-9))) - 1

    sharpe_like = (
        np.mean(frac * rets)
        /
        (np.std(frac * rets) + 1e-12)
    )

    results.append({
        "scenario": name,
        "fraction_used": frac,
        "final_multiple": final_multiple,
        "max_drawdown": dd.min(),
        "mean_return": np.mean(frac * rets),
        "std_return": np.std(frac * rets),
        "sharpe_like": sharpe_like,
        "cagr_like": cagr_like,
    })

# ============================================================
# RESULTS
# ============================================================

res = pd.DataFrame(results)

res = res.sort_values("sharpe_like", ascending=False)

print("\n============================================================")
print("FRACTIONAL KELLY RESULTS")
print("============================================================")

print(res)

# ============================================================
# VOL TARGETING
# ============================================================

print("\n============================================================")
print("VOLATILITY TARGETING")
print("============================================================")

target_vols = [0.005, 0.01, 0.015, 0.02]

vol_results = []

base_std = np.std(rets)

for tv in target_vols:

    leverage = tv / (base_std + 1e-12)

    scaled = rets * leverage

    equity = np.cumprod(1 + scaled)

    peaks = np.maximum.accumulate(equity)

    dd = (equity - peaks) / peaks

    vol_results.append({
        "target_vol": tv,
        "implied_leverage": leverage,
        "final_multiple": equity[-1],
        "max_drawdown": dd.min(),
        "mean_return": scaled.mean(),
        "std_return": scaled.std(),
        "sharpe_like": scaled.mean() / (scaled.std() + 1e-12),
    })

vol_df = pd.DataFrame(vol_results)

print(vol_df)

# ============================================================
# SAVE
# ============================================================

out1 = Path("/workspaces/RoboTrader812/s4_enhancement/fractional_kelly_report.csv")
out2 = Path("/workspaces/RoboTrader812/s4_enhancement/vol_targeting_report.csv")

res.to_csv(out1, index=False)
vol_df.to_csv(out2, index=False)

print("\n============================================================")
print("SAVED")
print("============================================================")
print(out1)
print(out2)

