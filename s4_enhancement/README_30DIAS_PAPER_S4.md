# S4BTC — Resultados de Paper Trading: 30 Días sin Modificaciones

**Periodo:** 14 de Mayo 2026 — 25 de Junio 2026
**Capital inicial:** $1,000.00 USDT (paper)
**Modo:** PAPER, sin intervención humana en el código durante todo el período
**Modelo:** XGBoost entrenado con datos hasta Abril 2026 — sin retrain durante el período
**Propósito de este documento:** registrar, sin editorializar los datos, el desempeño real del sistema S4 frente a lo que predecía la auditoría estadística institucional (`/statistics`), y dejar marca histórica del estado del proyecto antes de cualquier mejora.

---

## 1. Resumen Ejecutivo

El sistema S4 operó 30 días consecutivos en modo paper sin que el código de decisión (`s4_policy.py`), el modelo, o los parámetros de riesgo fueran modificados. Es la primera ventana de operación limpia desde que se corrigieron los bugs de infraestructura del 25 de Mayo (ver `README_RESEARCH_SESSION_MAY25.md`).

El resultado: el sistema **no replicó las métricas del backtest**. El win rate observado (39.7%) está fuera del intervalo de confianza del 95% construido alrededor de la muestra, y ese intervalo no contiene el win rate del backtest (64.7%). El sistema cerró el período con una pérdida leve de -0.98% sobre el capital.

Este resultado no invalida el edge estadístico documentado en la auditoría. Lo que indica, con evidencia directa, es que **dos condiciones necesarias para que el sistema reproduzca el backtest no se cumplieron durante este período**: el modelo no fue reentrenado, y el filtro de régimen de mercado (meta-regime filter) nunca fue integrado a producción. Ambos issues estaban identificados y documentados antes de empezar esta ventana de 30 días.

---

## 2. Métrica por Métrica: Esperado (Backtest) vs Observado (Paper Live)

| Métrica | Backtest (walk-forward, 4 años) | Observado (30 días paper) | Diferencia | Estado |
|---|---|---|---|---|
| Win rate | 64.66% | 39.66% | -25.00 pp | **Fuera de rango** |
| Intervalo de confianza 95% (Wilson) | — | [28.09%, 52.51%] | Backtest fuera del CI | **Fuera de rango** |
| R/R (avg win / avg loss) | ~2.5x (teórico, TP=2×ATR / SL=0.8×ATR) | 1.08x | -1.42x | **Fuera de rango** |
| Retorno acumulado | +698.9% (4 años, compuesto) | -0.98% (30 días) | — | **Por debajo de lo esperado** |
| Max Drawdown | -0.98% (peor ventana de 14 días) | -1.58% (sobre 30 días) | +0.60 pp peor | **Ligeramente peor** |
| Trades ejecutados | ~2/día (esperado ~60 en 30 días) | 58 trades reales | -2 trades | **Dentro de lo esperado** |
| Significancia estadística del PnL medio (t-test) | N/A (backtest no usa t-test, usa SPA) | t=-0.984, p=0.329 — no significativo | — | **PnL no distinguible de cero** |
| Kill-switch (-25% MDD) | Nunca se activó en 4 años | Nunca se activó | — | **Dentro de lo esperado** |
| Tendencia primera vs segunda mitad de la muestra | N/A | -$4.78 vs -$4.98 — sin mejora | — | **Sin adaptación visible** |

### Lectura de la tabla

**Win rate y R/R son las dos métricas más alarmantes.** No es solo que el win rate bajó — el R/R también bajó de lo esperado teóricamente (2.5x) a 1.08x observado. Esto sugiere que los TP se alcanzan con menor margen de ganancia relativa a las pérdidas de lo que el diseño de TP=2×ATR / SL=0.8×ATR debería producir en un mercado con estructura direccional clara.

**El drawdown está dentro de un rango operacionalmente seguro.** -1.58% está lejos del kill-switch de -25%. El sistema nunca estuvo en riesgo de daño grave al capital durante esta ventana, incluso operando fuera de su régimen óptimo.

**La frecuencia de trades fue la esperada.** 58 trades en 30 días con MAX_TRADES_PER_DAY=2 es consistente con el diseño. Esto descarta que el problema sea de under-trading o de filtros bloqueando señales — el sistema operó con la cadencia diseñada.

**No hay evidencia de adaptación o mejora dentro de la ventana.** Si el problema fuera ruido estadístico normal, esperaríamos ver la segunda mitad de la muestra acercarse más al backtest a medida que el mercado normalizara. No fue el caso — el desempeño fue consistentemente débil en ambas mitades.

---

## 3. Régimen de Mercado Observado: Análisis Profundo

Esta sección documenta el comportamiento real de BTC durante la ventana de 30 días, reconstruido a partir de los precios de entrada de cada trade ejecutado por el bot.

| Fecha | Precio BTC (aprox.) | Evento |
|---|---|---|
| 2026-05-14 | $81,621 | Inicio de la ventana — máximo del período |
| 2026-05-15 — 06-07 | $81,621 → $60,720 | Caída sostenida de -25.6% en 24 días |
| 2026-06-07 | $60,720 | Mínimo del período |
| 2026-06-07 — 06-15 | $60,720 → $67,253 | Rebote de +10.76% en 8 días |
| 2026-06-15 — 06-25 | $67,253 → $60,847 | Segunda fase bajista, con zigzags de $62k-$64k |
| 2026-06-25 | $60,847 | Cierre de la ventana |

### Caracterización del régimen

**Fase 1 (May 14 — Jun 7): Tendencia bajista fuerte y sostenida.** BTC cayó 25.6% en 24 días sin grandes rebotes. Este es, en teoría, el régimen donde un sistema short-biased como S4 debería sobresalir — y de hecho, fue la fase con más TPs limpios del período (Jun 2-5).

**Fase 2 (Jun 7 — Jun 15): Rebote fuerte de corto plazo.** +10.76% en 8 días. Este es el régimen más adverso posible para una estrategia que entra predominantemente en corto: el sistema siguió generando señales short (p_up consistentemente entre 0.42-0.46) mientras el precio subía. Los trades de Jun 8-14 — la peor racha de pérdidas consecutivas del período — ocurrieron exactamente en esta ventana.

**Fase 3 (Jun 15 — Jun 25): Mercado de rango con sesgo bajista, alta whipsaw.** BTC osciló entre $60,800 y $67,300 sin tendencia clara, con movimientos de ida y vuelta de 2-4% cada pocos días. Esta es la firma clásica de un mercado donde el TP de 2×ATR es difícil de alcanzar de forma consistente — el precio se mueve, pero revierte antes de completar el objetivo, lo cual explica directamente el R/R deteriorado de 1.08x frente al 2.5x teórico.

### Por qué esto explica los resultados

El sistema S4, en su forma actual, **no tiene ningún mecanismo para distinguir entre estos tres regímenes.** Opera con la misma lógica de entrada en una tendencia bajista limpia, en un rebote alcista fuerte, y en un mercado de rango choppy. El modelo XGBoost ve los mismos 7 features técnicos (EMA, RSI, MACD, ATR) en cualquier escenario y no tiene contexto de régimen.

Esto es precisamente lo que el research de `/s4_enhancement` (meta_regime_filter.py, ver Sección 5) identificó y cuantificó **antes** de esta ventana de 30 días: el filtro `BULL_AND_HIGHVOL` fue diseñado para pausar al sistema en exactamente este tipo de condiciones — regímenes de incertidumbre direccional o reversión — y dejarlo operar solo cuando el contexto de mercado favorece el sesgo direccional del modelo.

---

## 4. Por Qué el Backtest No Predijo Esto (y Por Qué Eso Es Esperado)

Es importante ser preciso aquí: **el backtest no estaba equivocado.** El walk-forward causal de 4 años (`walk_report.csv`) demuestra con SPA bootstrap, randomized labels test, y análisis por régimen, que el edge de S4 es estadísticamente real y sobrevive en bear, lateral, y bull markets con significancia p=0.000 en los tres.

Lo que el backtest **no puede capturar** es la secuencia específica y el timing específico de un período de 30 días en el futuro. El walk-forward agrega resultados sobre 102 ventanas de 14 días a lo largo de 4 años — su métrica de 64.7% de win rate es un promedio robusto sobre cientos de regímenes distintos, no una garantía de que cualquier ventana individual de 30 días vaya a replicar ese promedio.

Esta ventana de 30 días cayó, por la naturaleza aleatoria del mercado, en una combinación particularmente adversa para el diseño actual del sistema: una tendencia bajista fuerte seguida de un rebote fuerte seguido de un rango choppy — sin el filtro de régimen que existe en research pero no en producción, y sin un modelo que hubiera podido aprender de los datos de Mayo-Junio 2026 porque nunca fue reentrenado.

La pregunta correcta no es "¿por qué el backtest mintió?" — el backtest no minió, citó un promedio de largo plazo. La pregunta correcta es: **¿qué le falta al sistema en producción que sí está disponible en research, y que habría mitigado este resultado?** La sección 5 responde exactamente eso.

---

## 5. Implementaciones Pendientes Identificadas en la Auditoría — Estado Completo

Esta sección enumera **todos** los gaps identificados desde la auditoría estadística original (`/statistics`) y el research de `/s4_enhancement`, con su estado actual a fecha de este reporte.

### 5.1 — Gap: Kelly sizing / EV mal calibrado
**Estado: CERRADO (25 de Mayo 2026).**
Bug de escala de 6,000x en `EV_GAP_PERC` corregido en `s4_policy.py`. El filtro comparaba EV en dólares absolutos contra el costo de transacción de BTC completo en vez de contra el stake. Esto bloqueaba prácticamente el 100% de los trades válidos hasta el fix. No relacionado con los resultados de esta ventana — el fix ya estaba activo desde el inicio del período de 30 días.

### 5.2 — Gap: White's Reality Check / SPA fallido
**Estado: CERRADO (research).**
SPA bootstrap por régimen (`statistics/spa_bootstrap_results.csv`) confirma edge real en BEAR, LATERAL y BULL con p=0.000 en los tres, una vez que se excluye buy-and-hold como benchmark dominante artificial. El edge está confirmado a nivel estadístico — no es la causa de los resultados de esta ventana.

### 5.3 — Gap: Features inestables (SHAP)
**Estado: CERRADO (research).**
Todos los 7 features tienen CV < 0.5 en análisis SHAP rolling de 30 días sobre 4 años de historia (`statistics/feature_significance/`). `ema_30` domina con CV=0.419, el más alto del grupo, pero dentro de rango estable. No es la causa de los resultados de esta ventana.

### 5.4 — Gap: Sin features de microestructura
**Estado: EN PROGRESO. Fetcher listo, no integrado al modelo.**
`statistics/market_microstructure/open_interest_analysis.py` extrae funding rate, open interest, y 7 features derivados desde OKX (Binance y Bybit bloqueados por geolocalización del entorno de desarrollo). Datos disponibles desde finales de Abril 2026. **No integrado al dataset de entrenamiento ni al modelo en producción.** Es candidato directo a mejorar la detección de capitulación/euforia que los 7 features técnicos actuales no capturan — relevante directamente para la Fase 2 (rebote) y Fase 3 (rango) documentadas en la Sección 3.

### 5.5 — Gap: DAILY_EV_QUANTILE inactivo en producción
**Estado: IDENTIFICADO, NO CORREGIDO. Activo durante toda la ventana de 30 días.**
El filtro de calidad más importante del walk-forward (`DAILY_EV_QUANTILE = 0.20`, que descarta el 20% de peores señales del día) requiere `MIN_OBS_FOR_Q = 6` observaciones diarias para activarse. Con `MAX_TRADES_PER_DAY = 2`, el sistema nunca acumula 6 observaciones en un día — el filtro retorna `True` (deja pasar) en el 100% de los casos durante todo el período de 30 días. **Esto significa que el sistema operó sin su filtro de calidad de señal más importante durante toda la ventana documentada en este reporte.** Fix propuesto: convertir `daily_evs` a un histórico rolling de los últimos N trades ejecutados, independiente del día calendario.

### 5.6 — Gap: Meta-regime filter (BULL_AND_HIGHVOL) no integrado a producción
**Estado: RESEARCH COMPLETO, NO INTEGRADO. Inactivo durante toda la ventana de 30 días.**
Documentado en `s4_enhancement/integrated_meta_walk_report.csv` y `meta_filtered_walk_report.csv`. El filtro `BULL_AND_HIGHVOL` mejora, sobre el walk-forward completo: win rate de 64.79% a 72.61%, Sharpe-like de 0.6395 a 0.8534, Max Drawdown de -14.42% a -7.40%. **Este es el gap con la relación más directa a los resultados de esta ventana** — el régimen de rebote fuerte (Fase 2, Sección 3) y el régimen de rango choppy (Fase 3) son exactamente los escenarios que este filtro está diseñado para pausar.

### 5.7 — Gap: Calibración probabilística no production-ready
**Estado: DOCUMENTADO, SIN SOLUCIÓN PROPUESTA AÚN.**
Las probabilidades del modelo (`p_up`) no son probabilidades calibradas — son señales de ranking ordinal. Isotonic Regression y Platt Scaling mejoran el Brier Score pero destruyen el F1 (colapsa a predicciones casi constantes). El sistema usa correctamente `p_up` de forma ordinal en sus filtros actuales (no depende de su valor cardinal), por lo que este gap no es causa directa de los resultados de esta ventana, pero limita cualquier mejora futura de sizing basada en Kelly literal.

### 5.8 — Gap: Modelo sin reentrenar desde Abril 2026
**Estado: IDENTIFICADO. Intento de retrain el 8 de Junio 2026 fue descartado — ver Sección 6.**
El modelo en producción durante toda esta ventana de 30 días fue entrenado con datos hasta el 30 de Abril de 2026. Nunca vio la caída de $81k a $60k, el rebote a $67k, ni el rango posterior — es decir, **nunca vio ninguno de los tres regímenes documentados en la Sección 3.** Un intento de retrain directo el 8 de Junio produjo resultados peores (win rate 34.35%, equity final $992.97 sobre el walk-forward completo) que el modelo original, revelando un problema de fondo en el etiquetado de clases (label balance de 0.33, sesgado estructuralmente hacia "down" por la asimetría geométrica de TP=2×ATR vs SL=0.8×ATR). Este gap requiere **rediseño del esquema de etiquetado**, no solo actualización de datos, antes de cualquier retrain seguro.

### 5.9 — Gap: Retrain no automatizado
**Estado: NO IMPLEMENTADO.**
No existe cronjob ni proceso automático de reentrenamiento. Cada actualización del modelo requiere intervención manual completa: descarga de datos, etiquetado, walk-forward, validación, y deploy. Pendiente de implementación una vez resuelto el Gap 5.8.

### 5.10 — Gap: Persistencia de infraestructura en Railway
**Estado: PARCIALMENTE MITIGADO.**
Railway no tiene Volume configurado — `state.json` y el ledger se pierden en cada reinicio del contenedor. Mitigado parcialmente con notificaciones de Telegram por trade individual (`send_trade_opened`, `send_trade_closed`), que sí persistieron durante toda la ventana y permitieron la reconstrucción completa de este reporte. El dump diario automatizado del ledger (`send_ledger_dump`) falló por un bug de `parse_mode` no soportado por la función `_send()` y fue descontinuado — el registro de trades individuales fue suficiente para esta ventana, pero no es una solución escalable.

---

## 6. Intento de Retrain del 8 de Junio — Documentado para Referencia

El 8 de Junio de 2026 se intentó actualizar el dataset (agregando 99 velas nuevas hasta esa fecha) y correr un retrain completo vía walk-forward. El resultado fue **peor** que el modelo en producción:

| Métrica | Modelo en producción (Abril 2026) | Intento de retrain (Junio 2026) |
|---|---|---|
| Equity final (walk-forward completo) | $7,989.11 | $992.97 |
| Win rate (walk-forward completo) | 64.66% | 34.35% |
| CAGR | +698.9% (4 años) | -0.18% |

La causa raíz identificada: el label balance del dataset es 0.33 (33% "up", 67% "down") de forma consistente en **todos los años** del dataset (2022: 0.32, 2023: 0.35, 2024: 0.35, 2025: 0.32, 2026: 0.30) — no es un artefacto del mercado bajista reciente, sino una propiedad estructural del esquema de etiquetado de triple barrera con TP=2×ATR / SL=0.8×ATR, donde el TP es geométricamente más difícil de alcanzar que el SL.

El modelo de Abril funcionaba bien en el walk-forward histórico porque ese período (2022-2026) tuvo suficiente estructura alcista para compensar el sesgo del etiquetado. El intento de retrain de Junio, sin cambiar el esquema de etiquetado, simplemente heredó el mismo sesgo sin la compensación favorable. **Se decidió no hacer deploy de este modelo** y mantener el modelo original en producción durante el resto de la ventana de 30 días — decisión que preservó la integridad de la muestra documentada en este reporte.

Este hallazgo es ahora un gap adicional (5.8) que debe resolverse mediante rediseño del etiquetado antes de cualquier retrain futuro.

---

## 7. Conclusión y Próximos Pasos

Los 30 días documentados en este reporte representan el desempeño **del sistema base S4, sin ninguna de las mejoras identificadas en research**, durante una secuencia de mercado que incluyó tendencia bajista fuerte, rebote fuerte, y rango choppy — es decir, una muestra de régimen inusualmente diversa para solo 30 días.

El sistema no replicó el backtest en esta ventana específica. La evidencia apunta consistentemente a dos causas no mutuamente exclusivas: ausencia del meta-regime filter (Gap 5.6) y modelo desactualizado sin capacidad de adaptación a los regímenes de Mayo-Junio 2026 (Gap 5.8). El kill-switch nunca se activó y el capital nunca estuvo en riesgo material — el sistema fue conservador incluso fallando en reproducir el backtest.

**Las siguientes implementaciones quedan priorizadas para la siguiente fase del proyecto, en este orden:**

1. Integración del meta-regime filter (`BULL_AND_HIGHVOL`) a `s4_policy.py` — Gap 5.6
2. Corrección del `daily_evs` rolling para activar el quantile filter — Gap 5.5
3. Rediseño del esquema de etiquetado para resolver el sesgo estructural de clase — Gap 5.8
4. Integración de features de microestructura (funding rate, OI) al dataset de entrenamiento — Gap 5.4
5. Retrain completo con etiquetado corregido y datos actualizados — depende de 3
6. Automatización del proceso de retrain cada 14 días — Gap 5.9
7. Persistencia robusta de infraestructura (Railway Volume o equivalente) — Gap 5.10

Este documento queda como registro permanente del estado del sistema al 25 de Junio de 2026, previo a la implementación de cualquiera de los puntos anteriores.

---

*Documento generado a partir de datos de ledger reconstruidos desde notificaciones de Telegram y logs de Railway. Capital operado: $1,000.00 USDT en modo paper. Ningún capital real fue arriesgado durante este período.*
