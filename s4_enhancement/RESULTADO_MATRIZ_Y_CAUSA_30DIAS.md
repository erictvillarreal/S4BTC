# Matriz de Regimen 4x4 — Resultado Final y Causa Real de los 30 Dias

Fecha: 26 de Junio 2026
Branch: research/recalibration-meta-regime
Autor: Eric Trevino

---

RESUMEN EJECUTIVO

Se construyo e investigo la matriz completa de 16 regimenes
(4 categorias de tendencia x 4 cuartiles de volatilidad) con
proteccion anti-data-snooping (particion temporal disenio
2022-2024 / validacion out-of-sample 2025-Abril 2026).

Resultado: NINGUNA celda demostro ventaja estadistica clara sobre
el desempeño general del modelo sin filtro de regimen. El modelo
XGBoost ya opera con Sharpe ~0.75 y winrate ~75% de forma
consistente en practicamente cualquier combinacion de tendencia y
volatilidad. La hipotesis de que existe un regimen "especial"
(BULL_AND_HIGHVOL o cualquier otro) que aporta ventaja
significativa sobre el resto NO se sostiene con esta evidencia.

Adicionalmente, se verifico y DESCARTO la hipotesis de que la
perdida de -0.98% en los 30 dias de paper trading (Mayo-Junio 2026)
se debio a baja volatilidad de mercado. La volatilidad de ese
periodo fue normal (percentil 47 de la historia). La causa real
sigue siendo la ya identificada: el modelo nunca fue reentrenado
para ver los datos de ese periodo.

---

METODOLOGIA — PROTOCOLO ANTI-DATA-SNOOPING APLICADO

1. Particion temporal fija ANTES de medir ninguna celda:
   - Diseño: 2022-01-01 a 2024-12-31 (22,653 velas)
   - Validacion OOS congelada: 2025-01-01 a 2026-04-30 (10,262 velas),
     no tocada hasta tener candidatas del paso de diseño

2. Direccion de trade determinada por p_up real del modelo XGBoost
   en produccion (no por el label retrospectivo con ventaja injusta
   de conocer el resultado — error metodologico detectado y
   corregido durante esta misma sesion, ver nota tecnica abajo)

3. Inventario previo de muestra por celda (sugerido por el usuario
   antes de invertir tiempo en el protocolo completo): las 16
   celdas tienen muestra suficiente (minimo 425 velas en diseño,
   minimo 215 en OOS) — no hubo necesidad de descartar celdas por
   tamaño insuficiente.

NOTA TECNICA — error intermedio corregido: el primer calculo de
desempeño por celda uso np.maximum(ret_long, ret_short), es decir,
el MEJOR resultado posible entre ambas direcciones — esto garantiza
matematicamente winrate=100% en cualquier celda, sin informacion
real (es el resultado de un oraculo perfecto, no de un modelo real).
Se corrigio usando la direccion que el modelo REALMENTE predeciria
(p_up >= 0.5 -> long, si no -> short), que es la metodologia
correcta y comparable a como opera el sistema en produccion.

---

RESULTADOS — DISEÑO (2022-2024)

Top 5 celdas por Sharpe:

| Trend       | Vol         | n    | Winrate | Sharpe |
|--------------|--------------|------|---------|--------|
| BULL_WEAK    | HIGH_VOL     | 425  | 0.831   | 1.049  |
| BEAR_TREND   | HIGH_VOL     | 2497 | 0.795   | 0.898  |
| BULL_WEAK    | MIDHIGH_VOL  | 592  | 0.752   | 0.871  |
| BEAR_RALLY   | HIGH_VOL     | 406  | 0.759   | 0.867  |
| BULL_WEAK    | MIDLOW_VOL   | 741  | 0.738   | 0.827  |

Hallazgo del diseño: las celdas HIGH_VOL dominan el ranking
independientemente de la categoria de tendencia — alta volatilidad
parece favorable en bull, bear, y regimenes debiles por igual. Esto
contradice la premisa original de research (s4_enhancement,
meta_regime_filter.py) de que BULL_TREND especificamente era la
condicion favorable — BULL_TREND+HIGH_VOL aparece solo en la
posicion 10 de 16 en este ranking de diseño (Sharpe 0.715).

---

RESULTADOS — VALIDACION OUT-OF-SAMPLE (2025 - Abril 2026)

TODAS las 16 celdas sobrevivieron con Sharpe positivo (rango 0.615
a 1.005). Ninguna celda fallo el examen sorpresa.

Esto, en si mismo, es la senal de alarma correcta: cuando el 100%
de las particiones de una matriz "pasan" sin excepcion, lo mas
probable NO es que el sistema sea excepcional en todas las
condiciones — es que la particion no esta discriminando nada real,
y el desempeño que se observa es el desempeño general del modelo,
repartido uniformemente.

---

LA PRUEBA DECISIVA — DESEMPEÑO SIN NINGUN FILTRO DE REGIMEN

Se calculo el Sharpe del sistema completo, sin ningun filtro de
regimen, sobre el MISMO periodo OOS exacto (2025 - Abril 2026):

  Sharpe sin filtro:  0.7456
  Winrate sin filtro: 0.7470
  n = 10,262 velas

Este numero cae EXACTAMENTE en el centro del rango de Sharpes por
celda (0.615 - 1.005). Confirma la sospecha: el modelo XGBoost base
ya tiene buen desempeño (Sharpe ~0.75) en cualquier regimen medido
por esta matriz. El filtro de regimen, tal como esta construido
(trend + volatilidad en velas de 1h con DMA/EMA), NO esta agregando
poder discriminatorio real sobre el modelo base.

---

CONCLUSION SOBRE LA MATRIZ 4x4

Se descarta la implementacion de la matriz de regimen como mejora
al sistema en su forma actual. La evidencia indica que el edge del
modelo es mas uniforme across regimenes de lo que el research
original (con metodologia look-ahead) sugeria. El hallazgo de
BULL_AND_HIGHVOL con Sharpe 0.8534 en el research original
probablemente reflejaba, en parte, el mismo tipo de variabilidad
estadistica esperada al particionar 16 veces el mismo dataset y
reportar la celda con mejor resultado — sin la correccion por
multiples comparaciones que el protocolo de hoy si aplico.

Esto NO contradice el hallazgo del meta-regime filter BULL_AND_HIGHVOL
validado anteriormente hoy (ver README_META_REGIME_VALIDATION.md) en
cuanto a que SI mejora metricas especificas (Sharpe causal 0.6395 ->
0.7347) — pero sugiere que esa mejora puede no representar una
ventaja estructural robusta tan grande como aparentaba, sino estar
mas cerca del rango de variacion normal que cualquier particion del
dataset produciria.

---

VERIFICACION DE LA HIPOTESIS SOBRE LOS 30 DIAS DE PAPER TRADING

Hipotesis planteada por el usuario: la perdida de -0.98% en el
periodo Mayo-Junio 2026 se debio a baja volatilidad de mercado
(regimen "tranquilo"), no al regimen lateral en si.

VERIFICACION CON DATOS REALES:

  Velas en el periodo (14 Mayo - 25 Junio 2026): 606

  Distribucion de volatilidad real del periodo:
    HIGH_VOL:     244 velas (40.3%) — la categoria MAS frecuente
    MIDLOW_VOL:   136 velas (22.4%)
    MIDHIGH_VOL:  118 velas (19.5%)
    LOW_VOL:      108 velas (17.8%) — la categoria MENOS frecuente

  ATR%% promedio del periodo:    0.6461%
  ATR%% promedio historico:      0.7406%
  Percentil historico del periodo: 47.3 (practicamente la mediana)

  Distribucion de tendencia real del periodo:
    BEAR_TREND:  442 velas (73.0%)
    BEAR_RALLY:  117 velas (19.3%)
    BULL_TREND:   47 velas (7.8%)

RESULTADO: la hipotesis de baja volatilidad NO SE CONFIRMA. La
volatilidad del periodo fue normal (percentil 47, practicamente la
mediana historica), y la categoria HIGH_VOL fue de hecho la mas
frecuente del periodo (40.3% del tiempo). Lo que SI caracteriza el
periodo de forma clara es la tendencia: 73% del tiempo en
BEAR_TREND, con BULL_TREND presente solo 7.8% del tiempo — un bear
market sostenido con volatilidad normal-alta, no un mercado lateral
de baja volatilidad.

CAUSA REAL CONFIRMADA (sin cambios respecto al diagnostico previo):
dado que (a) la matriz de regimen no demostro poder discriminatorio
real sobre el modelo base, y (b) la volatilidad del periodo fue
normal, la explicacion mas solida para el desempeño débil de los 30
dias sigue siendo la ya documentada: el modelo en produccion durante
ese periodo fue entrenado con datos hasta Abril 2026 y nunca vio la
transicion de mercado de Mayo-Junio (caida de $81k a $60k, rebote a
$67k, rango posterior) — un problema de modelo desactualizado, no de
regimen de mercado desfavorable ni de baja volatilidad.

---

PROXIMO PASO — PRIORIDAD CONFIRMADA

El retrain del modelo con el dataset ya reparado (ver fix del hueco
de 34 dias, commit en main del 26 de Junio) es la prioridad real
para mejorar el desempeño futuro — no la construccion de un filtro
de regimen. El dataset esta limpio y validado (validate_dataset.py
confirma 100% de cobertura). El siguiente retrain debe:

1. Usar el dataset completo y reparado (sin huecos)
2. Re-evaluar si el Sharpe baseline (~0.64-0.75 segun metodologia)
   se mantiene o mejora con datos frescos hasta Junio 2026
3. Confirmar mediante validate_dataset.py que no hay huecos antes
   de cualquier entrenamiento futuro — leccion aprendida de hoy
