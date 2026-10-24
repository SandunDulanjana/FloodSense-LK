# M3 web app: Agricultural and Livelihood Impact Assessment

A zoomable web map (crop classes, flood damage, radar flood extent) with area tables, validation,
explainable-AI plots and a method page. No build step and no server code: it is plain HTML, CSS and JavaScript
(Leaflet is included in `vendor/`).

## 1. Make the data (Colab or PC, after the map and damage scripts have run)
```
python src/m3_export_web.py
```
This creates `web/data/` (map tiles, `summary.json`, `districts.geojson`, plot images).
Zoom levels 8 to 13 by default. Use `M3_ZMAX=14` for more detail (more files).

## 2. Open it on your own computer (stand-alone demo)
```
cd web
python -m http.server 8000
```
Visit http://localhost:8000 . Opening index.html by double-click does not work (the browser blocks loading data files).

## 3. Put it online (optional)
Drag the whole `web` folder onto https://app.netlify.com/drop , or publish it with GitHub Pages.

## 4. Plug it into the team dashboard (M4)
Copy the `web` folder (with its `data` folder) into the dashboard's static files, for example `public/m3/`, then add one dashboard tab that shows it in an iframe:
```html
<iframe src="/m3/index.html?embed=1&tabs=1&tab=map" style="width:100%;height:100%;border:0" title="M3 Agricultural impact"></iframe>
```
React example:
```jsx
export default function M3Impact() {
  return <iframe src="/m3/index.html?embed=1&tab=map" title="M3 Agricultural impact"
                 style={{ width: "100%", height: "calc(100vh - 64px)", border: 0 }} />;
}
```
URL options: `embed=1` (compact header), `tabs=0` (hide the tab bar), `tab=map|areas|validation|xai|about`,
`theme=light|dark`, `data=<url>` (load `summary.json` and tiles from another address).

The dashboard can also control the page with `postMessage`:
```js
frame.contentWindow.postMessage({ type: "m3:setDistrict", district: "Gampaha" }, "*");
frame.contentWindow.postMessage({ type: "m3:setLayers", layers: ["crop", "dmg_paddy"] }, "*");
frame.contentWindow.postMessage({ type: "m3:setTab", tab: "validation" }, "*");
```
The page sends `{ type: "m3:ready" }` to its parent when it has loaded.

## Data for the other modules
`data/summary.json` holds every table the page shows (areas, damage, validation, model metrics, layer list).
It is the simplest file for M4 to read if it wants numbers instead of the map.
