"""
RoboTrader S4 — state.py
Maneja el estado persistente del bot en var/state.json.
Thread-safe con filelock (o fallback si no disponible).
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from config import STATE_PATH

_DEFAULT = {
    "equity":         1000.0,
    "peak_equity":    1000.0,
    "trades_today":   0,
    "daily_evs":      [],
    "recent_evs":     [],   # rolling histórico de EVs de trades EJECUTADOS, no se resetea por día
    "current_day":    None,
    "day_open_equity": 1000.0,
    "kill_switch":    False,
    "last_updated":   None,
    "version":        "S4",
}

RECENT_EVS_MAXLEN = 20  # ventana rolling para el quantile filter causal

def load() -> dict:
    path = Path(STATE_PATH)
    if not path.exists():
        return _DEFAULT.copy()
    try:
        with open(path) as f:
            data = json.load(f)
        # fill missing keys with defaults
        for k, v in _DEFAULT.items():
            if k not in data:
                data[k] = v
        return data
    except Exception as e:
        print(f"[state] Error leyendo state.json: {e} — usando defaults")
        return _DEFAULT.copy()

def save(state: dict) -> None:
    path = Path(STATE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = str(path) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, path)   # atomic write

def reset(initial_equity: float = 1000.0) -> dict:
    state = _DEFAULT.copy()
    state["equity"]          = initial_equity
    state["peak_equity"]     = initial_equity
    state["day_open_equity"] = initial_equity
    save(state)
    print(f"[state] Reset — equity={initial_equity}")
    return state

def roll_day(state: dict) -> dict:
    """Llamar al inicio de cada día UTC. NOTA: recent_evs NO se resetea aquí —
    es histórico rolling independiente del día calendario."""
    today = datetime.now(timezone.utc).date().isoformat()
    if state.get("current_day") != today:
        state["trades_today"]    = 0
        state["daily_evs"]       = []
        state["day_open_equity"] = state["equity"]
        state["current_day"]     = today
        state.setdefault("recent_evs", [])
    return state

def push_recent_ev(state: dict, ev: float) -> dict:
    """Agrega un EV de trade EJECUTADO al histórico rolling, truncando a RECENT_EVS_MAXLEN."""
    recent = state.get("recent_evs", [])
    recent.append(float(ev))
    state["recent_evs"] = recent[-RECENT_EVS_MAXLEN:]
    return state

if __name__ == "__main__":
    s = load()
    print(json.dumps(s, indent=2, default=str))
