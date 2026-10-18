# ===== M1 Step 9b: Print all results compactly (for the report) =====
import json, pandas as pd, numpy as np, glob, os
R = '/content/drive/MyDrive/M1_Research'; RES = f'{R}/results'
cv = pd.concat([pd.read_csv(f'{RES}/cv_tabular.csv'), pd.read_csv(f'{RES}/cv_deep.csv')], ignore_index=True)
piv = cv.pivot(index='fold', columns='model', values='macro_f1').round(4)
ht = json.load(open(f'{RES}/hypothesis_tests.json'))
rc = [f for f in glob.glob(f'{RES}/cv_random_*.csv')][0]; rcm = os.path.basename(rc)[10:-4]; rr = pd.read_csv(rc)
imp = pd.read_csv(f'{RES}/feature_importance_lgbm.csv', index_col=0).iloc[:, 0]; imp = (imp / imp.sum()).round(4)
deep = pd.read_csv(f'{RES}/cv_deep.csv').groupby('model').params_M.first().to_dict()
out = dict(folds={m: piv[m].tolist() for m in piv.columns}, random_cv=dict(model=rcm, f1_random=round(rr.macro_f1.mean(), 4), auc_random=round(rr.auc_high.mean(), 4),
           f1_spatial=round(cv[cv.model == rcm].macro_f1.mean(), 4), auc_spatial=round(cv[cv.model == rcm].auc_high.mean(), 4)),
           importance=[[k, float(v)] for k, v in imp.items()], params_M=deep, tests=ht)
print('M1JSON_START' + json.dumps(out, default=float, separators=(',', ':')) + 'M1JSON_END')
