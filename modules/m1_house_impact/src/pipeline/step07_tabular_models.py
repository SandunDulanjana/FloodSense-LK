# ===== M1 Step 7: Labels, spatial folds, and tabular models (LR, RF, XGBoost, LightGBM) =====
import os, json, time, datetime, numpy as np, pandas as pd
os.makedirs('/content/drive/MyDrive/M1_Research/records', exist_ok=True)
json.dump({'high_m': 100, 'medium_m': 300, 'n_sample': 50000,
           'reason': 'High<=100 m (5.4% of buildings), Medium 100-300 m (~20%), Low >300 m (~75%); <=50 m too rare (1.35%)'},
          open('/content/drive/MyDrive/M1_Research/records/step07_label_config.json', 'w'), indent=2)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import f1_score, balanced_accuracy_score, cohen_kappa_score, roc_auc_score, accuracy_score
import xgboost as xgb, lightgbm as lgb

R = '/content/drive/MyDrive/M1_Research'; REC = f'{R}/records'; RES = f'{R}/results'; os.makedirs(RES, exist_ok=True)
SEED = 42; K = 10
CFG = json.load(open(f'{REC}/step07_label_config.json'))      # thresholds decided from Step 6 balance
T1, T2 = CFG['high_m'], CFG['medium_m']
df = pd.read_parquet(f'{R}/M1_buildings_dataset_v2.parquet')
d = df.LABEL_dist_to_flood_m.values
df['y'] = np.where(d <= T1, 2, np.where(d <= T2, 1, 0))       # 2 = High, 1 = Medium, 0 = Low exposure
CLASSES = ['Low', 'Medium', 'High']

# ---- fixed sample used by ALL models (tabular + deep) so comparisons are paired ----
N = CFG['n_sample']
samp = df.sample(n=min(N, len(df)), random_state=SEED).reset_index(drop=True)
blocks = samp.block.unique(); rng = np.random.RandomState(SEED); rng.shuffle(blocks)
fold_of_block = {b: i % K for i, b in enumerate(blocks)}
samp['fold'] = samp.block.map(fold_of_block)
samp.to_parquet(f'{R}/M1_sample_with_folds.parquet', index=False)
print(f'Sample {len(samp):,} buildings | {len(blocks)} blocks -> {K} spatial folds')
print('Class counts:', samp.y.value_counts().sort_index().rename(index=dict(enumerate(CLASSES))).to_dict())

FEATS = ['X_B2','X_B3','X_B4','X_B8','X_B11','X_ndvi','X_ndwi','X_dem_m','X_slope_deg','X_hand_m',
         'X_dist_river_m','X_built_frac_100m','X_landcover','X_area_m2']
nan_counts = samp[FEATS].isna().sum(); print('NaN per feature (filled with sample median):', nan_counts[nan_counts > 0].to_dict())
samp[FEATS] = samp[FEATS].fillna(samp[FEATS].median())
X = samp[FEATS].values.astype('float32'); y = samp.y.values
cw = len(y) / (3 * np.bincount(y, minlength=3))               # inverse-frequency class weights
sw_all = cw[y]

def models():
    return {
      'T1_LogReg':  make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight='balanced')),
      'T2_RandomForest': RandomForestClassifier(n_estimators=300, min_samples_leaf=5, class_weight='balanced', n_jobs=-1, random_state=SEED),
      'T3_XGBoost': xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                                      tree_method='hist', random_state=SEED, n_jobs=-1),
      'T4_LightGBM': lgb.LGBMClassifier(n_estimators=400, num_leaves=63, learning_rate=0.05, subsample=0.8, subsample_freq=1,
                                        colsample_bytree=0.8, class_weight='balanced', random_state=SEED, verbose=-1)}

def metrics(yt, yp, prob):
    out = dict(macro_f1=f1_score(yt, yp, average='macro'), bal_acc=balanced_accuracy_score(yt, yp),
               acc=accuracy_score(yt, yp), qwk=cohen_kappa_score(yt, yp, weights='quadratic'))
    try: out['auc_high'] = roc_auc_score((yt == 2).astype(int), prob[:, 2])   # High vs rest (comparable to susceptibility AUC)
    except ValueError: out['auc_high'] = np.nan
    return out

rows, oof = [], {}
for name in models():
    oof[name] = np.zeros((len(y), 3), 'float32')
for k in range(K):
    tr, te = samp.fold.values != k, samp.fold.values == k
    for name, m in models().items():
        t0 = time.time()
        if name == 'T3_XGBoost': m.fit(X[tr], y[tr], sample_weight=sw_all[tr])
        else: m.fit(X[tr], y[tr])
        fit_s = time.time() - t0
        t0 = time.time(); prob = m.predict_proba(X[te]); inf_ms = (time.time() - t0) / te.sum() * 1000 * 1000
        oof[name][te] = prob
        r = dict(model=name, fold=k, n_test=int(te.sum()), fit_s=round(fit_s, 2), infer_ms_per_1000=round(inf_ms, 2),
                 **metrics(y[te], prob.argmax(1), prob)); rows.append(r)
    print(f'fold {k}: ' + ' | '.join(f"{r['model']} F1={r['macro_f1']:.3f}" for r in rows[-4:]))
res = pd.DataFrame(rows); res.to_csv(f'{RES}/cv_tabular.csv', index=False)
np.savez_compressed(f'{RES}/oof_tabular.npz', y=y, fold=samp.fold.values, **oof)
summ = res.groupby('model')[['macro_f1','bal_acc','acc','qwk','auc_high','fit_s','infer_ms_per_1000']].agg(['mean','std']).round(4)
print('\n=== Spatial 10-fold CV (mean ± std) ==='); print(summ.to_string())

# ---- Random (non-spatial) CV for the same best tabular model: shows optimism of random splits ----
best = res.groupby('model').macro_f1.mean().idxmax()
rf = np.random.RandomState(SEED).randint(0, K, len(y)); rr = []
for k in range(K):
    tr, te = rf != k, rf == k; m = models()[best]
    (m.fit(X[tr], y[tr], sample_weight=sw_all[tr]) if best == 'T3_XGBoost' else m.fit(X[tr], y[tr]))
    p = m.predict_proba(X[te]); rr.append(metrics(y[te], p.argmax(1), p))
rr = pd.DataFrame(rr); rr.to_csv(f'{RES}/cv_random_{best}.csv', index=False)
print(f'\nRandom-split CV for {best}: macro-F1 {rr.macro_f1.mean():.3f} ± {rr.macro_f1.std():.3f} '
      f'(spatial CV: {res[res.model==best].macro_f1.mean():.3f}) | AUC_high random {rr.auc_high.mean():.3f}')

# ---- feature importance of best tree model (full sample fit) ----
m = models()['T4_LightGBM']; m.fit(X, y)
imp = pd.Series(m.booster_.feature_importance('gain'), index=FEATS).sort_values(ascending=False)
imp.to_csv(f'{RES}/feature_importance_lgbm.csv'); print('\nLightGBM gain importance (top 8):'); print((imp/imp.sum()).round(3).head(8).to_string())
json.dump({'step': 7, 'time': datetime.datetime.now().isoformat(), 'best_tabular': best}, open(f'{REC}/step07_done.json', 'w'))
