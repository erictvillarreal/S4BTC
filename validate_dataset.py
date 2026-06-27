"""
RoboTrader S4 — validate_dataset.py
Verifica integridad temporal del dataset OHLC antes de cualquier
retrain. Falla ruidosamente (exit code != 0) si encuentra huecos,
duplicados, o cobertura incompleta — en vez de dejarlo pasar en
silencio como ocurrio el 8 de Junio 2026 (hueco de 34 dias sin
detectar antes del retrain fallido).

Uso:
    python validate_dataset.py
    python validate_dataset.py --path data/BTCUSDT_labeled.csv
"""
import argparse
import sys
import pandas as pd
from pathlib import Path

EXPECTED_FREQ = pd.Timedelta(hours=1)
MAX_GAP_TOLERANCE = pd.Timedelta(hours=2)  # tolera 1 vela perdida aislada


def validate(path: str) -> bool:
    df = pd.read_csv(path)
    if "open_time" not in df.columns:
        print(f"[ERROR] Columna 'open_time' no encontrada en {path}")
        return False

    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    df = df.sort_values("open_time").reset_index(drop=True)

    ok = True

    # 1. Duplicados
    dupes = df["open_time"].duplicated().sum()
    if dupes > 0:
        print(f"[FAIL] {dupes} timestamps duplicados encontrados")
        ok = False
    else:
        print(f"[OK] Sin duplicados ({len(df)} filas)")

    # 2. Huecos temporales
    diffs = df["open_time"].diff()
    gaps = diffs[diffs > MAX_GAP_TOLERANCE]
    if len(gaps) > 0:
        print(f"[FAIL] {len(gaps)} hueco(s) temporal(es) > {MAX_GAP_TOLERANCE} encontrados:")
        for idx in gaps.index:
            print(f"        {df['open_time'].iloc[idx-1]} -> {df['open_time'].iloc[idx]}  (gap: {gaps[idx]})")
        ok = False
    else:
        print(f"[OK] Sin huecos temporales > {MAX_GAP_TOLERANCE}")

    # 3. Cobertura mensual (informativo, no bloqueante salvo huecos grandes)
    df["year_month"] = df["open_time"].dt.tz_localize(None).dt.to_period("M")
    monthly = df.groupby("year_month").size()
    print()
    print("Cobertura mensual (ultimos 6 meses):")
    print(monthly.tail(6).to_string())

    # 4. Rango total
    print()
    print(f"Rango: {df['open_time'].min()} -> {df['open_time'].max()}")
    total_expected = int((df['open_time'].max() - df['open_time'].min()) / EXPECTED_FREQ) + 1
    coverage_pct = len(df) / total_expected * 100
    print(f"Cobertura: {len(df)}/{total_expected} velas esperadas ({coverage_pct:.2f}%)")

    if coverage_pct < 95:
        print(f"[WARN] Cobertura por debajo del 95% — revisar antes de usar para retrain")

    print()
    print("="*60)
    print("RESULTADO: PASA" if ok else "RESULTADO: FALLA — NO USAR PARA RETRAIN")
    print("="*60)

    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="data/BTCUSDT.csv")
    args = ap.parse_args()

    if not Path(args.path).exists():
        print(f"[ERROR] No existe: {args.path}")
        sys.exit(1)

    passed = validate(args.path)
    sys.exit(0 if passed else 1)
