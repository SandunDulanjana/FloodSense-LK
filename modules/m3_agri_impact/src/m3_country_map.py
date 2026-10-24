"""
M3 - one presentation map: crop classes (Paddy / Tea / Other) for Ratnapura, Colombo and Gampaha
drawn on a Sri Lanka map with district boundaries. Forest, towns, water and roads are NOT coloured
(they were removed by the land-cover mask in m3_final_map.py).

Needs
  outputs/results/map/<District>_crop_class.tif     (from m3_final_map.py)
  SriLanka_districts.geojson                        (district boundaries from GEE, see below)
  outputs/results/map/area_by_district.csv          (optional, adds hectares to the legend)

Get the boundaries once in the GEE Code Editor, then run the task and download the file:
    var d = ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level2')
              .filter(ee.Filter.eq('ADM0_NAME', 'Sri Lanka'));
    Export.table.toDrive({collection: d.select(['ADM2_NAME']), description: 'SriLanka_districts',
                          folder: 'M3_GEE_exports', fileNamePrefix: 'SriLanka_districts', fileFormat: 'GeoJSON'});
Put SriLanka_districts.geojson anywhere under the rasters folder (M3_RASTER_DIR).

Run:  python src/m3_country_map.py
"""
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_bounds

ROOT = Path(__file__).resolve().parents[1]
RASTER_DIR = Path(os.environ.get("M3_RASTER_DIR", ROOT / "data" / "rasters"))
MAPDIR = ROOT / "outputs" / "results" / "map"
TARGETS = ["Ratnapura", "Colombo", "Gampaha"]
COLORS = {2: "#3dbb4a", 3: "#c8553d", 1: "#e9c46a"}          # Paddy, Tea, Other
NAMES = {2: "Paddy", 3: "Tea", 1: "Other crops / vegetation"}


# ------------------------------------------------------------------ boundaries (plain GeoJSON, no extra packages)
def load_boundaries():
    files = list(RASTER_DIR.rglob("SriLanka_districts*.geojson")) + list(ROOT.rglob("SriLanka_districts*.geojson"))
    if not files:
        raise SystemExit("SriLanka_districts.geojson not found. See the top of this script for the GEE export.")
    gj = json.loads(files[0].read_text())
    out = {}

    def polys_of(g):                       # Polygon / MultiPolygon / GeometryCollection -> list of polygons
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

    for f in gj["features"]:
        name = f["properties"].get("ADM2_NAME")
        polys = polys_of(f.get("geometry"))
        if name and polys:
            out.setdefault(name, []).extend(polys)      # list of polygons; polygon = [outer_ring, hole, ...]
    return out


def draw_outline(ax, polys, **kw):
    for poly in polys:
        for ring in poly:
            a = np.asarray(ring)
            ax.plot(a[:, 0], a[:, 1], **kw)


def fill_district(ax, polys):
    for poly in polys:                      # light grey = inside the district but not mapped
        a = np.asarray(poly[0]); ax.fill(a[:, 0], a[:, 1], color="#ececec", zorder=2, lw=0)


def centroid(polys):
    big = max(polys, key=lambda p: len(p[0]))
    a = np.asarray(big[0])
    return a[:, 0].mean(), a[:, 1].mean()


# ------------------------------------------------------------------ rasters
def read_classes(path, polys, stride):
    """Read the class raster, keep only pixels inside the district outline, and shrink it by `stride`
    using the most frequent crop class in each block (so small maps stay readable, not speckled)."""
    with rasterio.open(path) as s:
        arr = s.read(1)
        ext = [s.bounds.left, s.bounds.right, s.bounds.bottom, s.bounds.top]
    shapes = [{"type": "Polygon", "coordinates": p} for p in polys]
    inside = rasterize(shapes, out_shape=arr.shape, transform=from_bounds(ext[0], ext[2], ext[1], ext[3], arr.shape[1], arr.shape[0]),
                       fill=0, default_value=1, all_touched=True).astype(bool)
    arr = np.where(inside, arr, 0).astype(np.uint8)
    if stride > 1:
        pw, ph = (ext[1] - ext[0]) / arr.shape[1], (ext[3] - ext[2]) / arr.shape[0]
        h, w = (arr.shape[0] // stride) * stride, (arr.shape[1] // stride) * stride
        blocks = arr[:h, :w].reshape(h // stride, stride, w // stride, stride).transpose(0, 2, 1, 3).reshape(h // stride, w // stride, -1)
        counts = np.stack([(blocks == c).sum(-1) for c in (1, 2, 3)], -1)
        best = counts.argmax(-1) + 1
        arr = np.where(counts.sum(-1) >= 0.2 * stride * stride, best, 0).astype(np.uint8)
        ext = [ext[0], ext[0] + w * pw, ext[3] - h * ph, ext[3]]
    return arr, ext


def draw_class_raster(ax, path, polys, stride):
    arr, ext = read_classes(path, polys, stride)
    rgba = np.zeros(arr.shape + (4,), float)
    for code, col in COLORS.items():
        rgba[arr == code] = matplotlib.colors.to_rgba(col)
    ax.imshow(rgba, extent=ext, interpolation="nearest", zorder=3)


def scale_bar(ax, km, lat, frac_x=0.05, frac_y=0.04):
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    dx = km / (111.32 * np.cos(np.radians(lat)))
    xs, ys = x0 + frac_x * (x1 - x0), y0 + frac_y * (y1 - y0)
    ax.plot([xs, xs + dx], [ys, ys], color="black", lw=3, zorder=6)
    ax.text(xs + dx / 2, ys + 0.012 * (y1 - y0), f"{km} km", ha="center", fontsize=8, zorder=6)


def north_arrow(ax, fx=0.92, fy=0.12):
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    x, y = x0 + fx * (x1 - x0), y0 + fy * (y1 - y0)
    ax.annotate("N", xy=(x, y + 0.09 * (y1 - y0)), xytext=(x, y), ha="center", fontsize=10, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color="black"), zorder=6)


def bbox(polys_list):
    pts = np.vstack([np.asarray(r) for polys in polys_list for poly in polys for r in poly])
    return pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    bounds = load_boundaries()
    rasters = {d: MAPDIR / f"{d}_crop_class.tif" for d in TARGETS if (MAPDIR / f"{d}_crop_class.tif").exists()}
    if not rasters:
        raise SystemExit("No class maps found. Run m3_final_map.py first.")
    missing = [d for d in rasters if d not in bounds]
    if missing:
        raise SystemExit(f"District names {missing} not found in the boundary file. Names present: {sorted(bounds)}")

    area_txt = {}
    ap = MAPDIR / "area_by_district.csv"
    if ap.exists():
        a = pd.read_csv(ap)
        for d in rasters:
            area_txt[d] = {c: a[(a["district"] == d) & (a["class"] == n)]["area_ha"].sum() for c, n in ((2, "Paddy"), (3, "Tea"), (1, "Other"))}

    gx0, gy0, gx1, gy1 = bbox(bounds.values())          # whole island
    fig = plt.figure(figsize=(15, 10))
    ax_is = fig.add_axes([0.01, 0.03, 0.46, 0.92])

    # ---------- Panel 1: whole Sri Lanka, three districts filled with crop classes
    for name, polys in bounds.items():
        for poly in polys:
            a = np.asarray(poly[0]); ax_is.fill(a[:, 0], a[:, 1], color="#f3f1ea", zorder=1, lw=0)
        draw_outline(ax_is, polys, color="#9a9a9a", lw=0.5, zorder=2)
    for d in rasters:
        fill_district(ax_is, bounds[d])
        draw_class_raster(ax_is, rasters[d], bounds[d], stride=8)
        draw_outline(ax_is, bounds[d], color="black", lw=1.1, zorder=5)
        cx, cy = centroid(bounds[d])
        ax_is.annotate(d, xy=(cx, cy), xytext=(cx + (0.55 if d == "Ratnapura" else -0.55), cy + (-0.1 if d == "Ratnapura" else 0.05)),
                       fontsize=10, fontweight="bold", ha="center", zorder=7,
                       arrowprops=dict(arrowstyle="-", color="black", lw=0.8),
                       bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="black", lw=0.6))
    ax_is.set_xlim(gx0 - 0.15, gx1 + 0.5); ax_is.set_ylim(gy0 - 0.1, gy1 + 0.1)
    ax_is.set_aspect(1 / np.cos(np.radians(7.8))); ax_is.set_xticks([]); ax_is.set_yticks([])
    for sp in ax_is.spines.values(): sp.set_visible(False)
    ax_is.set_title("Sri Lanka: crop classes in Ratnapura, Colombo and Gampaha", fontsize=12)
    handles = [Patch(color=COLORS[c], label=NAMES[c]) for c in (2, 3, 1)]
    handles.append(Patch(facecolor="#ececec", edgecolor="#999", label="Not mapped (forest, built-up, water, roads)"))
    handles.append(Patch(facecolor="#f3f1ea", edgecolor="#999", label="Other districts (not studied)"))
    ax_is.legend(handles=handles, loc="upper right", fontsize=9, framealpha=0.95)
    scale_bar(ax_is, 50, 7.8, 0.05, 0.03); north_arrow(ax_is, 0.93, 0.07)

    # ---------- Panels 2-4: each district at full detail, drawn inside its own boundary
    order = [d for d in TARGETS if d in rasters]
    heights = {d: (bbox([bounds[d]])[3] - bbox([bounds[d]])[1]) for d in order}
    widths = {d: (bbox([bounds[d]])[2] - bbox([bounds[d]])[0]) for d in order}
    right_x, right_w, y_top = 0.50, 0.48, 0.95
    total_h = sum(heights.values()) + 0.15 * len(order)
    for d in order:
        h_frac = 0.88 * (heights[d] + 0.15) / total_h
        ax = fig.add_axes([right_x, y_top - h_frac, right_w, h_frac * 0.93])
        y_top -= h_frac + 0.01
        x0, y0, x1, y1 = bbox([bounds[d]])
        fill_district(ax, bounds[d])
        draw_class_raster(ax, rasters[d], bounds[d], stride=max(1, int(max(1, (x1 - x0) / 0.0009) // 1300)))
        draw_outline(ax, bounds[d], color="black", lw=1.2, zorder=5)
        ax.set_xlim(x0 - 0.02, x1 + 0.02); ax.set_ylim(y0 - 0.02, y1 + 0.02)
        ax.set_aspect(1 / np.cos(np.radians((y0 + y1) / 2)))
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values(): sp.set_visible(False)
        t = d
        if d in area_txt:
            t += "   |   " + "   ".join(f"{NAMES[c].split()[0]} {area_txt[d][c]:,.0f} ha" for c in (2, 3, 1))
        ax.set_title(t, fontsize=10, loc="left")

    out = MAPDIR / "SriLanka_3_districts_crop_map.png"
    plt.savefig(out, dpi=220, bbox_inches="tight", facecolor="white"); plt.close()
    print("Saved", out)
