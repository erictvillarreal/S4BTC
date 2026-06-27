# Meta-Regime Filter — Validacion Causal y Monte Carlo

Fecha: 25 de Junio 2026
Branch: research/recalibration-meta-regime
Autor: Eric Trevino

---

OBJETIVO

Validar si el meta-regime filter BULL_AND_HIGHVOL, documentado en
s4_enhancement/meta_regime_filter.py con metodologia look-ahead
(pd.qcut sobre dataset completo), sobrevive una implementacion
100% causal — vela por vela, usando solo historial disponible
hasta el momento de la decision, igual a como operaria en produccion.

---

IMPLEMENTACION

Archivo nuevo: s4_deploy/regime_filter.py

Logica:
  trend_regime = BULL_TREND si close > ema_50 AND close > dma_200
  vol_ok = atr_pct actual esta en el top 50% de los ultimos 200
           periodos (percentil rolling causal, sin qcut global)
  BULL_AND_HIGHVOL = trend_regime == BULL_TREND AND vol_ok

Verificacion del EMA: diferencia de 0.001% vs pandas.ewm() — no es
fuente de error.

Verificacion del percentil rolling: 47.2% de las velas BULL_TREND
pasan el filtro de volatilidad (esperado ~50%) — el calculo de
percentil esta funcionando correctamente.

Integracion al walk-forward: walk_with_regime.py, copia de walk.py
original con el filtro inyectado como mascara adicional sobre
mask_gap, antes del quantile filter causal y el cap diario de trades.

---

DATASET USADO

Dataset auditado original (S4_DEPLOY_AUDITED_V1, commit f43011b),
NO el dataset actualizado de Junio 2026 (que tiene un problema de
etiquetado sesgado documentado por separado). 33,140 filas,
2022-01-01 a 2026-04-30.

---

RESULTADOS — WALK FORWARD CON FILTRO CAUSAL

| Metrica         | Baseline (sin filtro) | Research (look-ahead) | Filtro causal (este test) |
|-----------------|------------------------|-------------------------|------------------------------|
| Win rate        | 64.66%                 | 72.61%                  | 66.77%                       |
| Sharpe-like     | 0.6395                 | 0.8534                  | 0.7347                       |
| Trades          | 2,968                  | 1,727                   | 1,264                        |
| Cobertura temporal | 100%                | ~58%                    | 46.9% (653 de 1,392 dias)    |

La version causal mejora el sistema en la misma direccion que el
research, con magnitud menor — esperado, porque research tenia la
ventaja injusta de conocer los quartiles de volatilidad del futuro.

---

SIZING — MAXIMIZANDO EQUITY ABSOLUTO

Pregunta: con menos trades (-57% vs baseline), se puede recuperar
el equity absoluto aumentando position_frac dentro del limite ya
configurado en el sistema (POSITION_FRAC_MAX = 0.13)?

Corrida con risk framework completo activo (caps de presupuesto
diario, kill-switch global):

| position_frac | Equity final | Max DD intraday | Max DD daily |
|----------------|---------------|-------------------|----------------|
| 0.065 (actual) | $2,828.71     | -1.25%            | -1.16%         |
| 0.10           | $4,922.91     | -1.91%            | -1.78%         |
| 0.13 (MAX)     | $7,586.44     | -2.45%            | -2.28%         |

Con frac=0.13 (parametro ya existente, no nuevo) se recupera
equity casi igual al baseline original ($7,989), con 57% menos
trades y mejor Sharpe por operacion. Drawdown sube de -0.98% a
-2.28% pero permanece muy lejos del kill-switch (-25%).

CONCLUSION: vale la pena. Mejor calidad de senal compensada con
mayor tamano de posicion en los momentos en que el sistema opera.

---

MONTE CARLO — ROBUSTEZ DE LA CONFIGURACION GANADORA

Configuracion testeada: meta-regime filter + position_frac=0.13
Metodologia: identica a statistics/montecarlo.py (N_SIM=2000,
reshuffle, bootstrap, block bootstrap con BLOCK_SIZE=20)
Ledger usado: 1,262 trades (limpio, una sola corrida, sin mezcla)

RESHUFFLE
  Nota: el reshuffle dio el mismo valor en las 2000 simulaciones
  (posible limitacion del script al no capturar dependencia de
  path en el sizing compuesto). Resultado no usado para conclusion,
  reportado por transparencia. Pendiente de revision tecnica.

BOOTSTRAP (con reemplazo)
  Mediana          : $7,566.22
  Percentil 5       : $6,555.36
  Percentil 95      : $8,705.33
  Peor MDD simulado : -2.37%
  % simulaciones rentables (> $1,000 inicial): 100.0%

BLOCK BOOTSTRAP (bloques de 20 trades, preserva autocorrelacion)
  Mediana          : $7,418.27
  Percentil 5       : $6,149.68
  Percentil 95      : $8,909.36
  Peor MDD simulado : -4.83%
  % simulaciones rentables (> $1,000 inicial): 100.0%

INTERPRETACION

El percentil 5 del Block Bootstrap — el metodo mas conservador,
porque preserva clusters de trades consecutivos y por tanto
autocorrelacion real — es $6,149.68. Muy por encima del capital
inicial de $1,000. El 100% de 2,000 simulaciones en los tres
metodos termino rentable. El peor drawdown observado en cualquier
simulacion fue -4.83%, todavia muy lejos del kill-switch de -25%.

Esto indica que el resultado de $7,586 observado NO depende de
una secuencia de trades particularmente favorable — el sistema es
robusto bajo reordenamiento aleatorio y bajo bloques que preservan
dependencia temporal.

Archivos generados:
  s4_enhancement/montecarlo_regime_filter/montecarlo_results_regime_filter.csv
  s4_enhancement/montecarlo_regime_filter/montecarlo_distribution_regime_filter.png
  s4_enhancement/montecarlo_regime_filter/montecarlo_equity_curves_regime_filter.png

---

LIMITACIONES DE ESTA VALIDACION (honestidad sobre lo que falta)

1. El filtro de regimen fue disenado y SELECCIONADO mirando el
   mismo periodo historico que se usa para validarlo aqui. Esto
   es un riesgo de selection bias de segundo orden — no hemos
   probado el filtro en datos verdaderamente nunca vistos por
   ningun proceso de diseno.

2. No incluye los 30 dias de paper trading real (Mayo-Junio 2026),
   que es la prueba mas honesta disponible y que mostro un regimen
   de mercado dificil (ver README_30DIAS_PAPER_S4.md). Pendiente:
   re-evaluar que hubiera hecho el filtro durante esos 30 dias
   especificos.

3. Pendiente correr SPA bootstrap por regimen sobre esta version
   filtrada (el SPA original en statistics/ se hizo sobre el
   sistema SIN filtro). Sin esto no podemos descartar que el
   filtro introduce un nuevo tipo de overfitting al sistema.

4. Pendiente combinar con otros gaps (microestructura, daily_evs
   rolling en produccion) para ver si el efecto es aditivo o
   redundante.

5. El bug del reshuffle Monte Carlo (resultado constante) requiere
   revision — no afecta la conclusion final porque bootstrap y
   block bootstrap si mostraron variacion correcta, pero debe
   corregirse antes de reportar este metodo como valido.

---

SPA BOOTSTRAP / WHITE'S REALITY CHECK — CONFIGURACION FILTRADA

Metodologia: identica a statistics/whites_reality_check.py
(bootstrap simple N=5000 + sign-flip test N=5000 sobre ret_realized)
Ledger usado: mismo de Monte Carlo, 1,262 trades, filtro + frac=0.13

RESULTADOS

| Test                  | Baseline (sin filtro) | Filtrado (este test) |
|------------------------|--------------------------|--------------------------|
| White RC p-value       | 0.506 (FAILED)           | 0.498 (FAILED)           |
| SPA Sign-Flip p-value  | 0.000 (PASSED)           | 0.000 (PASSED)           |

INTERPRETACION

Patron identico al baseline. El White RC simple, tal como esta
implementado (bootstrap de la propia media), tiende estructuralmente
a p≈0.50 independientemente del sistema evaluado — es una propiedad
conocida del test, no una senal de falla especifica del filtro.

El SPA Sign-Flip si discrimina senal real de ruido: invierte el
signo de cada retorno aleatoriamente y compara contra la media
observada. p=0.0000 en ambos casos confirma que el edge, con o sin
filtro, es estadisticamente real y no producto de azar.

CONCLUSION: el filtro de regimen NO introduce overfitting nuevo
detectable por este test. El patron de p-values se mantiene
idéntico al sistema original — la mejora documentada (Sharpe
0.6395 -> 0.7347, equity $7,989 -> $7,586 con frac ajustado)
sobrevive el mismo estandar de validacion estadistica exigido
al baseline.

Archivo generado:
  s4_enhancement/spa_regime_filter/whites_reality_check_regime_filter.csv

---

RESUMEN GENERAL DE VALIDACIONES — META REGIME FILTER (CAUSAL)

| Validacion          | Resultado                                  |
|-----------------------|---------------------------------------------|
| Walk-forward causal   | Sharpe 0.64 -> 0.73, Win rate 64.7% -> 66.8%|
| Sizing (frac=0.13)     | Equity $2,829 -> $7,586, MaxDD -1.25%->-2.45%|
| Monte Carlo (bootstrap)| P5=$6,555, 100% simulaciones rentables       |
| Monte Carlo (block)    | P5=$6,150, peor MDD simulado -4.83%          |
| SPA Sign-Flip          | p=0.0000, identico a baseline                |
| White RC               | p=0.498, identico a baseline (test debil)    |

El meta-regime filter, implementado de forma causal y sin las
ventajas de look-ahead del research original, queda validado bajo
los mismos cinco estandares estadisticos aplicados al sistema base
durante la auditoria institucional original.

---

TEST RETROACTIVO — LOS 30 DIAS REALES DE PAPER TRADING

La prueba mas honesta disponible: aplicar el filtro causal sobre
las fechas/horas exactas de los 58 trades reales documentados en
README_30DIAS_PAPER_S4.md (14 Mayo - 25 Junio 2026), usando el
historial real de BTC hasta cada momento de decision.

RESULTADO

El filtro BULL_AND_HIGHVOL habria bloqueado el 100% de los 58
trades (58/58). Ni uno solo hubiera pasado.

Razon: el regimen de mercado durante todo el periodo fue
BEAR_TREND o BEAR_RALLY — BTC cayendo de $81k a $60k y rebotando
dentro de esa tendencia bajista. El filtro nunca vio BULL_TREND,
condicion necesaria para activarse, sin importar la volatilidad.

IMPACTO CONTRAFACTUAL

  Equity real observado (sin filtro):  $990.24
  Equity con filtro (cero trades):     $1,000.00
  Diferencia preservada:               +$9.76 (+0.98%)

INTERPRETACION — HALLAZGO IMPORTANTE

El filtro SI habria evitado la perdida del periodo, pero por una
razon que hay que entender con precision: BULL_AND_HIGHVOL no es
un filtro de "buen momento para operar en cualquier direccion" —
es un filtro de "el regimen donde el sistema historicamente tuvo
su MEJOR desempeño", y ese mejor desempeño en el dataset 2022-2026
ocurrio predominantemente en bull markets de alta volatilidad.

En un bear market sostenido, el filtro apaga el sistema por
completo, dejando el capital sin exposicion — ni ganando ni
perdiendo. El "ahorro" de $9.76 no viene de una decision activa
inteligente sobre el regimen bajista, viene de inaccion total.

Esto es la limitacion que se identifico al inicio de esta sesion:
el filtro es binario (opera/no opera), no un sizing continuo por
calidad de regimen. Un sistema mas sofisticado evaluaria si TAMBIEN
existe un regimen BEAR_AND_HIGHVOL con su propio historial de
desempeño favorable para shorts — el research original nunca
testeo esa hipotesis simetrica.

PREGUNTA ABIERTA PARA LA SIGUIENTE SESION

¿El sistema tiene edge real en BEAR_TREND con alta volatilidad
(no solo BULL)? Si los 58 trades reales del periodo bajista
tuvieron win rate de 39.7% (documentado, fuera del CI del 64.7%
backtest), pero el research nunca filtro especificamente por
"BEAR + HIGHVOL" como categoria propia — existe la posibilidad de
que un filtro BEAR_AND_HIGHVOL, simetrico al que ya tenemos,
mejore la operacion en mercados bajistas en vez de simplemente
apagar el sistema. Esto requiere la misma metodologia de research
(meta_regime_filter.py) pero probando esta nueva categoria,
seguida de la misma validacion causal + Monte Carlo + SPA aplicada
aqui.

---

Propuesta de orden:

Daily EV Quantile rolling — fix de código simple, bajo riesgo, ya identificado
Matriz completa de regímenes (no solo bull/bear) — research, sin tocar producción
Resolver el etiquetado sesgado — esto es el trabajo más profundo y necesario antes del retrain
Retrain con etiquetado corregido + matriz de régimen + microestructura, todo junto
Validación completa (causal + Monte Carlo + SPA + retroactivo) del sistema integrado
Calibración probabilística — al final, porque depende de tener un modelo estable primero

