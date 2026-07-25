# Economic Thesis — S4BTC

## H1: Momentum de corto plazo (1h)
**Estado: RECHAZADA**

Autocorrelacion serial de retornos de 1h por regimen de volatilidad:

| Regimen     | n      | AC(1)   | p-value | Sig  |
|-------------|--------|---------|---------|------|
| HIGH_VOL    | 9,751  | -0.016  | 0.112   | n.s. |
| MIDHIGH_VOL | 9,065  | -0.002  | 0.871   | n.s. |
| MIDLOW_VOL  | 10,454 | -0.015  | 0.135   | n.s. |
| LOW_VOL     | 10,518 | -0.041  | 0.000   | ***  |
| ALL         | 39,788 | -0.011  | 0.035   | *    |

Todos los regimenes muestran autocorrelacion NEGATIVA — mean reversion,
no momentum. En HIGH_VOL la autocorrelacion es practicamente cero
(random walk). S4 no captura momentum serial en retornos de 1h.

Hallazgo secundario: LOW_VOL tiene la mayor mean reversion (-0.041, ***).
Consistente con mercados tranquilos donde el precio oscila en un rango
y cada movimiento tiende a revertir. Sin embargo S4 tiene peor desempeño
en LOW_VOL — lo que descarta que S4 capture esta mean reversion.

Implicacion: el edge de S4 no vive en la estructura serial de retornos.
Hipotesis alternativa mas probable: H2 (prima de liquidez / asimetria
TP-SL en momentos de alta volatilidad sin estructura direccional).

## H2: Prima de liquidez / asimetria TP-SL en HIGH_VOL
**Estado: EN INVESTIGACION**

Hipotesis: S4 no predice precio — cobra una prima por asumir riesgo
en momentos donde el mercado es volatil y el precio hace overshoot.
TP=2xATR alcanza el overshoot antes de que SL=0.8xATR sea tocado.

Proximos pasos:
- Comparar winrate por hora del dia (liquidez variable)
- Comparar winrate durante horas de alto volumen vs bajo volumen
- Correlacionar con funding rate de OKX en el momento del trade

## H3: Behavioral / Funding rate
**Estado: PENDIENTE — requiere datos de funding rate OKX**

## Papers relevantes
- Momentum: Grobys & Sapkota (2019) - Finance Research Letters
- Liquidez: Amihud (2002) - Journal of Financial Markets
- Behavioral: Baker & Wurgler (2006) - Journal of Finance
- Funding: Liu & Tsyvinski (2021)
- Survey: Fang et al. (2022) - Financial Innovation
