# Camino A — Sistema Simetrico TP=SL
## Estado: DESCARTADO
## Fecha: 28 Julio 2026

### Objetivo
Redisenar Triple Barrera con TP=SL=1.0xATR para eliminar el bias
short estructural y permitir operacion bidireccional (bull + bear).

### Resultado

| Metrica    | Sistema actual | Camino A |
|------------|---------------|----------|
| Equity     | $8,830        | $750.97  |
| Win rate   | 64.44%        | 48.37%   |
| CAGR       | +70.93%       | -12.36%  |
| Max DD     | -2.04%        | -24.88%  |
| Kill switch| No            | Si       |

### Por que fallo

Con TP=SL=1.0xATR el breakeven es exactamente 50% de winrate.
El modelo logro 48.37% — 1.63pp por debajo del umbral de supervivencia.

El modelo XGBoost sin el prior matematico del 71.4% short no tiene
poder predictivo suficiente para superar el 50% necesario en un
esquema simetrico. El edge del sistema actual no viene del modelo
sino de la ventaja matematica estructural de operar short con
TP/SL=2.5:1 en un activo que estadisticamente no sube 2xATR antes
de bajar 0.8xATR en el 73.5% de las velas.

### Conclusion

S4 es un sistema de ventaja matematica estructural, no de prediccion
direccional. Para un sistema bidireccional genuino se necesitarian
features con poder predictivo real de direccion (microestructura,
order flow, funding rate historico completo) — no disponibles hoy.

### Camino B (alternativa)
Mantener el sistema actual (bear/lateral) con un filtro macro
simple: operar solo cuando BTC esta por debajo de su MA200 diaria.
Evita los periodos de bull run sostenido donde el EV es negativo.
Sin cambios al modelo ni al esquema de etiquetado.
