"""Geospatial helpers: GEE pixel export, sliding-window scene inference, road exposure scoring."""
import math, numpy as np


# ---------------------------------------------------------------- GEE export (computePixels, tiled)
def ee_to_array(ee, img, bands, bounds, crs, scale, tile=1024, fill=-9999.0):
    """Download `img` (ee.Image) bands over `bounds`=(xmin,ymin,xmax,ymax) in `crs` units at `scale` m.
    Returns float32 (nb,H,W) with NaN where masked, plus the affine origin (xmin, ymax)."""
    xmin, ymin, xmax, ymax = bounds
    W, H = int(math.ceil((xmax - xmin) / scale)), int(math.ceil((ymax - ymin) / scale))
    out = np.full((len(bands), H, W), np.nan, np.float32)
    im = img.select(bands).unmask(fill).toFloat()
    for r0 in range(0, H, tile):
        for c0 in range(0, W, tile):
            h, w = min(tile, H - r0), min(tile, W - c0)
            req = {"expression": im, "fileFormat": "NUMPY_NDARRAY",
                   "grid": {"dimensions": {"width": w, "height": h}, "crsCode": crs,
                            "affineTransform": {"scaleX": scale, "shearX": 0, "translateX": xmin + c0 * scale,
                                                "shearY": 0, "scaleY": -scale, "translateY": ymax - r0 * scale}}}
            a = ee.data.computePixels(req)
            for i, b in enumerate(bands):
                v = a[b].astype(np.float32); v[v == fill] = np.nan
                out[i, r0:r0 + h, c0:c0 + w] = v
    return out, (xmin, ymax)


def write_tif(path, arr, origin, scale, crs, nodata=np.nan, dtype="float32", band_names=None):
    import rasterio
    from rasterio.transform import from_origin
    arr = arr if arr.ndim == 3 else arr[None]
    prof = dict(driver="GTiff", height=arr.shape[1], width=arr.shape[2], count=arr.shape[0], dtype=dtype, crs=crs,
                transform=from_origin(origin[0], origin[1], scale, scale), nodata=nodata, compress="deflate",
                tiled=True, blockxsize=256, blockysize=256)
    with rasterio.open(path, "w", **prof) as d:
        d.write(arr.astype(dtype))
        if band_names:
            for i, n in enumerate(band_names, 1): d.set_band_description(i, n)


# ---------------------------------------------------------------- scene inference
def sliding_predict(model, x_norm, valid, device, win=512, overlap=128, batch=4):
    """x_norm (2,H,W) normalised; returns water probability (H,W) float32, NaN outside `valid`.
    Overlapping windows are blended with a 2-D Hann-like weight to suppress tile-edge artefacts."""
    import torch, torch.nn.functional as F
    C, H, W = x_norm.shape
    st = win - overlap
    rows = list(range(0, max(H - win, 0) + 1, st)); cols = list(range(0, max(W - win, 0) + 1, st))
    if rows[-1] + win < H: rows.append(H - win)
    if cols[-1] + win < W: cols.append(W - win)
    w1 = np.hanning(win + 2)[1:-1].astype(np.float32); wt = np.outer(w1, w1) + 1e-3
    acc = np.zeros((H, W), np.float32); den = np.zeros((H, W), np.float32)
    pad = lambda a: np.pad(a, ((0, 0), (0, max(0, win - a.shape[1])), (0, max(0, win - a.shape[2]))), mode="reflect")
    coords = [(r, c) for r in rows for c in cols]
    model.eval()
    with torch.no_grad():
        for i in range(0, len(coords), batch):
            cs = coords[i:i + batch]
            xb = np.stack([pad(x_norm[:, r:r + win, c:c + win]) for r, c in cs])
            p = torch.sigmoid(model(torch.from_numpy(xb).to(device)))[:, 0].cpu().numpy()
            for (r, c), pi in zip(cs, p):
                h, w = min(win, H - r), min(win, W - c)
                acc[r:r + h, c:c + w] += pi[:h, :w] * wt[:h, :w]; den[r:r + h, c:c + w] += wt[:h, :w]
    prob = acc / np.maximum(den, 1e-6)
    prob[~valid] = np.nan
    return prob


# ---------------------------------------------------------------- roads
def segment_lines(gdf, max_len=100.0):
    """Split road LineStrings (projected CRS) into pieces of <= max_len metres so risk is local, not averaged over km."""
    from shapely.geometry import LineString
    from shapely.ops import substring
    rows = []
    for idx, r in gdf.iterrows():
        g = r.geometry
        if g is None or g.length == 0: continue
        n = max(1, int(math.ceil(g.length / max_len)))
        for k in range(n):
            seg = substring(g, k * g.length / n, (k + 1) * g.length / n)
            d = r.drop(labels="geometry").to_dict(); d.update({"parent": str(idx), "part": k, "geometry": seg})
            rows.append(d)
    import geopandas as gpd
    return gpd.GeoDataFrame(rows, crs=gdf.crs)


def sample_along(lines, raster_path, step=5.0):
    """Sample a single-band raster along each line every `step` m. Returns list of 1-D arrays (NaN = nodata)."""
    import rasterio, shapely
    out = []
    with rasterio.open(raster_path) as src:
        band = src.read(1).astype(np.float32); T = src.transform
        for g in lines.geometry:
            n = max(2, int(g.length / step) + 1)
            pts = shapely.line_interpolate_point(g, np.linspace(0, 1, n), normalized=True)
            xy = shapely.get_coordinates(pts)
            cc = np.floor((xy[:, 0] - T.c) / T.a).astype(int); rr = np.floor((xy[:, 1] - T.f) / T.e).astype(int)
            ok = (rr >= 0) & (rr < band.shape[0]) & (cc >= 0) & (cc < band.shape[1])
            v = np.full(n, np.nan, np.float32); v[ok] = band[rr[ok], cc[ok]]
            out.append(v)
    return out


def exposure_features(samples, p_thr=0.5):
    """Per-segment features from sampled flood probabilities.
    exposure  = mean probability along the segment (expected inundated fraction under the model)
    frac_wet  = fraction of samples with p >= p_thr (binary-overlap fraction)
    p_max     = max probability; valid_frac = share of samples with data."""
    f = []
    for v in samples:
        ok = np.isfinite(v)
        if ok.sum() == 0:
            f.append(dict(exposure=np.nan, frac_wet=np.nan, p_max=np.nan, valid_frac=0.0)); continue
        x = v[ok]
        f.append(dict(exposure=float(x.mean()), frac_wet=float((x >= p_thr).mean()), p_max=float(x.max()),
                      valid_frac=float(ok.mean())))
    return f


def classify(exposure, t_low, t_high):
    """3-level display class. Thresholds are calibrated on the calibration block only (see M2-04)."""
    return np.where(np.isnan(exposure), "no data", np.where(exposure >= t_high, "high", np.where(exposure >= t_low, "moderate", "low")))
