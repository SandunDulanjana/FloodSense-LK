# [AUTO] ===== M1 Step 6: Build building-level dataset from rasters (exact distances in Python) =====
# Inputs (Drive/M1_Research): M1_raster_stack_v1.tif (10 bands), M1_label_raster_v2.tif (flood_D, vv_change_db, landcover),
#                             M1_building_points_v2.csv (bid, lon, lat, area_m2, confidence)
import os, glob, json, datetime, numpy as np, pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling
from scipy import ndimage
from pyproj import Transformer

R = '/content/drive/MyDrive/M1_Research'; REC = f'{R}/records'; os.makedirs(REC, exist_ok=True)
WORK = '/content/m1'; os.makedirs(WORK, exist_ok=True)
def find(p):
    f = sorted(glob.glob(f'{R}/{p}*'));  assert f, f'missing {p} in {R}'; return f
stack_f = find('M1_raster_stack_v1'); label_f = find('M1_label_raster_v2'); pts_f = find('M1_building_points_v2')
print('stack files:', [os.path.basename(x) for x in stack_f]); print('label files:', [os.path.basename(x) for x in label_f])

def read_mosaic(files):                       # GEE may split big exports into several tiles
    if len(files) == 1:
        with rasterio.open(files[0]) as s: return s.read().astype('float32'), s.transform, s.crs, s.descriptions
    from rasterio.merge import merge
    srcs = [rasterio.open(f) for f in files]; arr, tr = merge(srcs); d = srcs[0].descriptions; crs = srcs[0].crs
    [s.close() for s in srcs]; return arr.astype('float32'), tr, crs, d
S, tr, crs, sdesc = read_mosaic(stack_f)
L, ltr, lcrs, ldesc = read_mosaic(label_f)
print('stack', S.shape, crs, '| label', L.shape, lcrs)
if L.shape[1:] != S.shape[1:] or ltr != tr:      # align label grid to stack grid if needed
    L2 = np.zeros((L.shape[0],) + S.shape[1:], 'float32')
    for b in range(L.shape[0]):
        reproject(L[b], L2[b], src_transform=ltr, src_crs=lcrs, dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest)
    L = L2; print('label re-aligned to stack grid')
B = dict(B2=0, B3=1, B4=2, B8=3, B11=4, dem=5, slope=6, hand=7, dist_river=8, bmask=9)
flood = L[0] > 0.5; vvch = L[1]; lc = L[2]
H, W = flood.shape; px = 10.0
print(f'grid {H}x{W} | flood pixels {flood.sum():,} ({flood.sum()*100/1e6:.2f} km2)')

# ---- exact label layers ----
dist_flood = ndimage.distance_transform_edt(~flood) * px          # metres to nearest flood pixel
def disk(r):
    y, x = np.ogrid[-r:r+1, -r:r+1]; k = (x*x + y*y <= r*r).astype('float32'); return k / k.sum()
flood_frac30 = ndimage.convolve(flood.astype('float32'), disk(3), mode='constant')
vv20 = ndimage.convolve(vvch, disk(2), mode='nearest')
built100 = ndimage.convolve(S[B['bmask']], disk(10), mode='constant')
np.save(f'{WORK}/dist_flood.npy', dist_flood.astype('float32'))

# ---- building points -> pixel row/col ----
pts = pd.read_csv(pts_f[0]); n0 = len(pts)
xs, ys = Transformer.from_crs('EPSG:4326', crs, always_xy=True).transform(pts.lon.values, pts.lat.values)
inv = ~tr; cols, rows = inv * (xs, ys); rows = np.floor(rows).astype(int); cols = np.floor(cols).astype(int)
ok = (rows >= 16) & (rows < H-16) & (cols >= 16) & (cols < W-16)       # keep room for 32x32 patches
pts = pts[ok].copy(); rows, cols = rows[ok], cols[ok]; pts['row'], pts['col'], pts['x'], pts['y'] = rows, cols, xs[ok], ys[ok]
s2ok = S[B['B4'], rows, cols] > 0                                       # drop pixels with no S2 data
pts = pts[s2ok].copy(); rows, cols = rows[s2ok], cols[s2ok]
def g(a): return a[rows, cols]
b2,b3,b4,b8,b11 = [g(S[B[k]]) for k in ['B2','B3','B4','B8','B11']]
pts = pts.assign(X_B2=b2, X_B3=b3, X_B4=b4, X_B8=b8, X_B11=b11,
    X_ndvi=(b8-b4)/(b8+b4+1e-6), X_ndwi=(b3-b8)/(b3+b8+1e-6),
    X_dem_m=g(S[B['dem']]), X_slope_deg=g(S[B['slope']]), X_hand_m=g(S[B['hand']]),
    X_dist_river_m=g(S[B['dist_river']]), X_built_frac_100m=g(built100), X_landcover=g(lc), X_area_m2=pts.area_m2,
    LABEL_dist_to_flood_m=g(dist_flood), LABEL_flood_frac_30m=g(flood_frac30), LABEL_vv_change_db=g(vv20))
# spatial blocks (2 km x 2 km) for spatial cross-validation
pts['block'] = ((pts.x // 2000).astype(int)).astype(str) + '_' + ((pts.y // 2000).astype(int)).astype(str)
pts.to_parquet(f'{R}/M1_buildings_dataset_v2.parquet', index=False)
print(f'buildings: {n0:,} exported -> {len(pts):,} usable | spatial blocks: {pts.block.nunique()}')

d = pts.LABEL_dist_to_flood_m
print('\nShare of buildings within X m of SAR flood water:')
bal = {}
for t in [0, 10, 30, 50, 100, 150, 200, 300]:
    bal[t] = round(float((d <= t).mean()*100), 2); print(f'   <= {t:3d} m : {bal[t]:5.2f}%  ({int((d<=t).sum()):,})')
print(f'   VV brightening > +3 dB: {(pts.LABEL_vv_change_db > 3).mean()*100:.2f}%')
near, far = pts[d <= 50], pts[d > 150]
print('\nMedian pre-flood features: near (<=50 m) vs far (>150 m)')
for c in ['X_hand_m','X_dem_m','X_dist_river_m','X_ndwi','X_built_frac_100m','X_slope_deg']:
    print(f'   {c:18s} near {near[c].median():9.2f} | far {far[c].median():9.2f}')
json.dump({'step': 6, 'time': datetime.datetime.now().isoformat(), 'n_points_exported': int(n0), 'n_usable': int(len(pts)),
           'n_blocks': int(pts.block.nunique()), 'flood_km2': float(flood.sum()*100/1e6), 'pct_within_m': bal},
          open(f'{REC}/step06_dataset.json', 'w'), indent=2)
print('\nSaved dataset + records/step06_dataset.json')
