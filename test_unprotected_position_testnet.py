"""
RoboTrader S4 — test_unprotected_position_testnet.py
Prueba de extremo a extremo de _handle_unprotected_position() (rollback
de posicion desprotegida en futures_broker.py) contra Binance Futures
TESTNET real.

CORRER ASI, directo en tu terminal — NUNCA pegando las credenciales en
ningun chat (ni el de Eric, ni el de Claude Code):

    export API_KEY="tu_api_key_de_testnet"
    export API_SECRET="tu_api_secret_de_testnet"
    python3 test_unprotected_position_testnet.py

Las credenciales se leen SOLO de os.environ. Este script:
- No acepta las credenciales como argumento de linea de comandos (quedarian
  visibles en el historial del shell / ps aux).
- No tiene ningun valor por defecto hardcodeado para API_KEY/API_SECRET --
  si no estan en el entorno, el script aborta con un mensaje claro, nunca
  corre con un valor vacio o de relleno.
- Nunca imprime el valor de API_KEY/API_SECRET, ni completo ni parcial.

REQUIERE:
- USE_TESTNET=true en el entorno (el script lo verifica y aborta si no).
- Una cuenta de testnet de Binance Futures con balance de prueba.

────────────────────────────────────────────────────────────────────
PASO 0 (ya confirmado, no requiere credenciales -- incluido aqui solo
para que quede documentado y sea reproducible):

  1. MODE=paper NO es simulacion 100% local: open_long/open_short con
     paper=True SI intentan llamadas GET publicas (sin autenticar) a
     /fapi/v1/exchangeInfo (redondeo de qty/price), pero NUNCA llaman a
     _market_order/_stop_order (POST) -- ninguna orden real se coloca
     en modo paper. Confirmado con un canario de red que intercepto
     requests.get/post/delete.

  2. MIN_NOTIONAL real de BTCUSDT en testnet: $50 (no un placeholder).
     Confirmado contra el endpoint publico /fapi/v1/exchangeInfo.

Ambos hallazgos se pueden reproducir sin credenciales corriendo
`verificar_paso_0()` abajo.
────────────────────────────────────────────────────────────────────

PROTOCOLO SI UN TEST DEJA UNA POSICION ABIERTA QUE NO SE CIERRA SOLA:
El script NUNCA intenta cerrarla por su cuenta como "limpieza" al
fallar -- si algo queda abierto de forma inesperada, se imprime el
estado EXACTO (get_position completo) y el script se detiene ahi. Esa
es la evidencia mas valiosa que puede salir de esta prueba -- cerrarla
a mano borraria la unica evidencia de que fue exactamente lo que fallo.
"""
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

# ── Guardarraíles de entorno, antes de importar nada que dependa de ellos ──

API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

if not API_KEY or not API_SECRET:
    print("ABORTANDO: API_KEY y/o API_SECRET no estan en el entorno.")
    print("Corre: export API_KEY=... ; export API_SECRET=... ; python3 " + sys.argv[0])
    sys.exit(1)

# Los inyectamos a os.environ bajo los nombres que config.py espera
# (BINANCE_API_KEY/BINANCE_API_SECRET) SOLO si no estan ya puestos asi --
# no pisamos algo que el usuario ya configuro explicitamente.
os.environ.setdefault("BINANCE_API_KEY", API_KEY)
os.environ.setdefault("BINANCE_API_SECRET", API_SECRET)

import config  # noqa: E402  (import tardio a proposito, ya con env listo)

if not config.USE_TESTNET:
    print("ABORTANDO: USE_TESTNET no esta activo. Este script SOLO corre contra testnet.")
    sys.exit(1)

import futures_broker as fb  # noqa: E402

SYMBOL = "BTCUSDT"
STAKE_USDT = 30.0  # notional = 30 * LEVERAGE(2.0) = $60, por encima del minimo real de $50


def _confirm_screenshot_gate():
    print("=" * 70)
    print("ANTES DE CONTINUAR:")
    print("¿Ya tomaste captura de pantalla del dashboard de testnet")
    print("mostrando la posición de BTCUSDT en CERO?")
    print("=" * 70)
    resp = input("Escribe exactamente CONFIRMADO para continuar: ").strip()
    if resp != "CONFIRMADO":
        print("No confirmado tal cual se pidió. Abortando sin correr ningún test.")
        sys.exit(1)


def _print_position_state(label: str):
    pos = fb.get_position(SYMBOL)
    print(f"--- Estado de posición ({label}) ---")
    print(pos)
    return pos


def _position_is_flat(pos: dict) -> bool:
    try:
        return abs(float(pos.get("positionAmt", 0))) < 1e-9
    except (TypeError, ValueError):
        return False


def _stop_and_report(pos: dict, contexto: str):
    print("=" * 70)
    print(f"DETENIENDO -- quedó una posición abierta que no se cerró sola ({contexto}).")
    print("NO se va a cerrar automáticamente. Estado exacto tal como quedó:")
    print(pos)
    print("Repórtale esto a Claude Code / al equipo tal cual, sin tocar nada más.")
    print("=" * 70)
    sys.exit(2)


# ── Paso 0: verificaciones sin credenciales (documentado arriba) ──────────

def verificar_paso_0():
    """Reproduce los dos hallazgos que no requieren API_KEY/API_SECRET reales."""
    import requests

    llamadas = []

    def _canary_get(*a, **kw):
        llamadas.append(a[0] if a else kw.get("url"))
        raise AssertionError("canario get")

    def _canary_mut(*a, **kw):
        raise AssertionError("canario post/delete -- NO deberia llegar aqui en paper=True")

    orig_get, orig_post, orig_delete = requests.get, requests.post, requests.delete
    requests.get, requests.post, requests.delete = _canary_get, _canary_mut, _canary_mut
    try:
        fb.open_long(SYMBOL, STAKE_USDT, 79000.0, 81000.0, paper=True, mock_price=80000.0)
    finally:
        requests.get, requests.post, requests.delete = orig_get, orig_post, orig_delete

    print(f"[Paso 0.1] paper=True intentó {len(llamadas)} llamada(s) GET (exchangeInfo), "
          f"0 llamadas POST/DELETE. Ninguna orden real se coloca en modo paper.")

    info = fb._get_symbol_info(SYMBOL)
    min_notional = next((f["notional"] for f in info.get("filters", [])
                          if f["filterType"] == "MIN_NOTIONAL"), None)
    print(f"[Paso 0.2] MIN_NOTIONAL real de {SYMBOL} en testnet: {min_notional}")


# ── Test 1: mock de _stop_order, entrada REAL en testnet ──────────────────

def test_1_stop_order_falla():
    print("\n" + "=" * 70)
    print("TEST 1 — entrada real en testnet, _stop_order mockeado para fallar")
    print("=" * 70)

    pos_antes = _print_position_state("antes del test")
    if not _position_is_flat(pos_antes):
        print("ABORTANDO: ya hay una posición abierta antes de empezar. No sigas sin resolver eso primero.")
        sys.exit(1)

    mark = fb.get_mark_price(SYMBOL)
    tp_price = round(mark * 0.98, 1)
    sl_price = round(mark * 1.02, 1)

    with patch.object(fb, "_stop_order", side_effect=RuntimeError("FALLA FORZADA PARA PRUEBA — TEST 1")):
        try:
            fb.open_long(SYMBOL, STAKE_USDT, tp_price, sl_price, paper=False)
            print("INESPERADO: open_long no relanzó la excepción. Revisar el diseño del rollback.")
        except RuntimeError as e:
            print(f"Excepción relanzada como se esperaba tras el rollback: {e}")

    pos_despues = _print_position_state("después del test")
    if not _position_is_flat(pos_despues):
        _stop_and_report(pos_despues, "Test 1")

    print("TEST 1 OK — el cierre de emergencia dejó la posición en cero.")


# ── Test 2: mock de AMBAS fallas — el escenario más agresivo ──────────────

def test_2_ambas_fallan():
    print("\n" + "=" * 70)
    print("TEST 2 — entrada real, _stop_order Y el cierre de emergencia mockeados para fallar")
    print("=" * 70)

    pos_antes = _print_position_state("antes del test")
    if not _position_is_flat(pos_antes):
        print("ABORTANDO: ya hay una posición abierta antes de empezar. No sigas sin resolver eso primero.")
        sys.exit(1)

    mark = fb.get_mark_price(SYMBOL)
    tp_price = round(mark * 0.98, 1)
    sl_price = round(mark * 1.02, 1)

    alertas_enviadas = []

    def _fake_send_critical_alert(title, detail):
        alertas_enviadas.append((title, detail))
        print(f"[MOCK] send_critical_alert habría enviado: {title}")
        return True  # simula que el envío del mensaje sí funcionó

    orig_market_order = fb._market_order

    def _market_order_solo_entrada_falla_en_cierre(symbol, side, qty, reduce_only=False):
        if reduce_only:
            raise RuntimeError("FALLA FORZADA PARA PRUEBA — cierre de emergencia (TEST 2)")
        return orig_market_order(symbol, side, qty, reduce_only=reduce_only)

    with patch.object(fb, "_stop_order", side_effect=RuntimeError("FALLA FORZADA PARA PRUEBA — TEST 2")), \
         patch.object(fb, "_market_order", side_effect=_market_order_solo_entrada_falla_en_cierre), \
         patch("telegram_notifier.send_critical_alert", side_effect=_fake_send_critical_alert):
        try:
            fb.open_long(SYMBOL, STAKE_USDT, tp_price, sl_price, paper=False)
            print("INESPERADO: open_long no relanzó la excepción.")
        except RuntimeError as e:
            print(f"Excepción relanzada como se esperaba: {e}")

    print(f"Alertas críticas disparadas: {len(alertas_enviadas)} (se esperaba exactamente 1)")

    pos_despues = _print_position_state("después del test")
    if not _position_is_flat(pos_despues):
        _stop_and_report(pos_despues, "Test 2 — esto es justo lo que este test intenta forzar; "
                                       "reporta el estado exacto, NO lo cierres a mano")
        # _stop_and_report ya hace sys.exit -- esta línea nunca se alcanza,
        # queda explícita para que quede claro que es el resultado esperado.

    print("TEST 2 completado sin dejar posición real abierta (el mock de _market_order de cierre "
          "solo bloqueaba la llamada reduce_only=True del propio código bajo prueba, no una "
          "posición real fuera de control).")


if __name__ == "__main__":
    verificar_paso_0()
    _confirm_screenshot_gate()
    test_1_stop_order_falla()
    _confirm_screenshot_gate()
    test_2_ambas_fallan()
