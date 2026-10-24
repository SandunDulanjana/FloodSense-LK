import os
from pathlib import Path
import numpy as np
import pandas as pd

#SAMPLES_DIR = Path(r"C:\Users\User\Desktop\M3_Project\data\samples") 
SAMPLES_DIR = Path(os.environ.get("M3_SAMPLES_DIR", r"C:\Users\User\Desktop\M3_Project\data\samples"))
DISTRICTS = ["Ratnapura", "Colombo", "Gampaha"]
NODATA = -9999

OUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "reference_dataset"
OUT_DIR.mkdir(parents=True, exist_ok=True)

META = ["field_id", "district", "crop_type", "class_id", "fill_level"]
BASE = ["B2","B3","B4","B5","B6","B7","B8","B8A","B11","B12","NDVI","NDWI","elevation","slope","aspect"]

frames = []
for d in DISTRICTS:
    files = [f for f in SAMPLES_DIR.glob(f"M3_{d}_TrainingSamples_*.csv")
             if "old" not in f.stem.lower()]
    if not files:
        raise SystemExit(f"{d}: no CSV found in {SAMPLES_DIR}")
    f = max(files, key=lambda p: p.stat().st_mtime)          # newest file
    df = pd.read_csv(f)
    print(f"{d}: {f.name} -> {len(df)} pixels, {df['field_id'].nunique()} fields")
    frames.append(df)

ts_sets = [{c for c in df.columns if c.startswith(("NDVI_", "NDWI_"))} for df in frames]
if any(s != ts_sets[0] for s in ts_sets):
    for d, s in zip(DISTRICTS, ts_sets):
        print(d, "time-series columns:", len(s))
    raise SystemExit("Time-series columns differ between districts. Re-run sampling for the odd one.")
TS_ALL = sorted(ts_sets[0])

data = pd.concat(frames, ignore_index=True)
need = META + BASE + TS_ALL
missing = [c for c in need if c not in data.columns]
if missing:
    raise SystemExit(f"Missing columns: {missing}")
keep = need + [c for c in ["longitude", "latitude"] if c in data.columns]
data = data[keep].replace(NODATA, np.nan)
data["crop_type"] = data["crop_type"].astype(str).str.strip().str.title()
data = data.dropna(subset=["field_id", "crop_type"] + BASE)   # time-series gaps stay as NaN

n_dist = data.groupby("field_id")["district"].nunique()
if (n_dist > 1).any():
    raise SystemExit(f"field_id used in more than one district: {list(n_dist[n_dist > 1].index)}")

print("\nClasses:", sorted(data["crop_type"].unique()))
print("\nFields per district x class:")
print(data.groupby(["district", "crop_type"])["field_id"].nunique().unstack(fill_value=0))
print("\nPixels per district x class:")
print(data.groupby(["district", "crop_type"]).size().unstack(fill_value=0))
print("\nPixels per field (min / median / max):",
      data.groupby("field_id").size().agg(["min", "median", "max"]).tolist())
print("Share of pixels by fill_level:", data["fill_level"].value_counts(normalize=True).round(3).to_dict())
gap = data.groupby("district")[TS_ALL].apply(lambda g: g.isna().mean()).T
print("\nMissing share per district, 10 worst time-series columns:")
print(gap.assign(worst=gap.max(axis=1)).sort_values("worst", ascending=False).head(10).round(3))

out = OUT_DIR / "M3_training_table_all_districts.csv"
data.to_csv(out, index=False)
print(f"\nSaved {len(data)} rows to {out}")