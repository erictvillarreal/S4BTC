"""
RoboTrader S4 — regime_filter.py
Meta-regime filter para produccion, version causal (sin look-ahead).

Replica la logica de research (s4_enhancement/meta_regime_filter.py)
pero calculado vela-por-vela usando solo historial disponible hasta
el momento de la decision.

Filtro: BULL_AND_HIGHVOL
  trend_regime == BULL_TREND  (close > ema_50 AND close > dma_200)
  vol_q en el top 50% de atr_pct historico (rolling causal)

Resultados documentados (s4_enhancement/integrated_meta_walk_report.csv):
  Winrate:   64.79% -> 72.61%
  Sharpe:    0.6395  -> 0.8534
  Max DD:   -14.42%  -> -7.40%
"""
import numpy as np

DMA_WINDOW   = 200
EMA_WINDOW   = 50
VOL_WINDOW   = 200
VOL_PCTL_MIN = 0.50


def _ema(values: list, span: int) -> float:
    if len(values) < span:
        return float("nan")
    alpha = 2.0 / (span + 1.0)
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema


def regime_ok(close: float, atr: float, close_history: list, atr_history: list) -> tuple:
    """
    close_history, atr_history: historicos cronologicos, sin incluir
    la vela actual. Misma longitud o suficientemente largos (>=200).

    Returns: (ok: bool, trend_regime: str, reason: str)
    """
    n = len(close_history)

    if n < DMA_WINDOW or len(atr_history) < DMA_WINDOW:
        return True, "UNKNOWN", "insufficient_history"

    dma_200 = float(np.mean(close_history[-DMA_WINDOW:]))
    ema_50  = _ema(close_history[-EMA_WINDOW * 3:], EMA_WINDOW)

    if close > ema_50 and close > dma_200:
        trend_regime = "BULL_TREND"
    elif close < ema_50 and close < dma_200:
        trend_regime = "BEAR_TREND"
    elif close > dma_200 and close < ema_50:
        trend_regime = "BULL_WEAK"
    else:
        trend_regime = "BEAR_RALLY"

    window = min(VOL_WINDOW, len(atr_history), len(close_history))
    hist_atr_pct = [
        atr_history[-i] / (close_history[-i] + 1e-12)
        for i in range(1, window + 1)
    ]
    atr_pct_now = atr / (close + 1e-12)
    pctl_rank = float(np.mean([atr_pct_now >= a for a in hist_atr_pct]))
    vol_ok = pctl_rank >= VOL_PCTL_MIN

    is_bull_highvol = (trend_regime == "BULL_TREND") and vol_ok
    if is_bull_highvol:
        reason = "ok"
    elif trend_regime != "BULL_TREND":
        reason = f"regime_not_bull:{trend_regime}"
    else:
        reason = "regime_lowvol"

    return is_bull_highvol, trend_regime, reason
