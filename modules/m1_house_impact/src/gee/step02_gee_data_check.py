# ===== M1 Step 2: GEE data availability check — Kelani basin, Cyclone Ditwah =====
# Run in Google Colab. Requires a registered Earth Engine Cloud project.
import ee, json, os, requests, datetime
from IPython.display import Image, display
from google.colab import drive
drive.mount('/content/drive')

PROJECT_ID = 'sliit-research-2026'
ee.Authenticate()
ee.Initialize(project=PROJECT_ID)

# Lower Kelani basin box (Colombo coast -> Avissawella). [west, south, east, north]
AOI = ee.Geometry.Rectangle([79.85, 6.90, 80.22, 7.02])
rec = {"step": 2, "time": datetime.datetime.now().isoformat(), "aoi": [79.85, 6.90, 80.22, 7.02]}

# 1) PRE-flood Sentinel-2 (2025, low cloud)
s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterBounds(AOI).filterDate('2025-01-01', '2025-10-31')
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)))
rec["s2_pre_count"] = s2.size().getInfo()
best = s2.sort('CLOUDY_PIXEL_PERCENTAGE').limit(5)
rec["s2_clearest"] = best.aggregate_array('system:index').getInfo()
rec["s2_clearest_cloud%"] = best.aggregate_array('CLOUDY_PIXEL_PERCENTAGE').getInfo()

# 2) POST-flood Sentinel-1 SAR (Ditwah) + a PRE-flood SAR reference
def s1(start, end):
    return (ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(AOI)
              .filterDate(start, end)
              .filter(ee.Filter.eq('instrumentMode', 'IW'))
              .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')))
s1_post = s1('2025-11-26', '2025-12-10')
s1_pre  = s1('2025-10-01', '2025-11-20')
fmt = lambda t: ee.Date(t).format('YYYY-MM-dd')
rec["s1_post_dates"] = sorted(set(s1_post.aggregate_array('system:time_start').map(fmt).getInfo()))
rec["s1_pre_dates"]  = sorted(set(s1_pre.aggregate_array('system:time_start').map(fmt).getInfo()))
rec["s1_post_orbit"] = s1_post.aggregate_array('orbitProperties_pass').distinct().getInfo()

# 3) Building footprints (Google Open Buildings v3)
blds = (ee.FeatureCollection('GOOGLE/Research/open-buildings/v3/polygons')
          .filterBounds(AOI).filter(ee.Filter.gte('confidence', 0.75)))
rec["buildings_conf>=0.75"] = blds.size().getInfo()

# 4) Elevation (SRTM 30 m)
dem = ee.Image('USGS/SRTMGL1_003')
rec["dem_stats_m"] = dem.reduceRegion(ee.Reducer.minMax(), AOI, 30, maxPixels=1e9).getInfo()
for k, v in rec.items(): print(f"{k:22s}: {v}")

# 5) Save evidence: two preview images + JSON record
OUT = '/content/drive/MyDrive/M1_Research/records'; os.makedirs(OUT, exist_ok=True)
url1 = s2.median().clip(AOI).getThumbURL({'bands': ['B4','B3','B2'], 'min': 0, 'max': 3000, 'dimensions': 900, 'region': AOI})
url2 = s1_post.select('VV').min().clip(AOI).getThumbURL({'min': -25, 'max': 0, 'dimensions': 900, 'region': AOI}) if rec["s1_post_dates"] else None
for name, url in [('step02_s2_pre_rgb.png', url1), ('step02_s1_post_vv.png', url2)]:
    if url:
        open(f'{OUT}/{name}', 'wb').write(requests.get(url).content)
        print("\n", name); display(Image(f'{OUT}/{name}'))
json.dump(rec, open(f'{OUT}/step02_gee_check.json', 'w'), indent=2)
print("\nSaved to", OUT)
