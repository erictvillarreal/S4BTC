from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent

ledger_path = Path("/workspaces/RoboTrader812/s4_deploy/trade_ledger.csv")

if not ledger_path.exists():
    raise FileNotFoundError(f"No existe: {ledger_path}")

df = pd.read_csv(ledger_path)

# =====================================================
# CONFIG
# =====================================================

N_SIM = 2000
START_EQUITY = 1000.0
BLOCK_SIZE = 20

# =====================================================
# RETURNS
# =====================================================

returns = df["pnl"] / df["equity_before"]

returns = (
    returns
    .replace([np.inf, -np.inf], np.nan)
    .dropna()
    .astype(float)
    .values
)

print(f"Trades loaded: {len(returns)}")

# =====================================================
# HELPERS
# =====================================================

def build_equity_curve(rets, start=START_EQUITY):

    eq = [start]

    for r in rets:
        eq.append(eq[-1] * (1.0 + r))

    return np.array(eq)

def max_drawdown(eq):

    peak = np.maximum.accumulate(eq)

    dd = eq / peak - 1.0

    return float(dd.min())

def summarize(name, final_eq, mdds):

    print("\n" + "=" * 60)
    print(name)
    print("=" * 60)

    print(f"Median Final Equity : {np.median(final_eq):,.2f}")
    print(f"Mean Final Equity   : {np.mean(final_eq):,.2f}")

    print(f"5th Percentile      : {np.percentile(final_eq,5):,.2f}")
    print(f"95th Percentile     : {np.percentile(final_eq,95):,.2f}")

    print(f"Median MDD          : {np.median(mdds):.4f}")
    print(f"Worst MDD           : {np.min(mdds):.4f}")

# =====================================================
# MONTE CARLO #1
# RESHUFFLE
# =====================================================

reshuffle_final = []
reshuffle_mdd = []

print("\nRunning Reshuffle Monte Carlo...")

for i in range(N_SIM):

    shuffled = np.random.permutation(returns)

    eq = build_equity_curve(shuffled)

    reshuffle_final.append(eq[-1])

    reshuffle_mdd.append(max_drawdown(eq))

    if (i + 1) % 100 == 0:
        print(f"Reshuffle: {i+1}/{N_SIM}")

# =====================================================
# MONTE CARLO #2
# BOOTSTRAP
# =====================================================

bootstrap_final = []
bootstrap_mdd = []

print("\nRunning Bootstrap Monte Carlo...")

for i in range(N_SIM):

    sample = np.random.choice(
        returns,
        size=len(returns),
        replace=True
    )

    eq = build_equity_curve(sample)

    bootstrap_final.append(eq[-1])

    bootstrap_mdd.append(max_drawdown(eq))

    if (i + 1) % 100 == 0:
        print(f"Bootstrap: {i+1}/{N_SIM}")

# =====================================================
# MONTE CARLO #3
# BLOCK BOOTSTRAP
# =====================================================

block_final = []
block_mdd = []

print("\nRunning Block Bootstrap Monte Carlo...")

for i in range(N_SIM):

    sampled = []

    while len(sampled) < len(returns):

        start = np.random.randint(
            0,
            len(returns) - BLOCK_SIZE
        )

        sampled.extend(
            returns[start:start + BLOCK_SIZE]
        )

    sampled = np.array(sampled[:len(returns)])

    eq = build_equity_curve(sampled)

    block_final.append(eq[-1])

    block_mdd.append(max_drawdown(eq))

    if (i + 1) % 100 == 0:
        print(f"Block Bootstrap: {i+1}/{N_SIM}")

# =====================================================
# TO NUMPY
# =====================================================

reshuffle_final = np.array(reshuffle_final)
bootstrap_final = np.array(bootstrap_final)
block_final = np.array(block_final)

reshuffle_mdd = np.array(reshuffle_mdd)
bootstrap_mdd = np.array(bootstrap_mdd)
block_mdd = np.array(block_mdd)

# =====================================================
# SUMMARY
# =====================================================

summarize(
    "RESHUFFLE",
    reshuffle_final,
    reshuffle_mdd
)

summarize(
    "BOOTSTRAP",
    bootstrap_final,
    bootstrap_mdd
)

summarize(
    "BLOCK BOOTSTRAP",
    block_final,
    block_mdd
)

# =====================================================
# SAVE RESULTS CSV
# =====================================================

results = pd.DataFrame({
    "reshuffle_final": reshuffle_final,
    "reshuffle_mdd": reshuffle_mdd,
    "bootstrap_final": bootstrap_final,
    "bootstrap_mdd": bootstrap_mdd,
    "block_final": block_final,
    "block_mdd": block_mdd,
})

results.to_csv(
    BASE / "montecarlo_results.csv",
    index=False
)

print("\nSaved: statistics/montecarlo_results.csv")

# =====================================================
# HISTOGRAM
# =====================================================

plt.figure(figsize=(12,7))

plt.hist(
    reshuffle_final,
    bins=50,
    alpha=0.5,
    label="Reshuffle"
)

plt.hist(
    bootstrap_final,
    bins=50,
    alpha=0.5,
    label="Bootstrap"
)

plt.hist(
    block_final,
    bins=50,
    alpha=0.5,
    label="Block Bootstrap"
)

plt.xlabel("Final Equity")
plt.ylabel("Frequency")

plt.title("Monte Carlo Final Equity Distribution")

plt.legend()

plt.grid(True)

plt.savefig(
    BASE / "montecarlo_distribution.png",
    dpi=300
)

print("Saved: statistics/montecarlo_distribution.png")

# =====================================================
# EQUITY CURVES SAMPLE
# =====================================================

plt.figure(figsize=(12,7))

for _ in range(100):

    shuffled = np.random.permutation(returns)

    eq = build_equity_curve(shuffled)

    plt.plot(eq, alpha=0.15)

plt.title("Monte Carlo Equity Curve Samples")
plt.xlabel("Trades")
plt.ylabel("Equity")

plt.grid(True)

plt.savefig(
    BASE / "montecarlo_equity_curves.png",
    dpi=300
)

print("Saved: statistics/montecarlo_equity_curves.png")
