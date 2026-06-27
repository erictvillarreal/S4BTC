"""
RoboTrader S4 — trader.py
Loop principal 24/7. Corre como systemd service (robo-s4).

Modo paper:  MODE=paper  (default)
Modo live:   MODE=live   (requiere API keys y USE_TESTNET=false)

Flujo por vela:
  1. Descarga la vela más reciente cerrada
  2. Computa features
  3. Aplica s4_policy.decide()
  4. Si take=True: abre posición vía futures_broker
  5. Actualiza state.json + ledger
  6. Envía notificación Telegram
  7. Sleep hasta el cierre de la próxima vela
"""
import os
import sys
import time
import signal
import logging
from datetime import datetime, timezone, timedelta

import pandas as pd

from config import (
    SYMBOL, INTERVAL, RAW_CSV, FEATURES,
    COMMISSION, SLIPPAGE, TP_MULT, SL_MULT, LEVERAGE,
)
from data_fetcher import get_historical_data
from tech_signals import add_technical_signals
from s4_policy import decide
from state import load as load_state, save as save_state, roll_day, push_recent_ev

def _seed_persist_volume():
    """
    Primera vez que corre con el Volume nuevo: copia model/, data/ desde
    el repo (incluidos en el build) hacia /app/persist/, para que el
    volumen no arranque vacio.
    """
    import shutil
    from pathlib import Path
    persist = Path("/app/persist")
    if not persist.exists():
        return  # local, sin volume — no hacer nada

    repo_root = Path(__file__).resolve().parent
    for sub in ["model", "data"]:
        src = repo_root / sub
        dst = persist / sub
        if dst.exists() and any(dst.iterdir()):
            continue  # ya tiene contenido, no sobreescribir
        if src.exists():
            dst.mkdir(parents=True, exist_ok=True)
            for f in src.iterdir():
                if f.is_file():
                    shutil.copy2(f, dst / f.name)
            print(f"[seed] Copiado {sub}/ al volumen persistente")

_seed_persist_volume()
from futures_broker import (
    initialize_symbol, open_long, open_short,
    get_balance, get_mark_price,
)
from telegram_notifier import (
    send_ledger_dump,
    send_startup, send_trade, send_trade_closed, send_daily, send_risk,
)
from trade_logger import log_trade

# ── Config ────────────────────────────────────────────────

MODE           = os.getenv("MODE", "paper").lower()   # "paper" | "live"
PAPER          = (MODE == "paper")
LOG_LEVEL      = os.getenv("LOG_LEVEL", "INFO")
LOOKBACK       = 300   # velas para features + ATR history
INITIAL_EQUITY = float(os.getenv("INITIAL_EQUITY", "1000.0"))
HEARTBEAT_MIN  = int(os.getenv("HEARTBEAT_MIN", "60"))   # Telegram heartbeat cada N min

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("robo-s4")

# ── Shutdown handler ──────────────────────────────────────

_running = True

def _handle_signal(signum, frame):
    global _running
    log.info(f"Signal {signum} recibido — cerrando limpiamente...")
    _running = False

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT,  _handle_signal)

# ── Interval helpers ──────────────────────────────────────

def _interval_sec(interval: str) -> int:
    n = int(interval[:-1])
    return n * {"m": 60, "h": 3600, "d": 86400}[interval[-1]]

def _seconds_to_next_close(interval: str) -> float:
    now_ts  = datetime.now(timezone.utc).timestamp()
    step    = _interval_sec(interval)
    elapsed = now_ts % step
    return step - elapsed + 8   # +2s de margen para que la vela esté cerrada

# ── Data helpers ──────────────────────────────────────────

def _fetch_latest(symbol: str, interval: str, n: int = LOOKBACK) -> pd.DataFrame:
    df = get_historical_data(symbol, interval, limit=n)
    if df.empty or len(df) < 50:
        raise RuntimeError(f"Datos insuficientes: {len(df)} filas")
    df = add_technical_signals(df)
    df = df.dropna(subset=FEATURES).reset_index(drop=True)
    return df

# ── Daily rollover ────────────────────────────────────────

def _maybe_roll_day(state: dict, prev_day: str) -> tuple:
    today = datetime.now(timezone.utc).date().isoformat()
    if today != prev_day:
        equity     = state["equity"]
        peak       = state["peak_equity"]
        trades     = state["trades_today"]
        daily_pnl  = equity - state.get("day_open_equity", equity)
        budget_cap = state.get("day_open_equity", equity) * 0.005
        budget_used = max(0, state.get("day_open_equity", equity) - equity)
        budget_pct  = (budget_used / budget_cap * 100) if budget_cap > 0 else 0.0

        send_daily(equity, peak, trades, daily_pnl, budget_pct, mode=MODE)
        send_ledger_dump(mode=MODE)
        state = roll_day(state)
        save_state(state)
        log.info(f"Día nuevo: {today} | equity={equity:.2f} | pnl={daily_pnl:+.2f}")
    return state, today

# ── Main loop ─────────────────────────────────────────────

def main():
    global _running
    log.info(f"=== RoboTrader S4 arrancando | MODE={MODE.upper()} SYMBOL={SYMBOL} ===")

    # Inicializar
    initialize_symbol(SYMBOL, paper=PAPER)
    # Respetar INITIAL_EQUITY si el state.json no existe aún
    state    = roll_day(load_state())
    if state["equity"] == 1000.0 and INITIAL_EQUITY != 1000.0:
        state["equity"] = INITIAL_EQUITY
        state["peak_equity"] = INITIAL_EQUITY
        state["day_open_equity"] = INITIAL_EQUITY
    save_state(state)
    send_startup(state["equity"], mode=MODE)

    current_day = datetime.now(timezone.utc).date().isoformat()
    atr_history = []
    last_processed_candle = None

    while _running:
        try:
            # ── Roll day check ────────────────────────────
            state, current_day = _maybe_roll_day(state, current_day)

            # ── Fetch + features ──────────────────────────
            df = _fetch_latest(SYMBOL, INTERVAL, LOOKBACK)

            # Usamos la vela -2 (penúltima = ya cerrada)
            row = df.iloc[-2].to_dict()
            atr_history = df["atr"].tolist()[-200:]

            candle_ts = str(row.get("open_time"))

            # Anti-duplicate candle protection
            if candle_ts == last_processed_candle:
                log.warning(f"Duplicate candle detected: {candle_ts} — skipping cycle")
                sleep_s = 15

                deadline = time.time() + sleep_s
                while _running and time.time() < deadline:
                    time.sleep(min(2, deadline - time.time()))

                continue

            last_processed_candle = candle_ts

            # ── Resolver trade pendiente ANTES de decidir ────
            pending = state.get("pending_trade")
            if pending and PAPER:
                high  = float(row.get("high", row["close"]))
                low   = float(row.get("low",  row["close"]))
                direction = pending["direction"]
                tp = pending["tp_price"]
                sl = pending["sl_price"]
                bars_open = pending.get("bars_open", 0) + 1
                pending["bars_open"] = bars_open
                if direction == "long":
                    tp_hit = high >= tp
                    sl_hit = low  <= sl
                else:
                    tp_hit = low  <= tp
                    sl_hit = high >= sl
                timeout = bars_open >= 12
                if tp_hit or sl_hit or timeout:
                    if tp_hit:
                        outcome = "tp"
                    elif sl_hit:
                        outcome = "sl"
                    else:
                        outcome = "timeout"
                    entry      = pending["entry"]
                    notional_p = pending["notional"]
                    fees_p     = pending["fees"]
                    if outcome == "tp":
                        if direction == "long":
                            gross = notional_p * (tp - entry) / entry
                        else:
                            gross = notional_p * (entry - tp) / entry
                    elif outcome == "sl":
                        if direction == "long":
                            gross = -notional_p * (entry - sl) / entry
                        else:
                            gross = -notional_p * (sl - entry) / entry
                    else:
                        # timeout: cierra al precio actual
                        exit_price = float(row["close"])
                        if direction == "long":
                            gross = notional_p * (exit_price - entry) / entry
                        else:
                            gross = notional_p * (entry - exit_price) / entry
                    pnl_real   = gross - fees_p
                    eq_before  = pending["eq_before"]
                    new_equity = max(eq_before + pnl_real, 0.01)
                    state["equity"]      = new_equity
                    state["peak_equity"] = max(state["peak_equity"], new_equity)
                    state.pop("pending_trade", None)
                    save_state(state)
                    log_trade(
                        SYMBOL, direction, entry,
                        tp, sl, pending["stake"], pending["qty"],
                        pending["p_up"], pending["ev"], 1.0,
                        eq_before, new_equity,
                        pnl_real, fees_p,
                        outcome=outcome, mode=MODE,
                    )
                    send_trade_closed(
                        SYMBOL, direction, pending["entry"],
                        pending["tp_price"], pending["sl_price"],
                        outcome, pnl_real, new_equity, mode=MODE,
                    )
                    log.info(
                        f"TRADE CERRADO {outcome.upper()} bars={bars_open} | "
                        f"pnl={pnl_real:+.4f} equity={new_equity:.4f}"
                    )
                else:
                    # Trade sigue abierto — guardar bars_open actualizado
                    state["pending_trade"] = pending
                    save_state(state)
                    log.info(f"Trade abierto — bar {bars_open}/12 | "
                             f"tp={tp:.2f} sl={sl:.2f}")

            # ── Guard: no decidir si hay pending activo ───
            if state.get("pending_trade"):
                log.info("Trade pendiente activo — skip decide()")
                sleep_s = _seconds_to_next_close(INTERVAL)
                log.info(f"Proxima vela en {sleep_s:.0f}s ({sleep_s/60:.1f} min)")
                deadline = time.time() + sleep_s
                while _running and time.time() < deadline:
                    time.sleep(min(10, deadline - time.time()))
                continue

            # ── Kill-switch check ─────────────────────────
            mdd = state["equity"] / state["peak_equity"] - 1
            if mdd <= -0.25 and not state.get("kill_switch"):
                state["kill_switch"] = True
                save_state(state)
                send_risk("KILL_SWITCH", state["equity"], state["peak_equity"],
                          f"MDD {mdd*100:.2f}%", mode=MODE)
                log.warning(f"KILL SWITCH activado — MDD={mdd*100:.2f}%")

            # ── Policy decision ───────────────────────────
            d = decide(row, state, atr_history)
            log.info(
                f"Vela {row.get('open_time','?')} | "
                f"p_up={d.p_up:.3f} | take={d.take} dir={d.direction} "
                f"ev={d.ev:.4f} reason={d.reason}"
            )

            if d.take:
                close = float(row["close"])
                atr   = float(row["atr"])
                notional = d.stake * LEVERAGE
                fees     = notional * (COMMISSION + SLIPPAGE) * 2
                qty      = notional / close

                # ── Ejecutar ──────────────────────────────
                if d.direction == "long":
                    result = open_long(
                        SYMBOL, d.stake, d.tp_price, d.sl_price,
                        paper=PAPER, mock_price=close
                    )
                else:
                    result = open_short(
                        SYMBOL, d.stake, d.tp_price, d.sl_price,
                        paper=PAPER, mock_price=close
                    )

                if PAPER:
                    # ── Simular cierre real esperando la siguiente vela ──
                    # Dormimos hasta que cierre la próxima vela, luego
                    # descargamos esa vela y determinamos outcome real
                    log.info(
                        f"TRADE ABIERTO {d.direction.upper()} | "
                        f"entry={close:.2f} tp={d.tp_price:.2f} "
                        f"sl={d.sl_price:.2f} stake={d.stake:.2f}"
                    )
                    # Notificar apertura
                    send_trade(
                        SYMBOL, d.direction, close,
                        d.tp_price, d.sl_price,
                        d.ev, d.p_up, d.stake, state["equity"], mode=MODE,
                    )

                    # Esperar cierre de vela (ya dormirá el loop principal)
                    # Guardar trade pendiente en estado para resolverlo
                    state["pending_trade"] = {
                        "direction": d.direction,
                        "entry":     close,
                        "tp_price":  d.tp_price,
                        "sl_price":  d.sl_price,
                        "stake":     d.stake,
                        "notional":  notional,
                        "fees":      fees,
                        "qty":       qty,
                        "p_up":      d.p_up,
                        "ev":        d.ev,
                        "eq_before": state["equity"],
                        "bars_open": 0,
                    }
                    state["trades_today"] = state.get("trades_today", 0) + 1
                    state.setdefault("daily_evs", []).append(d.ev)
                    push_recent_ev(state, d.ev)
                    save_state(state)

                else:
                    # Live: el exchange maneja el cierre vía TP/SL orders
                    state["trades_today"] = state.get("trades_today", 0) + 1
                    state.setdefault("daily_evs", []).append(d.ev)
                    push_recent_ev(state, d.ev)
                    save_state(state)
                    log.info(
                        f"TRADE LIVE {d.direction.upper()} | "
                        f"entry={close:.2f} tp={d.tp_price:.2f} "
                        f"sl={d.sl_price:.2f} stake={d.stake:.2f}"
                    )
        except KeyboardInterrupt:
            break
        except Exception as e:
            log.error(f"Error en loop: {e}", exc_info=True)

        # ── Sleep hasta siguiente cierre de vela ──────────
        sleep_s = _seconds_to_next_close(INTERVAL)
        log.info(f"Próxima vela en {sleep_s:.0f}s ({sleep_s/60:.1f} min)")

        # Sleep en chunks para responder a SIGTERM rápido
        deadline = time.time() + sleep_s
        while _running and time.time() < deadline:
            time.sleep(min(10, deadline - time.time()))

    log.info("=== RoboTrader S4 detenido limpiamente ===")

if __name__ == "__main__":
    main()