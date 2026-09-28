"""
RoboTrader S4 — model_risk_check.py
Model Risk Agent — primer entregable (Model_Risk_Agent_Spec.md).

Script de solo lectura y reporte periodico. Evalua si el modelo activo
de S4BTC sigue siendo confiable con la evidencia disponible: calibracion
de p_up, EV realizado vs esperado, cadencia de reentreno, y drift de
dataset entre reentrenos.

NO escribe a trade_ledger ni a strategy_state. NO se integra al loop de
trader.py — corre por separado, on-demand o programado (Seccion 2 del
protocolo: enforcement es codigo deterministico en el camino critico;
esto es capa de analisis periodica, fuera de ese camino).

Solo escribe a incident_log (event_type='model_degraded') cuando un
umbral definido se rompe — nunca tiene autoridad para pausar trading.
"""
import argparse
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import db_logger
from config import LOG_DIR

log = logging.getLogger("robo-s4.model_risk")

STRATEGY_ID = "S4BTC"
RETRAIN_HISTORY_PATH = LOG_DIR / "retrain_history.jsonl"
BACKFILL_EXPERIMENT_ID = "BACKFILL-TELEGRAM-2026-08-19"

# ── Umbrales (aprobados sobre muestra real de 8 trades, 24-ago-2026 —
# todos backfill, cero trades en vivo todavia) ──────────────────────
BIN_SIZE             = 0.05
MIN_BUCKET_N         = 20    # minimo de trades por bucket para evaluar calibracion
MIN_TOTAL_N          = 30    # minimo de trades totales para evaluar EV agregado
CALIBRATION_GAP_MAX  = 0.15  # |winrate_real - punto_medio_bucket| tolerado
EV_GAP_PCT_MAX       = 0.50  # |gap| tolerado como % de ev_expected promedio
RETRAIN_CADENCE_DAYS = 14
RETRAIN_GRACE_DAYS   = 3     # alerta si dias_desde_ultimo > 14 + 3
DRIFT_METRIC_EPSILON = 0.01  # que tan "identicas" deben verse winrate/cagr/max_drawdown para la nota de drift
MIN_RECENT_N         = 20    # mismo criterio que MIN_BUCKET_N -- ventana reciente evaluable


@dataclass
class Finding:
    check: str
    severity: str  # "ok" | "insufficient_sample" | "note" | "warn" | "alert"
    message: str
    detail: dict = field(default_factory=dict)


def fetch_trades(strategy_id: str = STRATEGY_ID, exclude_backfill: bool = False) -> list:
    """Solo lectura. Reutiliza la conexion de db_logger (mismo DATABASE_URL,
    mismo connect_timeout) en vez de reimplementarla aqui."""
    conn = db_logger._get_conn()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT p_up, ev_expected, pnl_net, outcome, experiment_id, ts_close, stake
                FROM trade_ledger
                WHERE strategy_id = %s
            """
            params = [strategy_id]
            if exclude_backfill:
                query += " AND experiment_id IS DISTINCT FROM %s"
                params.append(BACKFILL_EXPERIMENT_ID)
            cur.execute(query, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def bucket_by_p_up(trades: list, bin_size: float = BIN_SIZE) -> list:
    buckets = {}
    for t in trades:
        if t["p_up"] is None:
            continue
        p_up = float(t["p_up"])
        lo = round((int(p_up / bin_size)) * bin_size, 2)
        hi = round(lo + bin_size, 2)
        buckets.setdefault((lo, hi), []).append(t)

    result = []
    for (lo, hi), ts in sorted(buckets.items()):
        n = len(ts)
        n_tp = sum(1 for t in ts if t["outcome"] == "tp")
        n_sl = sum(1 for t in ts if t["outcome"] == "sl")
        n_timeout = sum(1 for t in ts if t["outcome"] == "timeout")
        ev_realized = [float(t["pnl_net"]) for t in ts if t["pnl_net"] is not None]
        ev_expected = [float(t["ev_expected"]) for t in ts if t["ev_expected"] is not None]
        result.append({
            "lo": lo, "hi": hi, "n": n,
            "n_tp": n_tp, "n_sl": n_sl, "n_timeout": n_timeout,
            "winrate_real": (n_tp / n) if n else None,
            "ev_realized_mean": (sum(ev_realized) / len(ev_realized)) if ev_realized else None,
            "ev_expected_mean": (sum(ev_expected) / len(ev_expected)) if ev_expected else None,
        })
    return result


def check_calibration(buckets: list) -> list:
    evaluated = [b for b in buckets if b["n"] >= MIN_BUCKET_N]
    if not evaluated:
        total_n = sum(b["n"] for b in buckets)
        largest = max((b["n"] for b in buckets), default=0)
        return [Finding(
            check="calibration", severity="insufficient_sample",
            message=(
                f"Muestra insuficiente para evaluar calibracion: {total_n} trades totales, "
                f"bucket mas grande tiene {largest} (minimo requerido: {MIN_BUCKET_N})"
            ),
            detail={"buckets": buckets},
        )]

    findings = []
    for b in evaluated:
        midpoint = round((b["lo"] + b["hi"]) / 2, 4)
        gap = abs(b["winrate_real"] - midpoint)
        if gap > CALIBRATION_GAP_MAX:
            findings.append(Finding(
                check="calibration", severity="alert",
                message=(
                    f"Bucket p_up [{b['lo']},{b['hi']}) mal calibrado: modelo dice ~{midpoint:.2f}, "
                    f"winrate real {b['winrate_real']:.2f} (n={b['n']}, gap={gap:.2f} > {CALIBRATION_GAP_MAX})"
                ),
                detail=b,
            ))
        else:
            findings.append(Finding(
                check="calibration", severity="ok",
                message=f"Bucket [{b['lo']},{b['hi']}) calibrado OK (n={b['n']}, gap={gap:.2f})",
                detail=b,
            ))
    return findings


def check_ev_gap(trades: list) -> Finding:
    n = len(trades)
    if n < MIN_TOTAL_N:
        return Finding(
            check="ev_gap", severity="insufficient_sample",
            message=f"Muestra insuficiente para EV agregado: {n} trades (minimo requerido: {MIN_TOTAL_N})",
        )

    realized = [float(t["pnl_net"]) for t in trades if t["pnl_net"] is not None]
    expected = [float(t["ev_expected"]) for t in trades if t["ev_expected"] is not None]
    mean_realized = (sum(realized) / len(realized)) if realized else 0.0
    mean_expected = (sum(expected) / len(expected)) if expected else 0.0

    sign_mismatch = (mean_realized > 0) != (mean_expected > 0)
    gap_pct = abs(mean_realized - mean_expected) / abs(mean_expected) if mean_expected else None

    if sign_mismatch or (gap_pct is not None and gap_pct > EV_GAP_PCT_MAX):
        reason = "signos opuestos" if sign_mismatch else f"gap {gap_pct:.0%} > {EV_GAP_PCT_MAX:.0%}"
        return Finding(
            check="ev_gap", severity="alert",
            message=f"EV realizado ({mean_realized:.4f}) diverge de EV esperado ({mean_expected:.4f}) — {reason}",
            detail={"mean_realized": mean_realized, "mean_expected": mean_expected, "n": n},
        )
    return Finding(
        check="ev_gap", severity="ok",
        message=f"EV realizado ({mean_realized:.4f}) vs esperado ({mean_expected:.4f}) dentro de rango (n={n})",
        detail={"mean_realized": mean_realized, "mean_expected": mean_expected, "n": n},
    )


def _load_retrain_history(path: Path) -> list:
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    entries.sort(key=lambda e: e["timestamp"])
    return entries


def check_retrain_cadence(entries: list) -> Finding:
    if not entries:
        return Finding(
            check="retrain_cadence", severity="insufficient_sample",
            message="Sin historial de retrain (retrain_history.jsonl vacio o inexistente)",
        )
    last = entries[-1]
    last_ts = datetime.fromisoformat(last["timestamp"])
    days_since = (datetime.now(timezone.utc) - last_ts).days
    threshold = RETRAIN_CADENCE_DAYS + RETRAIN_GRACE_DAYS

    if days_since > threshold:
        return Finding(
            check="retrain_cadence", severity="alert",
            message=(
                f"Retrain vencido: {days_since} dias desde el ultimo ({last['timestamp']}), "
                f"cadencia esperada {RETRAIN_CADENCE_DAYS}d + {RETRAIN_GRACE_DAYS}d de gracia = {threshold}d"
            ),
            detail={"days_since": days_since, "last_retrain": last["timestamp"]},
        )
    return Finding(
        check="retrain_cadence", severity="ok",
        message=f"Retrain al dia: {days_since} dias desde el ultimo (umbral {threshold}d)",
        detail={"days_since": days_since, "last_retrain": last["timestamp"]},
    )


def check_dataset_drift(entries: list) -> list:
    """Compara dataset_sha256 consecutivos. No define umbral de alerta (el
    spec no da uno numerico) — el caso 'metricas sospechosamente estables'
    se reporta con severidad 'warn' para que no pase desapercibido en el
    output, aunque no dispare incident_log."""
    findings = []
    for prev, curr in zip(entries, entries[1:]):
        prev_hash = prev.get("dataset_sha256")
        curr_hash = curr.get("dataset_sha256")
        if prev_hash == curr_hash:
            continue

        metrics = ["winrate", "cagr", "max_drawdown"]
        deltas = {m: abs(curr.get(m, 0) - prev.get(m, 0)) for m in metrics}
        suspiciously_stable = all(d <= DRIFT_METRIC_EPSILON for d in deltas.values())

        if suspiciously_stable:
            findings.append(Finding(
                check="dataset_drift", severity="warn",
                message=(
                    f"dataset_sha256 cambio entre {prev['timestamp']} y {curr['timestamp']} pero "
                    f"winrate/cagr/max_drawdown quedaron practicamente identicos (deltas: {deltas}) — "
                    f"revisar si el walk-forward corre sobre datos realmente distintos"
                ),
                detail={"prev_hash": prev_hash, "curr_hash": curr_hash, "deltas": deltas},
            ))
        else:
            findings.append(Finding(
                check="dataset_drift", severity="note",
                message=(
                    f"dataset_sha256 cambio entre {prev['timestamp']} y {curr['timestamp']}, "
                    f"metricas se movieron (deltas: {deltas}) — esperado"
                ),
                detail={"prev_hash": prev_hash, "curr_hash": curr_hash, "deltas": deltas},
            ))
    return findings


def _parse_retrain_ts(entry: dict) -> datetime:
    return datetime.fromisoformat(entry["timestamp"])


def _window_stats(trades: list, label: str) -> dict:
    """Stats de un tramo de trade_ledger REAL (no simulado). max_drawdown_window
    es peak-to-trough sobre pnl_net acumulado del tramo, no sobre equity absoluta
    (no tenemos snapshot historico de equity por fecha, solo el estado actual)."""
    n = len(trades)
    n_tp = sum(1 for t in trades if t["outcome"] == "tp")
    n_sl = sum(1 for t in trades if t["outcome"] == "sl")
    n_resolved = n_tp + n_sl  # excluye timeout -- misma poblacion que el baseline del backtest
    pnl = [float(t["pnl_net"]) for t in trades if t["pnl_net"] is not None]
    stake = [float(t["stake"]) for t in trades if t["stake"] is not None]
    total_pnl = sum(pnl)
    total_stake = sum(stake)

    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in sorted(trades, key=lambda x: x["ts_close"]):
        cum += float(t["pnl_net"] or 0.0)
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)

    return {
        "label": label, "n": n,
        # timeout cuenta como no-win (denominador = tp+sl+timeout) -- esta es
        # la que se usa para el gap contra el baseline en _evaluate(), sin cambios.
        "winrate": (n_tp / n) if n else None,
        # excluye timeout de numerador Y denominador -- misma definicion que
        # walk_summary.json (make_labeled_dataset.py descarta timeouts antes
        # de entrenar). Solo para mostrar, no alimenta ninguna alerta todavia.
        "winrate_ex_timeout": (n_tp / n_resolved) if n_resolved else None,
        "period_return_pct": (total_pnl / total_stake) if total_stake else None,
        "max_drawdown_window": max_dd,
    }


def _fmt_stats(stats: dict) -> str:
    winrate_s = f"{stats['winrate']:.2f}" if stats["winrate"] is not None else "n/a"
    winrate_ex_s = (
        f"{stats['winrate_ex_timeout']:.2f}" if stats.get("winrate_ex_timeout") is not None else "n/a"
    )
    ret_s = f"{stats['period_return_pct']:.2%}" if stats["period_return_pct"] is not None else "n/a"
    return (
        f"{stats['label']}: n={stats['n']}, "
        f"winrate (timeout=loss)={winrate_s}, "
        f"winrate (excluyendo timeout, comparable a baseline)={winrate_ex_s}, "
        f"retorno sobre stake (no equity)={ret_s}, "
        f"drawdown del tramo (USD, no % de equity)={stats['max_drawdown_window']:.4f}"
    )


def check_recent_window(trades: list, retrain_entries: list) -> list:
    """
    Ventana reciente de trades REALES (trade_ledger) desde el retrain mas
    reciente hasta ahora -- complementa el acumulado de walk_summary.json,
    no lo reemplaza (ese es simulado y esta diluido por ~2 anios de historial,
    ver hallazgo de retrain_pipeline.py del 25-ago-2026).

    INFORMATIVA SOLAMENTE (acordado 25-ago-2026): nunca produce
    severity="alert" pase lo que pase, asi que nunca dispara
    db_logger.log_incident(). Se promueve a capaz de alertar solo despues
    de revisar con >=2 ventanas completas de datos reales (~100 dias, o
    antes si el ritmo de trading aumenta).
    """
    if not retrain_entries:
        return [Finding(
            check="recent_window", severity="insufficient_sample",
            message="Sin historial de retrain — no se puede definir ventana reciente",
        )]

    def _trades_since(ts):
        return [t for t in trades if t.get("ts_close") is not None and t["ts_close"] > ts]

    def _evaluate(stats: dict, baseline_winrate: float) -> Finding:
        gap = abs(stats["winrate"] - baseline_winrate) if stats["winrate"] is not None else None
        msg = _fmt_stats(stats) + f" (baseline retrain={baseline_winrate:.2f}"
        msg += f", gap={gap:.2f})" if gap is not None else ")"
        if gap is not None and gap > CALIBRATION_GAP_MAX:
            return Finding(
                check="recent_window", severity="warn",
                message=msg + f" — gap > {CALIBRATION_GAP_MAX} (informativo, no dispara incident_log)",
                detail=stats,
            )
        return Finding(check="recent_window", severity="ok", message=msg, detail=stats)

    baseline_winrate = retrain_entries[-1].get("winrate")
    last_ts = _parse_retrain_ts(retrain_entries[-1])
    strict_trades = _trades_since(last_ts)
    strict_stats = _window_stats(
        strict_trades, f"ventana estricta (desde ultimo retrain {retrain_entries[-1]['timestamp']})"
    )

    findings = []
    if strict_stats["n"] >= MIN_RECENT_N:
        findings.append(_evaluate(strict_stats, baseline_winrate))
        return findings

    findings.append(Finding(
        check="recent_window", severity="insufficient_sample",
        message=f"{_fmt_stats(strict_stats)} — insuficiente (minimo {MIN_RECENT_N})",
        detail=strict_stats,
    ))

    # Ventana extendida: acumula retrocediendo por ciclos de retrain hasta
    # juntar MIN_RECENT_N o agotar el historial disponible.
    for k in range(2, len(retrain_entries) + 1):
        ts_k = _parse_retrain_ts(retrain_entries[-k])
        extended_trades = _trades_since(ts_k)
        extended_stats = _window_stats(
            extended_trades, f"ventana extendida ({k} ciclos, desde {retrain_entries[-k]['timestamp']})"
        )
        if extended_stats["n"] >= MIN_RECENT_N:
            findings.append(_evaluate(extended_stats, baseline_winrate))
            return findings
        if k == len(retrain_entries):
            findings.append(Finding(
                check="recent_window", severity="insufficient_sample",
                message=f"{_fmt_stats(extended_stats)} — insuficiente incluso acumulando todo el historial de retrains disponible",
                detail=extended_stats,
            ))
    return findings


_SEVERITY_LABEL = {
    "alert": "ALERTA",
    "warn": "ATENCION",
    "note": "nota",
    "ok": "ok",
    "insufficient_sample": "muestra insuficiente",
}


def _print_report(all_findings: list) -> None:
    print(f"=== Model Risk Check — {STRATEGY_ID} — {datetime.now(timezone.utc).isoformat()} ===\n")
    for f in all_findings:
        label = _SEVERITY_LABEL.get(f.severity, f.severity)
        print(f"[{label:>20}] ({f.check}) {f.message}")
    print()
    print("--- Siguiente paso pendiente (NO investigado en esta corrida) ---")
    print("Motivado por el hallazgo 'dataset_drift'/ATENCION de arriba: revisar")
    print("retrain_pipeline.py para confirmar si el walk-forward de cada retrain")
    print("corre sobre datos realmente frescos o hay algo cacheado entre corridas.")

    if any(f.check == "recent_window" for f in all_findings):
        print()
        print("--- Matiz metodologico (NO corregido todavia, solo documentado) ---")
        print("winrate_real de recent_window cuenta 'timeout' como no-win: n = tp+sl+timeout,")
        print("winrate = tp/n. El baseline de retrain_history.jsonl (walk_summary.json) mide")
        print("tp/(tp+sl) sobre una poblacion de la que 'timeout' fue excluido por completo")
        print("antes de entrenar (make_labeled_dataset.py descarta filas que no resuelven")
        print("en H velas). No son la misma metrica -- comparar winrate_real contra el")
        print("baseline sobreestima el gap en la proporcion de timeouts de la ventana.")


def main():
    parser = argparse.ArgumentParser(
        description="Model Risk Agent — chequeo de calibracion, EV y cadencia de retrain para S4BTC"
    )
    parser.add_argument(
        "--exclude-backfill", action="store_true",
        help=f"Excluir trades con experiment_id={BACKFILL_EXPERIMENT_ID}",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    trades = fetch_trades(STRATEGY_ID, exclude_backfill=args.exclude_backfill)
    buckets = bucket_by_p_up(trades)
    retrain_entries = _load_retrain_history(RETRAIN_HISTORY_PATH)

    all_findings = []
    all_findings += check_calibration(buckets)
    all_findings.append(check_ev_gap(trades))
    all_findings.append(check_retrain_cadence(retrain_entries))
    all_findings += check_dataset_drift(retrain_entries)
    all_findings += check_recent_window(trades, retrain_entries)

    _print_report(all_findings)

    for f in all_findings:
        if f.severity == "alert":
            try:
                db_logger.log_incident(
                    "model_degraded", f.message,
                    strategy_id=STRATEGY_ID,
                    payload={"check": f.check, **f.detail},
                    triggered_by="model_risk_check.py",
                )
            except Exception as e:
                log.error(f"[model_risk incident log] fallo: {e}")


if __name__ == "__main__":
    main()
