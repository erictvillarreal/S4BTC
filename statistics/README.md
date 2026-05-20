# S4 Quantitative Statistical Audit

## Objective
This directory contains all statistical validation,
robustness testing, significance analysis,
Monte Carlo simulations, regime filtering,
and market microstructure diagnostics
for the S4 ruled-based quantitative engine.

## Audit Principles
- No modification of current alpha logic
- No modification of execution policy
- No modification of feature generation
- All tests are additive and isolated
- Objective: statistical robustness and reportability

## Modules

### 1. Feature Significance
Permutation importance testing
p-value estimation
feature robustness analysis

### 2. Regime Filter
ATR percentile regime classification
trendiness regime validation
conditional activation diagnostics

### 3. Monte Carlo
Bootstrap resampling
equity path distribution
tail-risk estimation
drawdown distribution

### 4. Market Microstructure
Open interest correlation
liquidation cascade analysis
counterparty hypothesis testing
signal environment classification

### 5. Visualization
Equity curves
distribution plots
feature importance heatmaps
drawdown surfaces

