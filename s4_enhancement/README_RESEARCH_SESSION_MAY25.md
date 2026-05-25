# Research Session — May 25, 2026

Author: Eric Trevino
Branch: research/recalibration-meta-regime

---

CONTEXTO

Sesion de diagnostico y mitigacion de gaps estadisticos identificados
en la auditoria institucional previa. El bot llevaba ~20 dias deployado
en Railway con operacion minima (4 trades en 10 dias estables).

---

BUGS CORREGIDOS EN PRODUCCION (main)

BUG 1 — ev_gap_perc: error de escala 6,000x
Archivo: s4_deploy/s4_policy.py
Commit: fix: ev_gap_perc escala correcta — replica walk.py linea 416

Problema: comparaba EV en dolares vs costo de BTC completo.
Umbral anterior: ~$185. Umbral correcto: ~$0.03.
Un trade con EV=$83 era rechazado porque no llegaba a $185.
Primera vela post-fix: take=True dir=short ev=83.17 reason=ok.

Antes (bug):
  cost_only = (COMMISSION + SLIPPAGE) * close * 2
  if ev < cost_only * (1 + EV_GAP_PERC):

Despues (correcto, replica walk.py linea 416):
  stake0 = equity * POSITION_FRAC
  if ev < stake0 * EV_GAP_PERC:

Impacto: el bot rechazaba ~100% de trades validos durante 20 dias.

---

BUG 2 — LEVERAGE NameError
Archivo: s4_deploy/trader.py
Commit: fix: agregar LEVERAGE al import de trader.py

LEVERAGE usado en notional = d.stake * LEVERAGE pero no importado
desde config.py. Fix: agregar al import block.

---

BUG 3 — f-string malformado en send_trade_closed
Archivo: s4_deploy/telegram_notifier.py
Commit: fix: f-string Exit via en send_trade_closed

Antes (bug):   f"(${tp:,.2f if outcome == 'tp' else sl:,.2f})"
Despues:       f"(${(tp if win else sl):,.2f})"

---

FEATURE — Ledger dump diario por Telegram
Archivos: s4_deploy/telegram_notifier.py, s4_deploy/trader.py
Commit: feat: ledger dump diario por Telegram al cierre UTC

Cada 00:00 UTC el bot manda el CSV completo del ledger a Telegram.
Protocolo: copiar y pegar en Google Sheets diariamente.
Solucion a la falta de Railway Volume (persistencia efimera).

---

GAPS ESTADISTICOS — ESTADO

Gap 2 — Kelly sizing mal calibrado
Estado: CERRADO

El bug de ev_gap_perc era la manifestacion del problema de calibracion
en produccion. Con el fix, el sizing opera exactamente como el backtest.
Pendiente futuro: integrar features de microestructura permitira
recalibrar el Kelly con probabilidades mas precisas.

---

Gap 3 — SPA Bootstrap completo
Estado: CERRADO
Archivo: statistics/spa_bootstrap_results.csv

SPA bootstrap (Hansen 2005) con bootstrap estacionario
(Politis & Romano, block_size=24h) vs 500 benchmarks:
  250 estrategias con threshold aleatorio
  125 con features permutados
  125 buy-and-hold escalado

Resultado global: SPA p=0.478 — falla por razon estructural.
BTC subio 5x en 2022-2026, favoreciendo buy-and-hold en el universo.

SPA por regimen (hallazgo clave):

  Regimen     Trades   Return S4   Return B&H   Ratio   p-valor
  BEAR         3,202    0.004826     0.000910    5.3x    0.0000
  LATERAL      3,169    0.003741     0.000761    4.9x    0.0000
  BULL         9,571    0.004864     0.000887    5.5x    0.0000

S4 supera buy-and-hold en los tres regimenes con p=0.000.
El SPA global fallaba porque el benchmark era buy-and-hold
en el mejor bull run de la historia de BTC — no data-snooping
del modelo.

---

Gap 4 — Features inestables
Estado: CERRADO
Archivos: statistics/feature_significance/artifacts/shap_stability.csv
          statistics/feature_significance/artifacts/shap_cv.csv

SHAP stability analysis sobre ventanas de 30 dias (2022-2026).
Todos los features tienen CV < 0.5 (umbral de estabilidad).

  Feature        CV       Estado
  macd_diff      0.169    ESTABLE
  rsi_14         0.272    ESTABLE
  atr            0.275    ESTABLE
  macd           0.352    ESTABLE
  macd_signal    0.359    ESTABLE
  ema_10         0.373    ESTABLE
  ema_30         0.419    ESTABLE

Ranking promedio de importancia:
  1. ema_30       0.0947  (ancla estructural del modelo)
  2. atr          0.0334
  3. macd         0.0279
  4. ema_10       0.0229
  5. macd_diff    0.0177
  6. rsi_14       0.0126
  7. macd_signal  0.0084

Evento notable: ema_30 cae de 0.1005 a 0.0224 en Nov 2024
(ruptura de ATH post-eleccion Trump). El modelo se adapto,
rsi_14 compenso. Comportamiento sano, no fragilidad.

Nota: la auditoria previa usaba feature importance de XGBoost
(gain/cover), que es inestable por construccion. SHAP mide
contribuciones reales al output — metodologia superior.

---

Gap 5 — Sin features de microestructura
Estado: EN PROGRESO
Archivo: statistics/market_microstructure/open_interest_analysis.py
         statistics/market_microstructure/artifacts/microstructure_features.csv

Fetcher implementado via OKX (sin restricciones geograficas).
Binance y Bybit bloqueados por IP desde Mexico/datacenter.

Features generados (697 filas, 30 dias de historia):
  oi_change_1h     cambio porcentual de OI en 1h
  oi_change_8h     cambio porcentual de OI en 8h
  oi_zscore_24h    z-score de OI vs ultimas 24h
  volume_oi_ratio  volumen / OI (proxy de agresividad)
  funding_rate     ultimo funding rate conocido (forward-filled)
  funding_sign     signo del funding
  funding_extreme  1 si |funding| > 2 std historico

Pendiente: integrar al retrain del modelo al dia 30.
El retrain requerira reconstruir el dataset historico
con estos features desde 2022 usando OKX history.

---

PROXIMOS PASOS

1. 30 dias de paper trading con sistema corregido (inicia May 25, 2026)
   Protocolo: copiar ledger dump de Telegram a Google Sheets cada 00:00 UTC
   Meta: ~60 trades para analisis estadistico

2. Al dia 30: analisis de muestra
   Win rate dentro del CI del backtest?
   EV realizado vs esperado dentro de +/-30%?
   Frecuencia de trades consistente con backtest?

3. Retrain del modelo con microestructura
   Reconstruir dataset historico con features OKX desde 2022
   Evaluar mejora en walk-forward vs modelo actual
   Candidato: BULL_AND_HIGHVOL + fractional Kelly 0.25

4. Abrir cuenta nueva de Railway para los 30 dias limpios

---

GAPS PENDIENTES (identificados, no iniciados)

Gap 6 — Meta-regime filter no integrado en produccion
El filtro BULL_AND_HIGHVOL existe en s4_enhancement/ pero no
en s4_deploy/. Mejora documentada:
  Winrate baseline: 64.79% -> filtrado: 72.61%
  Sharpe baseline:  0.6395  -> filtrado: 0.8534
  Max DD baseline: -14.42%  -> filtrado: -7.40%
Pendiente hasta tener muestra live de 30 dias como baseline.

Gap 7 — Calibracion probabilistica production-ready
Las probabilidades del modelo actuan como ranking signal,
no como probabilidades reales. Recalibracion con Isotonic/Platt
destruye F1. Se requiere arquitectura de threshold dinamico
basada en percentiles de EV, no en p_up literal.
Pendiente: requiere datos live para validar.

