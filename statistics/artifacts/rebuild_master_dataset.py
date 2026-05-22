from pathlib import Path
import zipfile
import pandas as pd

RAW_DIR = Path("data/raw_backfill")
OUT_CSV = Path("data/BTCUSDT.csv")

frames = []

print("=======================================")
print("REBUILDING MASTER DATASET")
print("=======================================")

zip_files = sorted(RAW_DIR.glob("*.zip"))

print(f"[INFO] zip files found: {len(zip_files)}")

for zf in zip_files:
    print(f"[LOAD] {zf.name}")

    with zipfile.ZipFile(zf, "r") as z:
        inner = z.namelist()[0]

        df = pd.read_csv(z.open(inner))

        df = df.rename(columns={
            "open_time": "open_time",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "close_time": "close_time",
        })

        keep_cols = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
        ]

        df = df[keep_cols].copy()

        # timestamps Binance -> datetime
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

        # numeric conversion
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        frames.append(df)

master = pd.concat(frames, ignore_index=True)

master = (
    master
    .drop_duplicates("open_time")
    .sort_values("open_time")
    .reset_index(drop=True)
)

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
master.to_csv(OUT_CSV, index=False)

print("")
print("=======================================")
print("MASTER DATASET COMPLETE")
print("=======================================")

print(master.head())
print("")
print(master.tail())

print("")
print(f"[ROWS] {len(master)}")
print(f"[START] {master['open_time'].iloc[0]}")
print(f"[END]   {master['open_time'].iloc[-1]}")
print(f"[OUT]   {OUT_CSV}")