# Parse the Colab dump (M1JSON_START...M1JSON_END) + extra printed values -> results.json + figures for the PDF
import json, re, sys, os, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); os.makedirs(f'{HERE}/figs', exist_ok=True)
raw = open(f'{HERE}/dump.txt').read()
D = json.loads(re.search(r'M1JSON_START(.*?)M1JSON_END', raw, re.S).group(1))
extra = json.load(open(f'{HERE}/extra.json'))           # values read from other cell outputs (final model, etc.)
T = D['tests']
summary = T['summary']
for s in summary: s.setdefault('model', s.get('index'))
best, runner = T['best'], T['runner_up']
folds = D['folds']; models = [s['model'] for s in sorted(summary, key=lambda r: r['mean_rank'])]

# ---- figures ----
order = [s['model'] for s in sorted(summary, key=lambda r: -r['macro_f1'])]
fig, ax = plt.subplots(figsize=(10, 4.6))
bp = ax.boxplot([folds[m] for m in order], patch_artist=True, widths=.6)
for patch, m in zip(bp['boxes'], order):
    patch.set_facecolor('#e0453a' if m == best else ('#4aa3ff' if m.startswith('D') else '#9bb7d4')); patch.set_alpha(.85)
ax.set_xticks(range(1, len(order) + 1)); ax.set_xticklabels(order, rotation=30, ha='right', fontsize=8)
ax.set_ylabel('Macro-F1 per spatial fold'); ax.grid(axis='y', alpha=.3)
ax.set_title('Macro-F1 over 10 spatial folds (red = selected, blue = deep, grey = tabular)', fontsize=10)
plt.tight_layout(); plt.savefig(f'{HERE}/figs/fig_boxplot_f1.png', dpi=170); plt.close()

CD = T['nemenyi_CD']; ranks = sorted([(s['mean_rank'], s['model']) for s in summary])
fig, ax = plt.subplots(figsize=(10, 3.3)); lo, hi = 1, len(ranks)
ax.hlines(0, lo, hi, color='k', lw=1)
for r in range(lo, hi + 1): ax.vlines(r, -.05, .05, color='k', lw=1); ax.text(r, .1, str(r), ha='center', fontsize=8)
for i, (r, m) in enumerate(ranks):
    y = -0.25 - 0.13 * (i % 6); ax.plot([r, r], [0, y], color='grey', lw=.8); ax.plot(r, 0, 'o', color='#e0453a' if m == best else '#1f4e79')
    ax.text(r + .05, y, f'{m} ({r:.2f})', fontsize=7.5, va='center')
ax.plot([lo, lo + CD], [.35, .35], 'r-', lw=3); ax.text(lo, .45, f'Critical difference (Nemenyi, α=0.05) = {CD:.2f}', color='r', fontsize=8)
ax.set_ylim(-1.1, .6); ax.set_xlim(lo - .3, hi + 1.8); ax.axis('off'); ax.set_title('Mean Friedman rank (1 = best)', fontsize=10)
plt.tight_layout(); plt.savefig(f'{HERE}/figs/fig_cd_diagram.png', dpi=170); plt.close()

cm = np.array(T['confusion_best']); fig, ax = plt.subplots(figsize=(4.6, 4.1))
ax.imshow(cm / cm.sum(1, keepdims=True), cmap='Blues', vmin=0, vmax=1)
for i in range(3):
    for j in range(3): ax.text(j, i, f'{cm[i, j]:,}\n({cm[i, j] / cm[i].sum():.2f})', ha='center', va='center', fontsize=8,
                               color='white' if cm[i, j] / cm[i].sum() > .6 else 'black')
ax.set_xticks(range(3)); ax.set_yticks(range(3)); ax.set_xticklabels(['Low', 'Medium', 'High']); ax.set_yticklabels(['Low', 'Medium', 'High'])
ax.set_xlabel('Predicted'); ax.set_ylabel('SAR-derived (true)'); ax.set_title(best, fontsize=9); plt.tight_layout()
plt.savefig(f'{HERE}/figs/fig_confusion_best.png', dpi=170); plt.close()

# ---- results.json for the report ----
R = dict(generated=extra['generated'], n_buildings=341971, best=best, runner_up=runner, summary=summary,
         friedman=T['friedman'], nemenyi_CD=CD, wilcoxon=T['wilcoxon'], mcnemar=T['mcnemar'],
         bootstrap_ci=[{**c, 'model': c.get('model', c.get('index'))} for c in T['bootstrap_ci']],
         random_cv=D['random_cv'], importance=D['importance'], params_M=D['params_M'], **{k: v for k, v in extra.items() if k != 'generated'})
json.dump(R, open(f'{HERE}/results.json', 'w'), indent=2, default=float)
print('results.json + figs written; best =', best)
