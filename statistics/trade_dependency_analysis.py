from pathlib import Path
import pandas as pd
import numpy as np

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 220)

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
]

for c in required:
    if c not in df.columns:
        raise ValueError(f"Missing required column: {c}")

df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)

df = df.sort_values("time").reset_index(drop=True)

# ============================================================
# BASIC FLAGS
# ============================================================

df["win"] = (df["pnl"] > 0).astype(int)
df["loss"] = (df["pnl"] <= 0).astype(int)

# ============================================================
# STREAK ANALYSIS
# ============================================================

win_streaks = []
loss_streaks = []

current_win = 0
current_loss = 0

for x in df["win"]:

    if x == 1:
        current_win += 1

        if current_loss > 0:
            loss_streaks.append(current_loss)
            current_loss = 0

    else:
        current_loss += 1

        if current_win > 0:
            win_streaks.append(current_win)
            current_win = 0

if current_win > 0:
    win_streaks.append(current_win)

if current_loss > 0:
    loss_streaks.append(current_loss)

# ============================================================
# CONDITIONAL WINRATES
# ============================================================

df["prev_win"] = df["win"].shift(1)
df["prev2_win"] = df["win"].shift(2)

after_win = df[df["prev_win"] == 1]
after_loss = df[df["prev_win"] == 0]

after_2wins = df[(df["prev_win"] == 1) & (df["prev2_win"] == 1)]
after_2loss = df[(df["prev_win"] == 0) & (df["prev2_win"] == 0)]

# ============================================================
# AUTOCORRELATION
# ============================================================

ret_series = df["ret_realized"].fillna(0)

acf_1 = ret_series.autocorr(lag=1)
acf_2 = ret_series.autocorr(lag=2)
acf_5 = ret_series.autocorr(lag=5)
acf_10 = ret_series.autocorr(lag=10)

# ============================================================
# CLUSTERING ANALYSIS
# ============================================================

rolling_wr = (
    df["win"]
    .rolling(50)
    .mean()
)

rolling_ret = (
    df["ret_realized"]
    .rolling(50)
    .mean()
)

best_cluster = rolling_ret.max()
worst_cluster = rolling_ret.min()

# ============================================================
# REPORT
# ============================================================

print("\n")
print("=" * 70)
print("TRADE DEPENDENCY ANALYSIS")
print("=" * 70)

print(f"""
TOTAL TRADES              : {len(df)}

GLOBAL WINRATE            : {df["win"].mean():.4f}

AVG WIN STREAK            : {np.mean(win_streaks):.2f}
MAX WIN STREAK            : {np.max(win_streaks)}

AVG LOSS STREAK           : {np.mean(loss_streaks):.2f}
MAX LOSS STREAK           : {np.max(loss_streaks)}

WINRATE AFTER WIN         : {after_win["win"].mean():.4f}
WINRATE AFTER LOSS        : {after_loss["win"].mean():.4f}

WINRATE AFTER 2 WINS      : {after_2wins["win"].mean():.4f}
WINRATE AFTER 2 LOSSES    : {after_2loss["win"].mean():.4f}

RET AUTOCORR LAG1         : {acf_1:.4f}
RET AUTOCORR LAG2         : {acf_2:.4f}
RET AUTOCORR LAG5         : {acf_5:.4f}
RET AUTOCORR LAG10        : {acf_10:.4f}

BEST 50-TRADE CLUSTER     : {best_cluster:.5f}
WORST 50-TRADE CLUSTER    : {worst_cluster:.5f}
""")

# ============================================================
# SAVE
# ============================================================

summary = pd.DataFrame({
    "metric": [
        "global_winrate",
        "avg_win_streak",
        "max_win_streak",
        "avg_loss_streak",
        "max_loss_streak",
        "winrate_after_win",
        "winrate_after_loss",
        "winrate_after_2wins",
        "winrate_after_2losses",
        "acf_lag1",
        "acf_lag2",
        "acf_lag5",
        "acf_lag10",
        "best_cluster_50",
        "worst_cluster_50",
    ],
    "value": [
        df["win"].mean(),
        np.mean(win_streaks),
        np.max(win_streaks),
        np.mean(loss_streaks),
        np.max(loss_streaks),
        after_win["win"].mean(),
        after_loss["win"].mean(),
        after_2wins["win"].mean(),
        after_2loss["win"].mean(),
        acf_1,
        acf_2,
        acf_5,
        acf_10,
        best_cluster,
        worst_cluster,
    ]
})

out_path = Path("/workspaces/RoboTrader812/statistics/trade_dependency_report.csv")

summary.to_csv(out_path, index=False)

print(f"\nSaved: {out_path}")
