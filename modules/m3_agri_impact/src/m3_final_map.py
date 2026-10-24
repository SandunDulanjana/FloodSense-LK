"""
M3 - crop classification MAP (Paddy / Tea / Other) for the trained districts + district areas.

What it does
  1. Trains the FINAL Random Forest on the whole training table (15 base features) and saves it.
  2. Classifies the pre-flood feature stack of each district (GeoTIFF exported from GEE, VIEW step).
  3. Writes: class map GeoTIFF, confidence GeoTIFF, area table (pixels and hectares), PNG map.

Run (from the project folder, e.g. M3_colab):
    python src/m3_final_map.py --check-mask     # step 1: which WorldCover classes hold your polygons?
    python src/m3_final_map.py                  # step 2: train + classify + areas
    python src/m3_final_map.py --skip-train     # re-classify with the saved model

Folders: put the GEE exports (FeatureStack and WorldCover tif files) anywhere under RASTER_DIR.
    export M3_RASTER_DIR=/content/drive/MyDrive/M3_colab/rasters      (Colab: os.environ[...] = ...)
"""
import argparse
import json
import os
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.windows import Window
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------ settings
ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "outputs" / "reference_dataset" / "M3_training_table_all_districts.csv"
RASTER_DIR = Path(os.environ.get("M3_RASTER_DIR", ROOT / "data" / "rasters"))
OUT = ROOT / "outputs" / "results" / "map"; OUT.mkdir(parents=True, exist_ok=True)
MODELS = ROOT / "models"; MODELS.mkdir(parents=True, exist_ok=True)
MODEL_FILE = MODELS / "final_rf_base_map.joblib"

DISTRICTS = ["Ratnapura", "Colombo", "Gampaha"]
SEED = 42
STRIP = 256                       # rows per block (memory friendly)

# Band order of the GEE feature stack. Names are read from the tif when they exist.
BASE = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12",
        "NDVI", "NDWI", "elevation", "slope", "aspect"]

# ESA WorldCover classes where crops can be mapped. 40 = cropland only. Run --check-mask and edit this
# (tea is often NOT labelled cropland in WorldCover). You can also set it with M3_MASK_CLASSES="10,20,30,40".
MASK_CLASSES = [int(v) for v in os.environ.get("M3_MASK_CLASSES", "40").split(",") if v.strip().isdigit()]
USE_WORLDCOVER = os.environ.get("M3_MASK_CLASSES", "40").strip().lower() != "none"   # "none" = rely on NDVI + forest mask only
# Optional NDVI filter. OFF by default (-1). Use it only with the WorldCover mask, not with the national land-use mask.
# Pre-flood NDVI from the FeatureStack. Raise it (0.4) to keep only dense vegetation, lower it (0.2) to keep sparse crops.
NDVI_MIN = float(os.environ.get("M3_NDVI_MIN", "-1"))      # -1 = no NDVI filter (the land-use mask already decides where crops can be)
# ---- rules that use the national land-use map (only active when M3_<District>_LandUseCode.tif exists) ----
# The model may only say "Paddy" where the national map says Paddy, and "Tea" where it says Tea.
# Elsewhere the next most likely class (Other) is used. Set M3_USE_RULES=0 to switch the rules off.
USE_RULES = os.environ.get("M3_USE_RULES", "1") != "0"
PADDY_LU = [v.strip() for v in os.environ.get("M3_PADDY_LU", "Paddy,Paddy-abandoned").split(",") if v.strip()]
TEA_LU = [v.strip() for v in os.environ.get("M3_TEA_LU", "Tea").split(",") if v.strip()]
# Optional "sown in Maha" filter: predicted Paddy pixels with pre-flood NDVI below this value are treated as
# unsown / fallow paddy land and left unmapped. "auto" = 10th percentile of NDVI of your own training Paddy pixels.
# "none" (default) = off. A number such as 0.35 = use that value.
PADDY_NDVI_MIN_SETTING = os.environ.get("M3_PADDY_NDVI_MIN", "none").strip().lower()
WC_NAMES = {10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up",
            60: "Bare / sparse", 70: "Snow/ice", 80: "Water", 90: "Wetland", 95: "Mangroves", 100: "Moss"}

CLASS_NAMES = {1: "Other", 2: "Paddy", 3: "Tea"}      # raster codes (0 = not classified)
CLASS_COLORS = {0: "#ffffff", 1: "#9a9a9a", 2: "#3dbb4a", 3: "#c8553d"}


# ------------------------------------------------------------------ helpers
def find_raster(district, pattern):
    files = [p for p in RASTER_DIR.rglob(pattern.format(d=district)) if "old" not in p.stem.lower()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def row_area_m2(transform, crs, height):
    """Ground area of one pixel for every row. EPSG:4326 exports are NOT exactly 100 m2 per pixel."""
    if crs is not None and crs.is_geographic:
        lat = transform.f + (np.arange(height) + 0.5) * transform.e
        phi = np.radians(lat)
        m_per_deg_lat = 111132.92 - 559.82 * np.cos(2 * phi) + 1.175 * np.cos(4 * phi)
        m_per_deg_lon = 111412.84 * np.cos(phi) - 93.5 * np.cos(3 * phi)
        return abs(transform.a) * m_per_deg_lon * abs(transform.e) * m_per_deg_lat
    return np.full(height, abs(transform.a * transform.e))


def aligned(path, ref):
    """Read a raster resampled (nearest) onto the grid of `ref`."""
    with rasterio.open(path) as s:
        out = np.zeros((ref.height, ref.width), dtype=s.dtypes[0])
        reproject(source=rasterio.band(s, 1), destination=out, src_transform=s.transform,
                  src_crs=s.crs, dst_transform=ref.transform, dst_crs=ref.crs,
                  resampling=Resampling.nearest)
    return out


def band_indexes(src):
    names = [d for d in src.descriptions]
    if all(b in names for b in BASE):
        return [names.index(b) + 1 for b in BASE]
    print("  ! band names not stored in the tif; assuming the standard 15-band order")
    return list(range(1, len(BASE) + 1))


# ------------------------------------------------------------------ 0. which WorldCover classes hold the polygons?
def check_mask():
    df = pd.read_csv(TABLE)
    if not {"longitude", "latitude"} <= set(df.columns):
        raise SystemExit("longitude/latitude columns are missing from the training table.")
    parts = []
    for d in DISTRICTS:
        wc = find_raster(d, "M3_{d}_WorldCover*.tif")
        if wc is None:
            print(f"{d}: no WorldCover tif found under {RASTER_DIR}"); continue
        sub = df[df["district"] == d]
        with rasterio.open(wc) as s:
            vals = np.array([v[0] for v in s.sample(zip(sub["longitude"], sub["latitude"]))])
        parts.append(pd.DataFrame({"district": d, "crop_type": sub["crop_type"].values, "wc": vals}))
    if not parts:
        raise SystemExit("No WorldCover rasters found.")
    t = pd.concat(parts, ignore_index=True)
    t["WorldCover class"] = t["wc"].map(lambda v: f"{int(v)} {WC_NAMES.get(int(v), '?')}")
    ct = pd.crosstab(t["crop_type"], t["WorldCover class"], normalize="index").mul(100).round(1)
    print("\nShare (%) of your training pixels in each WorldCover class:\n")
    print(ct.to_string())
    ct.to_csv(OUT / "worldcover_check.csv")
    fparts = []
    for d in DISTRICTS:
        fm = find_raster(d, "M3_{d}_ForestMask*.tif")
        if fm is None:
            continue
        sub = df[df["district"] == d]
        with rasterio.open(fm) as s_:
            v = np.array([x[0] for x in s_.sample(zip(sub["longitude"], sub["latitude"]))])
        fparts.append(pd.DataFrame({"crop_type": sub["crop_type"].values, "in_forest_mask": v == 1}))
    if fparts:
        f = pd.concat(fparts, ignore_index=True)
        print("\nShare (%) of your training pixels that the FOREST MASK would remove (should be small, especially Tea):\n")
        print(f.groupby("crop_type")["in_forest_mask"].mean().mul(100).round(1).to_string())
    print("\nPut the classes that hold most of Paddy, Tea and Other in MASK_CLASSES (top of this script),"
          "\nfor example MASK_CLASSES = [10, 20, 30, 40]. Saved:", OUT / "worldcover_check.csv")


# ------------------------------------------------------------------ 1. final model
def train_final():
    df = pd.read_csv(TABLE)
    y = df["crop_type"].map({"Other": 0, "Paddy": 1, "Tea": 2}).values
    model = make_pipeline(
        SimpleImputer(strategy="median", keep_empty_features=True),
        RandomForestClassifier(n_estimators=300, min_samples_leaf=3, class_weight="balanced_subsample",
                               n_jobs=-1, random_state=SEED))
    model.fit(df[BASE], y)
    joblib.dump(model, MODEL_FILE, compress=3)
    (MODELS / "final_rf_base_map_meta.json").write_text(json.dumps(
        {"features": BASE, "classes": {"0": "Other", "1": "Paddy", "2": "Tea"},
         "raster_codes": {"1": "Other", "2": "Paddy", "3": "Tea"}, "trained_rows": int(len(df)),
         "trained_fields": int(df["field_id"].nunique())}, indent=2))
    print(f"Final Random Forest trained on {len(df)} pixels / {df['field_id'].nunique()} fields -> {MODEL_FILE.name}")
    return model


def paddy_ndvi_threshold():
    if PADDY_NDVI_MIN_SETTING in ("", "none", "off"):
        return None
    if PADDY_NDVI_MIN_SETTING == "auto":
        t = pd.read_csv(TABLE)
        return float(t.loc[t["crop_type"] == "Paddy", "NDVI"].quantile(0.10))
    return float(PADDY_NDVI_MIN_SETTING)


def landuse_codes(names):
    try:
        from m3_landuse_mask import CODE
    except Exception:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from m3_landuse_mask import CODE
    return [CODE[n] for n in names if n in CODE]


# ------------------------------------------------------------------ 2. classify one district
def classify_district(model, district):
    stack = find_raster(district, "M3_{d}_FeatureStack*.tif")
    if stack is None:
        print(f"{district}: no FeatureStack tif under {RASTER_DIR}; skipped"); return None
    wc_path = find_raster(district, "M3_{d}_WorldCover*.tif")
    print(f"\n{district}: {stack.name}")
    cls_path = OUT / f"{district}_crop_class.tif"
    conf_path = OUT / f"{district}_crop_confidence.tif"

    with rasterio.open(stack) as src:
        idx = band_indexes(src)
        cpath = find_raster(district, "M3_{d}_Cultivated*.tif")
        cult = aligned(cpath, src) if cpath else None
        if cult is not None:
            print("  using the national land-use cultivated mask:", cpath.name, "(WorldCover and forest mask ignored)")
            wc = forest = None
        else:
            wc = aligned(wc_path, src) if (wc_path and USE_WORLDCOVER) else None
            fpath = find_raster(district, "M3_{d}_ForestMask*.tif")
            forest = aligned(fpath, src) if fpath else None
            print("  forest mask:", fpath.name if fpath else "none found (forest will NOT be removed)")
        lu = None
        lupath = find_raster(district, "M3_{d}_LandUseCode*.tif") if (cult is not None and USE_RULES) else None
        if lupath:
            lu = aligned(lupath, src)
            print("  class rules ON: Paddy only in", PADDY_LU, "| Tea only in", TEA_LU)
        paddy_codes, tea_codes = (landuse_codes(PADDY_LU), landuse_codes(TEA_LU)) if lu is not None else ([], [])
        pad_min = paddy_ndvi_threshold()
        if pad_min is not None:
            print(f"  sown-paddy filter ON: Paddy pixels with NDVI < {pad_min:.3f} are left unmapped")
        unsown_px = 0
        if wc is None and cult is None:
            print("  ! no WorldCover raster: the WHOLE district will be classified (forest, towns, water too)")
        prof = src.profile.copy()
        prof.update(count=1, dtype="uint8", nodata=0, compress="lzw", tiled=True,
                    blockxsize=256, blockysize=256, BIGTIFF="IF_SAFER")
        areas_row = row_area_m2(src.transform, src.crs, src.height)
        i_b3, i_b4, i_b8 = BASE.index("B3"), BASE.index("B4"), BASE.index("B8")
        i_ndvi = BASE.index("NDVI")
        px = {1: 0, 2: 0, 3: 0}; m2 = {1: 0.0, 2: 0.0, 3: 0.0}
        n_inmask = n_unmapped = 0

        with rasterio.open(cls_path, "w", **prof) as dc, rasterio.open(conf_path, "w", **prof) as df_:
            for r0 in range(0, src.height, STRIP):
                h = min(STRIP, src.height - r0)
                win = Window(0, r0, src.width, h)
                arr = src.read(idx, window=win).astype("float32")
                ok = np.isfinite(arr).all(0) & (arr > -9000).all(0)
                ok &= ~((arr[i_b3] == 0) & (arr[i_b4] == 0) & (arr[i_b8] == 0))   # exported 'masked' pixels
                if cult is not None:
                    inmask = cult[r0:r0 + h] == 1
                else:
                    inmask = np.isin(wc[r0:r0 + h], MASK_CLASSES) if wc is not None else np.ones((h, src.width), bool)
                veg = arr[i_ndvi] >= NDVI_MIN
                sel = ok & inmask & veg
                if forest is not None:
                    sel &= forest[r0:r0 + h] != 1
                n_inmask += int(inmask.sum()); n_unmapped += int((inmask & ~ok).sum())
                cls = np.zeros((h, src.width), np.uint8); conf = np.zeros((h, src.width), np.uint8)
                if sel.any():
                    X = pd.DataFrame(arr[:, sel].T, columns=BASE)
                    p = model.predict_proba(X)
                    if lu is not None:
                        lus = lu[r0:r0 + h][sel]
                        p = p.copy()
                        p[~np.isin(lus, paddy_codes), 1] = 0.0
                        p[~np.isin(lus, tea_codes), 2] = 0.0
                        tot = p.sum(1, keepdims=True); tot[tot == 0] = 1.0
                        p = p / tot
                    c_sel = p.argmax(1).astype(np.uint8) + 1
                    cf_sel = np.round(p.max(1) * 100).astype(np.uint8)
                    if pad_min is not None:
                        unsown = (c_sel == 2) & (arr[i_ndvi][sel] < pad_min)
                        unsown_px += int(unsown.sum())
                        c_sel[unsown] = 0; cf_sel[unsown] = 0
                    cls[sel] = c_sel
                    conf[sel] = cf_sel
                dc.write(cls, 1, window=win); df_.write(conf, 1, window=win)
                for c in (1, 2, 3):
                    rows = (cls == c).sum(1)
                    px[c] += int(rows.sum()); m2[c] += float((rows * areas_row[r0:r0 + h]).sum())
            mean_px_m2 = float(areas_row.mean())

    mapped = sum(px.values())
    rows = []
    for c in (1, 2, 3):
        rows.append({"district": district, "class": CLASS_NAMES[c], "pixels": px[c],
                     "area_ha": round(m2[c] / 10000, 1), "area_ha_if_100m2_per_pixel": round(px[c] * 0.01, 1),
                     "share_of_mapped_pct": round(100 * px[c] / mapped, 2) if mapped else np.nan,
                     "mapped_pixels_total": mapped, "unmapped_pixels_in_mask_(cloud/no data)": n_unmapped,
                     "mean_pixel_area_m2": round(mean_px_m2, 2),
                     "ndvi_min": NDVI_MIN, "class_rules": bool(lu is not None), "paddy_unsown_pixels_left_unmapped": unsown_px, "mask_classes": ",".join(map(str, MASK_CLASSES)) if wc is not None else "none"})
    print(pd.DataFrame(rows)[["class", "pixels", "area_ha", "share_of_mapped_pct"]].to_string(index=False))
    print(f"  pixels in mask without data: {n_unmapped} ({100 * n_unmapped / max(n_inmask, 1):.2f}% of the mask)")
    draw_map(cls_path, district, {CLASS_NAMES[c]: m2[c] / 10000 for c in (1, 2, 3)})
    return rows


def draw_map(cls_path, district, areas):
    with rasterio.open(cls_path) as s:
        scale = max(1, int(np.ceil(max(s.width, s.height) / 2200)))
        a = s.read(1, out_shape=(s.height // scale, s.width // scale), resampling=Resampling.nearest)
        ext = [s.bounds.left, s.bounds.right, s.bounds.bottom, s.bounds.top]
    fig, ax = plt.subplots(figsize=(8, 8 * a.shape[0] / a.shape[1] + 0.8))
    ax.imshow(a, cmap=ListedColormap([CLASS_COLORS[i] for i in range(4)]), vmin=0, vmax=3,
              extent=ext, interpolation="nearest")
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    ax.set_title(f"{district}: pre-flood crop classification (Random Forest, Sentinel-2, 10 m)")
    ax.legend(handles=[Patch(color=CLASS_COLORS[c], label=f"{CLASS_NAMES[c]}: {areas[CLASS_NAMES[c]]:,.0f} ha")
                       for c in (2, 3, 1)] + [Patch(facecolor="white", edgecolor="black", label="not classified")],
              loc="lower left", fontsize=8)
    plt.tight_layout(); plt.savefig(OUT / f"{district}_crop_class_map.png", dpi=180); plt.close()


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-mask", action="store_true", help="show which WorldCover classes hold the training pixels")
    ap.add_argument("--skip-train", action="store_true", help="use the saved final model")
    args = ap.parse_args()
    if args.check_mask:
        check_mask(); raise SystemExit
    model = joblib.load(MODEL_FILE) if args.skip_train and MODEL_FILE.exists() else train_final()
    all_rows = []
    for d in DISTRICTS:
        r = classify_district(model, d)
        if r:
            all_rows += r
    if all_rows:
        pd.DataFrame(all_rows).to_csv(OUT / "area_by_district.csv", index=False)
        print("\nSaved", OUT / "area_by_district.csv")
