# M2-05: FINAL pixel-level test on the 15 hand-labelled Kelani Ditwah chips (pre-registered, decision D23).
# Run ONCE, only after the student has uploaded labelling_kit/KEL_labels.gpkg:
#   !python /content/drive/MyDrive/M2_flood_roads/src/m2_05_pixel_test.py
# Protocol fixed before labelling (D23): threshold P>=0.5 (no tuning); primary model = pre-selected model (selection.json);
# primary metric = water IoU over all labelled pixels of all chips (labels: water incl. permanent rivers); secondary:
# F1/precision/recall, flood-only (JRC occurrence>50 excluded), per stratum (urban / vegetated), cluster bootstrap over chips.
import os, sys, json, hashlib, datetime, numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio import features
ROOT = '/content/drive/MyDrive/M2_flood_roads'; K = f'{ROOT}/data/processed/kelani_ditwah'; KIT = f'{K}/labelling_kit'
OUT = f'{ROOT}/outputs/M2_05'; os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, f'{ROOT}/src')
from m2.metrics import scores
if os.path.exists(f'{OUT}/pixel_test_results.json'):
    raise SystemExit('M2-05 has already been run once (outputs/M2_05/pixel_test_results.json exists). Not re-running (D23).')
GP = f'{KIT}/KEL_labels.gpkg'
idx = json.load(open(f'{KIT}/kit_index.json')); sel = json.load(open(f'{ROOT}/outputs/M2_03/selection.json'))
WAT = gpd.read_file(GP, layer='water').to_crs(32644); UNS = gpd.read_file(GP, layer='unsure').to_crs(32644)
WAT = WAT[WAT.geometry.notna() & ~WAT.geometry.is_empty]; UNS = UNS[UNS.geometry.notna() & ~UNS.geometry.is_empty]
label_hash = hashlib.sha256(open(GP, 'rb').read()).hexdigest()

# ---- rasterise labels on each chip grid: inside chip 0 = not water, 1 = water, -1 = unsure (unsure wins)
LAB = {}
for ch in idx['chips']:
    cid = ch['chip_id']
    with rasterio.open(f'{KIT}/{cid}_post_db.tif') as s: T = s.transform; H, W = s.height, s.width; vv = s.read(1)
    lab = np.zeros((H, W), np.int16)
    if len(WAT): features.rasterize(((g, 1) for g in WAT.geometry), out=lab, transform=T)
    if len(UNS): features.rasterize(((g, -1) for g in UNS.geometry), out=lab, transform=T)
    lab[~np.isfinite(vv)] = -1
    LAB[cid] = lab
    with rasterio.open(f'{KIT}/{cid}_label_final.tif', 'w', driver='GTiff', height=H, width=W, count=1, dtype='int16',
                       crs='EPSG:32644', transform=T, nodata=-9999) as d: d.write(lab[None])
lab_summary = pd.DataFrame([{'chip_id': c, 'lc': ch['lc'], 'in_survey': ch['in_survey'], 'water_px': int((LAB[c] == 1).sum()),
                             'dry_px': int((LAB[c] == 0).sum()), 'unsure_px': int((LAB[c] == -1).sum())}
                            for ch in idx['chips'] for c in [ch['chip_id']]])
lab_summary.to_csv(f'{OUT}/label_summary.csv', index=False); print(lab_summary.to_string())
assert lab_summary.water_px.sum() > 0, 'No water polygons found in KEL_labels.gpkg (layer "water").'

# ---- predictions (saved by M2-03; no inference here), cropped to chip windows
with rasterio.open(f'{K}/jrc_occurrence.tif') as s: JRC = s.read(1)
MODELS = {os.path.basename(p)[5:-4]: p for p in [f'{K}/{f}' for f in os.listdir(K)] if os.path.basename(p).startswith(('prob_', 'pred_'))}
C = 256
def crop(a, ch): return a[ch['r']:ch['r'] + C, ch['c']:ch['c'] + C]
rows = []
for nm, path in sorted(MODELS.items()):
    with rasterio.open(path) as s: P = s.read(1)
    for ch in idx['chips']:
        cid = ch['chip_id']; lab = LAB[cid]; p = crop(P, ch); perm = crop(JRC, ch) > 50
        for scope, keep in [('all_water', lab >= 0), ('flood_only', (lab >= 0) & ~perm)]:
            k = keep & np.isfinite(p); y = lab[k] == 1; yh = p[k] >= 0.5
            rows.append({'model': nm, 'chip_id': cid, 'lc': ch['lc'], 'in_survey': ch['in_survey'], 'scope': scope,
                         'tp': int((y & yh).sum()), 'fp': int((~y & yh).sum()), 'fn': int((y & ~yh).sum()), 'tn': int((~y & ~yh).sum())})
R = pd.DataFrame(rows); R.to_csv(f'{OUT}/pixel_counts_per_chip.csv', index=False)

def agg(df):
    s = df[['tp', 'fp', 'fn', 'tn']].sum(); return pd.Series(scores(s.tp, s.fp, s.fn, s.tn))
rng = np.random.default_rng(0); chips = [c['chip_id'] for c in idx['chips']]
def boot(df, n=2000):
    v = []
    for _ in range(n):
        pick = rng.choice(chips, len(chips), replace=True)
        d = pd.concat([df[df.chip_id == c] for c in pick]); v.append(agg(d)['iou'])
    return np.nanpercentile(v, [2.5, 97.5]).round(4).tolist()
SUM = []
for (nm, scope), d in R.groupby(['model', 'scope']):
    for lc in ['all', 'urban', 'vegetated']:
        dd = d if lc == 'all' else d[d.lc == lc]
        SUM.append({'model': nm, 'scope': scope, 'lc': lc, **agg(dd).round(4).to_dict(), 'iou_ci95_chips': boot(dd) if lc == 'all' else None})
SUM = pd.DataFrame(SUM); SUM.to_csv(f'{OUT}/pixel_test_summary.csv', index=False)
prim = SUM[(SUM.model == f"{sel['selected_model']}") & (SUM.scope == 'all_water') & (SUM.lc == 'all')]
res = {'run_utc': datetime.datetime.now(datetime.UTC).isoformat(), 'labels_sha256': label_hash, 'protocol': 'D23',
       'selected_model': sel['selected_model'], 'primary': prim.to_dict('records'), 'n_chips': len(chips),
       'label_px': lab_summary[['water_px', 'dry_px', 'unsure_px']].sum().to_dict()}
json.dump(res, open(f'{OUT}/pixel_test_results.json', 'w'), indent=1, default=str)
print(SUM[(SUM.scope == 'all_water') & (SUM.lc == 'all')].sort_values('iou', ascending=False).to_string())
print(json.dumps(res, indent=1, default=str)); print('DONE M2_05 — do not re-run')
