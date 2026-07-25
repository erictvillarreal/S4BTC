# PnL Attribution — S4BTC

Fuente: walk_candidates.csv (auditado, f43011b), 2,968 trades,
modelo best_model.ubj (retrain Jun 2026), dataset 2022-2026.

## 1. Atribucion por direccion

| Direccion | n     | Winrate | Contribucion PnL |
|-----------|-------|---------|-----------------|
| Short     | 2,957 | 75.68%  | 100.3%          |
| Long      | 11    | 18.18%  | -0.3%           |

S4 es fundamentalmente un sistema de SHORT. El edge emergió del
entrenamiento — no fue diseñado explícitamente. El modelo aprendió
que en BTC perpetual futures el lado short tiene ventaja estructural.

## 2. Estabilidad temporal — edge por año

| Año  | n   | Winrate | Sharpe |
|------|-----|---------|--------|
| 2022 | 393 | 75.57%  | 0.733  |
| 2023 | 771 | 72.50%  | 0.696  |
| 2024 | 775 | 75.74%  | 0.848  |
| 2025 | 775 | 76.90%  | 0.818  |
| 2026 | 254 | 79.13%  | 0.918  |

El edge mejora con el tiempo. 2023 es el único año debil (mercado
lateral post-FTX con poca volatilidad direccional). Desde 2024,
Sharpe y winrate mejoran consistentemente — el modelo no decae,
madura con mas datos.

## 3. Atribucion por hora UTC

Top: 08h (93.8%, n=16), 13h (100%, n=2), 14h (100%, n=4)
Bottom: 07h (65.6%, n=32), 11h (62.5%, n=8), 21h (50%, n=2)

La apertura europea (08h UTC) tiene el mayor winrate con muestra
estadisticamente relevante. El peor horario (07h) es justo antes
de esa apertura. Consistente con H3: institucionales entrando a
las 08h UTC "resuelven" el desequilibrio acumulado por el retail
asiatico durante la madrugada, y S4 esta posicionado del lado
correcto de esa resolucion.

## 4. Atribucion por confianza del modelo (p_up bucket)

| Bucket   | n   | Winrate | Mean ret  |
|----------|-----|---------|-----------|
| Q1 bajo  | 595 | 81.01%  | 0.010597  |
| Q2       | 596 | 78.86%  | 0.009666  |
| Q3       | 684 | 74.42%  | 0.009236  |
| Q4       | 521 | 70.83%  | 0.005838  |
| Q5 alto  | 572 | 71.68%  | 0.008687  |

HALLAZGO CRITICO: la confianza del modelo es INVERSAMENTE proporcional
al winrate. Los trades con p_up mas bajo (Q1) ganan mas que los de
p_up alto (Q5). Confirma que p_up es un ranking ordinal, no una
probabilidad calibrada. Cuando el modelo dice "muy seguro de subida",
el precio ya subio (momentum) y revertira. Cuando dice "poco seguro",
el mercado esta en equilibrio inestable que se resuelve a favor del short.

## 5. Atribucion por ATR (volatilidad)

| Bucket    | n   | Winrate | Sharpe |
|-----------|-----|---------|--------|
| low_atr   | 742 | 72.91%  | 0.695  |
| mid_low   | 742 | 75.47%  | 0.919  |
| mid_high  | 742 | 75.88%  | 0.973  |
| high_atr  | 742 | 77.63%  | 0.994  |

Mayor ATR = mayor winrate y Sharpe, de forma lineal. Consistente con
la tesis de liquidacion de sobre-apalancamiento: en alta volatilidad
el precio tiene mas espacio para alcanzar TP=2xATR antes de tocar
SL=0.8xATR, y las liquidaciones de retail largo son mas frecuentes.

## Tesis economica consolidada

S4 captura la PRIMA DE SOBRE-APALANCAMIENTO DEL RETAIL LONG en BTC
perpetual futures. Mecanismo:

1. El retail en perpetuos tiende a estar sistematicamente largo
   (funding rate historicamente positivo en BTC).
2. Ese apalancamiento crea presion vendedora cuando se liquida.
3. S4 esta en el lado short de esa liquidacion estructural.
4. El efecto es mas fuerte durante apertura europea (08h UTC)
   cuando el flujo institucional entra y "resuelve" el desequilibrio
   acumulado durante la sesion asiatica.
5. La confianza del modelo actua como proxy inverso del momentum
   reciente: menor p_up = mercado en equilibrio inestable = mayor
   probabilidad de liquidacion a favor del short.

Clasificacion de ineficiencia: BEHAVIORAL + MICROSTRUCTURA
(sobre-apalancamiento retail + estructura de liquidaciones en perpetuos)
