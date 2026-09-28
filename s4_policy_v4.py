"""
RoboTrader S4 — s4_policy_v4.py (rama research/v4-geometry-no-ml)

DECISION DE DISEÑO (27-sep-2026, Fase 0 v2 + Model Risk Challenger
re-verificado con costos reconciliados Decision 11/12): elimina por
completo el modelo XGBoost del camino de decision.

Evidencia corrida hoy mismo (model_risk_challenger_baseline.py, bajo
Python 3.11.9 / .venv311, costos sin duplicar): el modelo (p_up + EV +
filtros) gana 64.15% de winrate; un short sistematico sin ningun filtro
gana 73.27%, sobre el mismo historial 2022-2026 (n=3250 vs n=28848).
Test z de dos proporciones: z ~= -11. El gap no es ruido de muestra.

El "edge" de S4 nunca fue el modelo -- es la asimetria geometrica
TP=2.0xATR / SL=0.8xATR: 71.4% de probabilidad de short en un random
walk puro (principio de reflexion), 73.5% empirico medido en BTC
perpetual (ver erictvillarreal.github.io/S4BTC, Executive Summary,
"S4 is short-biased by mathematical design, not by prediction").
El propio historial de investigacion del sitio ya apuntaba aqui:
"Camino A" (labels simetricos) fue rechazado porque el modelo no tiene
poder predictivo direccional sin el prior geometrico asimetrico
(ver site/06-roadmap.qmd). Lo nuevo de hoy es la pieza que faltaba:
CON el prior asimetrico, el modelo tampoco aporta -- resta.

Regla de entrada: SHORT SISTEMATICO en cada vela que llegue a decide()
-- sin p_up, sin ev_long/ev_short, sin ev_gap, sin filtro de cuantil de
EV. Reproduce exactamente la metodologia ya validada empiricamente en
model_risk_challenger_baseline.py.

LO QUE SIGUE ACTIVO, SIN CAMBIOS (son controles de riesgo, no el motor
de decision, y no dependen del modelo):
  - _check_kill()          -- kill-switch por MDD (MDD_KILL_PCT)
  - _check_daily_budget()  -- presupuesto diario (RISK_DAILY_PCT)
  - _vol_scale()           -- sizing por volatilidad (ATR-based,
                               mismo residuo conocido 0.75x-1.17x que
                               s4_policy.py, sin cambios aqui)
  - MAX_TRADES_PER_DAY     -- ver NOTA PENDIENTE abajo

NOTA PENDIENTE, NO RESUELTA EN ESTE COMMIT: model_risk_challenger_baseline.py
midio 73.27% ignorando TAMBIEN max_trades_per_day -- tradeando CADA
candidato geometricamente valido, sin cap (~24 trades/dia posibles en
timeframe 1h, contra ~2/dia hoy). Este archivo SI mantiene
MAX_TRADES_PER_DAY como guard activo -- decision conservadora, no la de
"cero cap" que uso el Challenger -- porque remover el cap es un cambio
operacional mucho mayor que nunca se corrio con motor de riesgo
completo (equity compuesta, vol-scaling, kill-switch intra-run): el
73.27% del Challenger usa stake fijo sin componer y sin motor de riesgo
(ver su propio docstring, "Simplificacion deliberada").

ESTE ARCHIVO NO ESTA VALIDADO PARA DEPLOY, NI SIQUIERA A PAPER. Es el
borrador de arquitectura acordado con Eric el 27-sep-2026. Antes de
cualquier deploy hace falta: (1) adaptar walk.py a esta regla exacta
(short sistematico, con y sin cap, probar ambas) y correr un
walk-forward completo con equity compuesta y costos reales; (2) decidir
con Eric si MAX_TRADES_PER_DAY se mantiene o se retira, con evidencia
de ambos escenarios, no una suposicion.
"""
import numpy as np
from dataclasses import dataclass

from config import (
    POSITION_FRAC, POSITION_FRAC_MAX,
    MAX_TRADES_PER_DAY,
    COMMISSION, SLIPPAGE,
    TP_MULT, SL_MULT,
    VOL_SCALE_CLIP, VOL_PCTL, VOL_CUT_FACTOR,
    RISK_DAILY_PCT, MDD_KILL_PCT, DAILY_BUDGET_IS_NET,
)

# Probabilidad estructural citada en erictvillarreal.github.io/S4BTC
# (Executive Summary: 71.4% teorica / 73.5% empirica historica). Aqui
# se usa el numero medido HOY por el Challenger (73.27%, mismo
# historial, costos reconciliados) para el EV informativo. Se usa
# SOLO para reportar un EV en logs/Telegram -- nunca como filtro de
# entrada (a diferencia de s4_policy.py, que sí filtraba por EV).
STRUCTURAL_SHORT_PROB = 0.7327


@dataclass
class Decision:
    take:      bool
    direction: str        # "short" | "none" -- "long" ya no existe en v4
    stake:     float      # USDT a arriesgar (sin leverage)
    tp_price:  float
    sl_price:  float
    ev:        float       # informativo, NO es un filtro (ver docstring)
    p_up:      float       # siempre = STRUCTURAL_SHORT_PROB; se deja el
                            # campo por compatibilidad con trade_logger/
                            # db_logger, que esperan esta clave -- no es
                            # una prediccion del modelo (ya no hay modelo).
    reason:    str

_NO_TRADE_REASON_EV = 0.0


# ── Risk checks (idénticos a s4_policy.py, sin dependencia del modelo) ──

def _check_kill(state: dict) -> bool:
    equity = state["equity"]
    peak   = state["peak_equity"]
    return (equity / peak - 1) <= -MDD_KILL_PCT


def _check_daily_budget(state: dict) -> bool:
    """True si aún hay presupuesto disponible."""
    equity     = state["equity"]
    day_open   = state.get("day_open_equity", equity)
    budget     = day_open * RISK_DAILY_PCT
    if DAILY_BUDGET_IS_NET:
        used = max(0.0, day_open - equity)
    else:
        daily_evs = state.get("daily_evs", [])
        used = sum(e for e in daily_evs if e < 0)
    return used < budget


# ── Volatility sizing (idéntica a s4_policy.py) ──────────────────

def _vol_scale(atr: float, close: float, atr_history: list) -> float:
    """Ver s4_policy._vol_scale para el detalle completo del residuo
    conocido (0.75x-1.17x vs. walk.py). Sin cambios aquí."""
    if len(atr_history) < 10:
        return 1.0
    ratio_hist  = [h / (close + 1e-12) for h in atr_history]
    ref_vol     = float(np.median(ratio_hist))
    extreme_vol = float(np.percentile(ratio_hist, VOL_PCTL * 100))
    ratio       = atr / (close + 1e-12)

    if ref_vol <= 1e-9 or ratio <= 1e-9:
        scale = 1.0
    else:
        scale = float(np.sqrt(ref_vol / ratio))

    if ratio >= extreme_vol:
        scale *= VOL_CUT_FACTOR

    return float(np.clip(scale, *VOL_SCALE_CLIP))


def _geometric_ev_short(close: float, atr: float) -> float:
    """EV informativo con probabilidad estructural FIJA (no predicha) --
    mismo calculo de costos que s4_policy._ev_short (Decision 11, sin
    x2), pero p ya no viene de un modelo. NO se usa como filtro."""
    tp_ret = TP_MULT * atr / close
    sl_ret = SL_MULT * atr / close
    p = STRUCTURAL_SHORT_PROB
    gross = p * tp_ret * close - (1 - p) * abs(sl_ret) * close
    cost  = (COMMISSION + SLIPPAGE) * close  # Decision 11: costo round-trip, sin x2
    return gross - cost


# ── Main decision function ────────────────────────────────

def decide(row: dict, state: dict, atr_history: list) -> Decision:
    """
    Short sistemático puro. row necesita solo 'close' y 'atr' -- ya no
    se leen las FEATURES del modelo (xgboost no se usa en este camino).
    """
    if state.get("kill_switch", False) or _check_kill(state):
        return Decision(False, "none", 0, 0, 0, _NO_TRADE_REASON_EV,
                         STRUCTURAL_SHORT_PROB, "kill_switch")

    if state.get("trades_today", 0) >= MAX_TRADES_PER_DAY:
        return Decision(False, "none", 0, 0, 0, _NO_TRADE_REASON_EV,
                         STRUCTURAL_SHORT_PROB, "max_trades_today")

    if not _check_daily_budget(state):
        return Decision(False, "none", 0, 0, 0, _NO_TRADE_REASON_EV,
                         STRUCTURAL_SHORT_PROB, "daily_budget_exhausted")

    try:
        close = float(row["close"])
        atr   = float(row["atr"])
    except (KeyError, TypeError) as e:
        return Decision(False, "none", 0, 0, 0, _NO_TRADE_REASON_EV,
                         STRUCTURAL_SHORT_PROB, f"missing_field:{e}")

    if atr <= 0 or close <= 0:
        return Decision(False, "none", 0, 0, 0, _NO_TRADE_REASON_EV,
                         STRUCTURAL_SHORT_PROB, "invalid_atr_or_close")

    ev = _geometric_ev_short(close, atr)

    # ── Sizing por volatilidad (idéntico a s4_policy.py) ──
    scale     = _vol_scale(atr, close, atr_history)
    base_frac = POSITION_FRAC * scale
    frac      = min(base_frac, POSITION_FRAC_MAX)
    stake     = state["equity"] * frac          # USDT sin leverage

    # ── Precios TP/SL — siempre short ─────────────────────
    tp_price = close - TP_MULT * atr
    sl_price = close + SL_MULT * atr
    if sl_price <= close:
        sl_price = close * (1 + SL_MULT * 0.001)

    return Decision(
        take=True,
        direction="short",
        stake=stake,
        tp_price=tp_price,
        sl_price=sl_price,
        ev=ev,
        p_up=STRUCTURAL_SHORT_PROB,
        reason="ok_geometric_short",
    )


if __name__ == "__main__":
    from state import load, roll_day

    state = roll_day(load())

    test_row = {"atr": 800.0, "close": 65000.0}
    atr_hist = [700.0 + i * 2 for i in range(100)]

    d = decide(test_row, state, atr_hist)
    print(f"Decision: take={d.take} dir={d.direction} stake={d.stake:.2f} "
          f"tp={d.tp_price:.2f} sl={d.sl_price:.2f} ev={d.ev:.4f} "
          f"p_up={d.p_up:.4f} reason={d.reason}")
