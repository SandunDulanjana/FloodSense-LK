# ===== M1 Step 5: Export pre-flood raster stack (10 m, UTM 44N) for CNN image patches =====
import ee, json, datetime
ee.Initialize(project='sliit-research-2026')
AOI = ee.Geometry.Rectangle([79.85, 6.90, 80.22, 7.02])
cs = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED')
s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(AOI).filterDate('2025-01-01', '2025-10-31')
        .linkCollection(cs, ['cs_cdf']).map(lambda i: i.updateMask(i.select('cs_cdf').gte(0.6)))
        .select(['B2','B3','B4','B8','B11']).median())
dem = ee.Image('USGS/SRTMGL1_003'); slope = ee.Terrain.slope(dem)
hand = ee.Image('MERIT/Hydro/v1_0_1').select('hnd')
perm = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').unmask(0)
d_riv = perm.gte(50).selfMask().fastDistanceTransform(512).sqrt().multiply(10).unmask(5120)
blds = ee.FeatureCollection('GOOGLE/Research/open-buildings/v3/polygons').filterBounds(AOI).filter(ee.Filter.gte('confidence', 0.75))
bmask = ee.Image().byte().paint(blds, 1).unmask(0)                       # building footprint raster (0/1)
# Band order (fixed): 0-4 S2 (B2,B3,B4,B8,B11), 5 dem, 6 slope, 7 hand, 8 dist_river, 9 building mask
stack = ee.Image.cat([s2, dem.rename('dem'), slope.rename('slope'), hand.rename('hand'),
                      d_riv.rename('dist_river'), bmask.rename('bmask')]).float().unmask(0).clip(AOI)
print("Bands:", stack.bandNames().getInfo())
task = ee.batch.Export.image.toDrive(image=stack, description='M1_raster_stack_v1', folder='M1_Research', fileNamePrefix='M1_raster_stack_v1',
                                     region=AOI, scale=10, crs='EPSG:32644', maxPixels=1e10, fileFormat='GeoTIFF')
task.start(); print("Raster export started. Task ID:", task.id)
json.dump({"step": 5, "time": datetime.datetime.now().isoformat(), "task_id": task.id,
           "bands": ['B2','B3','B4','B8','B11','dem','slope','hand','dist_river','bmask'], "crs": "EPSG:32644", "scale_m": 10},
          open('/content/drive/MyDrive/M1_Research/records/step05_raster_export.json', 'w'), indent=2)
