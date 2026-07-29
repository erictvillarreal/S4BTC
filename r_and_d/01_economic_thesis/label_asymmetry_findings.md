# Asimetria del Label y Edge Real del Modelo
## Fecha: 28 Julio 2026

---

## Hallazgo 1 — El bias short es matematico, no empirico

Con TP=2.0xATR y SL=0.8xATR, la probabilidad geometrica en random walk:
  P(short gana) = TP/(TP+SL) = 2.0/2.8 = 71.4%
  P(long gana)  = SL/(TP+SL) = 0.8/2.8 = 28.6%

Dataset observado: short gana 73.5% — apenas 2.1pp sobre el random walk.
El modelo no aprendio a ser short-biased por el periodo de entrenamiento.
Fue construido para serlo por el diseño asimetrico de Triple Barrera.

---

## Hallazgo 2 — El modelo XGBoost no aporta edge medible

WR baseline (short siempre, sin modelo): 73.5%
WR con modelo (predice direccion):       73.3%
Edge del modelo sobre baseline:          -0.2pp

El modelo no mejora sobre operar short en cada vela sin ninguna
prediccion. El edge que aparecia en el walk-forward (~3-4pp) probablemente
viene del filtro EV-gap, no del modelo en si.

---

## Hallazgo 3 — S4 tiene EV negativo en bull markets

| Periodo                    | WR short | EV por trade | Resultado |
|----------------------------|----------|--------------|-----------|
| Bear 2022 (47k->16k)       | 74.9%    | +0.097       | ✓ Positivo |
| Bull 2023-2024 (16k->73k)  | 71.2%    | -0.008       | ✗ Negativo |
| Bull peak 2024-25 (60k->109k)| 71.0%  | -0.011       | ✗ Negativo |
| Bear 2025-2026 (109k->60k) | 75.3%    | +0.107       | ✓ Positivo |

El umbral de breakeven es WR=71.4% (la probabilidad geometrica del
random walk). En bull markets el WR cae justo por debajo de ese umbral
y el EV se vuelve negativo.

Implicacion directa: si BTC va a nuevos maximos historicos (como
anticipado para Octubre 2026), S4 va a underperform un hold y
probablemente perder dinero de forma consistente.

---

## Hallazgo 4 — Optimizacion TP/SL

La combinacion TP=1.0xATR / SL=1.0xATR (simetrica) da el mayor EV
en todos los regimenes por el efecto de la distribucion real de labels
que supera el 50% necesario para EV positivo en cualquier regimen.

Sin embargo, esta comparacion usa el WR global del dataset — para
una conclusion valida habria que relabelar con cada combinacion de
TP/SL y reentrenar el modelo. Pendiente en Camino A.

---

## Caminos identificados

CAMINO A (nuevo branch): Redisenar el sistema para bull markets.
  - Relabelar con TP/SL simetrico o agregar long capability
  - Reentrenar el modelo con el nuevo esquema
  - Validar que el EV sea positivo en todos los regimenes

CAMINO B: Aceptar que S4 es bear/lateral y operarlo solo en esos
  regimenes via filtro macro (BTC bajo MA200 diaria).
  - Sin cambios al modelo actual
  - Agregar señal macro de encendido/apagado
  - Mas simple pero limita la operacion a ~50% del tiempo

---

## Estado del conocimiento acumulado

Lo que sabemos con certeza:
1. Edge estadistico existe (SPA p=0.000, randomized labels test)
2. El bias short es matematico por diseño de Triple Barrera
3. El modelo per se no aporta edge sobre el baseline
4. EV positivo solo en regimenes bajistas/laterales
5. El ER futuro predice outcome pero no es predecible ex-ante
6. El edge se concentra en apertura europea (08h UTC)

Lo que no sabemos:
1. Si el EV-gap filter es la fuente real del edge en el walk-forward
2. Si un sistema simetrico (TP=SL) con el mismo modelo daria EV positivo
   en bull markets
3. Si la señal del modelo (p_up) tiene valor predictivo real o es ruido
   que el sistema ignora efectivamente operando short siempre
