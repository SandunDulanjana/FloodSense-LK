"""
M3 extra evaluation: ablations, repeated CV, per-district results, leave-one-district-out,
ROC / PR curves, field-level confusion matrix, misclassified-field list, model-comparison plots.

Run after build_training_table.py and train_evaluate.py:
    python src/evaluate_extra.py
Outputs go to outputs/results/extra_eval/
"""
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder, label_binarize
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import (f1_score, accuracy_score, confusion_matrix, roc_curve, auc,
                             precision_recall_curve, average_precision_score, recall_score)

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------ settings
ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "outputs" / "reference_dataset" / "M3_training_table_all_districts.csv"
RES = ROOT / "outputs" / "results"
OUT = RES / "extra_eval"; OUT.mkdir(parents=True, exist_ok=True)

SEED = 42
N_FOLDS = 5
REPEAT_SEEDS = [42, 1, 2]          # 3 different field-grouped splits -> mean +- std
N_TREES = 200                      # a bit smaller than the main run, for speed
BASE = ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12",
        "NDVI", "NDWI", "elevation", "slope", "aspect"]
EXCLUDE = ["NDVI_count"]
TERRAIN = ["elevation", "slope", "aspect"]
CLASS_COLORS = {"Other": "#7f7f7f", "Paddy": "#2a9d8f", "Tea": "#c8553d"}

plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 9})

# ------------------------------------------------------------------ data
df = pd.read_csv(TABLE)
TS = [c for c in df.columns if c.startswith(("NDVI_", "NDWI_")) and c not in EXCLUDE]
le = LabelEncoder(); y = le.fit_transform(df["crop_type"])
classes = list(le.classes_); labels = list(range(len(classes)))
groups = df["field_id"].values
district = df["district"].values
print(f"{len(df)} rows | {df['field_id'].nunique()} fields | classes {classes}")

FEATURE_SETS = {
    "full (15 base + 26 TS)": BASE + TS,
    "base only (15)": BASE,
    "no terrain": [c for c in BASE + TS if c not in TERRAIN],
    "no September": [c for c in BASE + TS if "_2025_09" not in c],
    "no terrain, no Sept": [c for c in BASE + TS if c not in TERRAIN and "_2025_09" not in c],
    "spectral + indices only": [c for c in BASE if c not in TERRAIN],
    "time series only": TS,
}


def make_rf():
    return make_pipeline(
        SimpleImputer(strategy="median", keep_empty_features=True),
        RandomForestClassifier(n_estimators=N_TREES, min_samples_leaf=3,
                               class_weight="balanced_subsample", n_jobs=-1, random_state=SEED))


def folds_for(seed):
    cv = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed)
    return list(cv.split(np.zeros(len(y)), y, groups))


def oof_predict(cols, seed):
    """Field-grouped out-of-fold prediction. Returns labels, probabilities, fold scores."""
    X = df[cols]
    pred = np.zeros(len(y), dtype=int)
    proba = np.zeros((len(y), len(classes)))
    fold_f1 = []
    for tr, te in folds_for(seed):
        m = make_rf().fit(X.iloc[tr], y[tr])
        proba[te] = m.predict_proba(X.iloc[te])
        pred[te] = proba[te].argmax(1)
        fold_f1.append(f1_score(y[te], pred[te], labels=labels, average="macro", zero_division=0))
    return pred, proba, fold_f1


def field_vote(pred):
    t = pd.DataFrame({"field_id": groups, "district": district, "y": y, "p": pred})
    fl = t.groupby("field_id").agg(district=("district", "first"), y=("y", "first"),
                                   p=("p", lambda s: s.mode().iloc[0]))
    fl["share_correct"] = t.assign(ok=(t["y"] == t["p"])).groupby("field_id")["ok"].mean()
    return fl


# ------------------------------------------------------------------ 1. ablations + repeated CV
print("\n[1] Feature-set ablations (repeated field-grouped CV)")
rows, fold_records, keep = [], [], {}
for name, cols in FEATURE_SETS.items():
    per_rep = []
    for s in REPEAT_SEEDS:
        pred, proba, ff = oof_predict(cols, s)
        f1c = f1_score(y, pred, labels=labels, average=None, zero_division=0)
        per_rep.append({"macro_f1": f1c.mean(), "acc": accuracy_score(y, pred),
                        **{f"F1_{c}": v for c, v in zip(classes, f1c)}})
        fold_records += [{"feature_set": name, "seed": s, "fold": i, "macro_f1": v}
                         for i, v in enumerate(ff)]
        if name.startswith("full") and s == SEED:
            keep = {"pred": pred, "proba": proba}
    r = pd.DataFrame(per_rep)
    rows.append({"feature_set": name, "n_features": len(cols),
                 **{f"{c}_mean": r[c].mean() for c in r.columns},
                 **{f"{c}_std": r[c].std(ddof=0) for c in r.columns}})
    print(f"  {name:26s} macro-F1 {r['macro_f1'].mean():.3f} +- {r['macro_f1'].std(ddof=0):.3f} | "
          f"Tea F1 {r['F1_Tea'].mean() if 'F1_Tea' in r else float('nan'):.3f}")
abl = pd.DataFrame(rows).round(4)
abl.to_csv(OUT / "ablation_results.csv", index=False)
pd.DataFrame(fold_records).to_csv(OUT / "fold_scores_all_sets.csv", index=False)

# ablation bar chart: macro-F1 and per-class F1 with error bars
fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={"width_ratios": [1, 1.6]})
ax = axes[0]
order = abl.sort_values("macro_f1_mean")
ax.barh(order["feature_set"], order["macro_f1_mean"], xerr=order["macro_f1_std"],
        color="#4c6a92", capsize=3)
for i, (v, e, n) in enumerate(zip(order["macro_f1_mean"], order["macro_f1_std"], order["n_features"])):
    ax.text(v + e + 0.004, i, f"{v:.3f} ({n} feat.)", va="center", fontsize=8)
ax.set_xlim(max(0.5, order["macro_f1_mean"].min() - 0.08), 1.06)
ax.set_xlabel("Macro-F1 (mean +- std over 3 splits)"); ax.set_title("Feature-set ablation")
ax = axes[1]
w = 0.8 / len(classes); x = np.arange(len(abl))
for k, c in enumerate(classes):
    ax.bar(x + k * w, abl[f"F1_{c}_mean"], w, yerr=abl[f"F1_{c}_std"], capsize=2,
           label=c, color=CLASS_COLORS.get(c))
ax.set_xticks(x + w * (len(classes) - 1) / 2)
ax.set_xticklabels(abl["feature_set"], rotation=30, ha="right")
ax.axhline(0.75, color="black", ls="--", lw=0.8); ax.text(len(abl) - 0.5, 0.76, "target 0.75", fontsize=8, ha="right")
ax.set_ylim(0.5, 1.02); ax.set_ylabel("F1"); ax.set_title("Per-class F1 by feature set"); ax.legend(ncol=3)
plt.tight_layout(); plt.savefig(OUT / "ablation_overview.png", dpi=200); plt.close()

# fold-score spread
fs = pd.DataFrame(fold_records)
fig, ax = plt.subplots(figsize=(9, 4.4))
names = list(FEATURE_SETS)
ax.boxplot([fs.loc[fs.feature_set == n, "macro_f1"] for n in names], showmeans=True)
ax.set_xticklabels(names)
for i, n in enumerate(names, 1):
    v = fs.loc[fs.feature_set == n, "macro_f1"]
    ax.scatter(np.random.default_rng(0).normal(i, 0.04, len(v)), v, s=10, color="black", alpha=0.5)
ax.set_ylabel("Macro-F1 per fold"); ax.set_title("Fold-to-fold spread (3 splits x 5 folds)")
plt.xticks(rotation=25, ha="right"); plt.tight_layout()
plt.savefig(OUT / "fold_score_spread.png", dpi=200); plt.close()

# ------------------------------------------------------------------ 2. detailed look at the full model
print("\n[2] Per-district results, curves and field-level view (full feature set)")
pred, proba = keep["pred"], keep["proba"]

# per-district metrics (macro-F1 only over classes that exist in that district)
drows = []
for d in sorted(set(district)):
    m = district == d
    present = sorted(set(y[m]))
    drows.append({"district": d, "pixels": int(m.sum()), "fields": int(pd.Series(groups[m]).nunique()),
                  "classes": "/".join(classes[i] for i in present),
                  "accuracy": accuracy_score(y[m], pred[m]),
                  "macro_f1_present_classes": f1_score(y[m], pred[m], labels=present, average="macro", zero_division=0),
                  **{f"recall_{classes[i]}": recall_score(y[m], pred[m], labels=[i], average="macro", zero_division=0)
                     for i in present}})
dist_tbl = pd.DataFrame(drows).round(4)
dist_tbl.to_csv(OUT / "per_district_metrics.csv", index=False)
print(dist_tbl.to_string(index=False))

# confusion matrices per district + overall (pixel level, row-normalised)
dists = sorted(set(district))
fig, axes = plt.subplots(1, len(dists) + 1, figsize=(4.2 * (len(dists) + 1), 4.2))
for ax, (title, m) in zip(axes, [("All districts", np.ones(len(y), bool))] + [(d, district == d) for d in dists]):
    cm = confusion_matrix(y[m], pred[m], labels=labels)
    with np.errstate(invalid="ignore", divide="ignore"):
        cmn = np.nan_to_num(cm / cm.sum(1, keepdims=True))
    ax.imshow(cmn, vmin=0, vmax=1, cmap="Blues")
    ax.set_xticks(labels); ax.set_xticklabels(classes); ax.set_yticks(labels); ax.set_yticklabels(classes)
    for i in labels:
        for j in labels:
            ax.text(j, i, f"{cm[i, j]}\n{cmn[i, j] * 100:.0f}%", ha="center", va="center", fontsize=8,
                    color="white" if cmn[i, j] > 0.55 else "black")
    ax.set_title(title); ax.set_xlabel("Predicted"); ax.set_ylabel("Reference")
plt.tight_layout(); plt.savefig(OUT / "confusion_by_district.png", dpi=200); plt.close()

# field-level confusion matrix + list of problem fields
fl = field_vote(pred)
fl["true"] = le.inverse_transform(fl["y"]); fl["predicted"] = le.inverse_transform(fl["p"])
fl.reset_index()[["field_id", "district", "true", "predicted", "share_correct"]] \
  .sort_values("share_correct").round(3).to_csv(OUT / "field_level_predictions.csv", index=False)
fl[fl["y"] != fl["p"]].reset_index()[["field_id", "district", "true", "predicted", "share_correct"]] \
  .round(3).to_csv(OUT / "misclassified_fields.csv", index=False)
cm = confusion_matrix(fl["y"], fl["p"], labels=labels)
fig, ax = plt.subplots(figsize=(4.4, 4.2))
ax.imshow(cm, cmap="Greys"); ax.set_xticks(labels); ax.set_xticklabels(classes)
ax.set_yticks(labels); ax.set_yticklabels(classes)
for i in labels:
    for j in labels:
        ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
ax.set_title(f"Field-level confusion (majority vote)\naccuracy {accuracy_score(fl['y'], fl['p']):.2f}")
ax.set_xlabel("Predicted"); ax.set_ylabel("Reference")
plt.tight_layout(); plt.savefig(OUT / "confusion_field_level.png", dpi=200); plt.close()

# share of correct pixels per field (which fields are hard?)
fl_sorted = fl.reset_index().sort_values("share_correct")
fig, ax = plt.subplots(figsize=(10, 3.8))
ax.bar(range(len(fl_sorted)), fl_sorted["share_correct"],
       color=[CLASS_COLORS[c] for c in fl_sorted["true"]])
ax.set_xticks([]); ax.set_ylabel("Share of pixels classified correctly")
ax.set_title("Per-field pixel accuracy (colour = true class); low bars are fields to re-check in QGIS")
for c, col in CLASS_COLORS.items():
    ax.bar(0, 0, color=col, label=c)
ax.legend(ncol=3, loc="lower right"); plt.tight_layout()
plt.savefig(OUT / "per_field_accuracy.png", dpi=200); plt.close()

# ROC and precision-recall curves (one-vs-rest)
Y = label_binarize(y, classes=labels)
fig, axes = plt.subplots(1, 2, figsize=(10, 4.4))
for k, c in enumerate(classes):
    fpr, tpr, _ = roc_curve(Y[:, k], proba[:, k])
    axes[0].plot(fpr, tpr, color=CLASS_COLORS.get(c), label=f"{c} (AUC {auc(fpr, tpr):.3f})")
    p_, r_, _ = precision_recall_curve(Y[:, k], proba[:, k])
    axes[1].plot(r_, p_, color=CLASS_COLORS.get(c), label=f"{c} (AP {average_precision_score(Y[:, k], proba[:, k]):.3f})")
axes[0].plot([0, 1], [0, 1], "k--", lw=0.7)
axes[0].set(xlabel="False positive rate", ylabel="True positive rate", title="ROC (out-of-fold)")
axes[1].set(xlabel="Recall", ylabel="Precision", title="Precision-recall (out-of-fold)")
for a in axes: a.legend(loc="lower right" if a is axes[0] else "lower left")
plt.tight_layout(); plt.savefig(OUT / "roc_pr_curves.png", dpi=200); plt.close()

# confidence of correct vs wrong pixels
conf = proba.max(1); ok = pred == y
fig, ax = plt.subplots(figsize=(6.2, 3.8))
ax.hist(conf[ok], bins=25, alpha=0.7, label=f"correct ({ok.sum()})", color="#2a9d8f")
ax.hist(conf[~ok], bins=25, alpha=0.7, label=f"wrong ({(~ok).sum()})", color="#c8553d")
ax.set_xlabel("Model confidence (max class probability)"); ax.set_ylabel("Pixels")
ax.set_title("Is the model less confident when it is wrong?"); ax.legend()
plt.tight_layout(); plt.savefig(OUT / "confidence_correct_vs_wrong.png", dpi=200); plt.close()

# accuracy by field size
size = pd.Series(groups).map(pd.Series(groups).value_counts()).values
bins = pd.cut(size, [0, 20, 50, 100, 250, 2000], labels=["<=20", "21-50", "51-100", "101-250", ">250"])
bs = pd.DataFrame({"bin": bins, "ok": ok}).groupby("bin", observed=True)["ok"].agg(["mean", "size"])
fig, ax = plt.subplots(figsize=(6, 3.6))
ax.bar(bs.index.astype(str), bs["mean"], color="#4c6a92")
for i, (m_, n_) in enumerate(zip(bs["mean"], bs["size"])):
    ax.text(i, m_ + 0.005, f"n={n_}", ha="center", fontsize=8)
ax.set_ylim(0.5, 1.03); ax.set_xlabel("Pixels in the field"); ax.set_ylabel("Pixel accuracy")
ax.set_title("Accuracy by field size"); plt.tight_layout()
plt.savefig(OUT / "accuracy_by_field_size.png", dpi=200); plt.close()

# ------------------------------------------------------------------ 3. leave-one-district-out
print("\n[3] Leave-one-district-out (train on two districts, test on the third)")
lodo_rows = []
for set_name in ["full (15 base + 26 TS)", "no terrain"]:
    cols = FEATURE_SETS[set_name]
    for d in dists:
        te = district == d; tr = ~te
        m = make_rf().fit(df.loc[tr, cols], y[tr])
        p = m.predict(df.loc[te, cols])
        present = sorted(set(y[te]))
        row = {"feature_set": set_name, "held_out_district": d, "pixels": int(te.sum()),
               "accuracy": accuracy_score(y[te], p),
               "macro_f1_present_classes": f1_score(y[te], p, labels=present, average="macro", zero_division=0)}
        for i in present:
            row[f"recall_{classes[i]}"] = recall_score(y[te], p, labels=[i], average="macro", zero_division=0)
        lodo_rows.append(row)
        print(f"  {set_name:24s} hold out {d:10s} acc {row['accuracy']:.3f} macroF1 {row['macro_f1_present_classes']:.3f}")
lodo = pd.DataFrame(lodo_rows).round(4)
lodo.to_csv(OUT / "leave_one_district_out.csv", index=False)

fig, axes = plt.subplots(1, 2, figsize=(11, 4))
piv = lodo.pivot(index="held_out_district", columns="feature_set", values="macro_f1_present_classes")
piv.plot.bar(ax=axes[0], color=["#4c6a92", "#e9a03b"], rot=0)
axes[0].set_ylim(0, 1.02); axes[0].set_ylabel("Macro-F1 (classes present)")
axes[0].set_title("Train on 2 districts, test on the 3rd"); axes[0].legend(fontsize=8)
rec_cols = [f"recall_{c}" for c in classes]
hm = lodo[lodo.feature_set.str.startswith("full")].set_index("held_out_district")[rec_cols]
im = axes[1].imshow(hm.values.astype(float), vmin=0, vmax=1, cmap="Greens")
axes[1].set_xticks(range(len(rec_cols))); axes[1].set_xticklabels(classes)
axes[1].set_yticks(range(len(hm))); axes[1].set_yticklabels(hm.index)
for i in range(hm.shape[0]):
    for j in range(hm.shape[1]):
        v = hm.values[i, j]
        axes[1].text(j, i, "n/a" if pd.isna(v) else f"{v:.2f}", ha="center", va="center", fontsize=9)
axes[1].set_title("Recall per class on the unseen district (full features)")
plt.tight_layout(); plt.savefig(OUT / "leave_one_district_out.png", dpi=200); plt.close()

# ------------------------------------------------------------------ 4. plots from the main run (all 4 models)
mc_path, pc_path = RES / "model_comparison.csv", RES / "per_class_metrics.csv"
if mc_path.exists() and pc_path.exists():
    print("\n[4] Model-comparison plots from model_comparison.csv")
    mc = pd.read_csv(mc_path); pc = pd.read_csv(pc_path)
    mc["label"] = mc["model"] + "\n" + mc["feature_set"]
    mc = mc.sort_values("macro_f1")
    fig, ax = plt.subplots(figsize=(8.5, 5))
    yy = np.arange(len(mc))
    ax.barh(yy + 0.2, mc["macro_f1"], 0.38, xerr=mc["fold_f1_std"], capsize=2, label="Pixel macro-F1 (+- fold std)", color="#4c6a92")
    ax.barh(yy - 0.2, mc["field_macro_f1"], 0.38, label="Field-level macro-F1", color="#e9a03b")
    ax.set_yticks(yy); ax.set_yticklabels(mc["label"], fontsize=7.5)
    ax.set_xlim(0.7, 1.0); ax.set_xlabel("Macro-F1"); ax.legend(loc="lower right")
    ax.set_title("Model comparison (field-grouped 5-fold CV)")
    plt.tight_layout(); plt.savefig(OUT / "model_comparison_bars.png", dpi=200); plt.close()

    pc["row"] = pc["model"] + " | " + pc["feature_set"]
    hm = pc.pivot(index="row", columns="class", values="f1")
    fig, ax = plt.subplots(figsize=(5.8, 4.8))
    ax.imshow(hm.values, vmin=0.7, vmax=1.0, cmap="YlGnBu")
    ax.set_xticks(range(hm.shape[1])); ax.set_xticklabels(hm.columns)
    ax.set_yticks(range(hm.shape[0])); ax.set_yticklabels(hm.index, fontsize=8)
    for i in range(hm.shape[0]):
        for j in range(hm.shape[1]):
            ax.text(j, i, f"{hm.values[i, j]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title("Per-class F1, every model"); plt.tight_layout()
    plt.savefig(OUT / "per_class_f1_heatmap.png", dpi=200); plt.close()

    effect = mc.pivot(index="model", columns="feature_set", values="macro_f1")
    if {"base", "base+timeseries"} <= set(effect.columns):
        effect["gain from time series"] = effect["base+timeseries"] - effect["base"]
        fig, ax = plt.subplots(figsize=(6, 3.6))
        vals = effect["gain from time series"].sort_values()
        ax.barh(vals.index, vals.values, color=["#c8553d" if v < 0 else "#2a9d8f" for v in vals.values])
        ax.axvline(0, color="black", lw=0.8)
        ax.set_xlabel("Change in macro-F1 when time-series features are added")
        ax.set_title("Do time-series features help?"); plt.tight_layout()
        plt.savefig(OUT / "time_series_gain_by_model.png", dpi=200); plt.close()

print(f"\nDone. Files are in {OUT}")
