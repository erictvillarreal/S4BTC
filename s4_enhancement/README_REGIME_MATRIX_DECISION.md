# Decision: Meta-Regime — BULL_AND_HIGHVOL unico, caja de cambios pospuesta

Fecha: 26 de Junio 2026
Branch: research/recalibration-meta-regime
Autor: Eric Trevino

---

CONTEXTO

Durante la validacion del meta-regime filter (ver
README_META_REGIME_VALIDATION.md), surgio la pregunta de construir
una "caja de cambios completa" — multiples regimenes (BULL_AND_HIGHVOL,
BEAR_AND_HIGHVOL, etc.) en vez de un unico filtro binario, para evitar
que el sistema se quede inactivo durante mercados bajistas sostenidos.

---

HALLAZGO CRITICO — INESTABILIDAD DEL REGIMEN EN VELAS DE 1H

Se midio la duracion y frecuencia de cambio de clasificacion de
regimen (BULL_TREND / BEAR_TREND / BULL_WEAK / BEAR_RALLY) sobre el
dataset completo (33,140 velas de 1h, 2022-2026):

  Cambios de regimen por semana:     17.19
  Duracion mediana de cada racha:    3 horas
  % de rachas menores a 6 horas:     65.0%
  % de rachas mayores a 1 semana:    0.1%

Probar con EMAs mas lentas (50/100/150/200 periodos) NO resolvio el
problema — la duracion mediana se mantuvo en 2-3 horas en todos los
casos. Conclusion: el problema no es la velocidad del indicador, es
la escala de tiempo. Los ciclos reales de BTC (confirmados visualmente
por el usuario: bear desde Sept 2025, bull Abril-Sept 2025, bull
2023-2025) duran MESES, no se pueden medir con velas de 1 hora.

---

VALIDACION EN ESCALA DIARIA

Se repitio el analisis resampleando a velas diarias (DMA=100d,
EMA=50d). Resultado: rachas reales y largas SI aparecen:

  28 Oct 2025 - 5 Ene 2026:  BEAR_TREND, 69 dias continuos
  20 Ene - 15 Mar 2026:      BEAR_TREND, 54 dias continuos

Pero sin suavizado, la duracion mediana en diario sigue siendo de
solo 2 dias (69.2% de rachas menores a 1 semana) — hay ruido de
corto plazo mezclado con la senal real de regimen macro.

CON SUAVIZADO (confirmacion por moda/votacion mayoritaria sobre N
dias antes de aceptar un cambio de regimen):

| Dias de confirmacion | Duracion mediana | % rachas <7d | % rachas >30d |
|------------------------|---------------------|-----------------|------------------|
| Sin suavizado          | 2 dias              | 69.2%           | 10.5%            |
| 5 dias                 | 9 dias              | 39.7%           | 23.8%            |
| 7 dias                 | 12 dias             | 32.1%           | 28.3%            |
| 10 dias                | 14 dias             | 22.7%           | 36.4%            |
| 14 dias                | 17 dias             | 24.4%           | 43.9%            |

El suavizado a 10-14 dias SI produce regimenes estables y reales.

---

EL TRADE-OFF IDENTIFICADO

Un regimen confirmado a 14 dias es, por construccion, lento: tarda
~2 semanas en detectar un cambio real de tendencia. Eso significa
que el sistema perderia el inicio de cualquier movimiento nuevo —
que historicamente es donde esta la mejor parte del retorno.

No existe una version gratuita de esto: mas estabilidad = menos
velocidad de reaccion. Cualquier matriz de regimen construida sobre
esta base hereda este trade-off.

---

DECISION

Se descarta, POR AHORA, la construccion de la matriz completa de
16 regimenes (4 tendencias x 4 cuartiles de volatilidad) como
gap a resolver en esta fase del proyecto.

Se mantiene el filtro BULL_AND_HIGHVOL, ya validado con 5 capas de
evidencia (walk-forward causal, sizing, Monte Carlo, SPA, test
retroactivo vs 30 dias reales — ver README_META_REGIME_VALIDATION.md)
como la unica pieza de regimen a integrar a produccion en esta etapa.

RAZONES

1. Costo de validacion completo y honesto de la matriz multi-regimen
   (con escala diaria + confirmacion de 10-14 dias + reduccion de
   muestra de 33,140 a ~1,580 observaciones diarias) es
   significativamente mayor al disponible en esta sesion.

2. El riesgo de apresurar esta validacion es alto — la sesion de
   hoy ya demostro varias veces el costo de construir sobre
   resultados no verificados con cuidado (bugs de Monte Carlo,
   metodologias mezcladas, archivos de ledger contaminados).

3. BULL_AND_HIGHVOL es la pieza con mayor evidencia y menor riesgo
   disponible HOY. Es la jugada de menor riesgo en el tablero.

---

PROXIMOS PASOS — RESEARCH PARALELA (NO BLOQUEANTE)

La idea de la "caja de cambios completa" (incluyendo
BEAR_AND_HIGHVOL) queda como linea de investigacion separada,
documentada aqui para no perderla, a desarrollar cuando el resto
de los gaps prioritarios (etiquetado sesgado, retrain, daily EV
quantile) esten resueltos:

1. Repetir la matriz de regimen en escala diaria, con suavizado
   de 10-14 dias, para las 4 categorias de tendencia x volatilidad
   (8-16 combinaciones segun se decida).

2. Aplicar el protocolo anti-data-snooping ya definido (tamano
   minimo de muestra por celda, particion temporal de diseno vs
   validacion, correccion por multiples comparaciones) — critico
   dado que con datos diarios la muestra total es mucho menor.

3. Validar especificamente la hipotesis BEAR_AND_HIGHVOL con la
   misma metodologia de 5 capas usada para BULL_AND_HIGHVOL.

4. Si BEAR_AND_HIGHVOL tiene edge real validado, combinar ambos
   filtros (OR logico) y repetir el test retroactivo contra los
   30 dias reales de paper trading para confirmar que la "caja de
   cambios" de 2 velocidades efectivamente reduce el tiempo de
   inactividad del sistema sin destruir la calidad de senal.

5. Evaluar el trade-off de velocidad de reaccion vs estabilidad —
   posiblemente probar un esquema de confirmacion mas corto (5-7
   dias) que sacrifique algo de estabilidad por reaccionar mas
   rapido a cambios de regimen reales.
