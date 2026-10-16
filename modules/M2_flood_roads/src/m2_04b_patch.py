# M2-04b patch (decision D22) — %run -i /content/drive/MyDrive/M2_flood_roads/src/m2_04b_patch.py
# 1) Replace the degenerate t_low rule (recall>=0.8 -> 0.02, i.e. ~all roads 'moderate') with a lift rule fitted on
#    CALIBRATION blocks only: t_low = lowest threshold whose calib precision >= 2 x calib prevalence of affected length.
#    t_high (max calib F1) is unchanged. Evaluation blocks are used only for reporting, as before.
# 2) Build a light app package: raster road-class overlay PNG + vector GeoJSON for high-exposure segments only.
import os, json, shutil, zipfile, datetime
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio import features
from PIL import Image
ROOT = '/content/drive/MyDrive/M2_flood_roads'; K = f'{ROOT}/data/processed/kelani_ditwah'; OUT = f'{ROOT}/outputs/M2_04'
A = f'{ROOT}/app_data'

S = gpd.read_file(f'{OUT}/road_segments_risk.gpkg').to_crs(32644)
S['structure'] = S.structure.astype(bool); S['ref_affected'] = S.ref_affected.astype(bool)
v1 = json.load(open(f'{OUT}/road_summary.json'))
if not os.path.exists(f'{OUT}/road_summary_v1.json'):
    shutil.copy(f'{OUT}/road_summary.json', f'{OUT}/road_summary_v1.json')
    shutil.copy(f'{OUT}/road_level_eval_evalblocks.csv', f'{OUT}/road_level_eval_evalblocks_v1.csv')

def prf(pred, ref, w):
    tp = (w * (pred & ref)).sum(); fp = (w * (pred & ~ref)).sum(); fn = (w * (~pred & ref)).sum()
    p, r = tp / max(tp + fp, 1e-9), tp / max(tp + fn, 1e-9); return dict(precision=p, recall=r, f1=2 * p * r / max(p + r, 1e-9))

cal = S[(S.half == 'calib') & ~S.structure]; ev = S[(S.half == 'eval') & ~S.structure]
prev_cal = float((cal.len_m * cal.ref_affected).sum() / cal.len_m.sum())
grid = np.round(np.arange(0.01, 0.81, 0.01), 2)
curve = pd.DataFrame([{'t': t, **prf((cal.exposure >= t).values, cal.ref_affected.values, cal.len_m.values)} for t in grid])
t_high = float(curve.loc[curve.f1.idxmax(), 't'])
ok = curve[(curve.precision >= 2 * prev_cal) & (curve.t <= t_high)]
t_low = float(ok.t.min()) if len(ok) else t_high
print(f'calib prevalence={prev_cal:.3f}  t_low={t_low}  t_high={t_high}')

def classify(e):
    return np.where(np.isnan(e), 'no data', np.where(e >= t_high, 'high', np.where(e >= t_low, 'moderate', 'low')))
S['risk_class'] = classify(S.exposure.values); S.loc[S.structure, 'risk_class'] = 'structure (bridge) - check'

ev = S[(S.half == 'eval') & ~S.structure]
rules = {'continuous: exposure >= t_high (high)': ev.exposure >= t_high,
         'continuous: exposure >= t_low (moderate or high)': ev.exposure >= t_low,
         'binary: touches any P>=0.5 pixel': ev.touch.astype(bool), 'binary: >=50% of samples wet': ev.frac_wet >= 0.5}
RES = []
for name, pred in rules.items():
    for lc in ['all', 'urban', 'vegetated', 'cropland']:
        sub = ev if lc == 'all' else ev[ev.lc == lc]
        pp = pred.loc[sub.index].values
        RES.append({'rule': name, 'lc': lc, 'n_seg': len(sub), 'km': sub.len_m.sum() / 1000, 'flagged_km': (sub.len_m * pp).sum() / 1000,
                    'ref_affected_km': (sub.len_m * sub.ref_affected).sum() / 1000,
                    **{k: round(v, 4) for k, v in prf(pp, sub.ref_affected.values, sub.len_m.values).items()}})
RES = pd.DataFrame(RES); RES.to_csv(f'{OUT}/road_level_eval_evalblocks.csv', index=False)
curve.to_csv(f'{OUT}/threshold_curve_calib.csv', index=False)
ev_curve = pd.DataFrame([{'t': t, **prf((ev.exposure >= t).values, ev.ref_affected.values, ev.len_m.values)} for t in grid])
ev_curve.to_csv(f'{OUT}/threshold_curve_eval.csv', index=False)
print(RES[RES.lc == 'all'].round(3).to_string())

# sensitivity of class lengths to t_low / t_high (+-0.01, +-0.02)
sens = []
for dl in [-0.02, -0.01, 0, 0.01, 0.02]:
    for dh in [-0.02, 0, 0.02]:
        tl, th = max(0.01, t_low + dl), t_high + dh
        if tl > th: continue
        e = S.exposure.where(~S.structure)
        sens.append({'t_low': round(tl, 2), 't_high': round(th, 2), 'km_high': float(S.len_m[e >= th].sum() / 1000),
                     'km_moderate': float(S.len_m[(e >= tl) & (e < th)].sum() / 1000), 'km_low': float(S.len_m[e < tl].sum() / 1000),
                     **{f'eval_{k}': v for k, v in prf((ev.exposure >= th).values, ev.ref_affected.values, ev.len_m.values).items()}})
pd.DataFrame(sens).round(3).to_csv(f'{OUT}/threshold_sensitivity.csv', index=False)

summ = dict(v1); summ.update({'t_low': t_low, 't_high': t_high, 'calib_prevalence': prev_cal,
    't_rule': 't_high = max F1 on calibration blocks; t_low = lowest t with calibration precision >= 2x calibration prevalence (D22)',
    'km_by_class': (S.groupby('risk_class').len_m.sum() / 1000).round(1).to_dict(),
    'n_by_class': S.risk_class.value_counts().to_dict(), 'patched_utc': datetime.datetime.now(datetime.UTC).isoformat(),
    'v1_rule_note': 'v1 t_low=0.02 (recall>=0.8 rule) classified ~88% of road length as moderate; replaced (D22).'})
json.dump(summ, open(f'{OUT}/road_summary.json', 'w'), indent=1, default=str); print(json.dumps(summ['km_by_class']))
S.to_crs(4326).to_file(f'{OUT}/road_segments_risk.gpkg', driver='GPKG')

# ---------------- light app package
os.makedirs(A, exist_ok=True)
for fbig in ['road_segments_risk.geojson']:
    if os.path.exists(f'{A}/{fbig}'): os.remove(f'{A}/{fbig}')
with rasterio.open(f'{K}/survey_extent.tif') as s: prof = s.profile; T = s.transform; H, W = s.height, s.width
code = {'low': 1, 'moderate': 2, 'high': 3, 'structure (bridge) - check': 4}
order = ['low', 'moderate', 'structure (bridge) - check', 'high']            # burn high last so it stays visible
ras = np.zeros((H, W), np.uint8)
for c in order:
    g = S[S.risk_class == c].geometry
    if len(g): features.rasterize(((geom, code[c]) for geom in g), out=ras, transform=T, all_touched=True)
pal = {0: (0, 0, 0, 0), 1: (26, 152, 80, 150), 2: (243, 156, 18, 230), 3: (215, 48, 39, 255), 4: (90, 90, 90, 230)}
rgba = np.zeros((H, W, 4), np.uint8)
for k, v in pal.items(): rgba[ras == k] = v
Image.fromarray(rgba).save(f'{A}/roads_overlay.png', optimize=True)
hi = S[S.risk_class == 'high'].to_crs(4326).copy()
hi['geometry'] = hi.geometry.simplify(0.00003)
hi = hi[['seg_id', 'name', 'highway', 'lc', 'len_m', 'exposure', 'frac_wet', 'ref_frac', 'geometry']]
hi['exposure'] = hi.exposure.round(3); hi['frac_wet'] = hi.frac_wet.round(2); hi['len_m'] = hi.len_m.round(0); hi['ref_frac'] = hi.ref_frac.round(2)
hi['name'] = hi['name'].fillna('').astype(str).replace({'nan': '', 'None': ''})
hi.to_file(f'{A}/roads_high.geojson', driver='GeoJSON', COORDINATE_PRECISION=6)
c = hi.geometry.centroid
top = hi.assign(lat=c.y.round(5), lon=c.x.round(5)).drop(columns='geometry')
top[top['name'] != ''].sort_values('exposure', ascending=False).head(400).to_csv(f'{A}/roads_high_named_top.csv', index=False)
# shrink SAR background (14 MB -> grayscale+alpha, half resolution)
sv = Image.open(f'{A}/sar_vv.png').convert('LA'); sv = sv.resize((sv.width // 2, sv.height // 2)); sv.save(f'{A}/sar_vv.png', optimize=True)
for fsrc in [f'{OUT}/road_summary.json', f'{OUT}/road_level_eval_evalblocks.csv', f'{OUT}/threshold_curve_eval.csv',
             f'{OUT}/threshold_curve_calib.csv', f'{OUT}/threshold_sensitivity.csv', f'{OUT}/road_summary_v1.json']:
    shutil.copy(fsrc, A)
zp = f'{ROOT}/M2_app_data.zip'
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for fn in sorted(os.listdir(A)): z.write(f'{A}/{fn}', f'app_data/{fn}')
print({fn: round(os.path.getsize(f'{A}/{fn}') / 1e6, 2) for fn in sorted(os.listdir(A))})
print(zp, round(os.path.getsize(zp) / 1e6, 1), 'MB'); print('DONE M2_04b')
