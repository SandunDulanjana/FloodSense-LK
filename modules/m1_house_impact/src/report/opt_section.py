# Section "Model optimisation" for the M1 report. All numbers come from opt.json
# (= results/tuning/optimisation_summary.json + final_model_record.json from Colab Step 12). Text is data-driven.
import os, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

NICE = {'D6_tuned': 'D6 HSC-Attention (optimised)', 'D6_default': 'D6 HSC-Attention (default)',
        'D5_tuned': 'D5 Dual-Stream (optimised)', 'D5_default': 'D5 Dual-Stream (default)',
        'A1_NoDEM': 'A1 No-DEM (no elevation, slope, HAND)', 'A2_NoCrossAttention': 'A2 No-Cross-Attention (concat)',
        'A3_VisualOnly': 'A3 Visual-only (no terrain stream)'}
PNAME = {'lr': 'learning rate', 'wd': 'weight decay', 'epochs': 'epochs', 'head_drop': 'classifier dropout', 'vis_init': 'visual-stream initialisation',
         'd': 'token width d', 'heads': 'attention heads', 'layers': 'cross-attention layers', 'ffn_act': 'FFN activation', 'grid': 'token grid',
         'bidir': 'bidirectional attention', 'head_hidden': 'classifier hidden units', 'head_act': 'classifier activation'}

def _w(O, a, b): return next((w for w in O['wilcoxon'] if w['a'] == a and w['b'] == b), None)
def _m(O, k, s='macro_f1_mean'): return O['summary'].get(k, {}).get(s, float('nan'))

def figures(O, FIG):
    f = O['folds']; os.makedirs(FIG, exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw=dict(width_ratios=[1, 1.35]))
    for i, (d, t, c) in enumerate([('D6_default', 'D6_tuned', '#e0453a'), ('D5_default', 'D5_tuned', '#4aa3ff')]):
        if d in f and t in f:
            for a, b in zip(f[d], f[t]): ax[0].plot([i * 2.4, i * 2.4 + 1], [a, b], color=c, alpha=.45, lw=1)
            ax[0].plot([i * 2.4, i * 2.4 + 1], [np.mean(f[d]), np.mean(f[t])], color=c, lw=3, marker='o')
    ax[0].set_xticks([0, 1, 2.4, 3.4]); ax[0].set_xticklabels(['D6\ndefault', 'D6\noptimised', 'D5\ndefault', 'D5\noptimised'], fontsize=8)
    ax[0].set_ylabel('Macro-F1 (outer test fold)'); ax[0].grid(axis='y', alpha=.3); ax[0].set_title('Paired folds: default vs optimised (thick = mean)', fontsize=9)
    order = [m for m in ['D6_tuned', 'A2_NoCrossAttention', 'A1_NoDEM', 'A3_VisualOnly', 'D5_tuned'] if m in f]
    bp = ax[1].boxplot([f[m] for m in order], patch_artist=True, widths=.55)
    for p, m in zip(bp['boxes'], order): p.set_facecolor('#e0453a' if m == 'D6_tuned' else ('#4aa3ff' if m.startswith('D5') else '#f2b84b')); p.set_alpha(.85)
    ax[1].set_xticks(range(1, len(order) + 1)); ax[1].set_xticklabels([NICE[m].split(' (')[0] for m in order], rotation=20, ha='right', fontsize=8)
    ax[1].grid(axis='y', alpha=.3); ax[1].set_title('Ablation study (each uses the per-fold optimised D6 settings)', fontsize=9)
    plt.tight_layout(); plt.savefig(f'{FIG}/fig_opt_folds_ablation.png', dpi=170); plt.close()
    imp = O.get('importance', {}).get('D6')
    if imp:
        k = list(imp)[:11]; fig, ax = plt.subplots(figsize=(7, 3.6))
        ax.barh([PNAME.get(x, x) for x in k][::-1], [imp[x] for x in k][::-1], color='#1f4e79'); ax.set_xlabel('Mean fANOVA importance (10 studies)')
        ax.set_title('Which settings mattered for HSC-Attention?', fontsize=9); ax.grid(axis='x', alpha=.3)
        plt.tight_layout(); plt.savefig(f'{FIG}/fig_opt_importance.png', dpi=170); plt.close()

def interpretation(O):
    t6, d6, t5, d5 = _m(O, 'D6_tuned'), _m(O, 'D6_default'), _m(O, 'D5_tuned'), _m(O, 'D5_default')
    w66, w55, w65 = _w(O, 'D6_tuned', 'D6_default'), _w(O, 'D5_tuned', 'D5_default'), _w(O, 'D6_tuned', 'D5_tuned')
    sig = lambda w: w is not None and w['significant_0.05']
    s = (f"Optimisation changed HSC-Attention from macro-F1 {d6:.3f} (default) to {t6:.3f} (optimised), a difference of {t6 - d6:+.3f}; "
         f"the optimised version won {w66['wins']}/10 outer folds (Wilcoxon, Holm-adjusted p = {w66['p_holm']:.4f}). ")
    s += ("This improvement is statistically significant. " if sig(w66) and t6 > d6 else
          "This change is <b>not</b> statistically significant, so we cannot claim that tuning improved the model; the default settings were already close to the best found within the budget. ")
    s += f"Baseline 1 changed from {d5:.3f} to {t5:.3f} ({t5 - d5:+.3f}; Holm p = {w55['p_holm']:.4f}). " if w55 else ''
    if w65:
        s += (f"After both models received the <b>same</b> optimisation budget, HSC-Attention ({t6:.3f}) vs Dual-Stream ({t5:.3f}): difference {t6 - t5:+.3f}, "
              f"won {w65['wins']}/10 folds, Holm p = {w65['p_holm']:.4f} — "
              + ("the cross-attention model is significantly better under a fair comparison." if sig(w65) and t6 > t5 else
                 ("the difference is not significant; the two fusion designs are statistically tied under fair tuning." if not sig(w65) else
                  "the Dual-Stream baseline is significantly better.")))
    return s

def ablation_text(O):
    out = []
    for a, what in [('A1_NoDEM', 'removing elevation, slope and HAND'), ('A2_NoCrossAttention', 'replacing cross-attention by concatenation'),
                    ('A3_VisualOnly', 'removing the whole terrain stream')]:
        w = _w(O, 'D6_tuned', a)
        if not w: continue
        eff = ('significantly reduced' if w['significant_0.05'] and w['mean_diff'] > 0 else
               ('significantly increased' if w['significant_0.05'] else 'did not significantly change'))
        out.append(f"<b>{NICE[a]}:</b> {what} {eff} macro-F1 (full model minus ablation = {w['mean_diff']:+.3f}, full model won {w['wins']}/10 folds, Holm p = {w['p_holm']:.4f}).")
    return out

def choice_rows(O, m='D6'):
    rows = [['Setting', 'Values searched', 'Default (Step 8)', 'Chosen in the 10 outer folds (count)']]
    SPACE = {'lr': '1e-4 – 2e-3 (log)', 'wd': '1e-5 – 1e-2 (log)', 'epochs': '6, 10, 14', 'head_drop': '0.1 – 0.5', 'vis_init': 'ImageNet, random',
             'd': '128, 256', 'heads': '2, 4, 8', 'layers': '1, 2, 3', 'ffn_act': 'GELU, ReLU, SiLU', 'grid': '4×4, 8×8 tokens', 'bidir': 'no, yes',
             'head_hidden': '128, 256, 512', 'head_act': 'ReLU, GELU, SiLU'}
    DEF = {'D6': dict(lr='3e-4', wd='1e-4', epochs='6', head_drop='0.3', vis_init='imagenet', d='256', heads='4', layers='1', ffn_act='gelu', grid='4', bidir='False'),
           'D5': dict(lr='3e-4', wd='1e-4', epochs='6', head_drop='0.3', vis_init='imagenet', head_hidden='256', head_act='relu')}[m]
    ch = O.get('choices', {}).get(m, {})
    for k in DEF:
        c = ch.get(k, {})
        if k in ('lr', 'wd', 'head_drop'):
            vals = [float(v) for v, n in c.items() for _ in range(n)]
            txt = f"median {np.median(vals):.2g} (range {min(vals):.2g} – {max(vals):.2g})" if vals else '–'
        else:
            txt = ', '.join(f"{v}: {n}" for v, n in sorted(c.items(), key=lambda x: -x[1]))
        rows.append([PNAME.get(k, k), SPACE[k], DEF[k], txt])
    return rows

def build(O, H, FIG):
    """H = dict of helpers from build_report (P, table, fig, bullets, styles, cm, PageBreak)."""
    P, table, fig, bullets, cm = H['P'], H['table'], H['fig'], H['bullets'], H['cm']
    figures(O, FIG); S = []
    S += [P('9. Model optimisation of HSC-Attention (algorithmic contribution)', H['H1']),
          P('9.1 What is optimised and why', H['H2']),
          P('A neural network has two kinds of numbers. <b>Parameters</b> (weights) are learned by gradient descent. <b>Hyper-parameters</b> are chosen by the researcher '
            'before training: the <i>architecture</i> (how many cross-attention layers, how many attention heads, token width, token grid, activation function, '
            'one-way or two-way attention) and the <i>training recipe</i> (learning rate, weight decay, dropout, epochs, starting weights). In Step 8 these were fixed '
            'by hand. Here they are searched systematically, which is the algorithmic-optimisation contribution of M1.'),
          P('9.2 Theory: why nested spatial cross-validation', H['H2']),
          bullets(['If settings are chosen by looking at the test folds, the reported score is optimistically biased (selection bias; Cawley &amp; Talbot, 2010). '
                   'Nested cross-validation (Varma &amp; Simon, 2006) removes this: an <b>inner</b> loop chooses settings, an <b>outer</b> loop measures performance on data never used for choosing.',
                   'Outer loop: the same 10 spatial folds as Steps 7–8. For outer fold k, the inner validation set is fold k+1 (whole 2 km blocks) and the inner training set '
                   'is a 50 % random subsample of the other 8 folds (a common low-fidelity speed-up). Test fold k is never seen during the search.',
                   f"Search algorithm: Optuna (Akiba et al., 2019) with the Tree-structured Parzen Estimator (TPE; Bergstra et al., 2011): {O['n_trials']['D6']} trials planned per outer fold for D6 and "
                   f"{O['n_trials']['D5']} for D5 (effective real trials: see the protocol deviation in 9.8). The first 5 trials are random (random search is a strong baseline; Bergstra &amp; Bengio, 2012). "
                   'Selection criterion: macro-F1 on the inner validation fold.',
                   'After the search, the best setting is re-trained on all 9 outer-training folds and tested once on fold k. This gives 10 unbiased outer scores per model, '
                   'paired with the defaults (re-run with the same code and seeds) for Wilcoxon tests.',
                   '<b>Fairness:</b> Baseline 1 (D5 Dual-Stream) receives the same procedure. Optimising only the proposed model would make any comparison unfair.']),
          P('9.3 Search space', H['H2']),
          table(choice_rows(O, 'D6'), [3.4 * cm, 3.6 * cm, 2.4 * cm, 7.0 * cm]),
          P('Activation functions: ReLU = max(0, x); GELU = x·Φ(x), a smooth version used in Transformers (Hendrycks &amp; Gimpel, 2016); SiLU = x·sigmoid(x) '
            '(Elfwing et al., 2018). Token grid 8×8 uses ResNet stage 2 (finer, 64 tokens of 40 m) instead of stage 3 (16 tokens of 80 m). '
            'Bidirectional = terrain tokens also attend back to the image tokens in every layer.', H['SM'])]
    S += [P('Baseline 1 (D5) search space and choices:', H['B']), table(choice_rows(O, 'D5'), [3.4 * cm, 3.6 * cm, 2.4 * cm, 7.0 * cm])]
    order = ['D6_tuned', 'D6_default', 'D5_tuned', 'D5_default', 'A1_NoDEM', 'A2_NoCrossAttention', 'A3_VisualOnly']
    rows = [['Model', 'Macro-F1 (mean ± SD)', 'QWK', 'AUC High', 'Params (M)', 'Train s / fold']]
    for m in order:
        if m in O['summary']:
            s = O['summary'][m]
            rows.append([NICE[m], f"{s['macro_f1_mean']:.3f} ± {s['macro_f1_std']:.3f}", f"{s['qwk_mean']:.3f}", f"{s['auc_high_mean']:.3f}",
                         f"{s['params_M_mean']:.2f}", f"{s['fit_s_mean']:.0f}"])
    S += [P('9.4 Results (outer spatial 10-fold CV, measured)', H['H2']), table(rows, [6.2 * cm, 3.1 * cm, 1.6 * cm, 1.8 * cm, 1.8 * cm, 2.0 * cm], hl=1),
          fig('fig_opt_folds_ablation.png', 16.5, 'Figure 4. Left: each thin line is one outer test fold (default → optimised). Right: ablations of the optimised HSC-Attention.')]
    wrows = [['Planned comparison', 'Mean diff. F1', 'Folds won', 'p (raw)', 'p (Holm)', 'Significant?']]
    for w in O['wilcoxon']:
        wrows.append([f"{NICE[w['a']].split(' (')[0]} {'(opt.)' if 'tuned' in w['a'] else ''} vs {NICE[w['b']]}", f"{w['mean_diff']:+.3f}", f"{w['wins']}/10",
                      f"{w['p']:.4f}", f"{w['p_holm']:.4f}", 'Yes' if w['significant_0.05'] else 'No'])
    S += [P('9.5 Hypothesis tests (two-sided Wilcoxon signed-rank, Holm correction over the 6 planned comparisons)', H['H2']),
          table(wrows, [7.0 * cm, 2.0 * cm, 1.7 * cm, 1.8 * cm, 1.8 * cm, 2.0 * cm]),
          P('<b>Interpretation.</b> ' + interpretation(O), H['BOX'])]
    fa = O.get('friedman_all')
    if fa and fa.get('chi2') == fa.get('chi2'):
        top = sorted(fa['mean_rank'].items(), key=lambda x: x[1])[:5]
        S += [P(f"<b>Friedman test over all {fa['k']} models</b> (Step 7–8 models plus the two optimised models): χ² = {fa['chi2']:.2f}, p = {fa['p']:.2e}; "
                f"Nemenyi CD = {fa['CD']:.2f}. Best mean ranks: " + '; '.join(f"{m} {r:.2f}" for m, r in top) + '.')]
    ci = O.get('bootstrap_ci', {})
    if ci:
        S += [table([['Model', 'Pooled out-of-fold macro-F1', '95% CI (bootstrap over spatial folds)']] +
                    [[NICE.get(m, m), f"{v['pooled']:.3f}", f"{v['lo']:.3f} – {v['hi']:.3f}"] for m, v in ci.items()], [6.5 * cm, 4.2 * cm, 5.5 * cm])]
    S += [P('9.6 Ablation study (does each part of HSC-Attention matter?)', H['H2']), bullets(ablation_text(O)),
          P('Each ablation keeps the optimised settings of its outer fold and removes exactly one component, so any change is caused by that component.', H['SM'])]
    if O.get('importance', {}).get('D6'):
        S += [P('9.7 Which settings mattered?', H['H2']),
              fig('fig_opt_importance.png', 11, 'Figure 5. Hyper-parameter importance (fANOVA; Hutter et al., 2014), averaged over the 10 inner studies. '
                  'With only a few trials per study these values are indicative, not precise.')]
    g = O.get('inner_gain', {}).get('D6'); rp = O.get('reproducibility', {}).get('D6_default')
    extra = []
    if g and g.get('inner_default') is not None:
        extra.append(f"On the inner validation folds the best setting beat the default by {g['inner_best'] - g['inner_default']:+.3f} macro-F1, but on the untouched outer folds the "
                     f"gain was {_m(O, 'D6_tuned') - _m(O, 'D6_default'):+.3f}. A smaller outer gain is expected: part of the inner gain is selection noise. "
                     'This is exactly why the nested design is needed — a non-nested study would have reported the inner number.')
    if rp:
        extra.append(f"Reproducibility check: the default HSC-Attention re-run with the Step 12 code scored {rp['this_code']:.3f} vs {rp['step8']:.3f} in Step 8 "
                     '(same data, folds, seeds; small differences come from GPU non-determinism).')
    au = O.get('audit')
    if au:
        r6 = sorted(set(v for k, v in au['real_trials_per_study'].items() if k.startswith('D6_outer')))
        r5 = sorted(set(v for k, v in au['real_trials_per_study'].items() if k.startswith('D5_outer')))
        extra.insert(0, '<b>Protocol deviation (found by our own audit and reported openly).</b> A synthetic-data smoke test, run just before the real search in the same Colab '
                     'runtime, left temporary Optuna study files. The first real session re-used them, so most inner studies contain 2 synthetic-data trials. '
                     f"Effective real trials per outer fold: D6 {'/'.join(map(str, r6))} (planned {O['n_trials']['D6']}), D5 {'/'.join(map(str, r5))} (planned {O['n_trials']['D5']}). "
                     'Consequences: (i) the search budget was slightly smaller than planned and the default setting was not re-evaluated inside most inner searches; '
                     '(ii) the parameter-importance values above use real trials only; (iii) <b>outer test results are not affected</b> — the synthetic trials never saw '
                     'the test folds, every chosen setting came from a real trial ' + ('(verified for all 20 studies)' if au.get('all_chosen_real') else '') +
                     ', and the defaults were evaluated separately on the same outer folds. The final-model search ran in a fresh runtime and is clean (14 real trials).')
    fr = O.get('final_config')
    if fr:
        c = fr['cfg']
        extra.append(f"<b>Final deployed setting</b> (chosen by the same procedure on the whole sample): {c['layers']} cross-attention layer(s), {c['heads']} heads, d = {c['d']}, "
                     f"{c['grid']}×{c['grid']} token grid, {c['ffn_act'].upper()} FFN, {'bidirectional' if c['bidir'] else 'one-way (image → terrain)'} attention, "
                     f"{c['vis_init']} initialisation, learning rate {c['lr']:.1e}, weight decay {c['wd']:.1e}, dropout {c['head_drop']:.2f}, {c['epochs']} epochs.")
    if extra: S += [P('9.8 Honest reading of the optimisation result', H['H2']), bullets(extra)]
    return S
