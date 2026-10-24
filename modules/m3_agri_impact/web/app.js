/* M3 Agricultural and Livelihood Impact Assessment: web app.
   Stand-alone: open index.html through any static web server.
   Embedded in another dashboard: <iframe src=".../index.html?embed=1&tab=map"> (see README.md). */
(function () {
  "use strict";
  var params = new URLSearchParams(location.search);
  if (params.get("embed") === "1") document.body.classList.add("embed");
  if (params.get("tabs") === "0") document.body.classList.add("notabs");
  if (params.get("theme")) document.documentElement.setAttribute("data-theme", params.get("theme"));

  var DATA_URL = params.get("data") || "data/";
  var CROP_COL = { Paddy: "#3dbb4a", Tea: "#c8553d", Other: "#e9c46a" };
  var state = { data: null, map: null, tiles: {}, boundary: null, selected: "all", opacity: 0.85, base: null };

  function $(s, r) { return (r || document).querySelector(s); }
  function el(tag, attrs, html) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (html !== undefined) n.innerHTML = html;
    return n;
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function num(v, d) {
    if (v === null || v === undefined || v === "" || isNaN(Number(v))) return v == null ? "" : esc(v);
    return Number(v).toLocaleString("en-US", { maximumFractionDigits: d == null ? 0 : d, minimumFractionDigits: 0 });
  }
  function showError(msg) { var e = $("#error"); e.innerHTML = msg; e.hidden = false; }

  /* ---------- data loading ---------- */
  fetch(DATA_URL + "summary.json").then(function (r) {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }).then(function (d) {
    state.data = d;
    init();
  }).catch(function (e) {
    showError("<b>Could not load data/summary.json</b> (" + esc(e.message) + ").<br>Run <code>python src/m3_export_web.py</code> first, then open this page through a web server, for example <code>python -m http.server 8000</code> inside the <code>web</code> folder. Opening the file by double-click will not work.");
  });

  function init() {
    initTabs();
    initMap();
    initPanel();
    renderStats();
    renderAreas();
    renderValidation();
    renderXai();
    renderAbout();
    var t = params.get("tab") || (location.hash || "").replace("#", "");
    if (t) showTab(t);
    if (window.parent !== window) window.parent.postMessage({ type: "m3:ready", districts: state.data.districts }, "*");
  }

  /* ---------- tabs ---------- */
  function showTab(name) {
    var found = false;
    document.querySelectorAll("#tabs button").forEach(function (b) {
      var on = b.dataset.tab === name; if (on) found = true;
    });
    if (!found) return;
    document.querySelectorAll("#tabs button").forEach(function (b) { b.classList.toggle("on", b.dataset.tab === name); });
    document.querySelectorAll(".tab").forEach(function (s) { s.classList.toggle("on", s.id === "tab-" + name); });
    if (name === "map" && state.map) setTimeout(function () { state.map.invalidateSize(); }, 50);
  }
  function initTabs() {
    document.querySelectorAll("#tabs button").forEach(function (b) {
      b.addEventListener("click", function () { showTab(b.dataset.tab); });
    });
  }

  /* ---------- map ---------- */
  function initMap() {
    var map = L.map("map", { zoomControl: false, minZoom: 6, maxZoom: 18 });
    L.control.zoom({ position: "topright" }).addTo(map);
    state.map = map;
    var osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" });
    var sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, attribution: "Imagery &copy; Esri" });
    state.basemaps = { osm: osm, sat: sat };
    state.base = osm.addTo(map);
    L.control.scale({ imperial: false }).addTo(map);

    var v = state.data.view;
    if (v) map.fitBounds([[v[1], v[0]], [v[3], v[2]]]); else map.setView([7.5, 80.7], 8);

    fetch(DATA_URL + "districts.geojson").then(function (r) { return r.json(); }).then(function (gj) {
      state.boundary = L.geoJSON(gj, {
        style: function (f) {
          return f.properties.studied
            ? { color: "#111", weight: 2, fill: false }
            : { color: "#8a948e", weight: 0.8, fill: false, opacity: 0.8 };
        },
        onEachFeature: function (f, layer) {
          if (f.properties.studied) {
            layer.bindTooltip(f.properties.name, { sticky: true });
            layer.on("click", function () { selectDistrict(f.properties.name); });
          }
        }
      }).addTo(map);
      state.boundary.eachLayer(function (l) { if (!l.feature.properties.studied) l.bringToBack(); });
    }).catch(function () { /* boundaries are optional */ });

    state.data.layers.forEach(function (L0, idx) {
      var group = L.layerGroup();
      Object.keys(L0.districts).forEach(function (d) {
        var b = L0.districts[d];
        var tl = L.tileLayer(DATA_URL + L0.path + "/" + d + "/{z}/{x}/{y}.png", {
          minZoom: L0.minZoom, maxZoom: 18, maxNativeZoom: L0.maxNativeZoom, opacity: state.opacity,
          bounds: [[b[1], b[0]], [b[3], b[2]]], zIndex: 300 + idx, errorTileUrl: "data:image/gif;base64,R0lGODlhAQABAAAAACw="
        });
        group.addLayer(tl);
      });
      state.tiles[L0.id] = group;
      if (L0.on) group.addTo(map);
    });
  }

  function selectDistrict(name) {
    state.selected = name;
    $("#district").value = name;
    var bs = (state.data.layers[0] && state.data.layers[0].districts) || {};
    if (name !== "all" && bs[name]) { var b = bs[name]; state.map.fitBounds([[b[1], b[0]], [b[3], b[2]]]); }
    else if (state.data.view) { var v = state.data.view; state.map.fitBounds([[v[1], v[0]], [v[3], v[2]]]); }
    renderStats();
  }

  function initPanel() {
    var sel = $("#district");
    sel.appendChild(el("option", { value: "all" }, "All three districts"));
    state.data.districts.forEach(function (d) { sel.appendChild(el("option", { value: d }, d)); });
    sel.addEventListener("change", function () { selectDistrict(sel.value); });

    var groups = {};
    state.data.layers.forEach(function (L0) { (groups[L0.group] = groups[L0.group] || []).push(L0); });
    var host = $("#layers");
    Object.keys(groups).forEach(function (g) {
      var box = el("div", { "class": "layer-group" }, "<h4>" + esc(g) + "</h4>");
      groups[g].forEach(function (L0) {
        var row = el("label", { "class": "layer-row" });
        var cb = el("input", { type: "checkbox" }); cb.checked = !!L0.on;
        cb.addEventListener("change", function () {
          if (cb.checked) state.tiles[L0.id].addTo(state.map); else state.map.removeLayer(state.tiles[L0.id]);
          renderLegend();
        });
        row.appendChild(cb); row.appendChild(el("span", {}, esc(L0.name)));
        row.dataset.layer = L0.id;
        box.appendChild(row);
      });
      host.appendChild(box);
    });
    $("#opacity").addEventListener("input", function (e) {
      state.opacity = Number(e.target.value);
      Object.keys(state.tiles).forEach(function (k) { state.tiles[k].eachLayer(function (l) { l.setOpacity(state.opacity); }); });
    });
    $("#basemap").addEventListener("click", function (e) {
      var b = e.target.dataset.b; if (!b) return;
      state.map.removeLayer(state.base); state.base = state.basemaps[b].addTo(state.map); state.base.bringToBack();
      document.querySelectorAll("#basemap button").forEach(function (x) { x.classList.toggle("on", x.dataset.b === b); });
    });
    $("#panel-toggle").addEventListener("click", function () { $("#panel").classList.toggle("closed"); });
    if (window.innerWidth < 760) $("#panel").classList.add("closed");
    renderLegend();
  }

  function renderLegend() {
    var host = $("#legend"); host.innerHTML = "";
    state.data.layers.forEach(function (L0) {
      if (!state.map.hasLayer(state.tiles[L0.id])) return;
      var g = el("div", { "class": "legend-group" }, "<b>" + esc(L0.name) + "</b>");
      L0.legend.forEach(function (it) { g.appendChild(el("span", { "class": "sw" }, '<i style="background:' + it[1] + '"></i>' + esc(it[0]))); });
      host.appendChild(g);
    });
    if (!host.children.length) host.innerHTML = '<span class="hint">No layer switched on.</span>';
  }

  /* ---------- small tables ---------- */
  function table(cols, rows, opts) {
    opts = opts || {};
    var h = "<table class='t'><thead><tr>" + cols.map(function (c) { return "<th class='" + (c.left ? "l" : "") + "'>" + esc(c.h) + "</th>"; }).join("") + "</tr></thead><tbody>";
    rows.forEach(function (r) {
      h += "<tr>" + cols.map(function (c) {
        var v = c.f ? c.f(r) : num(r[c.k], c.d);
        return "<td class='" + (c.left ? "l" : "") + "'>" + v + "</td>";
      }).join("") + "</tr>";
    });
    return "<div class='tblwrap'>" + h + "</tbody></table></div>";
  }
  function badge(pass) { return "<span class='badge " + (pass ? "good" : "bad") + "'>" + (pass ? "Meets 80%" : "Below 80%") + "</span>"; }
  function truthy(v) { return v === true || v === "True" || v === "true" || v === 1; }

  function filterD(rows) {
    return state.selected === "all" ? rows : rows.filter(function (r) { return r.district === state.selected; });
  }

  /* ---------- map statistics card ---------- */
  function renderStats() {
    var box = $("#stats"), d = state.data;
    var title = state.selected === "all" ? "All three districts" : state.selected;
    var areas = filterD(d.areas), dmg = filterD(d.damage);
    var html = "<h3>" + esc(title) + "</h3>";
    if (areas.length) {
      var agg = {};
      areas.forEach(function (r) { agg[r["class"]] = (agg[r["class"]] || 0) + Number(r.area_ha); });
      var tot = Object.keys(agg).reduce(function (s, k) { return s + agg[k]; }, 0);
      html += "<table><thead><tr><th>Crop</th><th>Area (ha)</th><th>Share</th></tr></thead><tbody>";
      ["Paddy", "Tea", "Other"].forEach(function (k) {
        if (agg[k] == null) return;
        html += "<tr><td><span class='sw'><i style='background:" + CROP_COL[k] + "'></i>" + k + "</span></td><td>" + num(agg[k]) + "</td><td>" + num(100 * agg[k] / tot, 1) + "%</td></tr>";
      });
      html += "</tbody></table>";
    }
    if (dmg.length) {
      var by = {};
      dmg.forEach(function (r) {
        var o = by[r.crop] = by[r.crop] || { a: 0, x: 0 };
        o.a += Number(r.assessed_ha); o.x += Number(r.damaged_ha);
      });
      html += "<table><thead><tr><th>Flood damage</th><th>Damaged (ha)</th><th>% of crop</th></tr></thead><tbody>";
      ["Paddy", "Tea", "Other"].forEach(function (k) {
        if (!by[k] || by[k].a < 50) return;
        html += "<tr><td>" + k + "</td><td>" + num(by[k].x) + "</td><td>" + num(100 * by[k].x / by[k].a, 1) + "%</td></tr>";
      });
      html += "</tbody></table>";
    }
    html += "<div class='hint'>Click a district outline to focus on it. Details are in the other tabs.</div>";
    box.innerHTML = html;
  }

  /* ---------- Areas & damage tab ---------- */
  function renderAreas() {
    var d = state.data, host = $("#areas-page");
    var h = "<h2>Crop areas and flood damage</h2><p>Hectares are counted from classified 10 m Sentinel-2 pixels, using the true ground area of each pixel. Only land inside the national cultivated-land mask is classified.</p>";
    h += "<h3>Crop areas by district</h3>";
    if (d.areas.length) {
      var max = Math.max.apply(null, d.areas.map(function (r) { return Number(r.area_ha); }));
      h += table([
        { h: "District", k: "district", left: true }, { h: "Crop", k: "class", left: true },
        { h: "Area (ha)", f: function (r) { return num(r.area_ha) + "<span class='bar' style='width:" + Math.max(2, 90 * r.area_ha / max) + "px;background:" + (CROP_COL[r["class"]] || "#888") + "'></span>"; } },
        { h: "Share of mapped", f: function (r) { return num(r.share_of_mapped_pct, 1) + "%"; } },
        { h: "Pixels", k: "pixels" }
      ], d.areas);
    } else h += "<div class='empty'>area_by_district.csv was not found.</div>";

    h += "<h3>Flood damage by crop</h3><p>Damage is a drop in NDVI that is clearly larger than the normal change of the same crop in non-flooded pixels (2, 3 and 4 robust standard deviations for low, moderate and severe).</p>";
    if (d.damage.length) {
      h += table([
        { h: "District", k: "district", left: true }, { h: "Crop", k: "crop", left: true },
        { h: "Assessed (ha)", k: "assessed_ha" }, { h: "Low", k: "low_ha" }, { h: "Moderate", k: "moderate_ha" },
        { h: "Severe", k: "severe_ha" }, { h: "Damaged (ha)", k: "damaged_ha" },
        { h: "% of crop", f: function (r) { return num(r.damage_pct_of_assessed, 1) + "%"; } },
        { h: "Damaged and radar-flooded (ha)", k: "damaged_and_S1_flooded_ha" },
        { h: "Radar-flooded (ha)", k: "S1_flooded_ha" }
      ], d.damage);
    } else h += "<div class='empty'>crop_damage_by_district.csv was not found.</div>";
    if (d.damage_sensitivity.length) {
      h += "<h3>How sensitive is Paddy damage to the settings?</h3>" + table(Object.keys(d.damage_sensitivity[0]).map(function (k) { return { h: k.replace(/_/g, " "), k: k, d: 2, left: k === "district" }; }), d.damage_sensitivity);
    }
    host.innerHTML = h;
  }

  /* ---------- Validation tab ---------- */
  function renderValidation() {
    var d = state.data, host = $("#validation-page");
    var h = "<h2>Validation against official figures</h2><p>Agreement = 1 &minus; |map &minus; official| / official. The project target is 80%. Official figures measure slightly different things from the map, so read the notes under each table.</p>";
    h += "<h3>Crop area (paddy and tea)</h3>";
    if (d.area_validation.length) {
      h += table([
        { h: "District", k: "district", left: true }, { h: "Crop", k: "crop", left: true },
        { h: "Map (ha)", k: "satellite_ha" }, { h: "Official (ha)", k: "reference_ha" },
        { h: "Difference", f: function (r) { return num(r.difference_pct, 1) + "%"; } },
        { h: "Agreement", f: function (r) { return num(r.agreement_pct, 1) + "%"; } },
        { h: "Target", f: function (r) { return badge(truthy(r.meets_80pct)); } }
      ], d.area_validation);
      h += "<div class='note'><b>Paddy:</b> official figure is the area sown in Maha 2025/26 (Department of Census and Statistics). The map shows paddy land that is allowed by the national land-use map, so it is not exactly the same thing.<br><b>Tea:</b> official figure is registered small-holding land (Tea Board, updated 2023). It does not include large estates. Tea is only meaningful for Ratnapura, because the national map shows almost no tea in Colombo and Gampaha.</div>";
    } else h += "<div class='empty'>area_validation.csv was not found. Run m3_area_validation.py.</div>";

    h += "<h3>Paddy flood damage against the Department of Agriculture</h3>";
    if (d.damage_validation.length) {
      h += table([
        { h: "District", k: "district", left: true }, { h: "Map: damaged paddy (ha)", k: "damaged_ha", d: 0 },
        { h: "Official: affected paddy (ha)", k: "paddy_damaged_ha_ref" },
        { h: "Agreement", f: function (r) { return num(r.agreement_pct, 1) + "%"; } },
        { h: "Target", f: function (r) { return badge(truthy(r.meets_80pct)); } }
      ], d.damage_validation);
      h += "<div class='note'>The Department of Agriculture reports <i>affected</i> area, which includes land that was under water. This map reports crops whose NDVI stayed clearly lower 3&ndash;6 weeks later. The districts rank the same way in both, but the map finds less damage.</div>";
    } else h += "<div class='empty'>damage_validation_paddy.csv was not found.</div>";

    if (d.landuse_check.length) {
      h += "<h3>Do the training points sit in the right national land-use class?</h3><p>Share (%) of training points per class. Paddy points should be in Paddy, Tea points in Tea.</p>";
      var keys = Object.keys(d.landuse_check[0]);
      h += table(keys.map(function (k) { return { h: k.replace(/_/g, " "), k: k, d: 1, left: k === "crop_type" }; }), d.landuse_check);
    }
    if (d.model_comparison.length) {
      h += "<h3>Crop classifier: cross-validation results</h3><p>Field-level cross-validation: pixels of one field are never in both training and testing.</p>";
      h += table(Object.keys(d.model_comparison[0]).map(function (k) { return { h: k.replace(/_/g, " "), k: k, d: 3, left: /model|set|name|feature/i.test(k) }; }), d.model_comparison);
    }
    if (d.per_class_metrics.length) {
      h += "<h3>Per-class scores</h3>" + table(Object.keys(d.per_class_metrics[0]).map(function (k) { return { h: k.replace(/_/g, " "), k: k, d: 3, left: /model|class|set|name|feature/i.test(k) }; }), d.per_class_metrics);
    }
    host.innerHTML = h;
  }

  /* ---------- Explainable AI tab ---------- */
  function renderXai() {
    var d = state.data, host = $("#xai-page");
    var names = { xai: "Explainable AI (SHAP and importance)", evaluation: "Evaluation plots", model: "Model results", map: "Map outputs", damage: "Damage outputs" };
    var h = "<h2>Explainable AI and evaluation plots</h2><p>These plots explain which features drive the crop classifier (for example terrain for Tea) and how well it performs on unseen fields. Click a plot to enlarge it.</p>";
    var cats = []; d.images.forEach(function (i) { if (cats.indexOf(i.category) < 0) cats.push(i.category); });
    if (!cats.length) { host.innerHTML = h + "<div class='empty'>No plots found. Run the evaluation and XAI scripts, then export again.</div>"; return; }
    var cur = cats.indexOf("xai") >= 0 ? "xai" : cats[0];
    h += "<div class='chips' id='xai-chips'>" + cats.map(function (c) { return "<button data-c='" + c + "' class='" + (c === cur ? "on" : "") + "'>" + esc(names[c] || c) + "</button>"; }).join("") + "</div><div class='gallery' id='xai-gallery'></div>";
    host.innerHTML = h;
    function draw(c) {
      var g = $("#xai-gallery"); g.innerHTML = "";
      d.images.filter(function (i) { return i.category === c; }).forEach(function (i) {
        var f = el("figure", {}, "<img loading='lazy' alt='" + esc(i.title) + "' src='" + DATA_URL + esc(i.file) + "'><figcaption>" + esc(i.title) + "</figcaption>");
        f.addEventListener("click", function () { openBox(DATA_URL + i.file, i.title); });
        g.appendChild(f);
      });
    }
    draw(cur);
    $("#xai-chips").addEventListener("click", function (e) {
      var c = e.target.dataset.c; if (!c) return;
      document.querySelectorAll("#xai-chips button").forEach(function (b) { b.classList.toggle("on", b === e.target); });
      draw(c);
    });
  }
  function openBox(src, cap) {
    var b = $("#lightbox"); $("img", b).src = src; $("p", b).textContent = cap; b.hidden = false;
  }
  $("#lightbox").addEventListener("click", function () { this.hidden = true; });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") $("#lightbox").hidden = true; });

  /* ---------- About tab ---------- */
  function renderAbout() {
    $("#about-page").innerHTML =
      "<h2>Method and limits</h2>" +
      "<h3>What this module does</h3><p>It maps Paddy, Tea and Other cultivated crops before Cyclone Ditwah (November 2025) and estimates crop-specific flood damage for Ratnapura, Colombo and Gampaha.</p>" +
      "<h3>Steps</h3><p><b>1. Cultivated land.</b> Only land inside crop-capable classes of the national land-use map (Survey Department / SLNSDI Planning_Cadastre, Landuse layer) is classified. Forest, built-up land, water, roads, sand and rock stay unclassified.<br>" +
      "<b>2. Crop type.</b> A Random Forest, trained on 100 digitised fields with 15 Sentinel-2 and terrain features (pre-flood composite, 1 Oct&ndash;5 Nov 2025), labels each 10 m pixel. Paddy is allowed only where the national map shows Paddy or abandoned paddy, and Tea only where it shows Tea.<br>" +
      "<b>3. Damage.</b> NDVI change between the pre-flood and a post-flood composite (10 Dec 2025&ndash;16 Jan 2026) is compared with the normal change of the same crop in non-flooded pixels. Sentinel-1 radar flood pixels are shown as supporting evidence.<br>" +
      "<b>4. Explanation.</b> SHAP and permutation importance show which features drive the classifier.</p>" +
      "<h3>Limits to keep in mind</h3>" +
      "<div class='note'><ul style='margin:0;padding-left:18px'>" +
      "<li>The national land-use polygons were mostly made in 2016&ndash;2017, so recent land-use change is not captured. Total cropland extent comes from that map, not from the model.</li>" +
      "<li>Official paddy figures are sown area for one season. The map shows paddy land, so it is not identical.</li>" +
      "<li>Tea training fields are almost all in Ratnapura. Tea results for Colombo and Gampaha are not reliable.</li>" +
      "<li>The Department of Agriculture reports flood-affected area. The map reports crop decline still visible 3&ndash;6 weeks later, so it finds less damage.</li>" +
      "<li>&ldquo;Other&rdquo; groups many crops (rubber, coconut, home gardens and more). It has no official reference figure.</li>" +
      "<li>The pre-flood image is one composite, so sown and fallow paddy fields cannot be separated reliably.</li>" +
      "</ul></div>" +
      "<h3>Data sources</h3><p>Sentinel-2 SR and Sentinel-1 GRD (Copernicus, via Google Earth Engine); SRTM terrain; FAO GAUL district boundaries; national land-use map (SLNSDI Planning_Cadastre, Landuse); Department of Census and Statistics paddy statistics (Maha 2025/26); Tea Board small-holding registration (updated 2023); Department of Agriculture flood-affected crop area map (17 December 2025).</p>" +
      "<p>Generated: " + esc(state.data.generated) + "</p>";
  }

  /* ---------- messages from a host dashboard (optional) ---------- */
  window.addEventListener("message", function (e) {
    var m = e.data || {};
    if (!state.data) return;
    if (m.type === "m3:setTab") showTab(m.tab);
    if (m.type === "m3:setDistrict") selectDistrict(m.district || "all");
    if (m.type === "m3:setLayers" && Array.isArray(m.layers)) {
      state.data.layers.forEach(function (L0) {
        var on = m.layers.indexOf(L0.id) >= 0, g = state.tiles[L0.id];
        if (on && !state.map.hasLayer(g)) g.addTo(state.map);
        if (!on && state.map.hasLayer(g)) state.map.removeLayer(g);
        var row = document.querySelector(".layer-row[data-layer='" + L0.id + "'] input"); if (row) row.checked = on;
      });
      renderLegend();
    }
  });
})();
