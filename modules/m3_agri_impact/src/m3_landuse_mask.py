"""
M3 - cultivated-land mask from the national land-use map (Survey Dept / SLNSDI Planning_Cadastre, layer 4 "Landuse").

What it does, per district
  1. downloads the land-use polygons that cover the district's FeatureStack raster (REST service, 1000 per request)
  2. prints how much area each land-use class covers and which creation / revision years the polygons carry
  3. rasterizes them on the SAME 10 m grid as the FeatureStack and writes
        rasters/<District>/M3_<District>_Cultivated.tif   1 = cultivated class (kept), 0 = everything else
        rasters/<District>/M3_<District>_LandUseCode.tif  one code per land-use class (see landuse_codes.csv)
  4. checks your training points: which land-use class holds Paddy / Tea / Other samples (outputs/results/map/landuse_check.csv)

m3_final_map.py uses the Cultivated raster automatically (it then ignores WorldCover and the forest mask).

Needs internet (Colab is fine):   pip install rasterio requests
Run:  python src/m3_landuse_mask.py
Optional: os.environ["M3_LANDUSE_KEEP"] = "Paddy,Tea,Rubber,..."  to change the kept classes (exact service names, comma separated)
"""
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.features import rasterize

ROOT = Path(__file__).resolve().parents[1]
RASTER_DIR = Path(os.environ.get("M3_RASTER_DIR", ROOT / "data" / "rasters"))
TABLE = ROOT / "outputs" / "reference_dataset" / "M3_training_table_all_districts.csv"
CACHE = ROOT / "data" / "landuse"; CACHE.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "outputs" / "results" / "map"; OUT.mkdir(parents=True, exist_ok=True)
URL = "https://www.gisapps.nsdi.gov.lk/server/rest/services/SLNSDI/Planning_Cadastre/MapServer/4/query"
DISTRICTS = ["Ratnapura", "Colombo", "Gampaha"]
FIELD = "landuse_classification_2"

# classes where the crop model is allowed to work (everything else stays grey)
KEEP_DEFAULT = ["Paddy", "Paddy-abandoned", "Tea", "Rubber", "Coconut", "Cinnamon", "Cashew", "Chena",
                "Mixed tree and other perennial crop", "Other cultivation", "Sparsely used cropland", "Sugarcane",
                "Oil Palm", "Palmyrah", "Homesteads/Garden", "Agricultural farms"]
KEEP = [k.strip() for k in os.environ.get("M3_LANDUSE_KEEP", "").split(",") if k.strip()] or KEEP_DEFAULT
ALL_CLASSES = ["Agricultural farms", "Aquatic farms", "Associated non-agricultural land", "Barre Land", "Built up area",
               "Cashew", "Cemetry", "Chena", "Cinnamon", "Coconut", "Dense Forest", "Forest - Unclassified",
               "Forest Plantation", "Grassland", "Homesteads/Garden", "Livestock farms", "Mangrove", "Marsh",
               "Mixed tree and other perennial crop", "Oil Palm", "Open Forest", "Other cultivation", "Paddy",
               "Paddy-abandoned", "Palmyrah", "Playground", "Quarry", "Rock", "Rubber", "Sand", "Scrub land",
               "Sparsely used cropland", "Sugarcane", "Tea", "Unclassified"]
CODE = {n: i + 1 for i, n in enumerate(ALL_CLASSES)}          # 0 = no polygon


def get_json(params, tries=5):
    for k in range(tries):
        try:
            r = requests.get(URL, params=params, timeout=120)
            r.raise_for_status()
            js = r.json()
            if "error" in js:
                raise RuntimeError(js["error"])
            return js
        except Exception as e:
            print(f"    request failed ({e}); retry {k + 1}/{tries}")
            time.sleep(3 * (k + 1))
    raise SystemExit("The land-use service did not answer. Try again later or check the URL in a browser.")


def download(district, bounds):
    path = CACHE / f"{district}_landuse.geojson"
    if path.exists():
        print(f"  using saved {path.name} (delete it to download again)")
        return json.loads(path.read_text())
    x0, y0, x1, y1 = bounds
    feats, offset = [], 0
    while True:
        js = get_json({"where": "1=1", "geometry": f"{x0},{y0},{x1},{y1}", "geometryType": "esriGeometryEnvelope",
                       "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outSR": 4326,
                       "outFields": f"objectid,{FIELD},year_of_creation,year_of_revision",
                       "returnGeometry": "true", "geometryPrecision": 6, "orderByFields": "objectid",
                       "resultOffset": offset, "resultRecordCount": 1000, "f": "geojson"})
        got = js.get("features", [])
        feats += got
        print(f"    downloaded {len(feats)} polygons", end="\r")
        more = js.get("exceededTransferLimit") or js.get("properties", {}).get("exceededTransferLimit")
        if not got or (len(got) < 1000 and not more):
            break
        offset += len(got)
    print()
    gj = {"type": "FeatureCollection", "features": feats}
    path.write_text(json.dumps(gj))
    return gj


def process(district):
    stack = None
    for p in RASTER_DIR.rglob(f"M3_{district}_FeatureStack*.tif"):
        stack = p if stack is None or p.stat().st_mtime > stack.stat().st_mtime else stack
    if stack is None:
        print(f"{district}: FeatureStack tif not found under {RASTER_DIR}; skipped"); return None
    print(f"\n{district}: grid from {stack.name}")
    with rasterio.open(stack) as s:
        prof = s.profile.copy(); shape = (s.height, s.width); transform = s.transform
        b = s.bounds; bounds = (b.left, b.bottom, b.right, b.top)
    gj = download(district, bounds)
    feats = [f for f in gj["features"] if f.get("geometry") and f["properties"].get(FIELD)]
    if not feats:
        print("  no land-use polygons returned for this district"); return None
    names = pd.Series([f["properties"][FIELD] for f in feats])
    unknown = sorted(set(names) - set(ALL_CLASSES))
    if unknown:
        print("  ! class names not in my list (they stay 'no class'):", unknown)
    yrs = pd.DataFrame([{"creation": f["properties"].get("year_of_creation"), "revision": f["properties"].get("year_of_revision")} for f in feats])
    print("  polygon years (creation):", yrs["creation"].value_counts(dropna=False).head(6).to_dict())
    print("  polygon years (revision):", yrs["revision"].value_counts(dropna=False).head(6).to_dict())

    shapes = [(f["geometry"], CODE[f["properties"][FIELD]]) for f in feats if f["properties"][FIELD] in CODE]
    code = rasterize(shapes, out_shape=shape, transform=transform, fill=0, dtype="uint8", all_touched=False)
    keep_codes = [CODE[k] for k in KEEP if k in CODE]
    cult = np.isin(code, keep_codes).astype("uint8")

    outdir = RASTER_DIR / district; outdir.mkdir(parents=True, exist_ok=True)
    prof.update(count=1, dtype="uint8", nodata=None, compress="lzw")
    for tag, arr in (("Cultivated", cult), ("LandUseCode", code)):
        with rasterio.open(outdir / f"M3_{district}_{tag}.tif", "w", **prof) as d:
            d.write(arr, 1)
    inv = {v: k for k, v in CODE.items()}
    cnt = pd.Series(code[code > 0]).value_counts()
    tab = pd.DataFrame({"class": [inv[c] for c in cnt.index], "pixels": cnt.values})
    tab["share_%"] = (100 * tab["pixels"] / code.size).round(2); tab["kept"] = tab["class"].isin(KEEP)
    print(tab.to_string(index=False))
    print(f"  cultivated share of the raster: {100 * cult.mean():.1f}%   (no polygon at all: {100 * (code == 0).mean():.1f}%)")
    return code, transform, tab.assign(district=district)


if __name__ == "__main__":
    inv = {v: k for k, v in CODE.items()}
    pd.DataFrame({"code": list(CODE.values()), "class": list(CODE.keys())}).to_csv(OUT / "landuse_codes.csv", index=False)
    results = {d: process(d) for d in DISTRICTS}
    rows = [r[2] for r in results.values() if r]
    if rows:
        pd.concat(rows).to_csv(OUT / "landuse_area_by_class.csv", index=False)

    # where do YOUR training points fall in the national land-use map?
    if TABLE.exists():
        df = pd.read_csv(TABLE)
        if {"longitude", "latitude", "crop_type", "district"} <= set(df.columns):
            parts = []
            for d, r in results.items():
                if not r:
                    continue
                code, transform = r[0], r[1]
                sub = df[df["district"] == d]
                rr, cc = rasterio.transform.rowcol(transform, sub["longitude"].values, sub["latitude"].values)
                rr, cc = np.asarray(rr), np.asarray(cc)
                ok = (rr >= 0) & (rr < code.shape[0]) & (cc >= 0) & (cc < code.shape[1])
                v = np.where(ok, code[np.clip(rr, 0, code.shape[0] - 1), np.clip(cc, 0, code.shape[1] - 1)], 0)
                parts.append(pd.DataFrame({"crop_type": sub["crop_type"].values, "landuse": [inv.get(int(x), "no polygon") for x in v]}))
            if parts:
                t = pd.concat(parts, ignore_index=True)
                ct = pd.crosstab(t["crop_type"], t["landuse"], normalize="index").mul(100).round(1)
                ct.to_csv(OUT / "landuse_check.csv")
                kept = t.assign(inside=t["landuse"].isin(KEEP)).groupby("crop_type")["inside"].mean().mul(100).round(1)
                print("\nShare (%) of your training points that fall in a KEPT land-use class (want high, especially Tea and Paddy):")
                print(kept.to_string())
                print("\nFull table saved:", OUT / "landuse_check.csv")
    print("\nNext: python src/m3_final_map.py   (it picks up the Cultivated rasters automatically)")
