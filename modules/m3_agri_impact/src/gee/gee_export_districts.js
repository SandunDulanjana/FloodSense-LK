// Run in the GEE Code Editor, then press Run in the Tasks tab (right panel).
var d = ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level2')
          .filter(ee.Filter.eq('ADM0_NAME', 'Sri Lanka'));
print('Districts:', d.size());
Map.addLayer(d, {color: 'red'}, 'Sri Lanka districts');
Export.table.toDrive({
  collection: d.select(['ADM2_NAME']),
  description: 'SriLanka_districts',
  folder: 'M3_GEE_exports',
  fileNamePrefix: 'SriLanka_districts',
  fileFormat: 'GeoJSON'
});