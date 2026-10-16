# M2-05a: labelling-kit extras (model-independent). Colab:  %run -i /content/drive/MyDrive/M2_flood_roads/src/m2_05a_kit_extras.py
# Adds per chip: SAR change composite (R=pre VV, G=B=post VV; new open water appears RED) and Sentinel-2 L2A true/false colour
# for 2025-11-30 and 2025-12-05 on the exact chip grid. Adds an empty label GeoPackage (layers 'water', 'unsure', EPSG:32644).
# Zips the kit to MyDrive/M2_flood_roads/M2_labelling_kit.zip. Nothing here reads any model output.
import os, sys, json, zipfile, numpy as np, rasterio, geopandas as gpd
from rasterio.transform import from_origin
ROOT = '/content/drive/MyDrive/M2_flood_roads'; KIT = f'{ROOT}/data/processed/kelani_ditwah/labelling_kit'
sys.path.insert(0, f'{ROOT}/src')
from m2 import geo as G
idx = json.load(open(f'{KIT}/kit_index.json'))
u8 = lambda a, lo, hi: (np.clip((np.nan_to_num(a, nan=lo) - lo) / (hi - lo), 0, 1) * 254 + 1).astype('uint8')

def write_rgb(path, rgb, T, crs):
    with rasterio.open(path, 'w', driver='GTiff', height=rgb.shape[1], width=rgb.shape[2], count=3, dtype='uint8', crs=crs,
                       transform=T, nodata=0, photometric='RGB', compress='deflate') as d:
        d.write(rgb)

# 1) SAR change composite
for ch in idx['chips']:
    cid = ch['chip_id']
    with rasterio.open(f'{KIT}/{cid}_post_db.tif') as s: post = s.read(); T = s.transform; crs = s.crs
    with rasterio.open(f'{KIT}/{cid}_pre_db.tif') as s: pre = s.read()
    write_rgb(f'{KIT}/{cid}_change_rgb.tif', np.stack([u8(pre[0], -25, 0), u8(post[0], -25, 0), u8(post[0], -25, 0)]), T, crs)
print('change composites written')

# 2) Sentinel-2 L2A (cloud/shadow masked via SCL)
try:
    import ee
    from google.colab import auth
    auth.authenticate_user(); ee.Initialize(project='sliit-damage-detection')
    S2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    for day in ['2025-11-30', '2025-12-05']:
        d0 = ee.Date(day); im = S2.filterDate(d0, d0.advance(1, 'day')).mosaic()
        for ch in idx['chips']:
            cid = ch['chip_id']
            with rasterio.open(f'{KIT}/{cid}_post_db.tif') as s: T = s.transform; crs = s.crs; Wd, Ht = s.width, s.height
            b = (T.c, T.f - Ht * 10, T.c + Wd * 10, T.f)
            a, _ = G.ee_to_array(ee, im, ['B4', 'B3', 'B2', 'B8', 'B11', 'SCL'], b, 'EPSG:32644', 10)
            bad = np.isin(np.nan_to_num(a[5]), [0, 3, 8, 9, 10]) | np.isnan(a[0])
            tc = np.stack([u8(a[i], 0, 2500) for i in (0, 1, 2)]); fc = np.stack([u8(a[i], 0, 4000) for i in (4, 3, 0)])
            tc[:, bad] = 0; fc[:, bad] = 0
            tag = day.replace('-', '')
            write_rgb(f'{KIT}/{cid}_s2_{tag}_truecolour.tif', tc, T, crs)
            write_rgb(f'{KIT}/{cid}_s2_{tag}_swir_nir_red.tif', fc, T, crs)
            print(cid, day, 'cloud/shadow/no-data share', round(float(bad.mean()), 3))
except Exception as e:
    print('Sentinel-2 step skipped:', repr(e)[:300])

# 3) empty label GeoPackage (polygon layers, EPSG:32644)
gp = f'{KIT}/KEL_labels.gpkg'
if not os.path.exists(gp):
    for layer in ['water', 'unsure']:
        g = gpd.GeoDataFrame({'chip_id': ['template'], 'note': ['delete me']},
                             geometry=gpd.GeoSeries.from_wkt(['POLYGON((0 0,1 0,1 1,0 0))']), crs=32644)
        g.iloc[0:0].to_file(gp, layer=layer, driver='GPKG', geometry_type='Polygon')
    print('created', gp, gpd.list_layers(gp).to_dict('records'))
else:
    print('label GeoPackage exists — not overwritten:', gp)

# 4) zip the kit for one download
zp = f'{ROOT}/M2_labelling_kit.zip'
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for fn in sorted(os.listdir(KIT)):
        if fn.endswith('_label.tif'): continue        # superseded by KEL_labels.gpkg (polygon workflow)
        z.write(f'{KIT}/{fn}', f'labelling_kit/{fn}')
print(zp, round(os.path.getsize(zp) / 1e6, 1), 'MB'); print('DONE M2_05a')
