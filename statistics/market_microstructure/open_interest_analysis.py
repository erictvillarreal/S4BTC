"""
S4 — Microstructure Features via OKX (sin restricciones geográficas)
Fetches: funding rate, open interest, OI-weighted volume
Genera features adicionales para el próximo retrain del modelo.
"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

OKX_BASE = "https://www.okx.com/api/v5"

# ── Fetchers ──────────────────────────────────────────────

def get_funding_rate(instId: str = "BTC-USD-SWAP") -> dict:
    """Funding rate actual."""
    r = requests.get(f"{OKX_BASE}/public/funding-rate",
                     params={"instId": instId}, timeout=10)
    r.raise_for_status()
    d = r.json()["data"][0]
    return {
        "funding_rate":      float(d["fundingRate"]),
        "funding_time":      int(d["fundingTime"]),
        "interest_rate":     float(d["interestRate"]),
    }

def get_oi_volume_history(ccy: str = "BTC", period: str = "1H", limit: int = 500) -> pd.DataFrame:
    """
    Open Interest + Volume histórico por hora.
    Retorna DataFrame con columnas: ts, oi_usd, volume_usd
    """
    r = requests.get(f"{OKX_BASE}/rubik/stat/contracts/open-interest-volume",
                     params={"ccy": ccy, "period": period}, timeout=10)
    r.raise_for_status()
    raw = r.json()["data"]
    df = pd.DataFrame(raw, columns=["ts_ms", "oi_usd", "volume_usd"])
    df["ts"]         = pd.to_datetime(df["ts_ms"].astype(int), unit="ms", utc=True)
    df["oi_usd"]     = df["oi_usd"].astype(float)
    df["volume_usd"] = df["volume_usd"].astype(float)
    df = df.sort_values("ts").reset_index(drop=True)
    return df[["ts", "oi_usd", "volume_usd"]]

def get_funding_history(instId: str = "BTC-USD-SWAP", limit: int = 100) -> pd.DataFrame:
    """Historial de funding rates (cada 8h)."""
    r = requests.get(f"{OKX_BASE}/public/funding-rate-history",
                     params={"instId": instId, "limit": limit}, timeout=10)
    r.raise_for_status()
    raw = r.json()["data"]
    df = pd.DataFrame(raw)
    df["ts"]           = pd.to_datetime(df["fundingTime"].astype(int), unit="ms", utc=True)
    df["funding_rate"] = df["fundingRate"].astype(float)
    df = df.sort_values("ts").reset_index(drop=True)
    return df[["ts", "funding_rate"]]

# ── Feature Engineering ───────────────────────────────────

def build_microstructure_features(oi_df: pd.DataFrame, funding_df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye features de microestructura sobre el DataFrame de OI/Volume.

    Features generados:
      oi_change_1h    — cambio porcentual de OI en 1h
      oi_change_8h    — cambio porcentual de OI en 8h
      oi_zscore_24h   — z-score de OI vs últimas 24h
      volume_oi_ratio — volumen / OI (proxy de agresividad)
      funding_rate    — último funding rate conocido (forward-filled cada 8h)
      funding_sign    — signo del funding (+1 longs pagan, -1 shorts pagan)
      funding_extreme — 1 si |funding| > 2 std histórico
    """
    df = oi_df.copy()

    # OI changes
    df["oi_change_1h"] = df["oi_usd"].pct_change(1)
    df["oi_change_8h"] = df["oi_usd"].pct_change(8)

    # OI z-score rolling 24h
    oi_mean = df["oi_usd"].rolling(24).mean()
    oi_std  = df["oi_usd"].rolling(24).std()
    df["oi_zscore_24h"] = (df["oi_usd"] - oi_mean) / (oi_std + 1e-12)

    # Volume / OI ratio
    df["volume_oi_ratio"] = df["volume_usd"] / (df["oi_usd"] + 1e-12)

    # Merge funding (cada 8h → forward fill a 1h)
    funding_df = funding_df.set_index("ts").resample("1h").last().ffill().reset_index()
    df = pd.merge_asof(df.sort_values("ts"), funding_df.sort_values("ts"),
                       on="ts", direction="backward")

    # Funding features
    df["funding_sign"]    = np.sign(df["funding_rate"])
    fund_std              = df["funding_rate"].rolling(24*3).std()  # 3 días
    df["funding_extreme"] = (df["funding_rate"].abs() > 2 * fund_std).astype(int)

    return df.dropna().reset_index(drop=True)

# ── Main ──────────────────────────────────────────────────

if __name__ == "__main__":
    OUT = Path(__file__).parent / "artifacts"
    OUT.mkdir(exist_ok=True)

    print("Fetching OI + Volume history...")
    oi_df = get_oi_volume_history(limit=500)
    print(f"  {len(oi_df)} filas — {oi_df['ts'].min()} → {oi_df['ts'].max()}")

    print("Fetching funding rate history...")
    fund_df = get_funding_history(limit=100)
    print(f"  {len(fund_df)} filas")

    print("Building features...")
    features_df = build_microstructure_features(oi_df, fund_df)
    print(f"  {len(features_df)} filas con features completos")
    print(features_df.tail(5).to_string())

    out_path = OUT / "microstructure_features.csv"
    features_df.to_csv(out_path, index=False)
    print(f"\n✓ Guardado en {out_path}")

    # Funding actual
    print("\nFunding rate actual:")
    fr = get_funding_rate()
    for k, v in fr.items():
        print(f"  {k}: {v}")
