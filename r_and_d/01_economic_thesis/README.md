# Economic Thesis — S4BTC
## Estado del conocimiento: 25 Julio 2026

---

## Lo que sabemos con certeza

### 1. El edge es estadisticamente real
Randomized-label test: F1 colapsa de 0.218 a 0.014 al aleatorizar
los labels. SPA sign-flip: p=0.000 en los tres regimenes (bear,
lateral, bull). Esto es independiente de cualquier hipotesis sobre
el origen del edge. El modelo extrae señal genuina de los datos.

### 2. El sistema opera casi exclusivamente en short
2,957 shorts (wr=75.7%) vs 11 longs (wr=18.2%).
100.3% del PnL historico viene de shorts.
Esto no fue diseñado — emergio del entrenamiento sobre el label
de Triple Barrera. No sabemos por que el modelo aprendio a preferir
shorts si el esquema de etiquetado es simetrico.
PENDIENTE: investigar asimetria del label en direccion.

### 3. El edge no es direccional en el sentido macro
Durante los 30 dias de paper trading (Mayo-Junio 2026), BTC cayo
de $81k a $60k — un mercado marcadamente bajista donde un sistema
short-biased deberia ganar. Sin embargo, el sistema perdio -0.98%
con winrate 39.7%.

Esto descarta que S4 capture:
- Momentum bajista macro
- Prima de sobre-apalancamiento retail long (si fuera eso,
  deberia haber ganado durante la caida sostenida)
- Cualquier señal ligada a la tendencia de dias/semanas

### 4. El edge es local — vive en ventanas de 12 horas
La variable que mejor explica el desempeño es la eficiencia
direccional del movimiento en ventanas de 12h (el horizonte
real del sistema):

  Periodo real Mayo-Jun 2026:    std(ret_12h) = 1.433%
  Historico mismo regimen:       std(ret_12h) = 4.968%
  Razon de fallo: 3.5x menor eficiencia direccional

Cuando el precio se mueve con coherencia direccional en ventanas
de 12h (alto std), el sistema gana porque el TP=2xATR se alcanza
antes de que el SL=0.8xATR sea tocado. Cuando el precio "respira"
sin avance neto (bajo std, independientemente de si el mercado
sube o baja en terminos macro), el SL se activa mas.

Esto explica por que el backtest funciona en bull, bear y lateral
(el SPA lo confirma con p=0.000 en los tres) — porque en el
backtest todos los periodos tienen suficiente eficiencia
direccional en ventanas de 12h. No porque el sistema sepa
identificar regimenes macro.

---

## La narrativa mas honesta disponible

S4 es un sistema que captura la **resolucion de movimientos de
precio en ventanas de 12 horas en BTC perpetual futures**.
No predice la direccion del mercado en terminos de dias o semanas.
Predice si, dado el estado actual de los indicadores tecnicos de
1h, el precio va a moverse lo suficiente en los proximos 12h como
para alcanzar un nivel de 2xATR antes de retroceder 0.8xATR.

Cuando el mercado tiene **eficiencia direccional alta** (el precio
avanza netamente, ya sea al alza o a la baja, en ventanas de
varias horas) — el sistema gana independientemente del regimen macro.

Cuando el mercado tiene **eficiencia direccional baja** (el precio
oscila sin avance neto, el tipico mercado "choppy" o "noise") —
el sistema pierde independientemente del regimen macro.

La pregunta correcta para un inversor no es "¿esta BTC en bull
o bear?" sino "¿esta BTC moviendose con coherencia direccional
en ventanas de horas?" — y esa pregunta es mucho mas dificil de
responder en tiempo real.

---

## Cuando S4 es mas favorable (hipotesis de trabajo)

Con base en la evidencia empirica actual, S4 deberia operar mejor
en condiciones de:

1. **Alta volatilidad con direccion** — no solo alta volatilidad.
   ATR alto pero con movimientos que se sostienen en una direccion
   durante varias horas consecutivas. El regimen MIDHIGH_VOL
   (no HIGH_VOL) tuvo el mejor Sharpe (0.949), consistente con
   "suficiente movimiento, no tanto ruido".

2. **Apertura de sesion europea (08h-10h UTC)** — el winrate
   mas alto observado (93.8% a las 08h UTC) sugiere que la
   entrada de flujo institucional europeo "resuelve" desequilibrios
   acumulados durante la sesion asiatica, creando movimientos mas
   direccionales en las primeras horas de la manana europea.

3. **Post-eventos de alta conviccion** — FOMC, datos macro, noticias
   de ETF, eventos de funding extremo. Hipotesis no probada todavia
   (requiere datos de H3 completos). La logica: eventos de alta
   conviccion generan movimientos sostenidos en una direccion,
   exactamente el tipo de eficiencia direccional que el sistema
   necesita.

4. **Periodos de alta volatilidad post-consolidacion** — despues
   de rangos estrechos (como el que vivimos en Mayo-Junio 2026),
   el mercado suele "romper" con movimientos mas direccionales.
   Si el Efficiency Ratio de Kaufman (pendiente de implementar)
   pudiera detectar cuando el mercado sale de un periodo de baja
   eficiencia direccional, ese seria el momento de activar S4
   con mayor confianza.

---

## Lo que no sabemos todavia

1. **Por que el modelo prefiere shorts** si el label es simetrico.
   Hipotesis: el precio de BTC en el periodo de entrenamiento
   (2022-2026) tuvo mas episodios de caida brusca que de subida
   sostenida en ventanas de 12h, sesgando el dataset de entrenamiento
   hacia labels=0 (short wins). Requiere analisis del label
   distribution por regimen.

2. **Si la eficiencia direccional es predecible** antes de que
   ocurra, o si solo es observable en retrospectiva. Si es
   predecible (ej. via Kaufman ER), se convierte en un filtro
   de entrada de alto valor. Si no es predecible, el sistema
   tiene un riesgo estructural en periodos de baja eficiencia
   que no puede mitigarse con filtros de regimen.

3. **H3 — Behavioral/Funding** — no probada adecuadamente por
   falta de datos historicos de funding rate (OKX API limita
   a ~3 meses). Requiere acceso a datos historicos completos
   (Coinglass, CryptoQuant o similar) para probar si el funding
   rate extremo predice la eficiencia direccional en ventanas
   de 12h.

---

## Hipotesis de tesis economica (en construccion)

La ineficiencia que S4 podria estar capturando es la **prima
de resolucion de desequilibrio en mercados de derivados de 24/7**:

En mercados que nunca cierran, los desequilibrios de posicion
(retail sobre-apalancado, funding extremo, presion de una sesion
geografica) no se resuelven con un "close" diario sino con
movimientos bruscos y direccionales que el mercado ejecuta para
restablecer el equilibrio. S4 captura esos momentos de resolucion.

Esta hipotesis es consistente con:
- Edge mayor en apertura europea (resolucion del desequilibrio asiatico)
- Edge mayor en alta volatilidad (mas probabilidad de resolucion brusca)
- Fallo en periodos choppy (no hay desequilibrio que resolver,
  solo ruido sin conviccion)

Pendiente de prueba formal con datos de funding rate historico
completo (H3) y Efficiency Ratio de Kaufman como predictor
de eficiencia direccional.

## Bollinger Bandwidth — Hallazgos (31 Jul 2026)

### S4 performance por BBW (4 cuartiles, n=34,972 velas)

| Regimen      | BBW medio | WR     | Sharpe |
|--------------|-----------|--------|--------|
| Q1 squeeze   | 0.97      | 71.2%  | 0.626  |
| Q2           | 1.86      | 72.8%  | 0.786  |
| Q3           | 3.01      | 73.4%  | 0.831  |
| Q4 expansion | 6.33      | 76.0%  | 0.859  |

Lineal y monotono: mayor BBW = mejor WR y Sharpe.
S4 necesita movimiento para alcanzar TP=2xATR — en squeeze el mercado
no se mueve suficiente y el SL=0.8xATR se toca disproportionately.

### Post-squeeze analysis (329 eventos, BBW < percentil 10)

WR promedio S4 en las 20 velas post-squeeze: 71.9%

Pero con diferencia dramatica por direccion del break:

| Direccion del break | Frecuencia | WR S4 |
|--------------------|-----------|-------|
| Alza (>+1%)        | 25%       | 47.2% |
| Baja (>-1%)        | 24%       | 90.7% |
| Sin direccion clara| 51%       | 75.3% |

HALLAZGO CRITICO: cuando el squeeze resuelve hacia ABAJO, S4 tiene
90.7% de winrate en las siguientes 20 horas — su mejor ventana
historica documentada. Cuando resuelve hacia ARRIBA, cae a 47.2%
(casi breakeven), consistente con el hallazgo de que el sistema
sufre en movimientos alcistas sostenidos.

### Contexto actual (31 Jul 2026)

BBW actual del chart: 5.63 (percentil 87.7 historico).
NOTA: el 5.63 es relativo al contexto reciente (Dic 2025-Jul 2026).
El squeeze real de Julio 2026 tuvo minimo de 0.46 y media de 2.29.
El BBW actual esta EXPANDIENDO desde ese squeeze — la resolucion
ya esta en curso. La direccion del break determinara el performance
de S4 en las proximas 2-3 semanas.
