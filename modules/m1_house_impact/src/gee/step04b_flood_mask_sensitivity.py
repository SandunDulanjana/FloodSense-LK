# ===== M1 Step 4b: SAR flood-mask sensitivity test (4 rule variants) =====
# Result (run 23 Oct 2026): flood area A 6.87 / B 8.35 / C 9.88 / D 10.80 km2 -> variant D (VV or VH) chosen.
import ee, os, io, json, requests, datetime
import matplotlib.pyplot as plt
from PIL import Image as PILImage

PROJECT_ID = 'sliit-research-2026'
try: ee.Initialize(project=PROJECT_ID)
except Exception: ee.Authenticate(auth_mode='notebook'); ee.Initialize(project=PROJECT_ID)
AOI = ee.Geometry.Rectangle([79.85, 6.90, 80.22, 7.02])
OUT = '/content/drive/MyDrive/M1_Research/records'; os.makedirs(OUT, exist_ok=True)

# SAR before (mean Oct–mid Nov) and after (2 Dec), same DESCENDING orbit, VV and VH, 30 m focal median (speckle)
s1 = (ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(AOI)
        .filter(ee.Filter.eq('instrumentMode', 'IW')).filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING')))
sm = lambda i: i.focalMedian(30, 'circle', 'meters')
def pol(p):
    b = sm(s1.filterDate('2025-10-01', '2025-11-20').select(p).mean())
    a = sm(s1.filterDate('2025-12-02', '2025-12-03').select(p).mosaic())
    return a, a.subtract(b)
vv_a, vv_d = pol('VV'); vh_a, vh_d = pol('VH')
slope = ee.Terrain.slope(ee.Image('USGS/SRTMGL1_003'))
not_perm = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').unmask(0).lt(50)
def clean(m):
    m = m.And(not_perm)                                              # remove permanent water
    big = m.selfMask().connectedPixelCount(50).gte(8).unmask(0)       # drop patches < 8 pixels
    return m.And(big).clip(AOI)
V = {'A_current':  clean(vv_d.lt(-3).And(vv_a.lt(-16)).And(slope.lt(5))),
     'B_noSlope':  clean(vv_d.lt(-3).And(vv_a.lt(-16))),
     'C_relaxed':  clean(vv_d.lt(-2).And(vv_a.lt(-15))),
     'D_VV_or_VH': clean(vv_d.lt(-2).And(vv_a.lt(-15)).Or(vh_d.lt(-3).And(vh_a.lt(-22))))}
keys = list(V.keys()); masks = ee.Image.cat([V[k].rename(k) for k in keys])

area = masks.multiply(ee.Image.pixelArea()).reduceRegion(ee.Reducer.sum(), AOI, 10, maxPixels=1e10, tileScale=4).getInfo()
print("Flood area (km2) in AOI:"); [print(f"   {k:12s}: {area[k]/1e6:6.2f}") for k in keys]

flag = masks.reduceNeighborhood(ee.Reducer.mean(), ee.Kernel.circle(30, 'meters')).gte(0.20).rename(keys)
blds = ee.FeatureCollection('GOOGLE/Research/open-buildings/v3/polygons').filterBounds(AOI).filter(ee.Filter.gte('confidence', 0.75))
tiles = {"Kolonnawa": (79.895, 6.945), "Kaduwela": (79.983, 6.935), "Malwana": (80.015, 6.950)}
rec = {"step": "4b", "time": datetime.datetime.now().isoformat(), "area_km2": {k: round(area[k]/1e6, 2) for k in keys}, "tiles": {}}
for name, (lon, lat) in tiles.items():
    reg = ee.Geometry.Point([lon, lat]).buffer(750).bounds()
    s = flag.reduceRegions(collection=blds.filterBounds(reg).map(lambda f: ee.Feature(f.geometry().centroid(1))), reducer=ee.Reducer.first(), scale=10)
    d = ee.Dictionary.fromLists(keys, [s.aggregate_sum(k) for k in keys]).set('n', s.size()).getInfo()
    rec["tiles"][name] = d
    print(f"   {name:10s} n={d['n']:5d} | " + " | ".join(f"{k}: {int(d[k])} ({100*d[k]/d['n']:.1f}%)" for k in keys))

cs = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED')
s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(AOI).filterDate('2025-01-01', '2025-10-31')
        .linkCollection(cs, ['cs_cdf']).map(lambda i: i.updateMask(i.select('cs_cdf').gte(0.6))).select(['B2','B3','B4']).median())
rgb = s2.visualize(bands=['B4','B3','B2'], min=0, max=2500, gamma=1.2)
cols = [("VV 2 Dec (after)", vv_a.visualize(min=-25, max=0)),
        ("VV change (blue = darker)", vv_d.visualize(min=-6, max=6, palette=['0000ff','ffffff','ff0000']))]
cols += [(k, rgb.blend(V[k].selfMask().visualize(palette=['00a2ff'], opacity=0.7))) for k in keys]
def thumb(img, region, px=380):
    return PILImage.open(io.BytesIO(requests.get(img.getThumbURL({'region': region, 'dimensions': px, 'format': 'png'})).content)).convert('RGB')
fig, ax = plt.subplots(len(tiles), len(cols), figsize=(4*len(cols), 4.2*len(tiles)))
for r, (name, (lon, lat)) in enumerate(tiles.items()):
    reg = ee.Geometry.Point([lon, lat]).buffer(750).bounds()
    for c, (t, lay) in enumerate(cols):
        ax[r, c].imshow(thumb(lay, reg)); ax[r, c].axis('off'); ax[r, c].set_title(f"{name}\n{t}", fontsize=9)
plt.tight_layout(); plt.savefig(f'{OUT}/step04b_flood_sensitivity.png', dpi=100); plt.show()
json.dump(rec, open(f'{OUT}/step04b_record.json', 'w'), indent=2)
