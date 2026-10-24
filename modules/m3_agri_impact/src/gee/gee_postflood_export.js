// ============================================================
// M3 - STEP B: POST-FLOOD NDVI/NDWI COMPOSITE (+ optional Sentinel-1 flood layer)
// Run once per district. Edit ONLY the CONFIG block.
// Exports (Google Drive, folder M3_GEE_exports):
//   M3_<District>_PostFlood_<start>_<end>.tif   bands: NDVI_post, NDWI_post, post_fill
//   M3_<District>_S1Flood.tif                   band : s1_flood (1 = flood-like backscatter drop)
// ============================================================

// ===== CONFIG =====
var DISTRICT = 'Gampaha';        // Gampaha, Colombo, Ratnapura
var STEP     = 'EXPORT';             // 'VIEW' = check on the map, 'EXPORT' = queue the export tasks

// Post-flood optical windows (end dates are exclusive). Choose them after running gee_check_dates.js
var POST_START   = '2025-12-10';   // main window: water has receded, first reliable clear images
var POST_END     = '2026-01-16';
var POST_CLOUD   = 60;
var FALL_START   = '2025-12-01';   // fallback window, used only where the main window has no clear pixel
var FALL_END     = '2026-02-01';
var FALL_CLOUD   = 70;

// Sentinel-1 flood evidence (optional). Dates from the IWMI/DMC Ditwah products (14, 26 Nov and 2 Dec 2025)
var S1_BEFORE_START = '2025-11-08', S1_BEFORE_END = '2025-11-20';   // contains 14 Nov
var S1_DURING_START = '2025-11-26', S1_DURING_END = '2025-12-05';   // contains 26 Nov and 2 Dec
var S1_DROP_DB = -3;               // flood if backscatter fell by more than 3 dB
var S1_WATER_DB = -15;             // ... and is now below -15 dB (open-water level)

var NAME = DISTRICT.replace(/ /g, '');

// ===== AOI =====
var districts = ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level2')
  .filter(ee.Filter.eq('ADM0_NAME', 'Sri Lanka'));
var aoi = districts.filter(ee.Filter.eq('ADM2_NAME', DISTRICT)).geometry();
Map.centerObject(aoi, 10);
Map.addLayer(aoi, {color: 'red'}, DISTRICT + ' boundary');
var aoiMask = ee.Image.constant(1).clip(aoi).rename('aoi');

// ===== Sentinel-2 (same mask and same bands as the pre-flood script) =====
function maskS2(image) {
  var scl = image.select('SCL');
  var mask = scl.neq(1).and(scl.neq(3)).and(scl.neq(8))
                .and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));
  return image.updateMask(mask).divide(10000)
              .copyProperties(image, image.propertyNames());
}
var bands = ['B2','B3','B4','B5','B6','B7','B8','B8A','B11','B12'];
function getCol(start, end, cloudMax) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi).filterDate(start, end)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloudMax));
}
function medianOf(col) { return col.map(maskS2).select(bands).median(); }

var mainCol = getCol(POST_START, POST_END, POST_CLOUD);
var fallCol = getCol(FALL_START, FALL_END, FALL_CLOUD);
print('Main post-flood images:', mainCol.size());
print('Fallback images:', fallCol.size());

var main = medianOf(mainCol);
var fall = medianOf(fallCol);
var post = main.unmask(fall, false).clip(aoi);

// 0 = main window, 1 = fallback window, 3 = still missing
var mMain = main.select('B4').mask().unmask(0, false);
var mFall = fall.select('B4').mask().unmask(0, false);
var postFill = ee.Image(0)
  .where(mMain.not().and(mFall), 1)
  .where(mMain.not().and(mFall.not()), 3)
  .updateMask(aoiMask).rename('post_fill');

var ndviPost = post.normalizedDifference(['B8', 'B4']).rename('NDVI_post');
var ndwiPost = post.normalizedDifference(['B3', 'B8']).rename('NDWI_post');
var postStack = ndviPost.addBands(ndwiPost).addBands(postFill.toFloat())
                        .unmask(-9999, false).toFloat();

// coverage report
function areaPct(maskImg) {
  var a = ee.Image.pixelArea().updateMask(maskImg);
  var tot = ee.Image.pixelArea().updateMask(aoiMask);
  var s = a.reduceRegion({reducer: ee.Reducer.sum(), geometry: aoi, scale: 20, maxPixels: 1e11, bestEffort: true}).values().get(0);
  var t = tot.reduceRegion({reducer: ee.Reducer.sum(), geometry: aoi, scale: 20, maxPixels: 1e11, bestEffort: true}).values().get(0);
  return ee.Number(s).divide(ee.Number(t)).multiply(100);
}
print('District covered by main window %:', areaPct(postFill.eq(0)));
print('District covered by fallback only %:', areaPct(postFill.eq(1)));
print('District still missing %:', areaPct(postFill.eq(3)));

Map.addLayer(post, {bands: ['B4','B3','B2'], min: 0.02, max: 0.30}, 'Post-flood RGB');
Map.addLayer(ndviPost, {min: 0, max: 0.9, palette: ['brown','yellow','green']}, 'NDVI post', false);
Map.addLayer(ndwiPost, {min: -0.6, max: 0.4, palette: ['white','cyan','blue']}, 'NDWI post', false);

// ===== Sentinel-1 flood evidence (optional; M2 / M4 flood extent can replace this later) =====
var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(aoi)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .select('VV');
var before = s1.filterDate(S1_BEFORE_START, S1_BEFORE_END).median().focal_median(30, 'circle', 'meters');
var during = s1.filterDate(S1_DURING_START, S1_DURING_END).min().focal_median(30, 'circle', 'meters');
print('S1 images before / during:',
      s1.filterDate(S1_BEFORE_START, S1_BEFORE_END).size(),
      s1.filterDate(S1_DURING_START, S1_DURING_END).size());

var permanent = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').gt(50).unmask(0);
var slope = ee.Terrain.slope(ee.Image('USGS/SRTMGL1_003'));
var s1Flood = during.subtract(before).lt(S1_DROP_DB)
  .and(during.lt(S1_WATER_DB))
  .and(permanent.not())
  .and(slope.lt(5))
  .rename('s1_flood')
  .clip(aoi);
Map.addLayer(s1Flood.selfMask(), {palette: ['blue']}, 'S1 flood-like pixels', false);

// ===== EXPORTS =====
if (STEP === 'EXPORT') {
  Export.image.toDrive({
    image: postStack, description: 'M3_' + NAME + '_PostFlood',
    folder: 'M3_GEE_exports',
    fileNamePrefix: 'M3_' + NAME + '_PostFlood_' + POST_START + '_' + POST_END,
    region: aoi, scale: 10, maxPixels: 1e13, fileFormat: 'GeoTIFF'
  });
  Export.image.toDrive({
    image: s1Flood.unmask(0).toByte(), description: 'M3_' + NAME + '_S1Flood',
    folder: 'M3_GEE_exports', fileNamePrefix: 'M3_' + NAME + '_S1Flood',
    region: aoi, scale: 10, maxPixels: 1e13, fileFormat: 'GeoTIFF'
  });
}
