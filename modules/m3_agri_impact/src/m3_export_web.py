"""
M3 - turn your result files into the data folder used by the web app (web/index.html).

Reads (all made by the earlier scripts):
  outputs/results/map/<District>_crop_class.tif            crop classes (0 none, 1 Other, 2 Paddy, 3 Tea)
  outputs/results/damage/<District>_damage_severity.tif    damage (0 none, 1 low, 2 moderate, 3 severe, 255 nodata)
  rasters/**/M3_<District>_S1Flood.tif                     Sentinel-1 flood-like pixels (optional)
  SriLanka_districts.geojson                               district boundaries
  the CSV files and PNG plots in outputs/results/**        areas, validation, model metrics, XAI

Writes web/data/ :
  tiles/<layer>/<District>/{z}/{x}/{y}.png   map tiles (zoomable, like a normal web map)
  summary.json                               every table the web app shows
  districts.geojson, img/...                 boundaries and plots

Run (Colab or PC):   python src/m3_export_web.py
Options (environment variables): M3_RASTER_DIR, M3_WEB_DIR, M3_ZMIN (default 8), M3_ZMAX (default 13)
"""
import json
import math
import os
import shutil
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import from_bounds as win_from_bounds, Window

ROOT = Path(__file__).resolve().parents[1]
RASTER_DIR = Path(os.environ.get("M3_RASTER_DIR", ROOT / "data" / "rasters"))
RES = ROOT / "outputs" / "results"
WEB = Path(os.environ.get("M3_WEB_DIR", ROOT / "web" / "data"))
ZMIN, ZMAX = int(os.environ.get("M3_ZMIN", 8)), int(os.environ.get("M3_ZMAX", 13))
DISTRICTS = ["Ratnapura", "Colombo", "Gampaha"]
CROPS = {1: "Other", 2: "Paddy", 3: "Tea"}

CROP_COL = {2: (61, 187, 74), 3: (200, 85, 61), 1: (233, 196, 106)}            # Paddy (green), Tea, Other
DMG_COL = {1: (216, 180, 254), 2: (147, 51, 234), 3: (88, 28, 135)}             # low, moderate, severe (violet, so damage never looks like a crop colour)
FLOOD_COL = {1: (30, 144, 255)}
R_EARTH = 6378137.0
ORIGIN = math.pi * R_EARTH


# ------------------------------------------------------------------ tile maths (Web Mercator, XYZ)
def tile_bounds_m(z, x, y):
    size = 2 * ORIGIN / (2 ** z)
    return (-ORIGIN + x * size, ORIGIN - (y + 1) * size, -ORIGIN + (x + 1) * size, ORIGIN - y * size)


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat = max(min(lat, 85.0511), -85.0511)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def make_tiles(path, colors, out_dir, name):
    """Cut one class raster into XYZ PNG tiles. `colors` = {pixel value: (r,g,b)}; other values are transparent."""
    with rasterio.open(path) as ds:
        w, s, e, n = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds)
        src_res_m = abs(ds.transform.a) * 111320.0 * math.cos(math.radians((s + n) / 2))
        total = 0
        for z in range(ZMIN, ZMAX + 1):
            x0, y1 = lonlat_to_tile(w, s, z)
            x1, y0 = lonlat_to_tile(e, n, z)
            tile_m = 2 * ORIGIN / (2 ** z) / 256 * math.cos(math.radians((s + n) / 2))     # metres per tile pixel on the ground
            decim = max(1, int(tile_m / src_res_m / 2))
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    mb = tile_bounds_m(z, x, y)
                    lw, ls, le, ln = transform_bounds("EPSG:3857", ds.crs, *mb)
                    win = win_from_bounds(lw, ls, le, ln, ds.transform)
                    pad = 2 * decim
                    c0, r0 = int(math.floor(win.col_off)) - pad, int(math.floor(win.row_off)) - pad
                    c1, r1 = int(math.ceil(win.col_off + win.width)) + pad, int(math.ceil(win.row_off + win.height)) + pad
                    c0, r0, c1, r1 = max(c0, 0), max(r0, 0), min(c1, ds.width), min(r1, ds.height)
                    if c1 <= c0 or r1 <= r0:
                        continue
                    win = Window(c0, r0, c1 - c0, r1 - r0)
                    if decim > 1:
                        shape = (max(1, win.height // decim), max(1, win.width // decim))
                        arr = ds.read(1, window=win, out_shape=shape, resampling=Resampling.nearest)
                    else:
                        arr = ds.read(1, window=win)
                    if not np.isin(arr, list(colors)).any():
                        continue
                    t = ds.window_transform(win)
                    t = rasterio.Affine(t.a * win.width / arr.shape[1], t.b, t.c, t.d, t.e * win.height / arr.shape[0], t.f)
                    dst_t = from_bounds(*mb, 256, 256)
                    rgba = np.zeros((256, 256, 4), np.uint8)
                    if z < ZMAX - 1:                                # smooth: share of each class inside the tile pixel
                        share = {}
                        for v in colors:
                            d = np.zeros((256, 256), np.float32)
                            reproject((arr == v).astype(np.float32), d, src_transform=t, src_crs=ds.crs,
                                      dst_transform=dst_t, dst_crs="EPSG:3857", resampling=Resampling.average)
                            share[v] = d
                        stack = np.stack([share[v] for v in colors])
                        best = stack.argmax(0)
                        keep = stack.sum(0) >= 0.2
                        vals = np.array(list(colors))
                        picked = vals[best]
                    else:
                        d = np.zeros((256, 256), arr.dtype)
                        reproject(arr, d, src_transform=t, src_crs=ds.crs, dst_transform=dst_t, dst_crs="EPSG:3857",
                                  resampling=Resampling.nearest)
                        picked, keep = d, np.isin(d, list(colors))
                    for v, col in colors.items():
                        m = keep & (picked == v)
                        rgba[m] = (*col, 225)
                    if rgba[..., 3].max() == 0:
                        continue
                    f = out_dir / str(z) / str(x) / f"{y}.png"
                    f.parent.mkdir(parents=True, exist_ok=True)
                    Image.fromarray(rgba, "RGBA").save(f, optimize=True)
                    total += 1
    print(f"    {name}: {total} tiles")
    return [round(w, 5), round(s, 5), round(e, 5), round(n, 5)]


# ------------------------------------------------------------------ helpers
def find(pattern, base=None):
    files = list((base or RASTER_DIR).rglob(pattern))
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def csv_rows(path):
    if path and Path(path).exists():
        df = pd.read_csv(path)
        return json.loads(df.to_json(orient="records"))
    return []


def polys_of(g):
    if not g:
        return []
    t = g.get("type")
    if t == "Polygon":
        return [g["coordinates"]]
    if t == "MultiPolygon":
        return list(g["coordinates"])
    if t == "GeometryCollection":
        return [p for sub in g.get("geometries", []) for p in polys_of(sub)]
    return []


def export_boundaries():
    f = find("SriLanka_districts*.geojson") or find("SriLanka_districts*.geojson", ROOT)
    if not f:
        print("  ! SriLanka_districts.geojson not found: boundaries skipped")
        return None
    gj = json.loads(f.read_text())
    feats = []
    for ft in gj["features"]:
        name = ft["properties"].get("ADM2_NAME")
        polys = polys_of(ft.get("geometry"))
        if name and polys:
            feats.append({"type": "Feature", "properties": {"name": name, "studied": name in DISTRICTS},
                          "geometry": {"type": "MultiPolygon", "coordinates": polys}})
    (WEB / "districts.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    return {ft["properties"]["name"]: ft for ft in feats}


def copy_images():
    """Copy every PNG plot that the earlier scripts made, grouped for the XAI / evaluation tabs."""
    groups = {"xai": RES / "extra_xai", "evaluation": RES / "extra_eval", "model": RES, "map": RES / "map", "damage": RES / "damage"}
    out = []
    for cat, folder in groups.items():
        if not folder.exists():
            continue
        pngs = sorted(folder.glob("*.png")) if cat in ("model", "map", "damage") else sorted(folder.rglob("*.png"))
        for p in pngs:
            if cat == "map" and ("crop_class_map" in p.name or "SriLanka" in p.name):
                pass
            dst = WEB / "img" / cat / p.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            title = p.stem.replace("_", " ").strip().capitalize()
            out.append({"category": cat, "title": title, "file": f"img/{cat}/{p.name}"})
    return out


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    if WEB.exists():
        for sub in ("tiles", "img"):
            shutil.rmtree(WEB / sub, ignore_errors=True)
    WEB.mkdir(parents=True, exist_ok=True)
    print("Writing to", WEB)
    bounds_ft = export_boundaries()

    layers = {
        "crop": {"name": "Crop classes (Paddy / Tea / Other)", "group": "Pre-flood crop map", "on": True,
                 "legend": [["Paddy", "#3dbb4a"], ["Tea", "#c8553d"], ["Other crops", "#e9c46a"]], "districts": {}},
        "dmg_all": {"name": "Flood damage, all crops", "group": "Flood damage (NDVI change)", "on": False,
                    "legend": [["Low", "#d8b4fe"], ["Moderate", "#9333ea"], ["Severe", "#581c87"]], "districts": {}},
        "dmg_paddy": {"name": "Flood damage, Paddy", "group": "Flood damage (NDVI change)", "on": False,
                      "legend": [["Low", "#d8b4fe"], ["Moderate", "#9333ea"], ["Severe", "#581c87"]], "districts": {}},
        "dmg_tea": {"name": "Flood damage, Tea", "group": "Flood damage (NDVI change)", "on": False,
                    "legend": [["Low", "#d8b4fe"], ["Moderate", "#9333ea"], ["Severe", "#581c87"]], "districts": {}},
        "flood": {"name": "Sentinel-1 flood-like pixels", "group": "Flood extent", "on": False,
                  "legend": [["Flood-like (radar)", "#1e90ff"]], "districts": {}},
    }
    tmp = Path(tempfile.mkdtemp())
    for d in DISTRICTS:
        print(f"\n{d}")
        cls_p = RES / "map" / f"{d}_crop_class.tif"
        dmg_p = RES / "damage" / f"{d}_damage_severity.tif"
        fl_p = find(f"M3_{d}_S1Flood*.tif")
        if cls_p.exists():
            layers["crop"]["districts"][d] = make_tiles(cls_p, CROP_COL, WEB / "tiles" / "crop" / d, "crop")
        if cls_p.exists() and dmg_p.exists():
            with rasterio.open(cls_p) as a, rasterio.open(dmg_p) as b:
                if (a.width, a.height) != (b.width, b.height):
                    print("  ! class and damage rasters differ in size; damage layers skipped")
                else:
                    cls, dmg, prof = a.read(1), b.read(1), b.profile.copy()
                    prof.update(count=1, dtype="uint8", nodata=None, compress="lzw")
                    for key, code in (("dmg_all", None), ("dmg_paddy", 2), ("dmg_tea", 3)):
                        arr = np.where(dmg > 3, 0, dmg).astype(np.uint8)
                        if code is not None:
                            arr = np.where(cls == code, arr, 0).astype(np.uint8)
                        if code == 3 and not (arr > 0).any():
                            continue
                        tp = tmp / f"{key}_{d}.tif"
                        with rasterio.open(tp, "w", **prof) as o:
                            o.write(arr, 1)
                        layers[key]["districts"][d] = make_tiles(tp, DMG_COL, WEB / "tiles" / key / d, key)
        if fl_p:
            layers["flood"]["districts"][d] = make_tiles(fl_p, FLOOD_COL, WEB / "tiles" / "flood" / d, "flood")
    shutil.rmtree(tmp, ignore_errors=True)

    layer_list = []
    for key, L in layers.items():
        if L["districts"]:
            layer_list.append({"id": key, "name": L["name"], "group": L["group"], "on": L["on"], "legend": L["legend"],
                               "districts": L["districts"], "path": f"tiles/{key}", "minZoom": ZMIN, "maxNativeZoom": ZMAX})

    all_bounds = [b for L in layer_list for b in L["districts"].values()]
    view = None
    if all_bounds:
        view = [min(b[0] for b in all_bounds), min(b[1] for b in all_bounds), max(b[2] for b in all_bounds), max(b[3] for b in all_bounds)]

    summary = {
        "generated": str(date.today()),
        "districts": DISTRICTS,
        "view": view,
        "layers": layer_list,
        "areas": csv_rows(RES / "map" / "area_by_district.csv"),
        "area_validation": csv_rows(RES / "map" / "area_validation.csv"),
        "landuse_check": csv_rows(RES / "map" / "landuse_check.csv"),
        "damage": csv_rows(RES / "damage" / "crop_damage_by_district.csv"),
        "damage_validation": csv_rows(RES / "damage" / "damage_validation_paddy.csv"),
        "damage_sensitivity": csv_rows(RES / "damage" / "paddy_damage_sensitivity.csv"),
        "model_comparison": csv_rows(RES / "model_comparison.csv"),
        "per_class_metrics": csv_rows(RES / "per_class_metrics.csv"),
        "images": copy_images(),
    }
    (WEB / "summary.json").write_text(json.dumps(summary, indent=1))
    print("\nSaved", WEB / "summary.json")
    print("Layers:", [l["id"] for l in layer_list], "| images:", len(summary["images"]))
    print("Open the site:  cd web  &&  python -m http.server 8000   then visit http://localhost:8000")
