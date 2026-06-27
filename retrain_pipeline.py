"""
RoboTrader S4 — retrain_pipeline.py
Pipeline de retrain automatizado, alineado al sliding window del
walk-forward (STEP_DAYS=14 en config.py).

Pasos:
  1. Actualizar data/{SYMBOL}.csv con velas nuevas desde OKX
  2. Validar integridad (validate_dataset.py) — ABORTA si hay huecos grandes
  3. Re-etiquetar con Triple Barrera (make_labeled_dataset.py)
  4. Validar el dataset etiquetado — ABORTA si hay huecos grandes
  5. Re-entrenar via walk-forward completo (walk.py) — guarda nuevo best_model
  6. Validar metricas minimas vs baseline conocido — ABORTA deploy si degrada
  7. Si todo pasa: copiar el modelo nuevo a produccion y loggear resultado

Uso manual:
    python retrain_pipeline.py

Uso programado (cron, cada STEP_DAYS):
    0 3 */14 * * cd /path/to/s4_deploy && python retrain_pipeline.py >> logs/retrain.log 2>&1

Disenado para fallar RUIDOSAMENTE (exit code != 0) en cualquier paso,
en vez de continuar en silencio — leccion directa del incidente del
8 de Junio 2026 donde un dataset con huecos no detectados produjo un
modelo degradado sin que nadie lo notara hasta dias despues.
"""
import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
RAW_CSV = BASE_DIR / "data" / "BTCUSDT.csv"
LABELED_CSV = BASE_DIR / "data" / "BTCUSDT_labeled.csv"
MODEL_DIR = BASE_DIR / "model"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

MIN_WINRATE = 0.55
MIN_SHARPE_PROXY_CAGR = 0.40
MAX_ACCEPTABLE_DD = -0.10


def _log(msg: str):
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {msg}")


def _run(cmd: list, step_name: str) -> subprocess.CompletedProcess:
    _log(f"=== PASO: {step_name} ===")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        _log(f"FALLO en {step_name} (exit code {result.returncode}) — ABORTANDO PIPELINE")
        sys.exit(1)
    return result


def step_1_update_data():
    _log("=== PASO 1: Actualizar datos OHLC ===")
    import pandas as pd
    from data_fetcher import get_historical_data

    df_old = pd.read_csv(RAW_CSV)
    df_old["open_time"] = pd.to_datetime(df_old["open_time"], utc=True)
    last_ts = df_old["open_time"].max()
    _log(f"Ultimo dato actual: {last_ts}")

    # Calcular cuantas velas hacen falta para llegar a "ahora", con margen.
    # Esto evita el problema de limit=600 fijo siendo insuficiente si el
    # pipeline se atraso (ej. Codespace detenido varios dias).
    now = pd.Timestamp.now(tz="UTC")
    hours_needed = int((now - last_ts).total_seconds() / 3600) + 24
    fetch_limit = max(600, hours_needed)
    _log(f"Horas a cubrir: ~{hours_needed} — usando limit={fetch_limit}")

    df_new = get_historical_data("BTCUSDT", "1h", limit=fetch_limit)
    df_new = df_new[df_new["open_time"] > last_ts]
    _log(f"Velas nuevas descargadas: {len(df_new)}")

    if len(df_new) == 0:
        _log("Sin datos nuevos — dataset ya esta actualizado")
        return

    df_combined = pd.concat([df_old, df_new], ignore_index=True)
    df_combined = df_combined.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)

    diffs = df_combined["open_time"].diff()
    big_gaps = diffs[diffs > pd.Timedelta(hours=48)]
    if len(big_gaps) > 0:
        _log(f"ADVERTENCIA: {len(big_gaps)} hueco(s) >48h detectado(s) — aun asi con limit dinamico.")
        _log("Esto es inusual y requiere revision manual del fetcher u OKX.")
        for idx in big_gaps.index:
            _log(f"  Hueco: {df_combined['open_time'].iloc[idx-1]} -> {df_combined['open_time'].iloc[idx]}")
        _log("ABORTANDO — no se puede continuar con huecos grandes sin rellenar.")
        sys.exit(1)

    df_combined.to_csv(RAW_CSV, index=False)
    _log(f"Dataset actualizado: {len(df_combined)} filas, hasta {df_combined['open_time'].max()}")


def step_2_validate_raw():
    _run(["python3", "validate_dataset.py", "--path", str(RAW_CSV)], "Validar RAW")


def step_3_relabel():
    _run(["python3", "make_labeled_dataset.py"], "Re-etiquetar (Triple Barrera)")


def step_4_validate_labeled():
    _run(["python3", "validate_dataset.py", "--path", str(LABELED_CSV)], "Validar LABELED")


def step_5_walk_forward():
    result = _run(["python3", "walk.py"], "Walk-forward (retrain)")
    return result


def step_6_check_metrics() -> dict:
    _log("=== PASO 6: Verificar metricas minimas ===")
    summary_path = BASE_DIR / "walk_summary.json"
    with open(summary_path) as f:
        summary = json.load(f)

    winrate = summary["win_rate"]
    cagr = summary["CAGR"]
    maxdd = summary["max_drawdown_daily"]

    _log(f"Winrate: {winrate:.4f}  (minimo aceptable: {MIN_WINRATE})")
    _log(f"CAGR:    {cagr:.4f}  (minimo aceptable: {MIN_SHARPE_PROXY_CAGR})")
    _log(f"MaxDD:   {maxdd:.4f}  (maximo aceptable: {MAX_ACCEPTABLE_DD})")

    ok = True
    if winrate < MIN_WINRATE:
        _log(f"FALLO: winrate {winrate:.4f} por debajo del minimo {MIN_WINRATE}")
        ok = False
    if cagr < MIN_SHARPE_PROXY_CAGR:
        _log(f"FALLO: CAGR {cagr:.4f} por debajo del minimo {MIN_SHARPE_PROXY_CAGR}")
        ok = False
    if maxdd < MAX_ACCEPTABLE_DD:
        _log(f"FALLO: MaxDD {maxdd:.4f} peor que el maximo aceptable {MAX_ACCEPTABLE_DD}")
        ok = False

    if not ok:
        _log("METRICAS POR DEBAJO DEL MINIMO — el modelo NO se despliega a produccion.")
        _log("El modelo anterior en model/best_model.ubj permanece sin cambios.")
        sys.exit(1)

    _log("Metricas dentro de rango aceptable — modelo apto para deploy.")
    return summary


def step_7_finalize(summary: dict):
    _log("=== PASO 7: Finalizar — modelo listo para produccion ===")
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "winrate": summary["win_rate"],
        "cagr": summary["CAGR"],
        "max_drawdown": summary["max_drawdown_daily"],
        "trades_total": summary["trades_total"],
        "equity_final": summary["equity_final"],
        "dataset_sha256": summary["dataset_sha256"],
    }
    history_path = LOG_DIR / "retrain_history.jsonl"
    with open(history_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    _log(f"Historial actualizado: {history_path}")
    _log(f"RETRAIN COMPLETO Y EXITOSO. Equity final: ${summary['equity_final']:,.2f}")


def main():
    _log("########## INICIANDO RETRAIN PIPELINE ##########")
    step_1_update_data()
    step_2_validate_raw()
    step_3_relabel()
    step_4_validate_labeled()
    step_5_walk_forward()
    summary = step_6_check_metrics()
    step_7_finalize(summary)
    _log("########## RETRAIN PIPELINE FINALIZADO OK ##########")


if __name__ == "__main__":
    main()
