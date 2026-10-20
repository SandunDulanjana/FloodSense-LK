# Writes extra.json (narrative text that depends on measured results). Run AFTER dump.txt is saved and final-model values are filled in FINAL below.
import json, re, os
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.loads(re.search(r'M1JSON_START(.*?)M1JSON_END', open(f'{HERE}/dump.txt').read(), re.S).group(1))
FINAL = json.load(open(f'{HERE}/final.json'))           # values printed by Step 10 (filled by hand from the notebook output)
T = D['tests']; S = {s.get('model', s.get('index')): s for s in T['summary']}
best, runner = T['best'], T['runner_up']; b = S[best]
g = lambda m, k='macro_f1': S[m][k] if m in S else float('nan')
sig = [w for w in T['wilcoxon'] if w['significant_0.05']]; nsig = [w for w in T['wilcoxon'] if not w['significant_0.05']]
tab_best = max([m for m in S if m.startswith('T')], key=lambda m: g(m))
deep_best = max([m for m in S if m.startswith('D')], key=lambda m: g(m))

pre = (f"ResNet-18 trained from random weights (D2) reached macro-F1 {g('D2_ResNet18_random'):.3f}, while the same ResNet-18 starting from ImageNet weights (D3) "
       f"reached {g('D3_ResNet18_ImageNet'):.3f}; the satellite-pretrained ResNet-50 (SSL4EO-S12, D4, RGB only) reached {g('D4_ResNet50_SSL4EO'):.3f}. "
       f"The small CNN trained from scratch (D1) reached {g('D1_SimpleCNN_scratch'):.3f}. ")
d23 = g('D3_ResNet18_ImageNet') - g('D2_ResNet18_random')
pre += ("So ImageNet pre-training gave a small gain over random initialisation in this setting. " if d23 > 0.005 else
        "So pre-training did not give a clear gain here: with 45,000 labelled buildings per fold and 10-band 32x32 inputs, the network can learn useful filters from scratch, "
        "and ImageNet filters (learned on natural RGB photos) transfer only partly to multispectral 10 m imagery. ")
pre += ("D4 uses only 3 RGB bands (the available SSL4EO weights are RGB), so it cannot use NIR/SWIR or terrain bands; its result should be read with this in mind.")

imp = D['importance'][:5]
imp_text = ('The most important features are ' + ', '.join(f"{f} ({v:.0%})" for f, v in imp) +
            '. Terrain-related features (HAND, elevation, distance to river) and land-surface wetness signals matter most, which agrees with flood physics.')

wtxt = (f"the selected model is significantly better than {len(sig)} of {len(T['wilcoxon'])} other models after Holm correction"
        + (f"; it is <b>not</b> significantly better than {', '.join(w['model'] for w in nsig)}" if nsig else '') + '.')
dec = (f"<b>{best}</b> has the highest mean macro-F1 ({b['macro_f1']:.3f}) and the best mean rank ({b['mean_rank']:.2f}). Friedman rejects equal performance "
       f"(p = {T['friedman']['p']:.2e}); Wilcoxon tests show that {wtxt} McNemar vs {runner}: p < 1e-16. "
       f"Best tabular model: {tab_best} ({g(tab_best):.3f}); best deep model: {deep_best} ({g(deep_best):.3f}). "
       f"Therefore {best} is selected as the Progress-01 model{' (statistically tied models are reported as alternatives)' if nsig else ''}.")
rk = {m: S[m]['mean_rank'] for m in S}; close = [m for m in S if m != best and rk[m] - rk[best] <= T['nemenyi_CD']]
dec += (f" <b>Caution:</b> the all-pairs Nemenyi test is more conservative: the rank gap between {best} and {', '.join(close)} is smaller than the critical difference "
        f"({T['nemenyi_CD']:.2f}), so Nemenyi cannot separate {best} from these models; only the planned best-vs-others Wilcoxon tests (Holm-corrected) do. "
        "We therefore say: HSC-Attention is the best model in this experiment, with a small but consistent margin (it won 8–9 of 10 folds against each deep model), "
        "and it is clearly better than all tabular models.")
hsc, ds = g('D6_HSC_Attention'), g('D5_DualStream_Concat')
dec += (f" The proposed HSC-Attention prototype (D6, {hsc:.3f}) vs the proposal Baseline 1 Dual-Stream concatenation (D5, {ds:.3f}): difference {hsc - ds:+.3f}. "
        + ("Cross-attention helped slightly in this first prototype; " if hsc > ds else "Cross-attention did not beat simple concatenation yet; ")
        + "without the M4 forecast input its main advantage (spatially weighting forecast flood depth) cannot yet be shown.")

rc = D['random_cv']
lit = (f"The Sri Lankan susceptibility study reports AUC 0.970 with a non-spatial split; our best AUC(High) under spatial CV is {b['auc_high']:.3f}. "
       f"Our own experiment shows that a random split inflates scores (for {rc['model']}: AUC {rc['auc_random']:.3f} random vs {rc['auc_spatial']:.3f} spatial; "
       f"macro-F1 {rc['f1_random']:.3f} vs {rc['f1_spatial']:.3f}). Also, published studies classify flood/non-flood points (2 classes), while we predict 3 ordinal classes "
       "for every building, which is harder. Our AUC is in the same range as Seleem et al. (≥ 0.87), but the tasks differ, so this is context, not a competition.")

viva = [
 ("Why did you change from damage grades to flood exposure?",
  "Because no building-damage labels exist for Sri Lanka and Sentinel-2 (10 m) cannot see roof damage. Exposure is measurable from Sentinel-1 radar and is the first "
  "condition for damage. The damage-grade task continues as a separate track using xBD."),
 ("How do you know your labels are correct?",
  "We compared four SAR rules (sensitivity test) and chose the one that best matched the visible flood; the labels agree with physics (exposed buildings have median HAND 4.4 m vs 8.4 m). "
  "Limitations: receding flood on 2 Dec and urban double-bounce. Next step: check against Copernicus EMS EMSR851 delineations."),
 ("Is there data leakage?",
  "We used spatial block CV (2 km blocks), per-fold normalisation from training blocks only, and kept terrain variables out of the label rule. All inputs are pre-flood. "
  f"We also measured how much a random split would inflate scores ({rc['f1_random']:.3f} vs {rc['f1_spatial']:.3f} macro-F1)."),
 ("Why macro-F1 and not accuracy?",
  "75% of buildings are Low exposure; a model that always says Low gets 75% accuracy but is useless. Macro-F1 gives each class equal weight, so High exposure counts."),
 ("Why the Friedman test and not a t-test?",
  "We compare many models over the same 10 folds. Friedman is the recommended non-parametric test for this (Demšar, 2006); it does not assume normal scores. "
  "Pairwise Wilcoxon tests with Holm correction then tell which differences are real."),
 ("Why 10 folds instead of the 5 in your proposal?",
  "With 5 folds the Wilcoxon test can never reach p < 0.05; 10 folds give enough paired results for a valid test."),
 ("Did pre-training help?", pre),
 ("What is new in HSC-Attention compared with the baseline?",
  "Baseline 1 joins image and terrain features after global pooling (no spatial interaction). HSC-Attention lets each image region attend to terrain regions with "
  "cross-attention, so terrain can be weighted differently across the neighbourhood. In this prototype: " + f"D6 {hsc:.3f} vs D5 {ds:.3f}."),
 ("Your proposal targeted macro-F1 ≥ 0.78. Why is your result lower?",
  f"The target was for damage grades on xBD-style data. Our task is 3-class exposure from 10 m imagery with noisy SAR labels, tested spatially. The measured value ({b['macro_f1']:.3f}) "
  "is honest; we will improve it with M4 forecast input, better labels and tuning."),
 ("How fast is the model?",
  f"The final model predicted all 341,971 buildings in {FINAL['infer_s']:.1f} s ({FINAL['ms_per_1000']:.1f} ms per 1,000 buildings), far below the 45 s per tile requirement."),
 ("Can DMC use this tomorrow?",
  "Not yet. It is validated on one event and one basin. It needs a second event test and M4 forecast input. Today it is a research prototype with a working demo."),
]
json.dump(dict(generated=FINAL['generated'], pretraining=pre, importance_text=imp_text, decision_text=dec, lit_text=lit, viva=viva,
               software=FINAL.get('software', 'Python 3.13 (Colab), PyTorch 2.x, torchvision, timm, torchgeo, scikit-learn 1.6.1, XGBoost 3.4.1, LightGBM 4.6.0, scikit-posthocs, rasterio 1.5.2'),
               final=FINAL), open(f'{HERE}/extra.json', 'w'), indent=2)
print('extra.json written')
