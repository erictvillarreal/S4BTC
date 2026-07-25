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

## H2: Prima de liquidez
**Estado: NO CONCLUYENTE por volumen relativo (p=0.559)**

Winrate por cuartil de volumen: Q1=73.7%, Q2=77.6%, Q3=78.2%, Q4=72.4%.
Sin diferencia estadisticamente significativa. El edge no depende de
la liquidez medida por volumen relativo.

Hallazgos secundarios importantes:

1. EDGE POR HORA: winrate varia dramaticamente (65.6% a las 07h UTC
   vs 93.8% a las 08h UTC). Sesion europea (08-16h): 81.7%.
   Sesion USA (16-24h): 72.2%. Sesion Asia (00-08h): 75.3%.

2. CONCENTRACION DE TRADES: 90% de los trades ocurren entre 00h-02h UTC
   (retail asiatico dominante). Sugiere que el walk-forward selecciona
   oportunidades en horas de baja supervision institucional.

3. REGIMEN OPTIMO ES MIDHIGH_VOL, NO HIGH_VOL:
   MIDHIGH_VOL: winrate=77.8% sharpe=0.949 (mejor)
   HIGH_VOL:    winrate=76.5% sharpe=0.889
   LOW_VOL:     winrate=73.3% sharpe=0.672

Implicacion: el edge es sesion-dependiente y tipo-de-participante-
dependiente. Apunta a H3 (behavioral — retail asiatico predecible
en horas de baja supervision institucional).

## H3: Behavioral / Funding rate
**Estado: EN INVESTIGACION**

Hipotesis refinada tras H1 y H2:
S4 captura el comportamiento predecible del retail trader en BTC
perpetual futures durante horas de baja supervision institucional
(00h-08h UTC). El mecanismo probable: el retail sobre-reacciona
a movimientos de precio recientes, creando patrones de p_up que
el modelo XGBoost detecta como senalas de alta EV.

Sub-hipotesis especifica a probar:
- H3a: winrate correlaciona con funding rate extremo (retail
  sobre-apalancado = mercado mas predecible)
- H3b: la diferencia de winrate entre sesiones (Europa > Asia > USA)
  se explica por el tipo de participante dominante en cada sesion
  (institucional vs retail)

Requiere: datos de funding rate OKX por hora para cada trade.
