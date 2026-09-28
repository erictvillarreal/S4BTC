"""
Model Risk Challenger — model_risk_challenger_baseline.py
Primer entregable (Model_Risk_Challenger_Spec.md, "Primera linea de ataque").

Pregunta que responde: el modelo (p_up) realmente aporta algo sobre la
asimetria geometrica TP=2xATR / SL=0.8xATR, o el resultado observado se
explica igual de bien con un short sistematico sin filtro de p_up?

Metodo: toma TODOS los candidatos de walk_candidates.csv -- cada vela que
ya paso el criterio geometrico de ATR para ser candidata, sin importar si
el modelo la eligio o no (chosen_flag) -- y simula CADA UNA como short,
ignorando por completo p_up, ev_gap y max_trades_per_day. Compara el
agregado (retorno, drawdown, winrate) contra walk_summary.json, que es
lo que S4 realmente opero (modelo + filtros) sobre el mismo historial.

Simplificacion deliberada, documentada: usa position sizing fijo
(POSITION_FRAC de config.py sobre equity compuesta), sin el motor de
riesgo completo de walk.py (vol-scaling, risk caps, kill-switch
intra-simulacion, presupuesto diario). Es suficiente para responder la
pregunta direccional (aporta o no el filtro de p_up) -- no reproduce el
walk-forward de produccion byte a byte, y no pretende hacerlo. No
reimplementa calculo de EV/costos: reutiliza directamente ret_tp_short/
ret_sl_short/label ya generados por make_labeled_dataset.py.

NO escribe a produccion, NO toca trader.py, NO escribe a la DB, NO se
integra al loop de trading. Nivel de autonomia del Challenger: proponer
y cuantificar unicamente -- este script reporta el hallazgo, no actua
sobre el.
"""
import json
from pathlib import Path

import pandas as pd

from config import COMMISSION, SLIPPAGE, POSITION_FRAC, LEVERAGE, LABELED_CSV

BASE_DIR = Path(__file__).resolve().parent
CANDIDATES_CSV = BASE_DIR / "walk_candidates.csv"
WALK_SUMMARY_JSON = BASE_DIR / "walk_summary.json"

INITIAL_EQUITY = 1000.0


def load_candidates_with_returns() -> pd.DataFrame:
    """Une walk_candidates.csv (todos los candidatos, con y sin chosen_flag)
    contra el dataset etiquetado, por open_time, para obtener label y los
    retornos teoricos de TP/SL en short."""
    cand = pd.read_csv(CANDIDATES_CSV, parse_dates=["open_time"])
    labeled = pd.read_csv(LABELED_CSV, parse_dates=["open_time"])
    # walk_candidates.csv se escribio con timestamps naive UTC (walk.py les
    # quita el tz antes de procesar) -- normalizamos labeled igual para el join.
    labeled["open_time"] = pd.to_datetime(labeled["open_time"], utc=True).dt.tz_localize(None)
    labeled = labeled[["open_time", "label", "ret_tp_short", "ret_sl_short"]]
    merged = cand.merge(labeled, on="open_time", how="inner")
    merged = merged.sort_values("open_time").reset_index(drop=True)
    return merged


def simulate_baseline_short(df: pd.DataFrame, initial_equity: float = INITIAL_EQUITY) -> dict:
    """
    Simula CADA fila de df como un short forzado -- sin filtro de p_up,
    ev_gap, ni max_trades_per_day.

    Sizing: stake FIJO por trade (POSITION_FRAC * initial_equity, sin
    componer), no equity compuesta -- deliberado. Con ~26k trades y sin
    el motor de riesgo completo de walk.py (vol-scaling, risk caps),
    componer sobre equity creciente dispara el resultado a numeros sin
    sentido economico (se probo: >10^11% de retorno). Stake fijo aisla
    la pregunta real (gana o pierde cada trade, y cuanto) del efecto de
    compounding, que no es lo que el Challenger esta poniendo a prueba
    aqui. max_drawdown se reporta en USD acumulados, no en % de equity.

    Short gana si label==0 (precio cerro por debajo -- misma convencion
    que walk.py), pierde si label==1.
    """
    stake_unlev = initial_equity * POSITION_FRAC
    stake_lev = stake_unlev * LEVERAGE
    # Decision 11 (17-sep-2026): COMMISSION/SLIPPAGE ya son costo
    # round-trip completo -- no se multiplica por 2 (ver config.py).
    fees_per_trade = stake_lev * (COMMISSION + SLIPPAGE)

    cum_pnl = 0.0
    peak = 0.0
    max_dd_usd = 0.0
    wins = 0
    n = 0

    for _, row in df.iterrows():
        is_win = (row["label"] == 0)
        ret = row["ret_tp_short"] if is_win else row["ret_sl_short"]
        pnl = stake_lev * float(ret) - fees_per_trade
        cum_pnl += pnl
        peak = max(peak, cum_pnl)
        max_dd_usd = min(max_dd_usd, cum_pnl - peak)
        n += 1
        wins += int(is_win)

    return {
        "n_trades": n,
        "win_rate": (wins / n) if n else None,
        "total_pnl_usd": cum_pnl,
        "return_pct": (cum_pnl / initial_equity) if initial_equity else None,
        "max_drawdown_usd": max_dd_usd,
    }


def load_actual_summary() -> dict:
    """
    Lo que S4 realmente opero (modelo + filtros + motor de riesgo completo
    de walk.py) segun el ultimo walk-forward. OJO: estos numeros SI usan
    equity compuesta y el motor de riesgo real -- no son unidades
    comparables 1:1 contra el baseline de arriba (stake fijo, sin motor
    de riesgo). Solo winrate es directamente comparable entre ambos.
    """
    with open(WALK_SUMMARY_JSON) as f:
        summary = json.load(f)
    return {
        "n_trades": summary["trades_total"],
        "win_rate": summary["win_rate"],
        "equity_final": summary["equity_final"],
        "return_pct": (summary["equity_final"] / INITIAL_EQUITY - 1),
        "max_drawdown": summary["max_drawdown_daily"],
    }


def _fmt_actual(stats: dict) -> str:
    return (f"{'CON modelo (real, S4)':<32} n={stats['n_trades']:>6}  "
            f"winrate={stats['win_rate']:.2%}  retorno={stats['return_pct']:+.1%} "
            f"(compuesto, motor de riesgo completo)  equity_final=${stats['equity_final']:,.2f}  "
            f"maxDD={stats['max_drawdown']:.2%} (% equity)")


def _fmt_baseline(stats: dict) -> str:
    wr = f"{stats['win_rate']:.2%}" if stats.get("win_rate") is not None else "n/a"
    return (f"{'SIN modelo (short sistematico)':<32} n={stats['n_trades']:>6}  "
            f"winrate={wr}  pnl_total=${stats['total_pnl_usd']:,.2f} "
            f"(stake fijo, sin componer)  maxDD=${stats['max_drawdown_usd']:,.2f} (USD acumulados)")


def main():
    print("=== Model Risk Challenger — baseline sin filtro de p_up ===\n")

    merged = load_candidates_with_returns()
    print(f"Candidatos totales unidos (walk_candidates.csv x labeled): {len(merged)}")
    print(f"Rango: {merged['open_time'].min()} -> {merged['open_time'].max()}")

    max_ts = merged["open_time"].max()
    print(f"\n*** AVISO DE COBERTURA: walk_candidates.csv NO llega hasta hoy — el ultimo dato")
    print(f"    es {max_ts}. NO cubre la ventana ago-sep 2026 que motivo este analisis.")
    print(f"    walk_candidates.csv no se regenero en los ultimos retrains. Este baseline es")
    print(f"    sobre TODO el historial disponible (2022-2026), no sobre el periodo reciente. ***\n")

    baseline_full = simulate_baseline_short(merged)
    actual_full = load_actual_summary()

    print("--- Historial completo — comparacion ---")
    print(_fmt_actual(actual_full))
    print(_fmt_baseline(baseline_full))
    print()
    print("NOTA: 'CON modelo' usa equity compuesta + motor de riesgo completo de walk.py.")
    print("'SIN modelo' usa stake fijo, sin componer, sin motor de riesgo (ver docstring).")
    print("Las columnas de retorno/pnl/drawdown NO son comparables 1:1 entre ambas filas —")
    print("estan en unidades distintas (compuesto vs. no compuesto). SOLO winrate es")
    print("directamente comparable, porque es una tasa simple por trade en ambos casos.")
    print()

    print("--- Hallazgo formal (propuesta, no accion) ---")
    if baseline_full["win_rate"] is not None and actual_full["win_rate"] is not None:
        gap = actual_full["win_rate"] - baseline_full["win_rate"]
        print(f"Gap de winrate (modelo - baseline sin modelo): {gap:+.2%}")
        if gap < 0:
            print("El modelo (con p_up + filtros EV) gana MENOS seguido que shortear todo sin filtro,")
            print("sobre el historial completo disponible. Esto es evidencia a favor de la hipotesis")
            print("del Challenger: el filtro de p_up podria no estar aportando valor direccional real.")
    print("Pendiente: esta comparacion es sobre 2022-2026 completo, NO sobre la ventana")
    print("ago-sep 2026 que motivo la preocupacion inicial — walk_candidates.csv no la cubre.")
    print("Para esa ventana especifica, la evidencia disponible es la de model_risk_check.py")
    print("(check_recent_window(), datos reales de trade_ledger).")
    print("Este resultado se reporta como hallazgo formal del Model Risk Challenger.")
    print("No se escribe a produccion ni se toma ninguna accion automatica sobre el.")


if __name__ == "__main__":
    main()
