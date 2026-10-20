# M1 – House Impact (Progress Presentation 1)

**Component:** Predictive building flood impact under simulated future flood extents via a Spatial Cross-Attention (HSC-Attention) network
**Project:** J26-DS-360 FloodSense-LK (SLIIT) · **Author:** Sandun Dulanjana

## What this module does (PP1 scope)

For every building in the lower Kelani basin (bbox `79.85, 6.90, 80.22, 7.02`), the module predicts a **3-class flood exposure level**. It uses only **pre-flood** inputs: a Sentinel-2 composite, terrain, and hydrology. The labels come from Sentinel-1 SAR change detection for Cyclone Ditwah (flood peak 1–2 Dec 2025).

| Class | Rule (distance from building to SAR flood water) |
|---|---|
| High | ≤ 100 m |
| Medium | 100–300 m |
| Low | > 300 m |

**Scope change (honest note):** the proposal targets damage grades. No building-damage labels exist for Sri Lanka, and 10 m imagery cannot see roof damage. For PP1 the target is therefore *flood exposure*, which is the first condition for damage. The damage-grade task continues as a separate track using xBD.

## Data (all free)

- Sentinel-2 SR Harmonized + Cloud Score+ (cs_cdf ≥ 0.60), a median composite of 140 scenes
- Sentinel-1 GRD (VV/VH, descending): before = Oct to mid-Nov 2025, after = 2 Dec 2025
- Google Open Buildings v3 (confidence ≥ 0.75)
- SRTM DEM, MERIT Hydro HAND, JRC Global Surface Water, ESA WorldCover

Large rasters and parquet files live in Google Drive (`MyDrive/M1_Research`). They are not stored in git (see `.gitignore`).

## Pipeline

| Step | Script | Runs on |
|---|---|---|
| 2 | `src/gee/step02_gee_data_check.py` – data availability check | GEE |
| 3 | `src/gee/step03_cloudfree_composite_tiles.py` – cloud-free S2 composite | GEE |
| 4b | `src/gee/step04b_flood_mask_sensitivity.py` – 4-rule SAR flood mask sensitivity test (variant D chosen) | GEE |
| 4e | `src/gee/step04e_export_label_raster_and_points.py` – flood label raster + building points | GEE |
| 5 | `src/gee/step05_export_raster_stack.py` – 10-band input raster stack | GEE |
| 6 | `src/pipeline/step06_build_dataset.py` – building dataset, exact distance labels, 50k sample, 10 spatial folds (2 km blocks) | Colab |
| 7 | `src/pipeline/step07_tabular_models.py` – LogReg, RF, XGBoost, LightGBM | Colab |
| 8 | `src/pipeline/step08_deep_models.py` – SimpleCNN, ResNet18 (random / ImageNet), ResNet50 SSL4EO, Dual-Stream, HSC-Attention | Colab T4 |
| 9 | `src/pipeline/step09_hypothesis_tests.py`, `step09b_results_dump.py` – Friedman, Nemenyi, Wilcoxon-Holm, McNemar, bootstrap CI | Colab |
| 10 | `src/pipeline/step10_final_model_and_demo.py` – final model on all buildings + demo data | Colab T4 |
| Report | `src/report/*.py` – builds `docs/M1_PP1_Research_Report.pdf` | local |

The GEE scripts were reconstructed from the notebook cells that were actually run. The original Colab notebooks are in Drive.

## Results (spatial 10-fold CV, measured)

| Model | Macro-F1 (mean ± sd) | AUC (High) |
|---|---|---|
| **D6 HSC-Attention** | **0.666 ± 0.030** | **0.963** |
| D2 ResNet18 (random init) | 0.648 | 0.959 |
| D1 SimpleCNN | 0.644 | 0.953 |
| D3 ResNet18 (ImageNet) | 0.642 | 0.958 |
| D5 Dual-Stream concat (Baseline 1) | 0.636 | 0.957 |
| T2 Random Forest | 0.551 | 0.880 |
| T4 LightGBM | 0.543 | – |
| T3 XGBoost | 0.531 | – |
| D4 ResNet50 SSL4EO (RGB) | 0.528 | 0.928 |
| T1 Logistic Regression | 0.473 | – |

- Friedman χ² = 78.37, p = 3.4e-13. Wilcoxon with Holm correction: D6 is better than all 9 other models (p_holm ≤ 0.015).
- Nemenyi (CD = 4.28) **cannot** separate D6 from the other deep models, so the margin is small but consistent.
- Random vs spatial CV (RF): macro-F1 0.605 vs 0.551, which shows a random split inflates scores.
- Final model: 341,971 buildings predicted in 71.8 s (≈210 ms per 1,000). Macro-F1 on buildings outside the training sample is 0.758.

Full details are in `docs/M1_PP1_Research_Report.pdf` and `outputs/results/`.

## Reproduce

```bash
pip install -r requirements.txt
earthengine authenticate   # GEE project: sliit-research-2026
```

Run the GEE scripts (steps 2–5), then the pipeline scripts in Colab with Drive mounted at `/content/drive/MyDrive/M1_Research`. Seed = 42.

## Web demo (offline)

`web/index.html` with deck.gl 8.9.35, bundled in `web/assets/`. Step 10 generates the data file `web/assets/data.js` (~MBs). It is git-ignored: copy it from `MyDrive/M1_Research/demo/assets/`. Then open `run_demo.bat` or `index.html`.

## Limitations

- One event and one basin
- SAR labels are noisy (receding water on 2 Dec, urban double-bounce)
- The M4 forecast input is not yet connected, so HSC-Attention's main advantage is not yet tested
