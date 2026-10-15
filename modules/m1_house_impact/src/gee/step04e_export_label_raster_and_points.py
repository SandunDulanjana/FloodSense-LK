# ===== M1 Step 4e: export LABEL raster (flood variant D) + building points table =====
# Replaces the earlier per-building GEE table export, which failed with "Computation timed out".
# Distances/fractions are computed exactly in Python (Step 6) instead of in GEE.
import ee, json, datetime
ee.Initialize(project='sliit-research-2026')
AOI = ee.Geometry.Rectangle([79.85, 6.90, 80.22, 7.02])
s1 = (ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(AOI)
        .filter(ee.Filter.eq('instrumentMode', 'IW')).filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING')))
sm = lambda i: i.focalMedian(30, 'circle', 'meters')
def pol(p):
    b = sm(s1.filterDate('2025-10-01', '2025-11-20').select(p).mean())
    a = sm(s1.filterDate('2025-12-02', '2025-12-03').select(p).mosaic())
    return a, a.subtract(b)
vv_a, vv_d = pol('VV'); vh_a, vh_d = pol('VH')
perm_occ = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').unmask(0)
m = (vv_d.lt(-2).And(vv_a.lt(-15)).Or(vh_d.lt(-3).And(vh_a.lt(-22)))).And(perm_occ.lt(50))
big = m.selfMask().connectedPixelCount(50).gte(8).unmask(0)
flood = m.And(big).unmask(0).rename('flood_D')
lc = ee.ImageCollection('ESA/WorldCover/v200').first().rename('landcover')
lab = ee.Image.cat([flood.float(), vv_d.rename('vv_change_db').float(), lc.float()]).unmask(0).clip(AOI)
t1 = ee.batch.Export.image.toDrive(image=lab, description='M1_label_raster_v2', folder='M1_Research',
        fileNamePrefix='M1_label_raster_v2', region=AOI, scale=10, crs='EPSG:32644', maxPixels=1e10)
t1.start()
blds = ee.FeatureCollection('GOOGLE/Research/open-buildings/v3/polygons').filterBounds(AOI).filter(ee.Filter.gte('confidence', 0.75))
def to_point(f):
    c = f.geometry().centroid(1); xy = c.coordinates()
    return ee.Feature(None, {'lon': xy.get(0), 'lat': xy.get(1), 'area_m2': f.get('area_in_meters'),
                             'confidence': f.get('confidence'), 'bid': f.get('full_plus_code')})
t2 = ee.batch.Export.table.toDrive(collection=blds.map(to_point), description='M1_building_points_v2', folder='M1_Research',
        fileNamePrefix='M1_building_points_v2', fileFormat='CSV', selectors=['bid','lon','lat','area_m2','confidence'])
t2.start()
print("Label raster task:", t1.id); print("Building points task:", t2.id)
json.dump({"step": "4e", "time": datetime.datetime.now().isoformat(), "label_raster_task": t1.id, "points_task": t2.id,
           "flood_rule": "D: (VVdiff<-2 & VV<-15) | (VHdiff<-3 & VH<-22), JRC occ<50, patch>=8px"},
          open('/content/drive/MyDrive/M1_Research/records/step04e_exports.json', 'w'), indent=2)
