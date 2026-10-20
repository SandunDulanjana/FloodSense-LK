# Builds the M1 research report PDF from results.json + figures (all numbers come from actual Colab runs).
import json, os, sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
                                KeepTogether, ListFlowable, ListItem)
from reportlab.lib.enums import TA_CENTER

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, 'results.json')))
FIG = os.path.join(HERE, 'figs')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'M1_Research_Report.pdf')

ss = getSampleStyleSheet()
BLUE = colors.HexColor('#1f4e79')
H1 = ParagraphStyle('H1', parent=ss['Heading1'], fontSize=16, textColor=BLUE, spaceBefore=10, spaceAfter=6)
H2 = ParagraphStyle('H2', parent=ss['Heading2'], fontSize=12.5, textColor=BLUE, spaceBefore=8, spaceAfter=4)
H3 = ParagraphStyle('H3', parent=ss['Heading3'], fontSize=11, spaceBefore=6, spaceAfter=2)
B = ParagraphStyle('B', parent=ss['BodyText'], fontSize=10, leading=14, spaceAfter=5)
SM = ParagraphStyle('SM', parent=B, fontSize=8.5, leading=11, textColor=colors.HexColor('#444444'))
BOX = ParagraphStyle('BOX', parent=B, backColor=colors.HexColor('#eef4fa'), borderColor=BLUE, borderWidth=0.6,
                     borderPadding=6, spaceBefore=6, spaceAfter=10)
WARN = ParagraphStyle('WARN', parent=BOX, backColor=colors.HexColor('#fff4e5'), borderColor=colors.HexColor('#c77700'))
TC = ParagraphStyle('TC', parent=B, fontSize=8.3, leading=10.2, spaceAfter=0)
TCB = ParagraphStyle('TCB', parent=TC, fontName='Helvetica-Bold')

def P(t, s=B): return Paragraph(str(t).replace('²', '<super>2</super>').replace('Mean ΔF1', 'Mean diff. F1').replace('Δ', 'd').replace('p = < ', 'p < '), s)
def bullets(items, s=B):
    return ListFlowable([ListItem(P(i, s), leftIndent=12) for i in items], bulletType='bullet', start='•', leftIndent=12)
def table(rows, widths, header=True, hl=None, fs=None):
    data = [[P(str(c), TCB if (header and i == 0) else TC) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#b0b7c3')), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
          ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4)]
    if header: st.append(('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dbe5f1')))
    if hl is not None: st.append(('BACKGROUND', (0, hl), (-1, hl), colors.HexColor('#fff2cc')))
    t.setStyle(TableStyle(st)); return t
def fig(name, w=16, cap=None):
    p = os.path.join(FIG, name)
    if not os.path.exists(p): return P(f'[figure {name} missing]', SM)
    from PIL import Image as PI
    iw, ih = PI.open(p).size; h = w * ih / iw
    items = [Image(p, width=w * cm, height=h * cm)]
    if cap: items.append(P(cap, SM))
    return KeepTogether(items)
def f3(x): return '–' if x is None else f'{x:.3f}'
def pe(x): return '< 1e-16' if x <= 0 else (f'{x:.2e}' if x < 0.001 else f'{x:.4f}')

def footer(c, d):
    c.saveState(); c.setFont('Helvetica', 7.5); c.setFillColor(colors.grey)
    c.drawString(2 * cm, 1.2 * cm, 'J26-DS-360 · M1 · IT23401112 · Predictive building flood-exposure assessment (Progress 01 report)')
    c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f'Page {d.page}'); c.restoreState()

S = []   # story

# ============================ CONTENT ============================
best, runner = R['best'], R['runner_up']
bs = next(r for r in R['summary'] if r['model'] == best)
S += [Spacer(1, 2.2 * cm),
      P('<font size=20 color="#1f4e79"><b>Predictive Building Flood-Exposure Assessment for the Lower Kelani Basin</b></font>', ParagraphStyle('t', parent=B, leading=26, alignment=TA_CENTER)),
      Spacer(1, 6),
      P('<font size=12>Component M1 — Progress 01 Research Report: data, labels, model comparison, hypothesis testing and demo</font>', ParagraphStyle('t2', parent=B, alignment=TA_CENTER)),
      Spacer(1, 18),
      P('Project J26-DS-360 · AI-Powered Flood Disaster Impact Assessment and Decision Support System for Sri Lanka<br/>'
        'J.A.S. Dulanjana (IT23401112) · BSc (Hons) IT, Data Science · SLIIT<br/>Supervisor: Mr. Jeewaka Perera · Co-supervisor: Mr. Chamidu Rathsara<br/>'
        f'Report generated: {R["generated"]} · All numbers in this report come from real runs in Google Colab (notebook M1_Research_Main.ipynb).',
        ParagraphStyle('c', parent=B, alignment=TA_CENTER)),
      Spacer(1, 20)]
S += [P('<b>One-paragraph summary.</b> Using free satellite data in Google Earth Engine, we built a building-level dataset for '
        f'{R["n_buildings"]:,} buildings in the lower Kelani basin and labelled each one by its <b>flood exposure</b> during Cyclone Ditwah '
        '(distance to flood water detected by Sentinel-1 radar on 2 December 2025). Using only information available <b>before</b> the flood '
        f'(Sentinel-2 imagery, elevation, HAND, river distance, building density), we trained and compared {len(R["summary"])} models — '
        'classic machine learning and deep learning, with and without pre-training, including the proposal\'s Dual-Stream ResNet baseline '
        'and a first prototype of the proposed HSC-Attention model — under the same 10-fold <b>spatial</b> cross-validation. '
        f'A Friedman test showed the models do not perform equally (p = {pe(R["friedman"]["p"])}). The selected model is <b>{best}</b> '
        f'(macro-F1 {bs["macro_f1"]:.3f} ± {bs["f1_sd"]:.3f}). An interactive local web demo shows predictions for every building.', BOX),
      P('<b>Honesty note for the panel.</b> These are measured results, not the proposal targets. The task was adapted from "damage grade" to '
        '"flood exposure" because no building-damage labels exist for Sri Lanka and Sentinel-2 (10 m) cannot see roof damage. '
        'Damage-percentage regression (MAE) and segmentation IoU are therefore <b>not</b> reported, because valid ground truth does not exist for them.', WARN),
      PageBreak()]

# ---------- 1. Whole-project workflow ----------
S += [P('1. What the whole project does — step by step', H1),
      P('This section is the "map" of the research. Each step lists what was done, why, and its status. '
        'Steps marked <b>DONE</b> were executed and verified; <b>NEXT</b> are planned after Progress 01.')]
wf = [['#', 'Step', 'What we did / will do (simple words)', 'Status'],
      ['1', 'Proposal review', 'Read the full proposal, found risks (no damage labels for Sri Lanka, MAE/IoU not measurable, unverifiable claims).', 'DONE'],
      ['2', 'Environment', 'Laptop has no NVIDIA GPU, so all training ran on free Google Colab (Tesla T4 GPU). GEE project: sliit-research-2026.', 'DONE'],
      ['3', 'Data check (GEE)', '15 low-cloud Sentinel-2 scenes (2025), Sentinel-1 radar on 26 Nov, 2 Dec, 8 Dec 2025, 349,477 Open Buildings footprints, SRTM DEM.', 'DONE'],
      ['4', 'Cloud-free image', 'Cloud Score+ removed clouds pixel by pixel; 140 Sentinel-2 scenes combined into one clear pre-flood image.', 'DONE'],
      ['5', 'Flood map', 'SAR change detection (before vs after), 4 rule variants compared; variant D (VV or VH) chosen; 12.47 km² flood water.', 'DONE'],
      ['6', 'Labels', 'Exact distance from every building to flood water; 3 exposure classes: High ≤100 m, Medium 100–300 m, Low >300 m.', 'DONE'],
      ['7', 'Features & patches', '14 pre-flood features per building + 32×32-pixel (320 m) image patches with 10 bands.', 'DONE'],
      ['8', 'Spatial folds', '50,000 buildings, 144 blocks of 2 km × 2 km, grouped into 10 folds (no block is in train and test at the same time).', 'DONE'],
      ['9', 'Models', f'{len(R["summary"])} models trained on the same folds: LR, RF, XGBoost, LightGBM, CNN from scratch, ResNet (random / ImageNet / SSL4EO), Dual-Stream, HSC-Attention.', 'DONE'],
      ['10', 'Hypothesis tests', 'Friedman + Iman–Davenport, Nemenyi, Wilcoxon (Holm), McNemar, block-bootstrap CIs.', 'DONE'],
      ['11', 'Demo', 'Local web app (index.html / run_demo.bat) with map of all buildings + comparison tables.', 'DONE'],
      ['12', 'M4 integration', 'Replace "where flood happened" with M4\'s 3-day forecast flood probability as a model input.', 'NEXT'],
      ['13', 'Second event', 'Validate on another flood (May 2016 Kelani / June 2024) to test transferability over time.', 'NEXT'],
      ['14', 'Damage track', 'Train damage-grade model on xBD flood events (Florence, Harvey, Midwest) for the 4 damage classes.', 'NEXT'],
      ['15', 'Full HSC-Attention', 'Tune and run ablations (No-DEM, No-Cross-Attention) with forecast input; dashboard export (GeoJSON).', 'NEXT']]
S += [table(wf, [0.7 * cm, 2.8 * cm, 11.3 * cm, 1.6 * cm]), PageBreak()]

# ---------- 2. Problem & key ideas ----------
S += [P('2. The problem and the key ideas (theory in simple words)', H1),
      P('2.1 Problem', H2),
      P('During monsoon floods, Sri Lanka\'s Disaster Management Centre (DMC) needs to know which houses are at risk <i>before</i> or '
        '<i>while</i> water arrives. Field surveys take 2–4 weeks and optical satellites cannot see through monsoon cloud. '
        'M1 asks: <b>using only information available before a flood, can a model predict how exposed each building will be?</b>'),
      P('2.2 Flood exposure vs. flood damage', H2),
      P('<b>Exposure</b> = whether a building is in or near flood water. <b>Damage</b> = how badly the structure is broken. '
        'Exposure is the first and necessary condition for damage. Damage grades (No/Minor/Major/Destroyed) need sub-metre imagery and expert '
        'labelling; these do not exist for Sri Lanka. Therefore Progress 01 predicts exposure (measurable, Sri Lanka-specific), and the damage '
        'grade task is kept as a separate track using the xBD benchmark (Section 13).'),
      P('2.3 Satellites used', H2),
      bullets(['<b>Sentinel-2 (optical, 10 m):</b> a photograph-like image in visible and infrared bands. One house ≈ 1 pixel, so the model sees the '
               '<i>neighbourhood</i> (roofs, paddy, marsh, trees, river), not the house shape.',
               '<b>Sentinel-1 (radar/SAR, 10 m):</b> sends microwaves and measures the echo (backscatter, in dB). Calm water reflects the signal away, '
               'so it looks <b>dark</b>. Radar works through cloud and at night, which is why it gives the flood "answer".',
               '<b>Double-bounce:</b> in towns, the radar bounces water → wall → satellite, so flooded streets can look <b>bright</b>. This is why '
               'simple "dark = water" misses some urban flooding (a limitation we report).',
               '<b>SRTM DEM (30 m)</b> = ground height. <b>HAND</b> (MERIT Hydro) = Height Above the Nearest Drainage: how many metres a place is above '
               'the nearest stream. Low HAND = water reaches it first.',
               '<b>Google Open Buildings v3</b> = AI-drawn building footprints from 50 cm imagery (we kept confidence ≥ 0.75).']),
      P('2.4 Study area and event', H2),
      P('Lower Kelani basin box 79.85–80.22 °E, 6.90–7.02 °N (Colombo coast → Avissawella). Cyclone Ditwah formed over Sri Lanka on 27 Nov 2025 '
        '(Copernicus EMS activation EMSR851). The Kelani at Nagalagam Street reached the critical level of 8.45 ft on 1 Dec 2025 and fell to the minor '
        'flood level (6.9 ft) on the afternoon of 2 Dec 2025. Our flood image (Sentinel-1, 2 Dec, descending orbit) therefore shows a '
        '<b>receding</b> flood — an important assumption.')]

# ---------- 3. Data and labels ----------
S += [P('3. Data and label generation', H1),
      P('3.1 Data inventory (verified in Earth Engine)', H2),
      table([['Data', 'Source / GEE ID', 'Use', 'Verified value'],
             ['Sentinel-2 L2A', 'COPERNICUS/S2_SR_HARMONIZED + GOOGLE/CLOUD_SCORE_PLUS', 'Pre-flood image (Jan–Oct 2025)', '140 scenes in composite; 15 scenes <20% cloud'],
             ['Sentinel-1 GRD', 'COPERNICUS/S1_GRD (IW, VV+VH, descending)', 'Flood "answer" (2 Dec) vs reference (Oct–mid Nov)', 'Post dates 26 Nov, 2 Dec, 8 Dec 2025'],
             ['Buildings', 'GOOGLE/Research/open-buildings/v3/polygons', 'One sample per building', '349,477 (conf ≥ 0.75); 341,971 usable'],
             ['Elevation', 'USGS/SRTMGL1_003', 'Height, slope', '−11 to 367 m in box'],
             ['HAND', 'MERIT/Hydro/v1_0_1 (hnd)', 'Height above drainage', '—'],
             ['Permanent water', 'JRC/GSW1_4/GlobalSurfaceWater', 'Remove rivers from flood map; distance to river', 'occurrence ≥ 50%'],
             ['Land cover', 'ESA/WorldCover/v200', 'Feature', '—']],
            [2.4 * cm, 5.3 * cm, 4.3 * cm, 4.4 * cm]),
      P('3.2 Flood map: SAR change detection and sensitivity test', H2),
      P('A pixel is called <b>new flood water</b> when it became much darker than its normal (mean of Oct–mid-Nov 2025) and is now dark. '
        'Four rule variants were compared visually and numerically before choosing one (a <i>sensitivity analysis</i>):'),
      table([['Variant', 'Rule', 'Flood area (km²)', 'Decision'],
             ['A_current', 'ΔVV < −3 dB & VV < −16 dB & slope < 5°', '6.87', 'Too strict; slope filter removes real water'],
             ['B_noSlope', 'A without slope filter', '8.35', '—'],
             ['C_relaxed', 'ΔVV < −2 dB & VV < −15 dB', '9.88', '—'],
             ['D_VV_or_VH', 'C OR (ΔVH < −3 dB & VH < −22 dB)', '10.80 (GEE) / 12.47 (export grid)', '<b>Chosen</b>: best match to visible dark patches']],
            [2.4 * cm, 6.6 * cm, 3.4 * cm, 4.0 * cm]),
      P('All variants also remove permanent water (JRC occurrence ≥ 50 %) and patches smaller than 8 pixels. We deliberately did <b>not</b> use slope or '
        'HAND inside the final label rule, because those are also model inputs; using them in the label would let the model "learn our rule" '
        '(circular labelling).', SM),
      P('3.3 From flood map to building labels', H2),
      P('For every building we computed the exact Euclidean distance (in metres) from its centroid to the nearest flood pixel. '
        'The ordinal exposure classes are: <b>High</b> ≤ 100 m, <b>Medium</b> 100–300 m, <b>Low</b> > 300 m. '
        '≤ 50 m was rejected as a class boundary because only 1.35 % of buildings fall in it (too few to learn).'),
      table([['Distance to flood water', '≤ 0 m', '≤ 30 m', '≤ 50 m', '≤ 100 m', '≤ 150 m', '≤ 200 m', '≤ 300 m'],
             ['% of 341,971 buildings', '0.01', '0.33', '1.35', '5.40', '10.46', '15.66', '25.38']],
            [3.6 * cm] + [1.83 * cm] * 7),
      P('Physical sanity check (medians, near ≤ 50 m vs far > 150 m): HAND 4.40 vs 8.40 m; elevation 12 vs 19 m; distance to river 1,376 vs 1,841 m. '
        'Exposed buildings are lower and closer to drainage, which matches flood physics — evidence the labels are meaningful.', SM)]

S += [P('3.4 Assumptions (stated openly)', H2),
      bullets(['A1. SAR flood water on 2 Dec 2025 represents flood exposure for Ditwah (it is ~1 day after the Kelani peak, so true exposure is likely <b>larger</b>).',
               'A2. Distance to flood water is a valid proxy for exposure; it is <b>not</b> a damage measurement.',
               'A3. Open Buildings footprints (conf ≥ 0.75) are correct enough; missing/false buildings add noise.',
               'A4. The 2025 cloud-free Sentinel-2 composite represents conditions just before the flood.',
               'A5. 2 km spatial blocks are large enough to reduce spatial leakage between training and test buildings.',
               'A6. The 50,000-building random sample represents the 341,971 buildings (same class proportions).',
               'A7. Thresholds (−2/−15 dB, −3/−22 dB, 100/300 m) are research choices, justified by the sensitivity test and class balance, not universal constants.']),
      PageBreak()]

# ---------- 4. Models ----------
S += [P('4. Models compared and why', H1),
      P('We compare three families. All use exactly the same 50,000 buildings and the same 10 spatial folds, so differences come from the model, not the data.'),
      table([['ID', 'Model', 'Input', 'Pre-training', 'Why it is in the comparison'],
             ['T1', 'Logistic Regression', '14 tabular features', 'none', 'Simplest linear baseline'],
             ['T2', 'Random Forest (300 trees)', '14 tabular features', 'none', 'Strong classic model; best in Seleem et al. (2022)'],
             ['T3', 'XGBoost', '14 tabular features', 'none', 'Gradient boosting standard'],
             ['T4', 'LightGBM', '14 tabular features', 'none', 'Best in Sri Lankan study (Kurugama et al., 2024)'],
             ['D1', 'Simple CNN (5 conv layers)', '10-band 32×32 patch', '<b>none (from scratch)</b>', 'Does a small CNN learn from images alone?'],
             ['D2', 'ResNet-18', '10-band patch', '<b>none (random init)</b>', 'Same architecture as D3, isolates effect of pre-training'],
             ['D3', 'ResNet-18', '10-band patch', '<b>ImageNet</b> (natural photos)', 'Classic transfer learning'],
             ['D4', 'ResNet-50', 'RGB patch', '<b>SSL4EO-S12</b> (Sentinel-2, MoCo)', 'Pre-trained on satellite images (Wang et al., 2023)'],
             ['D5', 'Dual-Stream ResNet + concatenation', 'S2 stream + terrain stream', 'ImageNet (visual stream)', '<b>Proposal Baseline 1</b>'],
             ['D6', 'HSC-Attention (prototype)', 'S2 tokens attend to terrain tokens', 'ImageNet (visual stream)', '<b>Proposed model</b> (first prototype)']],
            [0.8 * cm, 3.5 * cm, 3.2 * cm, 3.4 * cm, 5.5 * cm]),
      P('4.1 How the main models work', H2),
      bullets(['<b>Random Forest:</b> many decision trees, each trained on a random part of the data and random features; the forest votes. Averaging many '
               'noisy trees reduces variance (bagging).',
               '<b>XGBoost / LightGBM (boosting):</b> trees are added one by one; each new tree corrects the errors of the previous ones (gradient boosting). '
               'LightGBM grows trees leaf-wise and uses histograms, so it is fast.',
               '<b>CNN:</b> learns small filters (3×3) that detect patterns such as water edges, paddy texture or dense roofs, then combines them into higher-level features.',
               '<b>ResNet:</b> a deep CNN with "skip connections" (output = F(x) + x) that make very deep networks trainable.',
               '<b>Transfer learning / fine-tuning:</b> start from weights already trained on a large dataset (ImageNet photos, or SSL4EO Sentinel-2 images) and '
               'continue training on our task. Fine-tuning means <i>all</i> weights are updated with a small learning rate (3×10<super>-4</super>). '
               'For 10-band inputs, the first layer was widened: RGB filters were copied to B4/B3/B2 and the mean filter was used for other bands.',
               '<b>Dual-Stream + concatenation (D5):</b> stream A (ResNet-18) encodes Sentinel-2; stream B (4-layer CNN) encodes terrain (DEM, slope, HAND, river distance, '
               'building mask). The two feature vectors are simply joined (concatenated) and passed to a classifier.',
               '<b>HSC-Attention (D6):</b> instead of joining, each of the 16 visual tokens (4×4 grid, 256-dim) asks the 16 hydro-terrain tokens "which places matter '
               'for me?" using cross-attention: Attention(Q,K,V) = softmax(QK<super>T</super>/√d)V, with Q from the image and K,V from terrain, 4 heads, followed by '
               'residual + LayerNorm + feed-forward. This lets the model weight terrain differently for different parts of the neighbourhood.']),
      P('<b>What is technically different between D5 and D6?</b> Only the fusion step: D5 = global-average then concatenate (no spatial interaction); '
        'D6 = token-level cross-attention (spatially-aware interaction). So D6 vs D5 is exactly the proposal\'s "No-Cross-Attention" ablation.', BOX)]

# ---------- 5. Experimental design ----------
S += [P('5. Experimental design', H1),
      P('5.1 Spatial cross-validation (why not random split?)', H2),
      P('Neighbouring buildings look alike and have similar labels (spatial autocorrelation). If neighbours are split between training and test, '
        'the model is tested on "almost seen" data and the score is too optimistic (Ploton et al., 2020). We therefore cut the area into '
        '2 km × 2 km blocks (144 blocks) and assigned <b>whole blocks</b> to 10 folds. Each fold is used once as the test set. '
        'We also ran a random-split CV for the best tabular model to measure how optimistic random splits would be (Section 7.3).'),
      P('5.2 Why 10 folds and not 5?', H2),
      P('The Wilcoxon signed-rank test with n = 5 paired folds can never give p < 0.05 (the smallest possible two-sided p is 0.0625). With n = 10 the smallest one-sided '
        'p is 1/1024 ≈ 0.001, so real differences can be detected. This is why the proposal\'s 5-fold plan was changed to 10 folds.'),
      P('5.3 Training settings (fixed, same for all deep models)', H2),
      bullets(['Sample: 50,000 buildings (seed 42); class counts Low 37,462 · Medium 9,844 · High 2,694.',
               'Class imbalance handled with inverse-frequency class weights in the loss (all models).',
               'Deep models: 6 epochs, batch 256, AdamW (weight decay 1e-4), one-cycle learning-rate schedule, mixed precision, flips + 90° rotations augmentation; '
               'patches upsampled 32→64 px for ResNets; per-fold band normalisation computed from training blocks only (no leakage).',
               'Tabular: 14 features (S2 bands B2,B3,B4,B8,B11, NDVI, NDWI, DEM, slope, HAND, distance to river, building density within 100 m, land cover, footprint area).',
               'No hyper-parameter tuning on the test folds. Fixed reasonable defaults were used for every model so that the comparison is fair (tuning is future work with nested CV).']),
      P('5.4 Metrics', H2),
      table([['Metric', 'Meaning (simple)', 'Why'],
             ['Macro-F1 (primary)', 'Average of F1 for Low, Medium, High (each class counts equally)', 'Fair under imbalance; proposal metric'],
             ['Balanced accuracy', 'Average recall of the three classes', 'Shows how many of each class are found'],
             ['QWK', 'Quadratic-weighted kappa: agreement beyond chance, big mistakes (Low↔High) penalised more', 'Classes are ordered (ordinal)'],
             ['AUC (High vs rest)', 'Probability the model ranks a High building above a non-High one', 'Comparable to flood-susceptibility papers'],
             ['Latency', 'Milliseconds to predict 1,000 buildings', 'Operational speed (NFR-2.1)']],
            [3.3 * cm, 8.3 * cm, 4.8 * cm]),
      P('IoU and MAE from the proposal are not used: IoU needs a segmentation output and MAE needs true damage percentages — neither exists for this task.', SM),
      PageBreak()]

# ---------- 6. Hypothesis testing theory ----------
S += [P('6. Hypothesis testing — the theory used to select the best model', H1),
      P('A higher average score can happen by chance. Hypothesis testing tells us whether the difference is larger than random fold-to-fold variation. '
        'We follow the method recommended by Demšar (2006) for comparing several models over several test sets.'),
      table([['Test', 'Null hypothesis H0', 'What it uses', 'Decision rule'],
             ['Friedman', 'All models have equal performance (equal mean ranks)', 'Rank of each model in each of the 10 folds', 'p < 0.05 → at least one model differs'],
             ['Iman–Davenport', 'Same as Friedman (less conservative F version)', 'Friedman χ² converted to F', 'p < 0.05 → reject H0'],
             ['Nemenyi post-hoc', 'Two models have equal mean rank', 'Critical difference CD = q<sub>α</sub>√(k(k+1)/6n)', 'Rank gap > CD → different'],
             ['Wilcoxon signed-rank (Holm)', 'Best model is not better than model j', '10 paired fold differences in macro-F1', 'Holm-adjusted p < 0.05 → best is better'],
             ['McNemar', 'Best and runner-up make the same number of errors', 'Buildings where only one of the two is correct (b vs c)', 'p < 0.05 → error rates differ'],
             ['Block bootstrap 95% CI', '—', '1,000 resamples of whole spatial blocks', 'Non-overlapping CIs = clear separation']],
            [3.2 * cm, 4.6 * cm, 4.6 * cm, 4.0 * cm]),
      bullets(['<b>p-value:</b> the probability of seeing a difference at least this large if H0 were true. Small p = evidence against H0.',
               '<b>α = 0.05:</b> we accept a 5 % risk of a false "better" claim. With many pairwise tests we use the <b>Holm correction</b> to keep this risk at 5 % overall.',
               '<b>Why non-parametric tests:</b> fold scores are few (10) and not guaranteed normal; rank-based tests do not assume normality.',
               '<b>Selection rule used:</b> the selected model is the one with the best mean rank / macro-F1; we then report whether it is <i>statistically</i> better than '
               'each other model. If not significant, we say the models are statistically tied and prefer the simpler/faster one.']),
      PageBreak()]

# ---------- 7. Results ----------
summ = sorted(R['summary'], key=lambda r: -r['macro_f1'])
rows = [['Model', 'Macro-F1 (mean ± SD)', 'Bal. acc.', 'QWK', 'AUC High', 'Mean rank', 'Train s / fold', 'ms / 1000 bldgs']]
hl = None
for i, r in enumerate(summ):
    rows.append([r['model'], f"{r['macro_f1']:.3f} ± {r['f1_sd']:.3f}", f3(r['bal_acc']), f3(r['qwk']), f3(r['auc_high']),
                 f"{r['mean_rank']:.2f}", f"{r['fit_s']:.1f}", f"{r['infer_ms_per_1000']:.1f}"])
    if r['model'] == best: hl = i + 1
S += [P('7. Results', H1),
      P('7.1 Main comparison table (spatial 10-fold CV, measured)', H2),
      table(rows, [3.9 * cm, 2.9 * cm, 1.5 * cm, 1.4 * cm, 1.5 * cm, 1.5 * cm, 1.8 * cm, 1.9 * cm], hl=hl),
      P('Highlighted row = selected model. Latency for tabular models is CPU time in Colab (2 vCPU); for deep models it is T4 GPU time. '
        'Training time is per fold (about 45,000 training buildings).', SM),
      fig('fig_boxplot_f1.png', 16, 'Figure 1. Macro-F1 of every model in each of the 10 spatial folds. Each box = 10 numbers.')]
pre = R.get('pretraining')
if pre:
    S += [P('7.2 Does pre-training help? (same architecture, different starting weights)', H2), P(pre)]
rc = R['random_cv']
S += [P('7.3 Random split vs spatial split (why spatial CV matters)', H2),
      P(f"For {rc['model']}, a random 10-fold split gives macro-F1 {rc['f1_random']:.3f} and AUC(High) {rc['auc_random']:.3f}, while the spatial split gives "
        f"{rc['f1_spatial']:.3f} and {rc['auc_spatial']:.3f}. The difference ({rc['f1_random'] - rc['f1_spatial']:+.3f} macro-F1) is the optimism that a random split "
        'would have added. This is why our numbers should not be compared one-to-one with papers that used random splits.'),
      P('7.4 What the model learned (feature importance, LightGBM gain)', H2),
      table([['Feature', 'Share of total gain']] + [[f, f'{v:.3f}'] for f, v in R['importance'][:8]], [6 * cm, 4 * cm]),
      P(R.get('importance_text', ''), SM),
      fig('fig_confusion_best.png', 8.5, f'Figure 2. Pooled out-of-fold confusion matrix of {best} (rows = SAR-derived class, columns = prediction).'),
      PageBreak()]

# ---------- 8. Hypothesis test results ----------
fr = R['friedman']
S += [P('8. Hypothesis-testing results and model selection', H1),
      P(f"<b>Friedman test:</b> χ² = {fr['chi2']:.2f}, p = {pe(fr['p'])}; Iman–Davenport F = {fr['iman_F']:.2f}, p = {pe(fr['p_iman'])} "
        f"(k = {len(R['summary'])} models, n = 10 folds). "
        + ('<b>H0 is rejected</b>: the models do not all perform the same.' if fr['p'] < 0.05 else 'H0 cannot be rejected.')),
      P(f"<b>Nemenyi critical difference</b> (α = 0.05): CD = {R['nemenyi_CD']:.2f} rank units. Models whose mean ranks differ by more than this are significantly different."),
      fig('fig_cd_diagram.png', 16, 'Figure 3. Critical-difference diagram (mean Friedman rank; lower is better; red bar = CD).')]
wrows = [['Selected model vs', 'Mean ΔF1', 'Folds won', 'p (raw)', 'p (Holm)', 'Significant at 0.05?']]
for w in R['wilcoxon']:
    wrows.append([w['model'], f"{w['mean_diff']:+.3f}", f"{w['wins']}/10", pe(w['p_raw']), pe(w['p_holm']), 'Yes' if w['significant_0.05'] else 'No'])
mc = R['mcnemar']
S += [P('<b>Pairwise Wilcoxon signed-rank tests</b> (one-sided H1: selected model is better), Holm-corrected:'),
      table(wrows, [4.6 * cm, 2 * cm, 2 * cm, 2.4 * cm, 2.4 * cm, 3 * cm]),
      P(f"<b>McNemar test</b> ({best} vs runner-up {runner}) on all 50,000 out-of-fold predictions: b = {mc['b']} buildings only {best} got right, "
        f"c = {mc['c']} only {runner} got right; χ² = {mc['chi2']:.2f}, p = {pe(mc['p'])}."),
      table([['Model', 'Pooled macro-F1', '95% CI (block bootstrap)']] +
            [[c['model'], f"{c['pooled_macro_f1']:.3f}", f"{c['ci_low']:.3f} – {c['ci_high']:.3f}"] for c in R['bootstrap_ci']], [5.5 * cm, 3.5 * cm, 5 * cm]),
      P('<b>Decision.</b> ' + R['decision_text'], BOX), PageBreak()]

# ---------- 9. Literature ----------
S += [P('9. Comparison with published research', H1),
      table([['Study', 'Task / data', 'Validation', 'Best model', 'Reported result'],
             ['Kurugama et al. (2024), J. Flood Risk Management, doi:10.1111/jfr3.12980', 'Flood susceptibility, Rathnapura (Sri Lanka); 595 inventory points, 13 factors', 'Train/test split (not spatially blocked)', 'LightGBM (vs GBM, XGBoost, CatBoost, LogitBoost)', 'AUC 0.970, F1 0.907, κ 0.813'],
             ['Seleem et al. (2022), Geomatics, Natural Hazards & Risk 13(1)', 'Urban pluvial flood susceptibility, Berlin; CNN, ANN, RF, SVM; 2–30 m', 'Test set + transfer to another area', 'Random Forest; CNN transferred best', 'All AUC ≥ 0.87; transfer AUC ≥ 0.80'],
             ['Gupta et al. (2019), CVPR-W (xBD)', 'Building damage (4 classes) from pre+post 0.5 m imagery', 'Official split', 'Baseline CNN', 'Different task (post-event damage)'],
             ['<b>This work (M1)</b>', 'Building-level flood exposure, lower Kelani; 341,971 buildings; pre-flood inputs only', 'Spatial 10-fold block CV + hypothesis tests',
              best, f"Macro-F1 {bs['macro_f1']:.3f}; AUC(High) {bs['auc_high']:.3f}"]],
            [3.6 * cm, 4.2 * cm, 2.9 * cm, 2.8 * cm, 2.9 * cm]),
      P('<b>How to read this comparison.</b> ' + R['lit_text']),
      P('The proposal\'s targets (macro-F1 ≥ 0.78, MAE ≤ 12 %, IoU ≥ 0.75) were set for a damage-grade task. They are <b>not met and not directly applicable</b> to the '
        'exposure task; we report this honestly. The claim "Baseline 1 ResNet F1 of 0.69" in the proposal could not be traced to a source and should be removed.', WARN)]

# ---------- 10. Demo ----------
FN = R['final']
S += [P('10. Final model and local web demo', H1),
      P(f"The selected model ({best}) was re-trained on all 50,000 sample buildings and then applied to all {R['n_buildings']:,} buildings in "
        f"{FN['infer_s']:.1f} s ({FN['ms_per_1000']:.1f} ms per 1,000 buildings). On the {FN['n_unseen']:,} buildings that were never in the 50,000-building sample, "
        f"agreement with the SAR-derived class is macro-F1 {FN['f1_unseen']:.3f} (note: these buildings share neighbourhoods with training buildings, so this is not a spatial test). "
        f"Predicted classes (Low / Medium / High): {FN['pred_counts'][0]:,} / {FN['pred_counts'][1]:,} / {FN['pred_counts'][2]:,}; SAR-derived: "
        f"{FN['sar_counts'][0]:,} / {FN['sar_counts'][1]:,} / {FN['sar_counts'][2]:,}."),
      P('The folder <b>M1_demo</b> contains <b>index.html</b>, <b>run_demo.bat</b> and an <b>assets</b> folder. It works offline.'),
      bullets(['Option A: double-click <b>index.html</b> (Chrome or Edge).',
               'Option B (local web server): double-click <b>run_demo.bat</b> → it runs <font face="Courier">python -m http.server 8000</font> and opens http://localhost:8000.',
               f'The map shows all {R["n_buildings"]:,} buildings on the cloud-free Sentinel-2 image. Colour by model prediction, SAR label, correct/wrong, or P(High). '
               'Toggle the SAR flood-water layer. Click a building to see its prediction, SAR label, distance to flood and HAND.',
               'Below the map: the model comparison table, bar chart, hypothesis-test results, figures, literature comparison and limitations.']),
      P('<b>Suggested 3-minute demo script:</b> (1) show the Sentinel-2 image and SAR flood layer; (2) switch to "SAR label" then "Model prediction" — point at '
        'Kolonnawa/Kaduwela where High exposure clusters; (3) switch to "Correct / wrong" and explain errors honestly (urban double-bounce, receding flood); '
        '(4) scroll to the comparison table and Friedman/Wilcoxon results; (5) end with limitations and next steps.', BOX)]

# ---------- 11. Limitations ----------
S += [P('11. Limitations and threats to validity', H1),
      bullets(['<b>Label proxy:</b> exposure (distance to SAR water), not damage. No damage percentages exist, so MAE is not measurable.',
               '<b>Timing:</b> the 2 Dec SAR image is ~1 day after the Kelani peak; true exposure was larger, so some exposed buildings are labelled Low (label noise, biased towards under-labelling High).',
               '<b>Urban SAR blindness:</b> double-bounce hides water between dense buildings (1.47 % of buildings showed strong VV brightening).',
               '<b>One event, one basin:</b> results may not transfer to other floods or rivers without re-validation.',
               '<b>Resolution:</b> Sentinel-2 10 m cannot see individual roofs; SRTM 30 m DEM has metre-level vertical errors in towns.',
               '<b>No M4 forecast yet:</b> the forecast flood probability, the key input of the proposed HSC-Attention design, is not yet available; the D6 prototype uses terrain only.',
               '<b>Fixed hyper-parameters:</b> no tuning was done (to keep the comparison fair and avoid test-set tuning); deep models trained only 6 epochs on a free GPU.',
               '<b>Sample:</b> models were compared on 50,000 of 341,971 buildings; the final model predicts all buildings.'])]

# ---------- 12. Next steps ----------
S += [P('12. Next steps after Progress 01', H1),
      table([['Priority', 'Task', 'Expected output'],
             ['1', 'Get M4 3-day flood probability raster for Ditwah (or simulate with HAND-based inundation for prototype)', 'Hydro stream with forecast input → true "predictive" HSC-Attention'],
             ['2', 'Second event (May 2016 Kelani / June 2024)', 'Temporal transfer test: train Ditwah, test other flood'],
             ['3', 'Nested CV hyper-parameter tuning for best tabular and best deep model', 'Fair tuned comparison'],
             ['4', 'Ablations on HSC-Attention (No-DEM, No-HAND, concat vs attention, heads)', 'Evidence for each design choice'],
             ['5', 'xBD flood events damage-grade track', '4-class damage model (supports the proposal\'s damage objective)'],
             ['6', 'Validate labels with Copernicus EMS EMSR851 / UNOSAT delineations', 'Independent label quality check'],
             ['7', 'GeoJSON export + dashboard integration with M2–M4', 'System integration (FR-1.6, FR-1.7)']],
            [1.6 * cm, 8.6 * cm, 6.2 * cm]), PageBreak()]

# ---------- 13. Viva Q&A ----------
qa = R['viva']
S += [P('13. Likely panel questions and answers', H1)]
for q, a in qa:
    S += [P(f'<b>Q: {q}</b>', B), P('A: ' + a, B)]
S += [PageBreak()]

# ---------- 14. Reproducibility ----------
S += [P('14. Reproducibility record', H1),
      table([['Item', 'Value'],
             ['Notebook', 'Google Drive: M1_Research_Main.ipynb (steps 6–10); Untitled21.ipynb (steps 2–5, GEE exploration)'],
             ['GEE project', 'sliit-research-2026'],
             ['GEE export task IDs', 'Raster stack 3QTMHS34SYPVPNRMMOU36N3B · Label raster W2FKP3R7YTK2VFCLBNQC4E24 · Building points GT56UEQQHY3FCCRN2RE4HGR5'],
             ['Data files (Drive/M1_Research)', 'M1_raster_stack_v1.tif, M1_label_raster_v2.tif, M1_building_points_v2.csv, M1_buildings_dataset_v2.parquet, M1_sample_with_folds.parquet'],
             ['Results (Drive/M1_Research/results)', 'cv_tabular.csv, cv_deep.csv, oof_*.npz, hypothesis_tests.json, model_summary.csv, nemenyi_pvalues.csv, figures/, predictions_all_buildings.parquet'],
             ['Random seed', '42 (sample, folds, models); fold k uses seed 42+k for deep models'],
             ['Software', R.get('software', 'Python 3.13, PyTorch, scikit-learn 1.6.1, XGBoost 3.4.1, LightGBM 4.6.0, torchgeo, scikit-posthocs')],
             ['Hardware', 'Google Colab free tier, NVIDIA Tesla T4 (15 GB)']],
            [4.2 * cm, 12.2 * cm])]

# ---------- References ----------
refs = ['Demšar, J. (2006). Statistical comparisons of classifiers over multiple data sets. Journal of Machine Learning Research, 7, 1–30.',
        'Gupta, R. et al. (2019). xBD: A dataset for assessing building damage from satellite imagery. CVPR Workshops.',
        'Kurugama, K. M., Kazama, S., Hiraga, Y., Samarasuriya, C. (2024). A comparative spatial analysis of flood susceptibility mapping using boosting machine learning algorithms in Rathnapura, Sri Lanka. Journal of Flood Risk Management. doi:10.1111/jfr3.12980.',
        'Ploton, P. et al. (2020). Spatial validation reveals poor predictive performance of large-scale ecological mapping models. Nature Communications, 11, 4540.',
        'Seleem, O., Ayzel, G., Costa Tomaz de Souza, A., Bronstert, A., Heistermann, M. (2022). Towards urban flood susceptibility mapping using data-driven models in Berlin, Germany. Geomatics, Natural Hazards and Risk, 13(1), 1640–1662.',
        'Wang, Y., Ait Ali Braham, N., Xiong, Z., Liu, C., Albrecht, C. M., Zhu, X. X. (2023). SSL4EO-S12: A large-scale multi-modal, multi-temporal dataset for self-supervised learning in Earth observation. arXiv:2211.07044 (IEEE GRSM).',
        'He, K., Zhang, X., Ren, S., Sun, J. (2016). Deep residual learning for image recognition. CVPR.',
        'Vaswani, A. et al. (2017). Attention is all you need. NeurIPS.',
        'Breiman, L. (2001). Random forests. Machine Learning, 45, 5–32.  ·  Chen, T., Guestrin, C. (2016). XGBoost. KDD.  ·  Ke, G. et al. (2017). LightGBM. NeurIPS.',
        'Dietterich, T. G. (1998). Approximate statistical tests for comparing supervised classification learning algorithms. Neural Computation, 10(7), 1895–1923.',
        'Copernicus EMS (2025). EMSR851 — Flood in Sri Lanka (Tropical Cyclone Ditwah). mapping.emergency.copernicus.eu',
        'Ada Derana (2 Dec 2025). Water level of Kelani River dropped to minor flood level; Newsfirst (1 Dec 2025). Kelani River at 8.45 feet.',
        'Google Earth Engine data catalog: Sentinel-1 GRD, Sentinel-2 SR Harmonized, Cloud Score+, Open Buildings v3, SRTM, MERIT Hydro, JRC GSW 1.4, ESA WorldCover v200.']
S += [P('References', H1)] + [P(r, SM) for r in refs]

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=2 * cm,
                        title='M1 Research Report — Predictive Building Flood-Exposure Assessment', author='J.A.S. Dulanjana (IT23401112)')
doc.build(S, onFirstPage=footer, onLaterPages=footer)
print('PDF written:', OUT)
