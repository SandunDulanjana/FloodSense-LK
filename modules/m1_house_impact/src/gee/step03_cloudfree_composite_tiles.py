# ===== M1 Step 3: Cloud-free S2 composite (Cloud Score+) + zoomed tiles with buildings & SAR flood =====
import ee, os, io, json, requests, datetime
import matplotlib.pyplot as plt
from PIL import Image as PILImage

PROJECT_ID = 'sliit-research-2026'
try: ee.Initialize(project=PROJECT_ID)
except Exception: ee.Authenticate(auth_mode='notebook'); ee.Initialize(project=PROJECT_ID)

AOI = ee.Geometry.Rectangle([79.85, 6.90, 80.22, 7.02])
OUT = '/content/drive/MyDrive/M1_Research/records'; os.makedirs(OUT, exist_ok=True)

# 1) Cloud-free Sentinel-2 using Cloud Score+ (pixel-level cloud removal, cs_cdf >= 0.60) + median composite
cs = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED')
s2_all = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(AOI).filterDate('2025-01-01', '2025-10-31').linkCollection(cs, ['cs_cdf']))
s2_clean = (s2_all.map(lambda img: img.updateMask(img.select('cs_cdf').gte(0.60)))
                  .select(['B2', 'B3', 'B4', 'B8']).median())
print("S2 scenes used (all, before pixel masking):", s2_all.size().getInfo())

# 2) SAR before (14 Nov) and after (2 Dec)
def s1_day(day):
    d = ee.Date(day)
    return (ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(AOI).filterDate(d, d.advance(1, 'day'))
              .filter(ee.Filter.eq('instrumentMode', 'IW')).select('VV').mosaic())
sar_before, sar_after = s1_day('2025-11-14'), s1_day('2025-12-02')

# 3) Buildings
blds = (ee.FeatureCollection('GOOGLE/Research/open-buildings/v3/polygons')
          .filterBounds(AOI).filter(ee.Filter.gte('confidence', 0.75)))
outline = ee.Image().byte().paint(featureCollection=blds, color=1, width=1).visualize(palette=['ffff00'])

# 4) Visual layers
rgb_vis = s2_clean.visualize(bands=['B4', 'B3', 'B2'], min=0, max=2500, gamma=1.2)
layers = [("S2 pre-flood (10 m)", rgb_vis), ("S2 + buildings", rgb_vis.blend(outline)),
          ("SAR 14 Nov (before)", sar_before.visualize(min=-25, max=0)),
          ("SAR 2 Dec (after) + buildings", sar_after.visualize(min=-25, max=0).blend(outline))]

# 5) Five sample tiles along the Kelani (lon, lat) — 1.5 km x 1.5 km each
tiles = {"Kolonnawa/Wellampitiya": (79.895, 6.945), "Kaduwela": (79.983, 6.935), "Malwana": (80.015, 6.950),
         "Hanwella": (80.080, 6.910), "Avissawella side": (80.200, 6.953)}
def thumb(img, region, px=450):
    url = img.getThumbURL({'region': region, 'dimensions': px, 'format': 'png'})
    return PILImage.open(io.BytesIO(requests.get(url).content)).convert('RGB')

rec = {"step": 3, "time": datetime.datetime.now().isoformat(), "tile_building_counts": {}}
fig, axes = plt.subplots(len(tiles), 4, figsize=(16, 4 * len(tiles)))
for r, (name, (lon, lat)) in enumerate(tiles.items()):
    region = ee.Geometry.Point([lon, lat]).buffer(750).bounds()
    rec["tile_building_counts"][name] = n = blds.filterBounds(region).size().getInfo()
    for c, (title, layer) in enumerate(layers):
        axes[r, c].imshow(thumb(layer, region)); axes[r, c].axis('off')
        axes[r, c].set_title(f"{name}\n{title}" if c == 0 else title, fontsize=9)
    print(f"{name:25s} buildings: {n}")
plt.tight_layout(); plt.savefig(f'{OUT}/step03_zoom_tiles.png', dpi=110); plt.show()
full = thumb(rgb_vis, AOI, 1200); full.save(f'{OUT}/step03_s2_cloudfree_full.png')
json.dump(rec, open(f'{OUT}/step03_record.json', 'w'), indent=2)
print("Saved to", OUT)
