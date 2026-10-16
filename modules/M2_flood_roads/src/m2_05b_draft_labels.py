# M2-05b: AI-drafted reference labels for the 15 Kelani chips (decision D24). Colab:  %run -i .../src/m2_05b_draft_labels.py
# Evidence used (all model-independent): S1 VV/VH 2025-12-02 (labelled date), S1 2025-11-26 (same orbit, dry), S2 L2A 2025-11-30
# (MNDWI, SCL cloud mask), JRC GSW occurrence, SRTM slope, ESA WorldCover. No model prediction or probability is read here.
# Rule per chip (defaults; per-chip overrides OV[i] are logged):
#   core   = VVpost_med3 < t  AND (VVpre_med3 - VVpost_med3 >= d  OR  JRC occurrence > 50  OR  S2 MNDWI > m)
#   water  = core grown (8-connected) into pixels with VVpost_med3 < t + g AND (drop >= d/2 OR JRC > 50 OR MNDWI > m)  [hysteresis]
#   unsure = dark & not water (tarmac / sand / shadow / unknown)  |  slope > s & dark  |
#            S2 says water (MNDWI > m) but radar dry  |  S2 cloud where radar is ambiguous (t < VV < t+2)  |  manual boxes
#   clean  : remove water blobs < a px, fill holes < a px; unsure wins over water.
import os, sys, json, numpy as np, rasterio, matplotlib.pyplot as plt
from scipy import ndimage as ndi
ROOT = '/content/drive/MyDrive/M2_flood_roads'; K = f'{ROOT}/data/processed/kelani_ditwah'; KIT = f'{K}/labelling_kit'
idx = json.load(open(f'{KIT}/kit_index.json')); CH = idx['chips']; C = 256
OV = {i: {} for i in range(len(CH))}
if os.path.exists(f'{KIT}/draft_label_params.json'):
    OV.update({int(k): v for k, v in json.load(open(f'{KIT}/draft_label_params.json'))['overrides'].items()})

def crop(path, ch):
    with rasterio.open(path) as s: a = s.read(1, window=((ch['r'], ch['r'] + C), (ch['c'], ch['c'] + C)))
    return a.astype('float32')
# S2 30 Nov raw bands for MNDWI (GEE)
import ee
try: ee.Number(1).getInfo()
except Exception:
    from google.colab import auth; auth.authenticate_user(); ee.Initialize(project='sliit-damage-detection')
sys.path.insert(0, f'{ROOT}/src'); from m2 import geo as G
S2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterDate('2025-11-30', '2025-12-01').mosaic()
BASE = {}
for i, ch in enumerate(CH):
    cid = ch['chip_id']
    with rasterio.open(f'{KIT}/{cid}_post_db.tif') as s: post = s.read(); T = s.transform
    with rasterio.open(f'{KIT}/{cid}_pre_db.tif') as s: pre = s.read()
    b = (T.c, T.f - C * 10, T.c + C * 10, T.f)
    s2, _ = G.ee_to_array(ee, S2, ['B2', 'B3', 'B4', 'B8', 'B11', 'SCL'], b, 'EPSG:32644', 10)
    cloud = np.isin(np.nan_to_num(s2[5]), [0, 3, 8, 9, 10]) | np.isnan(s2[1])
    mndwi = (s2[1] - s2[4]) / (s2[1] + s2[4] + 1e-6); mndwi[cloud] = np.nan
    dem = crop(f'{K}/srtm.tif', ch); gy, gx = np.gradient(dem, 10.0); slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    BASE[i] = dict(cid=cid, T=T, vv=ndi.median_filter(np.nan_to_num(post[0], nan=0.0), 3), vvpre=ndi.median_filter(np.nan_to_num(pre[0], nan=0.0), 3),
                   valid=np.isfinite(post[0]), jrc=crop(f'{K}/jrc_occurrence.tif', ch), wc=crop(f'{K}/worldcover2021.tif', ch),
                   slope=slope, mndwi=mndwi, cloud=cloud, rgb=np.dstack([s2[2], s2[1], s2[0]]), fc=np.dstack([s2[4], s2[3], s2[2]]),
                   raw=post[0], rawpre=pre[0])
print('base layers ready for', len(BASE), 'chips')

exec(open(f'{ROOT}/src/m2_05b_funcs.py').read())
