"""
RoboTrader S4 — db_logger.py
Persistencia a Postgres (Supabase) segun db/schema.sql — Quant Fund /
Protocolo de Gobernanza de Agentes, Seccion 14.

Este modulo NUNCA crea ni modifica el esquema: la fuente de verdad es
schema.sql, ya desplegado en Supabase. verify_schema() confirma por
LECTURA, antes de cualquier escritura, que las tablas/columnas que el
codigo espera existen tal cual — si algo no coincide, lanza un error
con el detalle exacto en vez de intentar escribir a ciegas.

Cada funcion abre y cierra su propia conexion (el loop corre por vela,
~1h de por medio) con connect_timeout corto para que un Postgres lento
o caido nunca bloquee el ciclo principal por mas de unos segundos. Los
llamadores en trader.py deben envolver cada llamada en su propio
try/except: este modulo no silencia errores internamente.
"""
import os
import logging

import psycopg2
from psycopg2.extras import Json

log = logging.getLogger("robo-s4.db")

_CONNECT_TIMEOUT = 5  # segundos

# Valores permitidos por el CHECK constraint de incident_log.event_type
# (schema.sql) — cualquier otro valor es rechazado por la DB.
VALID_EVENT_TYPES = {
    "retrain", "kill_switch", "manual_override", "data_incident",
    "model_degraded", "strategy_retired", "challenge_raised", "escalation",
}

_EXPECTED_COLUMNS = {
    "strategy_state": {
        "strategy_id", "timestamp_utc", "equity", "peak_equity",
        "open_positions", "trading_allowed", "daily_pnl_used",
        "last_heartbeat", "mode", "schema_version", "updated_at",
    },
    "trade_ledger": {
        "trade_id", "strategy_id", "ts_open", "ts_close", "symbol",
        "direction", "entry_price", "exit_price", "qty", "stake",
        "leverage", "pnl_gross", "fees", "slippage_estimated", "pnl_net",
        "outcome", "mode", "model_version", "dataset_hash",
        "experiment_id", "p_up", "tp_price", "sl_price", "ev_expected",
        "inserted_at",
    },
    "incident_log": {
        "incident_id", "event_type", "strategy_id", "timestamp_utc",
        "payload", "triggered_by", "inserted_at",
    },
}


def _get_conn():
    database_url = os.environ["DATABASE_URL"]
    return psycopg2.connect(database_url, connect_timeout=_CONNECT_TIMEOUT)


def verify_schema() -> None:
    """
    Solo-lectura. Confirma que strategy_state / trade_ledger / incident_log
    existen con las columnas que este modulo necesita. Lanza RuntimeError
    con el detalle exacto (tabla + columnas faltantes) si algo no coincide.
    Reporta (log.warning) columnas presentes en la DB que el codigo no usa,
    sin fallar por eso.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            for table, expected_cols in _EXPECTED_COLUMNS.items():
                cur.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (table,),
                )
                actual_cols = {r[0] for r in cur.fetchall()}
                if not actual_cols:
                    raise RuntimeError(f"[schema] tabla '{table}' no existe en la DB conectada")
                missing = expected_cols - actual_cols
                extra = actual_cols - expected_cols
                if missing:
                    raise RuntimeError(
                        f"[schema] '{table}' — columnas que el codigo espera y NO existen: {sorted(missing)}"
                    )
                if extra:
                    log.warning(
                        f"[schema] '{table}' — columnas en DB no usadas por el codigo: {sorted(extra)}"
                    )
    finally:
        conn.close()


def upsert_strategy_state(state: dict, strategy_id: str, mode: str) -> None:
    """
    Sincroniza el snapshot operativo (equity, posiciones abiertas, etc).

    NUNCA escribe trading_allowed: ese campo es el interruptor remoto que
    solo un humano/operador debe poder cambiar en Supabase. Si el heartbeat
    lo sobreescribiera en cada vela, cualquier pausa manual se revertiria
    en el siguiente ciclo (por eso queda fuera del INSERT/UPDATE).
    """
    pending = state.get("pending_trade")
    open_positions = [pending] if pending else []
    day_open = state.get("day_open_equity", state["equity"])
    daily_pnl_used = max(0.0, day_open - state["equity"])

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_state
                    (strategy_id, timestamp_utc, equity, peak_equity,
                     open_positions, daily_pnl_used, last_heartbeat, mode)
                VALUES (%s, now(), %s, %s, %s, %s, now(), %s)
                ON CONFLICT (strategy_id) DO UPDATE SET
                    timestamp_utc  = now(),
                    equity         = EXCLUDED.equity,
                    peak_equity    = EXCLUDED.peak_equity,
                    open_positions = EXCLUDED.open_positions,
                    daily_pnl_used = EXCLUDED.daily_pnl_used,
                    last_heartbeat = now(),
                    mode           = EXCLUDED.mode
                """,
                (
                    strategy_id, state["equity"], state["peak_equity"],
                    Json(open_positions), daily_pnl_used, mode,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def log_trade(
    strategy_id: str, symbol: str, direction: str,
    ts_open: str, ts_close: str,
    entry_price: float, exit_price: float, qty: float, stake: float,
    leverage: float, pnl_gross: float, fees: float, pnl_net: float,
    outcome: str, mode: str,
    p_up: float = None, tp_price: float = None, sl_price: float = None,
    ev_expected: float = None,
) -> None:
    """
    Inserta UNA fila completa por trade cerrado (ts_open + ts_close juntos).

    trade_ledger es append-only — un trigger en la DB bloquea UPDATE/DELETE
    — asi que no se puede insertar al abrir y completar la fila despues:
    siempre se llama una sola vez, al cierre, con el trade completo.

    p_up / tp_price / sl_price / ev_expected: columnas agregadas ago-19
    via backfill, fuera del schema.sql original — opcionales (NULL si no
    se pasan) para no romper llamadores existentes.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trade_ledger
                    (strategy_id, symbol, direction, ts_open, ts_close,
                     entry_price, exit_price, qty, stake, leverage,
                     pnl_gross, fees, pnl_net, outcome, mode,
                     p_up, tp_price, sl_price, ev_expected)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    strategy_id, symbol, direction, ts_open, ts_close,
                    entry_price, exit_price, qty, stake, leverage,
                    pnl_gross, fees, pnl_net, outcome, mode,
                    p_up, tp_price, sl_price, ev_expected,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def log_incident(
    event_type: str, message: str,
    strategy_id: str = None, payload: dict = None, triggered_by: str = "code",
) -> None:
    """incident_log no tiene columna de texto libre: el mensaje viaja dentro de payload (JSONB)."""
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"event_type invalido: {event_type!r} — validos: {sorted(VALID_EVENT_TYPES)}")
    full_payload = dict(payload or {})
    full_payload["message"] = message

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO incident_log (event_type, strategy_id, payload, triggered_by)
                VALUES (%s, %s, %s, %s)
                """,
                (event_type, strategy_id, Json(full_payload), triggered_by),
            )
        conn.commit()
    finally:
        conn.close()


def get_trading_allowed(strategy_id: str) -> bool:
    """
    Interruptor remoto opcional. Si no hay fila para el strategy_id, se
    asume permitido (fail-open) — el kill-switch local por MDD ya cubre
    la proteccion critica de forma independiente de la DB.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trading_allowed FROM strategy_state WHERE strategy_id = %s",
                (strategy_id,),
            )
            row = cur.fetchone()
        return True if row is None else bool(row[0])
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    verify_schema()
    print("OK — esquema verificado, coincide con lo que el codigo espera. Sin escrituras realizadas.")
