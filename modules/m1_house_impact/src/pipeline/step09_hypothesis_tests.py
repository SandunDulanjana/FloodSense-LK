# ===== M1 Step 9: Hypothesis testing to select the best model =====
# H0 (Friedman): all models have the same median macro-F1 across the 10 spatial folds.
# Post-hoc: Nemenyi (all pairs) + Wilcoxon signed-rank best-vs-each (Holm correction).
# McNemar: best vs runner-up on pooled out-of-fold predictions (same buildings).
# Bootstrap: 95% CI of macro-F1 by resampling spatial BLOCKS (keeps spatial dependence).
import os, json, datetime, numpy as np, pandas as pd
from scipy import stats
import scikit_posthocs as sp
from sklearn.metrics import f1_score, confusion_matrix
import matplotlib.pyplot as plt
R = '/content/drive/MyDrive/M1_Research'; RES = f'{R}/results'
cv = pd.concat([pd.read_csv(f'{RES}/cv_tabular.csv')] + ([pd.read_csv(f'{RES}/cv_deep.csv')] if os.path.exists(f'{RES}/cv_deep.csv') else []), ignore_index=True)
complete = cv.groupby('model').fold.nunique(); models = complete[complete == 10].index.tolist()
cv = cv[cv.model.isin(models)]
M = cv.pivot(index='fold', columns='model', values='macro_f1')[models]
summary = cv.groupby('model').agg(macro_f1=('macro_f1', 'mean'), f1_sd=('macro_f1', 'std'), bal_acc=('bal_acc', 'mean'),
                                  qwk=('qwk', 'mean'), auc_high=('auc_high', 'mean'), fit_s=('fit_s', 'mean'),
                                  infer_ms_per_1000=('infer_ms_per_1000', 'mean')).sort_values('macro_f1', ascending=False)
summary['mean_rank'] = M.rank(axis=1, ascending=False).mean().reindex(summary.index)
print('=== Model summary (spatial 10-fold CV) ==='); print(summary.round(3).to_string())

chi2, p_fr = stats.friedmanchisquare(*[M[c].values for c in models])
k, n = len(models), len(M)
iman_F = (n - 1) * chi2 / (n * (k - 1) - chi2); p_iman = 1 - stats.f.cdf(iman_F, k - 1, (k - 1) * (n - 1))
print(f'\nFriedman chi2={chi2:.2f}, p={p_fr:.2e} | Iman-Davenport F={iman_F:.2f}, p={p_iman:.2e}  (k={k} models, n={n} folds)')
nem = sp.posthoc_nemenyi_friedman(M.values); nem.index = nem.columns = models
q_alpha = {2:1.960,3:2.343,4:2.569,5:2.728,6:2.850,7:2.949,8:3.031,9:3.102,10:3.164,11:3.219,12:3.268}[k]
CD = q_alpha * np.sqrt(k * (k + 1) / (6 * n)); print(f'Nemenyi critical difference (alpha=0.05): CD = {CD:.2f} rank units')

best = summary.index[0]; runner = summary.index[1]
wil = []
for m in models:
    if m == best: continue
    s, p = stats.wilcoxon(M[best], M[m], alternative='greater', zero_method='zsplit')
    wil.append(dict(model=m, mean_diff=float((M[best] - M[m]).mean()), wins=int((M[best] > M[m]).sum()), p_raw=p))
wil = pd.DataFrame(wil).sort_values('p_raw'); mcount = len(wil)
wil['p_holm'] = np.minimum(1, np.maximum.accumulate(wil.p_raw.values * (mcount - np.arange(mcount))))
wil['significant_0.05'] = wil.p_holm < 0.05
print(f'\nWilcoxon signed-rank (one-sided: {best} > other), Holm-corrected:'); print(wil.round(4).to_string(index=False))

# McNemar on pooled out-of-fold predictions
oof = {}
for f in ['oof_tabular.npz', 'oof_deep.npz']:
    if os.path.exists(f'{RES}/{f}'):
        z = np.load(f'{RES}/{f}'); oof.update({k_: z[k_] for k_ in z.files})
y = oof['y']; samp = pd.read_parquet(f'{R}/M1_sample_with_folds.parquet')
pb, pr = oof[best].argmax(1), oof[runner].argmax(1)
b_ = int(((pb == y) & (pr != y)).sum()); c_ = int(((pb != y) & (pr == y)).sum())
mc = (abs(b_ - c_) - 1) ** 2 / (b_ + c_); p_mc = 1 - stats.chi2.cdf(mc, 1)
print(f'\nMcNemar {best} vs {runner}: b={b_} (only best correct), c={c_} (only runner-up correct), chi2={mc:.2f}, p={p_mc:.2e}')

# Block bootstrap 95% CI
rng = np.random.RandomState(42); blocks = samp.block.values; ub = np.unique(blocks); idx_by = {b: np.where(blocks == b)[0] for b in ub}
ci = {}
for m in summary.index:
    pred = oof[m].argmax(1); vals = []
    for _ in range(1000):
        ii = np.concatenate([idx_by[b] for b in rng.choice(ub, len(ub), replace=True)])
        vals.append(f1_score(y[ii], pred[ii], average='macro'))
    ci[m] = (f1_score(y, pred, average='macro'), np.percentile(vals, 2.5), np.percentile(vals, 97.5))
ci = pd.DataFrame(ci, index=['pooled_macro_f1', 'ci_low', 'ci_high']).T.loc[summary.index]
print('\nPooled out-of-fold macro-F1 with 95% block-bootstrap CI:'); print(ci.round(3).to_string())
cm = confusion_matrix(y, oof[best].argmax(1)); print(f'\nConfusion matrix ({best}) rows=true [Low,Medium,High]:\n{cm}')

# Figures
os.makedirs(f'{RES}/figures', exist_ok=True)
fig, ax = plt.subplots(figsize=(10, 5)); M[summary.index].boxplot(ax=ax, rot=35); ax.set_ylabel('Macro-F1 (per spatial fold)')
ax.set_title('Model comparison: macro-F1 over 10 spatial folds'); plt.tight_layout(); plt.savefig(f'{RES}/figures/fig_boxplot_f1.png', dpi=150); plt.close()
ranks = summary['mean_rank'].sort_values(); fig, ax = plt.subplots(figsize=(10, 3.2))
ax.hlines(0, ranks.min() - .5, ranks.max() + .5, color='grey'); ax.plot(ranks.values, np.zeros(len(ranks)), 'o')
for i, (m, r) in enumerate(ranks.items()): ax.annotate(f'{m}\n{r:.2f}', (r, 0), xytext=(0, 18 if i % 2 else -34), textcoords='offset points', ha='center', fontsize=7)
ax.plot([ranks.min(), ranks.min() + CD], [0.6, 0.6], 'r-', lw=3); ax.text(ranks.min(), 0.75, f'CD = {CD:.2f}', color='r', fontsize=8)
ax.set_ylim(-1, 1); ax.set_yticks([]); ax.set_xlabel('Mean rank (1 = best)'); ax.set_title('Nemenyi critical-difference diagram')
plt.tight_layout(); plt.savefig(f'{RES}/figures/fig_cd_diagram.png', dpi=150); plt.close()
fig, ax = plt.subplots(figsize=(4.5, 4)); im = ax.imshow(cm / cm.sum(1, keepdims=True), cmap='Blues', vmin=0, vmax=1)
for i in range(3):
    for j in range(3): ax.text(j, i, f'{cm[i,j]}\n{cm[i,j]/cm[i].sum():.2f}', ha='center', va='center', fontsize=8)
ax.set_xticks(range(3)); ax.set_yticks(range(3)); ax.set_xticklabels(['Low', 'Med', 'High']); ax.set_yticklabels(['Low', 'Med', 'High'])
ax.set_xlabel('Predicted'); ax.set_ylabel('True'); ax.set_title(f'Confusion matrix: {best}', fontsize=9); plt.tight_layout()
plt.savefig(f'{RES}/figures/fig_confusion_best.png', dpi=150); plt.close()

out = dict(time=datetime.datetime.now().isoformat(), models=models, best=best, runner_up=runner,
           friedman=dict(chi2=chi2, p=p_fr, iman_F=iman_F, p_iman=p_iman), nemenyi_CD=CD,
           wilcoxon=wil.to_dict('records'), mcnemar=dict(b=b_, c=c_, chi2=mc, p=p_mc),
           summary=summary.reset_index().to_dict('records'), bootstrap_ci=ci.reset_index().to_dict('records'), confusion_best=cm.tolist())
json.dump(out, open(f'{RES}/hypothesis_tests.json', 'w'), indent=2, default=float)
nem.to_csv(f'{RES}/nemenyi_pvalues.csv'); summary.to_csv(f'{RES}/model_summary.csv'); print('\nSaved results/hypothesis_tests.json + figures')
