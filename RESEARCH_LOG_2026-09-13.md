# Research Log — S4BTC — 13 de septiembre de 2026

Registro de las Decisiones 5, 6 y 7 del checkpoint de hoy. Solo documentación —
ningún fix de sizing ni de costos aplicado. `walk_summary.json` y demás
archivos públicos/de reporte no se tocaron.

---

## Decisión 5 — Reversión de la hipótesis de régimen de mercado

**Hipótesis previa:** el mal desempeño real de S4 en ago-sep 2026 (winrate real
23-38% vs. 64% de backtest) se explicaba por un régimen de mercado adverso
(rally sostenido de BTC, alta volatilidad).

**Prueba realizada:** proxy de régimen (ATR relativo a su propia media
histórica) calculado sobre las 110 slices de `walk_report.csv` (2022-2026),
correlacionado contra retorno y winrate de cada ventana de test.

**Hallazgo:**
- Sí existe un patrón histórico real y recurrente: `regime_ratio` correlaciona
  negativo con `win_rate` (-0.235) y con `acc` (-0.285) en todo 2022-2026 — S4
  gana menos seguido en ventanas de mayor volatilidad, de forma estructural,
  no como excusa puntual de este trimestre.
- Pero las ventanas de test que cubren ago-sep 2026, medidas con el propio
  walk-forward (modelo contemporáneo a cada ventana, no el modelo congelado
  que corría en vivo), **no fueron de alta volatilidad**: percentiles 1, 9,
  16, 58 de todo el historial. Winrate de esas ventanas: 51.9%-61.1%, todas
  con retorno positivo (+0.51% a +1.75%), ninguna a más de 1.33 desviaciones
  estándar de la tendencia histórica esperada para ese nivel de volatilidad.

**Conclusión:** la hipótesis de "régimen difícil" no se sostiene como
explicación del mal desempeño real observado. El backtest, con un modelo
correctamente vigente para ese período, dice que ago-sep 2026 debió ser un
período normal e incluso rentable. La brecha real está en otro lado —
refuerza cuantitativamente que el Bug 1 (modelo de producción congelado desde
mayo 2026, corregido el 12-sep-2026 en el commit `51681ef`) fue la causa
dominante, no el mercado.

---

## Decisión 6 — Tres divergencias confirmadas entre `walk.py` (backtest) y
## producción (`s4_policy.py` / `trader.py`)

### 6.1 — Direction / EV-gap — **CORREGIDA**
- **Bug:** `s4_policy.py` elegía dirección con `p_up >= MIN_P_LONG` (umbral de
  probabilidad fijo) y el filtro `ev_gap_low` comparaba el EV absoluto de la
  dirección ya elegida. `walk.py` elige dirección comparando `ev_long` vs.
  `ev_short` directamente, y el filtro compara la brecha `|ev_long - ev_short|`.
- **Impacto medido:** 0 de 34 trades reales cambiaron de dirección o de
  resultado del filtro bajo la lógica corregida — `p_up` real nunca superó
  0.46, muy lejos de MIN_P_LONG=0.55, así que el bug nunca se manifestó en los
  datos que tenemos. Único ejemplo de divergencia real: sintético
  (`ev_long=$100.00` vs `ev_short=$100.03`).
- **Estado:** corregido y desplegado — commit `29645e98c5d6425ba5f3045453dc73b835e93039`.

### 6.2 — Sizing por volatilidad — **CUANTIFICADA, SIN CORREGIR**
- **Bug:** `walk.py._vol_position_scale` usa `sqrt(ref_vol / atr_ratio)` con
  `ref_vol` = mediana del ATR de entrenamiento, más un corte `×0.75` si se
  cruza el percentil 95 ("extreme"). `s4_policy._vol_scale` usa
  `pctl_95 / atr_ratio` (sin raíz cuadrada) usando el percentil 95 como si
  fuera la referencia normal (no como umbral de extremo), más un corte fijo
  `×0.5` bajo una condición distinta.
- **Impacto medido (34 trades reales vs. fórmula de `walk.py` sobre la misma
  fecha/volatilidad):**
  - stake real promedio: $77.54 — stake según fórmula de `walk.py`: $62.86
  - ratio promedio real/walk: 1.247 — mediana: 1.436
  - 23 de 34 trades reales fueron >5% más GRANDES que lo que `walk.py` habría
    dimensionado; 11 de 34 fueron >5% más CHICOS; **0 de 34 coincidieron**
    dentro de ±5%.
  - No es un sesgo simple en una sola dirección — es divergencia inconsistente
    en ambos sentidos, sin relación estable con lo que el backtest asumió.
- **Estado:** sin corregir. No aplicar fix hasta próxima revisión.

### 6.3 — Costos de transacción — **CUANTIFICADA, SIN CORREGIR**
- **Bug:** `walk.py` usa `fee_pct = commission + slippage` (un solo lado) tanto
  para el EV de selección de candidatos como para el PnL simulado.
  `s4_policy._ev_long`/`_ev_short` y `trader.py` (costo real cobrado en cada
  trade en vivo) usan `(commission + slippage) × 2`. `walk.py` es
  internamente consistente consigo mismo, pero asume la mitad del costo real
  de producción.
- **Impacto medido:** recálculo de las 3,250 trades elegidas (`chosen_flag=1`,
  historial completo 2022-2026) con costo ×2 en vez de ×1, manteniendo fijo
  el conjunto de trades ya seleccionado (no se rederivó la selección bajo el
  costo nuevo — ver limitación abajo). Script de recomputo validado: la
  versión ×1 reproduce exacto el `walk_summary.json` real (equity $9,178.69,
  CAGR 69.59%, MaxDD -1.74%).
  - Equity final: $9,178.69 → **$5,580.25**
  - Retorno total: +817.9% → **+458.0%**
  - CAGR: 69.6% → **50.6%**
  - MaxDD: -1.74% → **-2.64%**
  - **Solo el 56% del retorno total reportado sobrevive con el costo real —
    el 44% restante era artefacto de medio costo de transacción.**
  - Limitación: al mantener fijo el conjunto de trades elegidos, esto es una
    cota conservadora — con costos reales desde el inicio, algunos candidatos
    marginales dejarían de pasar el filtro EV-gap/quantile, y el impacto real
    de una reconstrucción completa podría ser distinto (probablemente mayor).
- **Estado:** sin corregir. No aplicar fix hasta próxima revisión. No se tocó
  `walk_summary.json` ni ningún archivo de reporte público.

---

## Decisión 7 — Conclusión: `walk.py` y producción son, en la práctica, dos
## sistemas distintos que comparten el mismo nombre

Con las tres divergencias documentadas (dirección/EV-gap, sizing, costos), y
sumado al Bug 1 (modelo de producción congelado 4+ meses), la evidencia
acumulada esta sesión indica que el backtest que ha respaldado las
afirmaciones de due diligence (`walk_summary.json`, `retrain_history.jsonl`,
el sitio público de S4BTC) y lo que realmente ha corrido en producción no son
el mismo sistema evaluado dos veces — son dos implementaciones paralelas del
mismo diseño conceptual, con diferencias reales y medibles en cada eslabón
verificado hasta ahora (selección de dirección, filtrado por EV, tamaño de
posición, costo de transacción). Ninguna de las cifras públicas citadas hasta
hoy (CAGR 70%, winrate 64%, equity_final) puede tomarse como una predicción
directa de lo que producción puede lograr sin, al menos, la corrección de
costos (Decisión 6.3) y una revisión del sizing (Decisión 6.2).

**Pendiente para la próxima sesión:** aplicar fix de sizing y de costos (con
revisión humana previa, Regla 4 de `CLAUDE.md` — ambos cambian qué tamaño de
posición y qué EV ve el bot en vivo), y considerar si `walk_summary.json`
debe republicarse con el costo corregido antes de cualquier decisión de
capital real.
