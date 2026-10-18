# ===== M1 Step 10: Final model -> predictions for ALL buildings -> local web demo (offline-capable) =====
# Uses the best model chosen by the hypothesis tests (results/hypothesis_tests.json).
import os, json, glob, io, base64, shutil, time, datetime, numpy as np, pandas as pd, rasterio, urllib.request
from PIL import Image
R = '/content/drive/MyDrive/M1_Research'; RES = f'{R}/results'; DEMO = f'{R}/demo'; os.makedirs(f'{DEMO}/assets', exist_ok=True)
HT = json.load(open(f'{RES}/hypothesis_tests.json')); BEST = HT['best']; print('Best model (from hypothesis tests):', BEST)
CFG = json.load(open(f'{R}/records/step07_label_config.json'))
full = pd.read_parquet(f'{R}/M1_buildings_dataset_v2.parquet'); samp = pd.read_parquet(f'{R}/M1_sample_with_folds.parquet')
d = full.LABEL_dist_to_flood_m.values; full['y'] = np.where(d <= CFG['high_m'], 2, np.where(d <= CFG['medium_m'], 1, 0))
FEATS = ['X_B2','X_B3','X_B4','X_B8','X_B11','X_ndvi','X_ndwi','X_dem_m','X_slope_deg','X_hand_m',
         'X_dist_river_m','X_built_frac_100m','X_landcover','X_area_m2']
med = samp[FEATS].median()
t0 = time.time()
if BEST.startswith('T'):                                   # ---- tabular best model ----
    import xgboost as xgb, lightgbm as lgb
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    Xs = samp[FEATS].fillna(med).values.astype('float32'); ys = samp.y.values
    cw = len(ys) / (3 * np.bincount(ys, minlength=3))
    mdl = {'T1_LogReg': make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight='balanced')),
           'T2_RandomForest': RandomForestClassifier(n_estimators=300, min_samples_leaf=5, class_weight='balanced', n_jobs=-1, random_state=42),
           'T3_XGBoost': xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, tree_method='hist', random_state=42),
           'T4_LightGBM': lgb.LGBMClassifier(n_estimators=400, num_leaves=63, learning_rate=0.05, subsample=0.8, subsample_freq=1,
                                             colsample_bytree=0.8, class_weight='balanced', random_state=42, verbose=-1)}[BEST]
    (mdl.fit(Xs, ys, sample_weight=cw[ys]) if BEST == 'T3_XGBoost' else mdl.fit(Xs, ys))
    Xf = full[FEATS].fillna(med).values.astype('float32'); t1 = time.time(); prob = mdl.predict_proba(Xf); t_inf = time.time() - t1
    import joblib; joblib.dump(mdl, f'{RES}/final_model_{BEST}.joblib')
else:                                                       # ---- deep best model (uses classes defined in Step 8 cell) ----
    import torch, torch.nn.functional as F
    files = sorted(glob.glob(f'{R}/M1_raster_stack_v1*.tif'))
    with rasterio.open(files[0]) as s: S = np.nan_to_num(s.read().astype('float32'))
    S[8] = np.log1p(S[8]); P = 32
    def patches(df_):
        r0, c0 = df_.row.values - P // 2, df_.col.values - P // 2
        ir = r0[:, None] + np.arange(P)[None, :]; ic = c0[:, None] + np.arange(P)[None, :]
        return np.stack([S[b][ir[:, :, None], ic[:, None, :]] for b in range(10)], 1).astype('float16')
    Xs = torch.tensor(patches(samp), device=DEV); ys = samp.y.values
    mu_t = Xs.float().mean((0, 2, 3)).view(1, -1, 1, 1); sd_t = Xs.float().std((0, 2, 3)).view(1, -1, 1, 1) + 1e-6
    torch.manual_seed(42); np.random.seed(42); net = fix_head(build(BEST), BEST).to(DEV)
    opt = torch.optim.AdamW(net.parameters(), lr=LR.get(BEST, 3e-4), weight_decay=1e-4)
    steps = EPOCHS * int(np.ceil(len(ys) / BS)); sch = torch.optim.lr_scheduler.OneCycleLR(opt, LR.get(BEST, 3e-4), total_steps=steps)
    cwt = torch.tensor(len(ys) / (3 * np.bincount(ys, minlength=3)), dtype=torch.float32, device=DEV); scaler = torch.amp.GradScaler('cuda')
    for ep in range(EPOCHS):
        net.train(); perm = np.random.permutation(len(ys))
        for i in range(0, len(perm), BS):
            b = perm[i:i + BS]; xb = (Xs[torch.tensor(b, device=DEV)].float() - mu_t) / sd_t; yb = torch.tensor(ys[b], device=DEV)
            if np.random.rand() < .5: xb = xb.flip(3)
            xb = torch.rot90(xb, np.random.randint(4), (2, 3))
            with torch.autocast('cuda'): loss = F.cross_entropy(net(xb), yb, weight=cwt)
            opt.zero_grad(); scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); sch.step()
    torch.save(net.state_dict(), f'{RES}/final_model_{BEST}.pt'); net.eval(); probs = []; t1 = time.time()
    with torch.no_grad(), torch.autocast('cuda'):
        for i in range(0, len(full), 20000):
            xb = torch.tensor(patches(full.iloc[i:i + 20000]), device=DEV)
            for j in range(0, len(xb), 2048): probs.append(F.softmax(net((xb[j:j + 2048].float() - mu_t) / sd_t).float(), 1).cpu().numpy())
    prob = np.concatenate(probs); t_inf = time.time() - t1; del S
pred = prob.argmax(1)
print(f'Final model trained + predicted {len(full):,} buildings in {time.time()-t0:.0f}s (inference {t_inf:.1f}s = {t_inf/len(full)*1000*1000:.1f} ms per 1000 buildings)')
full['pred'] = pred; full['p_high'] = prob[:, 2]
in_sample = full.bid.isin(samp.bid)
from sklearn.metrics import f1_score
print(f'Agreement with SAR-derived label on buildings NOT in the 50k training sample: macro-F1 = {f1_score(full.y[~in_sample], full.pred[~in_sample], average="macro"):.3f}')
print('Predicted class counts (Low, Medium, High):', np.bincount(pred, minlength=3).tolist(), '| SAR label counts:', np.bincount(full.y, minlength=3).tolist())
full[['bid','lon','lat','y','pred','p_high','LABEL_dist_to_flood_m','X_hand_m','X_dem_m']].to_parquet(f'{RES}/predictions_all_buildings.parquet', index=False)

# ---- demo data (compact columnar JSON in a .js file so index.html works from file:// without a server) ----
lon = np.round(full.lon.values, 5); lat = np.round(full.lat.values, 5)
data = dict(lon=lon.tolist(), lat=lat.tolist(), y=full.y.astype(int).tolist(), p=full.pred.astype(int).tolist(),
            ph=np.round(full.p_high.values * 100).astype(int).tolist(), hand=np.round(full.X_hand_m.values, 1).tolist(),
            dist=np.round(np.minimum(full.LABEL_dist_to_flood_m.values, 9999)).astype(int).tolist())
# background images: cloud-free S2 RGB and SAR flood mask, both in lon/lat bounds of the AOI
from rasterio.warp import transform_bounds
with rasterio.open(sorted(glob.glob(f'{R}/M1_raster_stack_v1*.tif'))[0]) as s:
    rgb = s.read([3, 2, 1]).astype('float32'); bnds = transform_bounds(s.crs, 'EPSG:4326', *s.bounds)
rgb = np.clip(np.nan_to_num(rgb) / 2500.0, 0, 1) ** (1 / 1.2); img = Image.fromarray((np.moveaxis(rgb, 0, -1) * 255).astype('uint8'))
img = img.resize((img.width // 2, img.height // 2)); img.save(f'{DEMO}/assets/s2_rgb.jpg', quality=85)
with rasterio.open(sorted(glob.glob(f'{R}/M1_label_raster_v2*.tif'))[0]) as s: fl = s.read(1) > 0.5
ov = np.zeros(fl.shape + (4,), 'uint8'); ov[fl] = [0, 140, 255, 190]
Image.fromarray(ov).resize((fl.shape[1] // 2, fl.shape[0] // 2), Image.NEAREST).save(f'{DEMO}/assets/flood_mask.png')
b64 = lambda p, mt: f'data:{mt};base64,' + base64.b64encode(open(p, 'rb').read()).decode()
summary = pd.read_csv(f'{RES}/model_summary.csv').rename(columns={'Unnamed: 0': 'model'})
meta = dict(best=BEST, bounds=bnds, n=len(full), generated=datetime.datetime.now().isoformat(timespec='minutes'),
            classes=['Low (>300 m)', 'Medium (100-300 m)', 'High (<=100 m)'],
            summary=summary.round(4).to_dict('records'), tests={k: HT[k] for k in ['friedman', 'nemenyi_CD', 'mcnemar', 'wilcoxon', 'runner_up', 'bootstrap_ci']},
            infer_ms_per_1000=round(t_inf / len(full) * 1e6, 2),
            img_s2=b64(f'{DEMO}/assets/s2_rgb.jpg', 'image/jpeg'), img_flood=b64(f'{DEMO}/assets/flood_mask.png', 'image/png'))
with open(f'{DEMO}/assets/data.js', 'w') as f:
    f.write('window.M1DATA=' + json.dumps(data, separators=(',', ':')) + ';\nwindow.M1META=' + json.dumps(meta, default=float) + ';')
for fig in glob.glob(f'{RES}/figures/*.png'): shutil.copy(fig, f'{DEMO}/assets/')
try:
    urllib.request.urlretrieve('https://unpkg.com/deck.gl@8.9.35/dist.min.js', f'{DEMO}/assets/deckgl.min.js'); print('deck.gl saved for offline use')
except Exception as e: print('deck.gl download failed (demo will use CDN):', e)
print('Demo assets written to', DEMO, '| data.js size', round(os.path.getsize(f'{DEMO}/assets/data.js') / 1e6, 1), 'MB')

# ---- copy the demo page (web/index.html, run_demo.bat, README.txt from this repo) next to the generated assets, then zip ----
# In Colab the page files were written from embedded copies; here they are kept as normal files in modules/m1_house_impact/web/.
zp = shutil.make_archive(f'{R}/M1_demo', 'zip', DEMO)
print('Demo zip:', zp, round(os.path.getsize(zp) / 1e6, 1), 'MB')
