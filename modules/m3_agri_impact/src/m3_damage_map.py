"""
M3 - crop-specific flood DAMAGE map (Cyclone Ditwah 2025) from pre/post NDVI change.

Inputs per district (all from GEE, same grid):
  outputs/results/map/<District>_crop_class.tif      crop map  (m3_final_map.py)
  M3_<District>_FeatureStack*.tif                    pre-flood composite (bands incl. NDVI, NDWI)
  M3_<District>_PostFlood*.tif                       NDVI_post, NDWI_post, post_fill  (gee_postflood_export.js)
  M3_<District>_S1Flood*.tif                         optional Sentinel-1 flood layer

Method (no hand-picked threshold)
  change      = NDVI_post - NDVI_pre
  baseline    = the typical change of the SAME crop in pixels not flagged as flooded (median, robust sigma)
  anomaly     = change - baseline        (removes the normal seasonal change, e.g. Maha paddy growing)
  severity    = anomaly below -2 / -3 / -4 robust sigma  (low / moderate / severe), with a minimum NDVI drop
  Results are then compared with the Department of Agriculture damaged-paddy hectares.

Run:  python src/m3_damage_map.py
"""
import os
import warnings
from pathlib import Path
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

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------ settings
ROOT = Path(__file__).resolve().parents[1]
RASTER_DIR = Path(os.environ.get("M3_RASTER_DIR", ROOT / "data" / "rasters"))
MAPDIR = ROOT / "outputs" / "results" / "map"
OUT = ROOT / "outputs" / "results" / "damage"; OUT.mkdir(parents=True, exist_ok=True)
REF_DAMAGE = ROOT / "data" / "reference" / "damage_reference_DoA.csv"

DISTRICTS = ["Ratnapura", "Colombo", "Gampaha"]
BASE = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12",
        "NDVI", "NDWI", "elevation", "slope", "aspect"]
CLASS_NAMES = {1: "Other", 2: "Paddy", 3: "Tea"}

K = {1: 2.0, 2: 3.0, 3: 4.0}              # severity cut-offs in robust sigma units
FLOOR = {1: 0.10, 2: 0.20, 3: 0.30}       # minimum NDVI drop (after baseline removal) for each level
MIN_CONTROL = 500                         # fewer control pixels than this -> use all valid pixels of the class
TARGET = 0.80

SEV_COLORS = ["#dcdcdc", "#f6e05e", "#ed8936", "#9b1c1c"]       # none, low, moderate, severe
SEV_NAMES = ["No / minor change", "Low", "Moderate", "Severe"]


# ------------------------------------------------------------------ helpers
def find(district, pattern):
    files = [p for p in RASTER_DIR.rglob(pattern.format(d=district)) if "old" not in p.stem.lower()]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def row_area_m2(transform, crs, height):
    if crs is not None and crs.is_geographic:
        lat = transform.f + (np.arange(height) + 0.5) * transform.e
        phi = np.radians(lat)
        mlat = 111132.92 - 559.82 * np.cos(2 * phi) + 1.175 * np.cos(4 * phi)
        mlon = 111412.84 * np.cos(phi) - 93.5 * np.cos(3 * phi)
        return abs(transform.a) * mlon * abs(transform.e) * mlat
    return np.full(height, abs(transform.a * transform.e))


def read_band(path, ref, band, resampling=Resampling.nearest, dtype="float32"):
    with rasterio.open(path) as s:
        out = np.zeros((ref.height, ref.width), dtype=dtype)
        reproject(source=rasterio.band(s, band), destination=out, src_transform=s.transform,
                  src_crs=s.crs, dst_transform=ref.transform, dst_crs=ref.crs, resampling=resampling)
    return out


def band_no(path, name, default):
    with rasterio.open(path) as s:
        d = list(s.descriptions)
    return d.index(name) + 1 if name in d else default


def area_ha(mask, areas_row):
    return float((mask.sum(1) * areas_row).sum() / 10000.0)


def robust(x):
    med = float(np.median(x)); mad = float(np.median(np.abs(x - med)))
    return med, 1.4826 * mad


def severity_from(anom, sigma):
    sev = np.zeros(anom.shape, np.uint8)
    for lvl in (1, 2, 3):
        sev[anom <= -max(K[lvl] * sigma, FLOOR[lvl])] = lvl
    return sev


# ------------------------------------------------------------------ one district
def run_district(district):
    cls_p = MAPDIR / f"{district}_crop_class.tif"
    pre_p, post_p = find(district, "M3_{d}_FeatureStack*.tif"), find(district, "M3_{d}_PostFlood*.tif")
    fl_p = find(district, "M3_{d}_S1Flood*.tif")
    if not (cls_p.exists() and pre_p and post_p):
        print(f"{district}: need class map, FeatureStack and PostFlood rasters; skipped"); return None, None
    print(f"\n{district}\n  pre : {pre_p.name}\n  post: {post_p.name}\n  S1  : {fl_p.name if fl_p else 'not used'}")

    with rasterio.open(cls_p) as c:
        ref = c; cls = c.read(1); transform, crs = c.transform, c.crs
        prof = c.profile.copy()
    areas_row = row_area_m2(transform, crs, cls.shape[0])
    pre = read_band(pre_p, ref, band_no(pre_p, "NDVI", BASE.index("NDVI") + 1), Resampling.bilinear)
    ndwi_pre = read_band(pre_p, ref, band_no(pre_p, "NDWI", BASE.index("NDWI") + 1), Resampling.bilinear)
    post = read_band(post_p, ref, band_no(post_p, "NDVI_post", 1), Resampling.bilinear)
    ndwi_post = read_band(post_p, ref, band_no(post_p, "NDWI_post", 2), Resampling.bilinear)
    flood = read_band(fl_p, ref, 1, Resampling.nearest, "uint8") if fl_p else None

    valid = (cls > 0) & np.isfinite(pre) & np.isfinite(post) & (post > -9000) & (pre > -1) & (pre < 1) & (post < 1)
    d_ndvi = np.where(valid, post - pre, np.nan).astype("float32")
    d_ndwi = np.where(valid, ndwi_post - ndwi_pre, np.nan).astype("float32")
    print(f"  usable pixels (crop map & both dates clear): {int(valid.sum()):,} of {int((cls > 0).sum()):,} mapped")

    sev = np.full(cls.shape, 255, np.uint8)
    rows, base_info = [], {}
    for c in (1, 2, 3):
        in_c = valid & (cls == c)
        if in_c.sum() == 0:
            continue
        ctrl = in_c & (flood == 0) if flood is not None else in_c
        if ctrl.sum() < MIN_CONTROL:
            ctrl = in_c
        med, sigma = robust(d_ndvi[ctrl])
        base_info[c] = (med, sigma, d_ndvi[in_c] - med)
        anom = d_ndvi - med
        s = severity_from(np.where(in_c, anom, 0), sigma)
        sev[in_c] = s[in_c]
        tot = area_ha(cls == c, areas_row)
        low, mod, sevr = (area_ha(in_c & (s == l), areas_row) for l in (1, 2, 3))
        dam = low + mod + sevr
        dam_fl = area_ha(in_c & (s > 0) & (flood == 1), areas_row) if flood is not None else np.nan
        rows.append({"district": district, "crop": CLASS_NAMES[c], "mapped_ha": round(tot, 1),
                     "assessed_ha": round(area_ha(in_c, areas_row), 1),
                     "low_ha": round(low, 1), "moderate_ha": round(mod, 1), "severe_ha": round(sevr, 1),
                     "damaged_ha": round(dam, 1),
                     "damage_pct_of_assessed": round(100 * dam / max(area_ha(in_c, areas_row), 1e-9), 2),
                     "damaged_and_S1_flooded_ha": round(dam_fl, 1) if flood is not None else np.nan,
                     "S1_flooded_ha": round(area_ha(in_c & (flood == 1), areas_row), 1) if flood is not None else np.nan,
                     "baseline_change_median": round(med, 3), "baseline_sigma": round(sigma, 3),
                     "mean_dNDVI": round(float(np.nanmean(d_ndvi[in_c])), 3),
                     "mean_dNDWI": round(float(np.nanmean(d_ndwi[in_c])), 3)})
    tbl = pd.DataFrame(rows)
    print(tbl[["crop", "assessed_ha", "damaged_ha", "damage_pct_of_assessed", "baseline_change_median"]]
          .to_string(index=False))

    # severity raster
    prof.update(dtype="uint8", nodata=255, compress="lzw", count=1)
    with rasterio.open(OUT / f"{district}_damage_severity.tif", "w", **prof) as dst:
        dst.write(sev, 1)

    # sensitivity: paddy damaged hectares for other settings
    sens = []
    if 2 in base_info:
        med, sigma, _ = base_info[2]
        in_p = valid & (cls == 2); anom = np.where(in_p, d_ndvi - med, 0)
        for kk in (1.5, 2, 3):
            for fl in (0.05, 0.10, 0.15, 0.20):
                m = in_p & (anom <= -max(kk * sigma, fl))
                sens.append({"district": district, "k_sigma": kk, "min_drop": fl, "paddy_damaged_ha": round(area_ha(m, areas_row), 1)})
    draw(district, cls, sev, d_ndvi, flood)
    return tbl, pd.DataFrame(sens)


def draw(district, cls, sev, d_ndvi, flood):
    s = max(1, int(np.ceil(max(cls.shape) / 1800)))
    cls_s, sev_s = cls[::s, ::s], sev[::s, ::s]
    panels = [("Pre-flood crop map", None),
              ("Paddy: flood damage", 2), ("Tea: flood damage", 3)]
    fig, axes = plt.subplots(1, 3, figsize=(17, 6.4 * cls.shape[0] / cls.shape[1] + 1.2))
    cm_cls = ListedColormap(["#ffffff", "#9a9a9a", "#2a9d8f", "#c8553d"])
    for ax, (title, crop) in zip(axes, panels):
        if crop is None:
            ax.imshow(cls_s, cmap=cm_cls, vmin=0, vmax=3, interpolation="nearest")
            ax.legend(handles=[Patch(color="#2a9d8f", label="Paddy"), Patch(color="#c8553d", label="Tea"),
                               Patch(color="#9a9a9a", label="Other")], loc="lower left", fontsize=8)
        else:
            img = np.full(cls_s.shape, -1, int)                       # -1 = not this crop (white)
            sel = (cls_s == crop) & (sev_s != 255)
            img[sel] = sev_s[sel]
            ax.imshow(np.where(img < 0, np.nan, img), cmap=ListedColormap(SEV_COLORS), vmin=0, vmax=3,
                      interpolation="nearest")
            ax.set_facecolor("white")
            ax.legend(handles=[Patch(color=SEV_COLORS[i], label=SEV_NAMES[i]) for i in range(4)],
                      loc="lower left", fontsize=8)
        ax.set_title(f"{district}: {title}"); ax.set_xticks([]); ax.set_yticks([])
    plt.tight_layout(); plt.savefig(OUT / f"{district}_damage_maps.png", dpi=170); plt.close()


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    tables, sens = [], []
    for d in DISTRICTS:
        t, s = run_district(d)
        if t is not None:
            tables.append(t); sens.append(s)
    if not tables:
        raise SystemExit("Nothing processed. Check RASTER_DIR and that m3_final_map.py has run.")
    res = pd.concat(tables); res.to_csv(OUT / "crop_damage_by_district.csv", index=False)
    pd.concat(sens).to_csv(OUT / "paddy_damage_sensitivity.csv", index=False)
    print("\nSaved", OUT / "crop_damage_by_district.csv")

    if not REF_DAMAGE.exists():            # values read from the DoA/FAO flood-affected crop map (as of 17/12/2025)
        REF_DAMAGE.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"district": ["Gampaha", "Colombo", "Ratnapura"], "paddy_damaged_ha_ref": [2150, 727, 419],
                      "source": ["Dept. of Agriculture, flood affected crop area map, as of 17/12/2025 (check)"] * 3}
                     ).to_csv(REF_DAMAGE, index=False)
        print("Created", REF_DAMAGE, "- check the numbers against the original map.")
    ref = pd.read_csv(REF_DAMAGE)
    pad = res[res["crop"] == "Paddy"][["district", "damaged_ha"]].merge(ref, on="district")
    pad["agreement_pct"] = (100 * (1 - (pad["damaged_ha"] - pad["paddy_damaged_ha_ref"]).abs()
                                   / pad["paddy_damaged_ha_ref"]).clip(lower=0)).round(1)
    pad["meets_80pct"] = pad["agreement_pct"] >= 100 * TARGET
    pad.to_csv(OUT / "damage_validation_paddy.csv", index=False)
    print("\nPaddy damage vs Department of Agriculture:\n", pad.to_string(index=False))

    fig, ax = plt.subplots(figsize=(6.5, 4.2)); x = np.arange(len(pad))
    ax.bar(x - 0.2, pad["paddy_damaged_ha_ref"], 0.4, label="Dept. of Agriculture (17/12/2025)", color="#e9a03b")
    ax.bar(x + 0.2, pad["damaged_ha"], 0.4, label="M3 NDVI-change estimate", color="#4c6a92")
    ax.set_xticks(x); ax.set_xticklabels(pad["district"]); ax.set_ylabel("Damaged paddy (ha)"); ax.legend(fontsize=8)
    ax.set_title("Paddy flood damage: M3 vs official"); plt.tight_layout()
    plt.savefig(OUT / "damage_validation_paddy.png", dpi=200); plt.close()
