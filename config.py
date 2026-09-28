"""
RoboTrader S4 — config.py
Single source of truth. All modules import CONFIG from here.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ── Exchange ──────────────────────────────────────────────
FUTURES_BASE   = os.getenv("BINANCE_FUTS_BASE", "https://fapi.binance.com")
TESTNET_BASE   = os.getenv("BINANCE_TESTNET_BASE", "https://testnet.binancefuture.com")
USE_TESTNET    = os.getenv("USE_TESTNET", "true").lower() in ("1", "true", "yes")

API_KEY        = os.getenv("BINANCE_API_KEY", "")
API_SECRET     = os.getenv("BINANCE_API_SECRET", "")

# ── Symbol & Timeframe ────────────────────────────────────
SYMBOL         = os.getenv("BOT_SYMBOL", "BTCUSDT")
INTERVAL       = os.getenv("BOT_TIMEFRAME", "1h")

# ── Paths ─────────────────────────────────────────────────
# En Railway, /app/persist es un Volume montado (sobrevive reinicios).
# Localmente (Codespace) esa ruta no existe, asi que se usa BASE_DIR
# como siempre. Esto evita perder data/model/var en cada redeploy.
from pathlib import Path as _Path
_PERSIST_ROOT = _Path("/app/persist")
_ROOT = _PERSIST_ROOT if _PERSIST_ROOT.exists() else BASE_DIR

DATA_DIR       = _ROOT / "data"
MODEL_DIR      = _ROOT / "model"
LOG_DIR        = _ROOT / "logs"
VAR_DIR        = _ROOT / "var"

for _d in (DATA_DIR, MODEL_DIR, LOG_DIR, VAR_DIR):
    _d.mkdir(parents=True, exist_ok=True)

RAW_CSV        = DATA_DIR / f"{SYMBOL}.csv"
LABELED_CSV    = DATA_DIR / f"{SYMBOL}_labeled.csv"
MODEL_PATH     = MODEL_DIR / "best_model.pkl"
STATE_PATH     = VAR_DIR  / "state.json"
LEDGER_PATH    = LOG_DIR  / "trade_ledger.csv"

# ── Triple Barrera ────────────────────────────────────────
TP_MULT        = 2.0
SL_MULT        = 0.8
HORIZON        = 12     # velas

# ── Walk-Forward ──────────────────────────────────────────
WINDOW_DAYS    = 180
STEP_DAYS      = 14

# ── Features (orden fijo — no cambiar sin re-etiquetar) ───
FEATURES = ["ema_10", "ema_30", "rsi_14", "macd", "macd_signal", "macd_diff", "atr"]

# ── Costos realistas ──────────────────────────────────────
# Decision 11 (protocolo de gobernanza, 17-sep-2026): COMMISSION ya
# representa el costo ROUND-TRIP completo (entrada+salida), no una sola
# pierna -- confirmado por Eric. 0.0010 = 0.10%, el doble de la tarifa
# taker real de Binance Futures (0.05%), por eso NO se multiplica por 2
# en ningun lado del codigo (s4_policy.py, trader.py). walk.py ya
# aplicaba el costo una sola vez y queda sin cambio. Esta decision
# revierte la convencion "x2 disperso" que el autor uso originalmente
# desde el primer commit (8e7916f, 4-mayo-2026) en _ev_long, _ev_short
# y el costo real cobrado en trader.py -- si encuentras un "* 2" cerca
# de COMMISSION/SLIPPAGE fuera de walk.py, es un regreso accidental a
# la convencion vieja, no lo "corrijas" sin releer esta nota primero.
COMMISSION     = 0.0010   # 10 bps, round-trip completo (Decision 11)
SLIPPAGE       = 0.0002   # 2 bps estimado, round-trip completo (Decision 11)

# ── Política / Sizing ─────────────────────────────────────
LEVERAGE           = 2.0
POSITION_FRAC      = 0.065
POSITION_FRAC_MAX  = 0.13
MAX_TRADES_PER_DAY = 2
MIN_P_LONG         = 0.55
EV_CUSHION_MULT    = 1.0

# Sizing por volatilidad
VOL_SCALE_CLIP  = (0.6, 1.5)
VOL_PCTL        = 0.95
VOL_CUT_FACTOR  = 0.75

# Filtros EV
EV_MIN_PERC_STAKE  = 0.003
PROB_EDGE_MIN      = 0.04
EV_GAP_PERC        = 0.0005
DAILY_EV_QUANTILE  = 0.20
MIN_OBS_FOR_Q      = 6

# ── Marco de riesgo ───────────────────────────────────────
RISK_DAILY_PCT      = 0.005   # S4_causal_safe params
MDD_KILL_PCT        = 0.25
DAILY_BUDGET_IS_NET = True

# ── Walk model ────────────────────────────────────────────
N_ESTIMATORS   = 1200
LEARNING_RATE  = 0.03
VAL_SPLIT      = 0.15

# ── Telegram ──────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Alias dict para compatibilidad con scripts legacy ─────
CONFIG = {
    "futures_base":        FUTURES_BASE,
    "testnet_base":        TESTNET_BASE,
    "use_testnet":         USE_TESTNET,
    "api_key":             API_KEY,
    "api_secret":          API_SECRET,
    "symbol":              SYMBOL,
    "interval":            INTERVAL,
    "raw_csv":             str(RAW_CSV),
    "labeled_csv":         str(LABELED_CSV),
    "model_path":          str(MODEL_PATH),
    "state_path":          str(STATE_PATH),
    "ledger_path":         str(LEDGER_PATH),
    "tp_mult":             TP_MULT,
    "sl_mult":             SL_MULT,
    "horizon":             HORIZON,
    "window_days":         WINDOW_DAYS,
    "step_days":           STEP_DAYS,
    "features":            FEATURES,
    "commission":          COMMISSION,
    "slippage":            SLIPPAGE,
    "leverage":            LEVERAGE,
    "position_frac":       POSITION_FRAC,
    "position_frac_max":   POSITION_FRAC_MAX,
    "max_trades_per_day":  MAX_TRADES_PER_DAY,
    "min_p_long":          MIN_P_LONG,
    "risk_daily_pct":      RISK_DAILY_PCT,
    "mdd_kill_pct":        MDD_KILL_PCT,
    "telegram_token":      TELEGRAM_TOKEN,
    "telegram_chat_id":    TELEGRAM_CHAT_ID,
}
