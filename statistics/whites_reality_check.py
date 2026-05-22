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

required = ["ret_realized"]

for c in required:
    if c not in df.columns:
        raise ValueError(f"Missing required column: {c}")

rets = df["ret_realized"].astype(float).values

# ============================================================
# BASE STATS
# ============================================================

mean_ret = np.mean(rets)
std_ret  = np.std(rets)

sharpe = (
    mean_ret / (std_ret + 1e-12)
)

print("\n")
print("=" * 90)
print("BASE STRATEGY")
print("=" * 90)

print(f"Mean Return     : {mean_ret:.6f}")
print(f"Std Return      : {std_ret:.6f}")
print(f"Sharpe-like     : {sharpe:.6f}")

# ============================================================
# WHITE REALITY CHECK
# ============================================================

# Null hypothesis:
# Strategy has no real predictive edge.
# Returns are exchangeable/random.

N_BOOT = 5000

boot_means = []

rng = np.random.default_rng(42)

print("\nRunning bootstrap reality check...\n")

for i in range(N_BOOT):

    sample = rng.choice(rets, size=len(rets), replace=True)

    boot_mean = np.mean(sample)

    boot_means.append(boot_mean)

    if (i + 1) % 250 == 0:
        print(f"Bootstrap {i+1}/{N_BOOT}")

boot_means = np.array(boot_means)

# ============================================================
# P-VALUE
# ============================================================

p_value = np.mean(boot_means >= mean_ret)

# ============================================================
# CONFIDENCE INTERVALS
# ============================================================

ci_95_low  = np.percentile(boot_means, 2.5)
ci_95_high = np.percentile(boot_means, 97.5)

# ============================================================
# RANDOM SIGN-FLIP TEST
# ============================================================

print("\nRunning sign-flip SPA approximation...\n")

flip_means = []

for i in range(N_BOOT):

    signs = rng.choice([-1, 1], size=len(rets))

    flipped = rets * signs

    flip_mean = np.mean(flipped)

    flip_means.append(flip_mean)

    if (i + 1) % 250 == 0:
        print(f"SPA Flip {i+1}/{N_BOOT}")

flip_means = np.array(flip_means)

spa_pvalue = np.mean(flip_means >= mean_ret)

# ============================================================
# OUTPUT
# ============================================================

print("\n")
print("=" * 90)
print("WHITE REALITY CHECK / SPA")
print("=" * 90)

print(f"\nObserved Mean Return      : {mean_ret:.6f}")

print(f"\nBootstrap Mean            : {boot_means.mean():.6f}")
print(f"Bootstrap Std             : {boot_means.std():.6f}")

print(f"\n95% CI LOW                : {ci_95_low:.6f}")
print(f"95% CI HIGH               : {ci_95_high:.6f}")

print(f"\nWhite RC p-value          : {p_value:.6f}")

print(f"\nSPA Sign-Flip p-value     : {spa_pvalue:.6f}")

# ============================================================
# INTERPRETATION
# ============================================================

print("\n")
print("=" * 90)
print("INTERPRETATION")
print("=" * 90)

if p_value < 0.05:
    print("\nWhite RC PASSED (<0.05)")
else:
    print("\nWhite RC FAILED")

if spa_pvalue < 0.05:
    print("SPA approximation PASSED (<0.05)")
else:
    print("SPA approximation FAILED")

# ============================================================
# SAVE
# ============================================================

out = pd.DataFrame({
    "metric": [
        "mean_return",
        "std_return",
        "sharpe_like",
        "white_rc_pvalue",
        "spa_signflip_pvalue",
        "ci_95_low",
        "ci_95_high"
    ],
    "value": [
        mean_ret,
        std_ret,
        sharpe,
        p_value,
        spa_pvalue,
        ci_95_low,
        ci_95_high
    ]
})

save_path = "/workspaces/RoboTrader812/statistics/whites_reality_check_report.csv"

out.to_csv(save_path, index=False)

print(f"\nSaved: {save_path}")

