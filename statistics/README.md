# S4 Statistical Due Diligence
## Institutional Quantitative Audit — Research Layer

Author: Eric Trevino  
Project: S4 BTC Systematic Trading Engine  
Environment: Walk-Forward / Regime-Aware / EV-Based Quant Framework

---

# OBJECTIVE

The purpose of this directory is to perform a full institutional-grade statistical due diligence process over the S4 trading engine before:

- live deployment,
- leverage scaling,
- external capital allocation,
- or production integration.

This audit attempts to answer:

1. Does the strategy possess statistically significant edge?
2. Is the edge robust across regimes?
3. Is the system overfit?
4. Can the strategy survive realistic market frictions?
5. Is the edge scalable with leverage and sizing?
6. Can the edge survive randomized sanity tests?
7. Does the strategy exhibit conditional alpha or structural alpha?

---

# BASELINE SYSTEM SNAPSHOT

## Core Walk-Forward Results

Dataset:
- BTCUSDT 1H
- ~33,140 observations
- 2022–2026

Walk-forward configuration:
- 180-day rolling train window
- 14-day test step
- calibrated probabilities
- EV-based trade selection
- leverage-aware risk constraints

---

## BASELINE PERFORMANCE

| Metric | Value |
|---|---|
| Final Equity | $7,989 |
| Starting Equity | $1,000 |
| CAGR | ~72% |
| Winrate | 64.65% |
| Trades | 2,968 |
| Mean Accuracy | 61.63% |
| Mean F1 | 0.218 |
| Mean Precision | 0.286 |
| Mean Recall | 0.266 |
| Max Drawdown (Daily) | -2.04% |
| Max Drawdown (Intraday) | -2.14% |
| Worst Daily Return | -0.40% |

---

# PRIORITY 1 — PROBABILITY CALIBRATION AUDIT

## Objective

Validate whether predicted probabilities correspond to realized outcomes.

This phase aimed to detect:
- overconfidence,
- probability drift,
- threshold distortion,
- false certainty.

---

## Files

- calibration.py
- calibration_table.csv
- reliability_diagram.png
- probability_sharpness.png
- confidence_analysis.csv

---

## Findings

The calibration audit revealed a major issue:

### Predicted probabilities were overconfident.

Observed:

- high-confidence predictions did NOT translate into proportionally higher realized winrates.
- confidence bins clustered near 0.50.
- model confidence compressed aggressively.

Example:

| Avg Confidence | Realized Winrate |
|---|---|
| 0.49 | 0.23 |
| 0.47 | 0.30 |
| 0.45 | 0.28 |

This indicated:
- poor probabilistic calibration,
- weak separation power,
- threshold instability.

---

## Recalibration Research

A secondary recalibration study was later performed in:

/s4_enhancement/probabilistic_recalibration.py

Results:

| Model | Brier | LogLoss | F1 |
|---|---|---|---|
| RAW | 0.292 | 1.031 | 0.269 |
| ISOTONIC | 0.211 | 1.121 | 0.0005 |
| PLATT | 0.210 | 1.115 | 0.0000 |

---

## Interpretation

Recalibration improved:
- Brier score,
- probability consistency.

BUT:
- destroyed F1 classification performance.

Conclusion:
- probabilities became statistically smoother,
- but thresholds became invalid.

This strongly suggests:

### Future work requires:
- EV-aware thresholds,
- percentile thresholds,
- dynamic decision boundaries,
- calibration-aware walk-forward integration.

---

# PRIORITY 2 — REGIME SEGMENTATION

## Objective

Determine:
- where the edge exists,
- where it disappears,
- and when the strategy should deactivate.

---

## Files

- regime_segmentation.py
- regime_volatility.csv
- trend_regime_segmentation.py
- trend_regime_report.csv
- dma200_report.csv
- regime_analysis.py
- regime_report.csv

---

# VOLATILITY REGIMES

| Regime | Winrate | Avg Return |
|---|---|---|
| Q4_HIGH | 64.15% | 1.24% |
| Q3_MEDHIGH | 67.03% | 0.87% |
| Q2_MEDLOW | 63.55% | 0.59% |
| Q1_LOW | 64.45% | 0.36% |

---

## Key Discovery

The strategy performs best during:
- elevated volatility,
- volatility expansion states.

---

# TREND REGIMES

| Regime | Winrate | Avg Return |
|---|---|---|
| BULL_TREND | 67.38% | 0.85% |
| BEAR_TREND | 64.08% | 0.74% |
| BULL_WEAK | 64.90% | 0.72% |
| BEAR_RALLY | 56.77% | 0.56% |

---

# 200 DMA REGIMES

| Regime | Winrate |
|---|---|
| ABOVE_200DMA | 66.89% |
| BELOW_200DMA | 62.52% |

---

## Interpretation

The system is NOT:
- always-on alpha.

Instead, it behaves as:

### conditional regime alpha.

Best environments:
- bullish trend,
- above 200DMA,
- high volatility.

Worst environment:
- bear rallies.

This later motivated:
- meta-regime filtering research,
- regime-aware leverage,
- future dynamic system activation.

---

# PRIORITY 3 — REALITY MODELING

## Objective

Stress-test the system under realistic trading conditions.

---

## Files

- reality_modeling.py
- reality_modeling_report.csv

---

## Simulated Frictions

Included:
- spread widening,
- slippage expansion,
- liquidity degradation,
- execution friction.

---

## Results

| Scenario | Outcome |
|---|---|
| BASELINE | Extremely profitable |
| LIGHT_FRICTION | Survived |
| MEDIUM_FRICTION | Survived |
| HEAVY_FRICTION | Survived |
| EXTREME_FRICTION | Collapsed |

---

## Interpretation

The edge survives:
- realistic execution friction,
- moderate liquidity degradation.

But:
- catastrophic friction destroys profitability.

This suggests:
- the edge is real,
- but execution quality remains critical.

---

# PRIORITY 4 — POSITION SIZING RESEARCH

## Objective

Determine:
- optimal leverage,
- Kelly sizing,
- volatility targeting feasibility.

---

## Files

- fractional_kelly_research.py
- fractional_kelly_report.csv
- vol_targeting_report.csv

---

## Results

### Kelly Fraction

Estimated full Kelly:

0.505

This is unusually high for systematic trading systems.

---

## Fractional Kelly

| Fraction | Max DD |
|---|---|
| 0.10 Kelly | -0.78% |
| 0.25 Kelly | -1.94% |
| 0.50 Kelly | -3.84% |
| 1.00 Kelly | -7.54% |

---

## Interpretation

The system appears:
- risk scalable,
- leverage tolerant,
- structurally smooth.

This is atypical for overfit systems.

---

# PRIORITY 5 — RANDOMIZED LABEL SANITY CHECK

## Objective

Determine whether the model extracts genuine signal or exploits noise.

---

## Files

- randomized_labels_sanity.py
- randomized_labels_report.csv

---

## Results

| Metric | Value |
|---|---|
| Mean Accuracy | 72.9% |
| Mean Precision | 0.044 |
| Mean Recall | 0.009 |
| Mean F1 | 0.014 |

---

## Interpretation

When labels were randomized:
- predictive quality collapsed,
- F1 nearly vanished,
- recall disappeared.

This strongly suggests:
- the original model was NOT simply memorizing noise.

---

# PRIORITY 6 — TRADE DEPENDENCY ANALYSIS

## Objective

Study:
- clustering,
- path dependency,
- serial correlation,
- streak behavior.

---

## Files

- trade_dependency_analysis.py
- trade_dependency_report.csv

---

## Results

| Metric | Value |
|---|---|
| Global Winrate | 64.79% |
| Avg Win Streak | 17.94 |
| Max Win Streak | 120 |
| Avg Loss Streak | 9.75 |
| Max Loss Streak | 52 |
| Lag1 Autocorr | 0.851 |

---

## Interpretation

Trades exhibit:
- significant clustering,
- non-random sequencing,
- persistent market-state behavior.

This further supports:
- regime dependence,
- structural conditional alpha.

---

# PRIORITY 7 — WHITE'S REALITY CHECK / SPA

## Objective

Test whether the observed edge survives:
- multiple testing bias,
- data snooping concerns.

---

## Files

- whites_reality_check.py
- whites_reality_check_report.csv

---

## Results

| Metric | Value |
|---|---|
| Observed Mean Return | 0.007652 |
| White RC p-value | 0.506 |
| SPA Sign-Flip p-value | 0.000 |

---

## Interpretation

### White RC FAILED
### SPA approximation PASSED

Interpretation:
- possible sensitivity to data-mining,
- BUT edge survives sign-flip SPA testing.

This result is mixed:
- not definitive proof,
- but not a rejection either.

---

# MONTE CARLO ANALYSIS

## Objective

Stress-test return distribution robustness.

---

## Files

- montecarlo.py
- montecarlo_results.csv
- montecarlo_distribution.png
- montecarlo_equity_curves.png

---

## Purpose

Evaluate:
- path variability,
- probabilistic survivability,
- drawdown robustness,
- compounding stability.

---

# FEATURE SIGNIFICANCE / STABILITY

## Objective

Measure:
- feature importance,
- feature stability,
- overfit indicators.

---

## Files

- feature_significance.py
- feature_significance_full.csv
- feature_significance_summary.csv

---

## Findings

Most features displayed:
- unstable importance,
- shifting predictive contribution.

Highly unstable:
- volume,
- MACD derivatives,
- EMA structures,
- RSI,
- ATR.

---

## Interpretation

This suggests:
- the edge may emerge from feature interaction,
- not single dominant predictors.

Also suggests:
- regime dependence,
- dynamic feature relevance,
- possible need for adaptive models.

---

# META-REGIME RESEARCH (TRANSITION TO /s4_enhancement)

Later research discovered:

## Filtering by:
- bullish trend,
- high volatility,
- above 200DMA

significantly improved system quality.

---

## Integrated Meta-Regime Walk

Best result:

### BULL_AND_HIGHVOL

| Metric | Value |
|---|---|
| Winrate | 72.61% |
| Sharpe-like | 0.853 |
| Max DD | -7.4% |

vs baseline:

| Metric | Value |
|---|---|
| Winrate | 64.79% |
| Sharpe-like | 0.639 |
| Max DD | -14.4% |

---

# FINAL CONCLUSIONS

The audit strongly suggests:

## The system likely possesses genuine conditional edge.

Evidence:
- survives randomized labels,
- survives realistic friction,
- improves coherently under favorable regimes,
- displays structured clustering,
- remains profitable under leverage scaling.

---

# HOWEVER

The system is NOT yet production-grade.

Remaining critical tasks:

1. Live shadow deployment
2. Calibration-aware walk-forward
3. Dynamic thresholds
4. Funding/perp features
5. Microstructure signals
6. Order-flow integration
7. Live execution validation

---

# CURRENT CLASSIFICATION

The system is currently best described as:

### "Research-grade promising systematic strategy"

NOT yet:
- institutional production system.

BUT:
- substantially beyond hobby backtesting.

