# Auditoría de Pre-Vuelo — S4BTC — 18 de septiembre de 2026

Fase 0, primera pasada. Metodología: 4 preguntas (corrección interna,
consistencia con gemelo, riesgo de falla silenciosa, documentación vs.
realidad) aplicadas a las 8 etapas del pipeline. Cada hallazgo abajo fue
verificado con código y/o datos reales — no hay "probablemente" ni "parece
que". Esta es una primera pasada rigurosa, no una garantía de cobertura al
100% — quedan sub-ítems de la lista original sin agotar (ver "No cubierto
todavía" al final).

No se aplicó ningún fix durante esta fase. Solo diagnóstico.

---

## CRÍTICO

### C1 — Riesgo real de trade duplicado en cualquier reinicio del proceso
**Dónde:** `trader.py:175` (`last_processed_candle = None`, variable en
memoria, nunca persistida) + `trader.py:421` (`send_trade()`, Telegram) vs.
`trader.py:429/447` (`state["pending_trade"]` se asigna y se guarda
DESPUÉS del envío de Telegram).

**Por qué importa:** si el proceso se cae o Railway lo reinicia entre el
envío de la notificación de Telegram y el guardado del estado, al reiniciar
el bot no tiene memoria de haber procesado esa vela ni de haber decidido
ese trade. Vuelve a evaluar la misma vela desde cero, con el mismo modelo
determinístico → muy probablemente toma la misma decisión otra vez →
duplica el trade (y el mensaje de Telegram). En modo paper esto duplica
una posición simulada; en modo live implicaría una segunda orden real.

**Evidencia:** confirmado leyendo el orden exacto de las líneas citadas.
Railway se reinició varias veces esta semana por nuestros propios pushes
(`51681ef`, `29645e9`, y los cambios de hoy) — esta ventana de carrera se
puso a prueba varias veces, sin forma de confirmar desde aquí si algún
trade real resultó duplicado (necesitaría cruzar timestamps de Telegram
contra Postgres, y Telegram no está en mi alcance).

**No se corrigió** — es exactamente el tipo de cambio a `trader.py` que
requiere diff mostrado y aprobado (Regla 4).

### C2 — Rama LIVE de `futures_broker.py` sin manejo de error, nunca ejecutada
**Dónde:** `futures_broker.py:217-222` (`open_long`) y `:252-257`
(`open_short`), rama `else` (no-paper).

**Por qué importa:** si `_market_order` (entrada) tiene éxito pero
`_stop_order` (TP o SL) falla después — red, rechazo del exchange, margen
insuficiente — no hay ningún rollback ni cancelación de la entrada ya
ejecutada. La excepción se propaga cruda. Con capital real, esto dejaría
una posición abierta sin protección de TP/SL, indefinidamente, hasta que
alguien lo note manualmente.

**Evidencia:** `MODE` ha sido `"paper"` en el 100% de lo observado esta
semana (confirmado en múltiples verificaciones contra la DB real) — esta
rama de código **nunca se ha ejecutado ni una sola vez**. No es solo un
bug potencial, es código de producción con cero horas de vuelo real.

**No se corrigió.**

---

## IMPORTANTE

### I1 — El gate de cobertura del 95% en `validate_dataset.py` no es un gate
**Dónde:** `validate_dataset.py:83-84`.

```python
if coverage_pct < 95:
    print(f"[WARN] Cobertura por debajo del 95% — revisar antes de usar para retrain")
```

No hay `ok = False` en este bloque. `ok` solo lo afectan los checks de
duplicados y de huecos grandes (>48h en labeled, >2h en raw) — la
cobertura es puramente informativa.

**Evidencia corrida contra datos reales hoy:** `data/BTCUSDT_labeled.csv`
tiene **87.47% de cobertura** (35,995/41,152 velas esperadas) — por debajo
del umbral — y el script imprime el `[WARN]` pero termina en
`RESULTADO: PASA`, exit code 0. Esto no es hipotético: está pasando en
cada retrain, ahora mismo, y como el pipeline corre 100% manual (ver Tarea
3 de la sesión anterior) nadie ha estado mirando ese WARN en tiempo real.

**Nota de diseño:** el propio comentario del script explica que huecos
chicos dispersos son "esperados por diseño de Triple Barrera" — la
decisión de no bloquear podría ser intencional. Pero el mensaje del WARN
("revisar antes de usar para retrain") promete una revisión humana que en
la práctica nunca ocurre, porque nada fuerza a que ocurra.

### I2 — `walk.py` no modela el guard de "trade pendiente" de `trader.py`
**Dónde:** `walk.py:449-488` (selección `chosen` por día + loop de
ejecución).

La selección limita a `max_trades_per_day` candidatos **por día
calendario** (`walk.py:455`), pero el loop de ejecución resuelve cada
candidato elegido **instantáneamente vía el label** (líneas 520-526) sin
verificar si un trade "anterior" seguiría abierto dentro de su horizonte
de 12 velas. `trader.py`, en cambio, bloquea explícitamente cualquier
nueva decisión mientras `state.get("pending_trade")` esté activo (hasta
12 horas).

**Por qué importa:** el backtest puede efectivamente tomar dos candidatos
el mismo día aunque estén a 1-2 horas de distancia — algo que producción
nunca podría hacer, porque el primero seguiría "pendiente". El throughput
de trades que el backtest asume es estructuralmente mayor al que
producción puede lograr, incluso respetando el mismo `MAX_TRADES_PER_DAY`.
Esta es la quinta divergencia real entre backtest y producción encontrada
en dos semanas — no estaba en la lista de las 4 ya conocidas.

**No se corrigió ni se cuantificó el impacto en $ todavía** — queda
pendiente de decidir si vale la pena simularlo.

### I3 — `state.py` promete "thread-safe con filelock" y no lo es
**Dónde:** `state.py:4` (docstring) vs. todo el archivo (sin
`import filelock`, sin ningún mecanismo de lock).

`save()` sí usa escritura atómica (`os.replace` tras escribir a un
`.tmp`), lo cual protege contra corrupción del archivo por un crash a
media escritura — pero eso no es lo mismo que "thread-safe con filelock".
No hay ningún lock real. Mitigado hoy porque `trader.py` corre como un
solo proceso sin hilos concurrentes escribiendo al mismo `state.json` —
pero la documentación afirma una garantía que el código no cumple, el
mismo patrón exacto que ya encontramos dos veces esta semana (docstring
de `retrain_pipeline.py` y comentario de `s4_policy.py`).

### I4 — `get_historical_data()` puede devolver menos filas de las pedidas sin avisar
**Dónde:** `data_fetcher.py:93-96`.

Si el loop principal termina (`break`, tanto en el endpoint normal como en
history-candles) antes de alcanzar `limit`, la función simplemente
devuelve lo que haya acumulado en `frames` — sin ningún log ni warning
sobre el faltante. El propio archivo documenta (líneas 56-61) que este
patrón exacto de "parar en silencio sin avisar" ya causó un incidente real
(hueco de 15 días no detectado) que se corrigió — pero esa corrección fue
para el caso de "una página devuelve menos de lo pedido", no para el caso
de "el loop completo termina sin alcanzar el total". El único guardarraíl
downstream es el chequeo de `trader.py` (`len(df) < 50 → error`), que
atraparía una falla total pero no un faltante parcial (p. ej. pedir 300 y
recibir 220 no dispara nada).

### I5 — Canal de registro local (`trade_logger.py` → `logs/trade_ledger.csv`) sin verificar
**Dónde:** `logs/trade_ledger.csv` (copia en git).

La copia de este archivo en el repositorio tiene **4 filas, todas del
14-15 de mayo de 2026** — el mismo patrón que ya vimos con
`walk_candidates.csv` y el `trade_ledger.csv` de la raíz: un snapshot
comiteado una vez (`a3a5a10`) y nunca vuelto a actualizar en git. **No
puedo confirmar si el archivo real en el volumen persistente de Railway
sigue recibiendo cada trade** — `trader.py` sí llama a `log_trade()` (el
de `trade_logger.py`) en cada cierre, pero no tengo acceso a
`/app/persist/logs/trade_ledger.csv` para verificarlo. Este es un tercer
canal de registro (además de Telegram y Postgres) que nadie ha confirmado
que siga funcionando.

### I6 — Requisito ya identificado, confirmado que sigue abierto: dependencias sin fijar
**Dónde:** `requirements.txt` — todas las líneas usan `>=`, ninguna usa `==`.

Confirmado que sigue exactamente igual que antes. Con `runtime.txt`
fijando `python-3.11.9`, pero las librerías (`xgboost`, `pandas`, etc.) sin
versión exacta, dos instalaciones distintas (ej. Railway vs. una máquina
local) pueden resolver versiones diferentes — relevante en particular para
`xgboost`, dado que ya tuvimos un problema de compatibilidad de formato de
modelo (`.ubj`/`.pkl`) esta semana.

### I7 — `USE_TESTNET` real en Railway: no verificable desde aquí
**Dónde:** `.env.example:6` documenta `USE_TESTNET=true` por defecto.

No tengo forma de confirmar qué valor tiene realmente configurado el
servicio en Railway — necesito que Eric lo confirme directamente desde el
dashboard. Dado que `MODE=paper` ha sido el modo real observado toda la
semana, el riesgo práctico hoy es bajo (paper mode no llama a los
endpoints firmados), pero este pendiente, ya anotado antes, sigue sin
cerrarse porque requiere acceso que no tengo.

---

## MENOR

### M1 — `close_time` hardcodeado a +1 hora en `data_fetcher.py`
**Dónde:** `data_fetcher.py:44` (`df["close_time"] = df["open_time"] + pd.Timedelta(hours=1)`).

No usa el parámetro `interval` real — si algún día `BOT_TIMEFRAME` cambia
de `1h` a otro valor, `close_time` quedaría mal calculado en silencio. Hoy
no tiene efecto porque el sistema siempre corre en 1h.

### M2 — Residuo de sizing (0.75x-1.17x), ya documentado en código esta semana
Referenciado aquí para que quede en el mismo reporte de auditoría. Ver
comentario en `s4_policy.py._vol_scale` (Decisión 12) para el detalle
completo — no es un hallazgo nuevo de esta auditoría.

---

## SOLO NOTA — revisado, sin problema

- **`tech_signals.py`** — las 4 funciones (`_ema`, `_rsi`, `_macd`, `_atr`)
  verificadas rastreando sus dependencias de índice, no solo leyendo el
  código. Todas causales (`.ewm()`, `.shift(1)`, `.rolling()` sin
  `center=True`). **Sin look-ahead, limpio.**
- **Purge/embargo** en `walk.py` (`_embargo_timedelta`, `_purge_by_embargo`)
  — alineado correctamente con `HORIZON=12`. Confirmado que NO existe (ni
  debería existir) en `make_labeled_dataset.py`, porque ese script no hace
  ningún split train/test — el purge le corresponde a quien parte los
  datos, y `walk.py` sí lo implementa.
- **`step_6_check_metrics()` de `retrain_pipeline.py`** — no se asumió que
  funciona, se probó: se simuló un `walk_summary.json` con métricas malas
  (winrate 30%, CAGR 10%, MaxDD -50%) y se confirmó que aborta con
  `sys.exit(1)` de verdad. El archivo real se restauró sin dejar rastro
  (`git diff` vacío tras la prueba).
- **`MDD_KILL_PCT=0.25` / `RISK_DAILY_PCT=0.005`** — sin ningún cambio en
  todo el historial de git desde el commit inicial (`8e7916f`, 4-mayo). No
  hubo drift accidental en ningún commit de esta semana.
- **`walk.py` vs. `walk_backup.py`** — son byte-idénticos (`diff` vacío).
  Archivo redundante, no una divergencia oculta.
- **Búsqueda de `except: pass`** en todo el repositorio (`.py`, excluyendo
  `.venv311`) — cero resultados. No se encontró ese patrón específico de
  falla silenciosa.
- **Telegram vs. Postgres al cierre de un trade** — `db_logger.log_trade()`
  (Postgres) se llama primero, envuelto en su propio try/except;
  `send_trade_closed()` (Telegram) se llama después, sin su propio
  try/except. Si Telegram falla, el trade ya quedó en Postgres. El único
  escenario donde un trade no quedaría en ninguno de los dos es que ambos
  fallen en el mismo trade — posible en teoría, sin evidencia de que haya
  ocurrido.

---

## No cubierto todavía (para la siguiente pasada)

- Barrido función-por-función de `s4_policy.py` buscando cualquier otra
  que reclame equivalencia con `walk.py` más allá de las 4 ya auditadas
  (dirección, ev_gap, costos, sizing).
- Cuantificar en $ el impacto de I2 (guard de trade pendiente ausente en
  `walk.py`) — hoy solo está identificado, no medido.
- Confirmar si algún trade real ha llegado a duplicarse por C1 — requeriría
  cruzar timestamps de Telegram contra Postgres, fuera de mi alcance
  directo hoy.
- Verificar el contenido real de `/app/persist/logs/trade_ledger.csv` en
  Railway (I5) — requiere que alguien con acceso lo revise.
- `paper_engine.py` — mencionado la sesión pasada como pendiente aparte,
  no se auditó a fondo en esta pasada.

---

**Resumen:** 2 hallazgos críticos (ambos sin corregir, ambos requieren
decisión antes de cualquier capital real), 7 importantes, 2 menores, y 7
ítems revisados y confirmados limpios. Ningún fix aplicado — todo queda
para que se priorice y se decida qué hacer con cada uno, igual que con las
4 divergencias de esta semana.
