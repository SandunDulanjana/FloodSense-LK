import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import (accuracy_score, f1_score, precision_score,
                             recall_score, cohen_kappa_score, confusion_matrix)
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "outputs" / "reference_dataset" / "M3_training_table_all_districts.csv"
RES = ROOT / "outputs" / "results"; RES.mkdir(parents=True, exist_ok=True)
MODELS = ROOT / "models"; MODELS.mkdir(parents=True, exist_ok=True)

SEED, N_FOLDS, TARGET_F1 = 42, 5, 0.75
RUN_SVM = True                    # set False if the SVM takes too long
BASE = ["B2","B3","B4","B5","B6","B7","B8","B8A","B11","B12","NDVI","NDWI","elevation","slope","aspect"]
EXCLUDE = ["NDVI_count"]
TREE_MODELS = ["Random Forest", "XGBoost", "LightGBM"]

df = pd.read_csv(TABLE)
TS = [c for c in df.columns if c.startswith(("NDVI_", "NDWI_")) and c not in EXCLUDE]
FEATURE_SETS = {"base": BASE, "base+timeseries": BASE + TS}
print({k: len(v) for k, v in FEATURE_SETS.items()})

le = LabelEncoder(); y = le.fit_transform(df["crop_type"])
classes, labels = list(le.classes_), list(range(len(le.classes_)))
groups = df["field_id"].values

def make_models():
    m = {
        "Random Forest": make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
                                   class_weight="balanced_subsample", n_jobs=-1, random_state=SEED)),
        "XGBoost": XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1,
                                 subsample=0.8, colsample_bytree=0.8, eval_metric="mlogloss",
                                 n_jobs=-1, random_state=SEED),
        "LightGBM": LGBMClassifier(n_estimators=300, learning_rate=0.1, num_leaves=31,
                                   class_weight="balanced", n_jobs=-1, random_state=SEED, verbose=-1),
    }
    if RUN_SVM:
        m["SVM (RBF)"] = make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(),
            SVC(C=10, gamma="scale", class_weight="balanced", random_state=SEED))
    return m

def fit(name, model, Xtr, ytr):
    if name == "XGBoost":
        model.fit(Xtr, ytr, sample_weight=compute_sample_weight("balanced", ytr))
    else:
        model.fit(Xtr, ytr)
    return model

def slug(s):
    return s.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("+", "_")

def field_level(pred):
    t = pd.DataFrame({"field_id": groups, "y": y, "p": pred})
    fl = t.groupby("field_id").agg(y=("y", "first"), p=("p", lambda s: s.mode().iloc[0]))
    return fl["y"].values, fl["p"].values

# Same folds for every model and feature set; all pixels of a field stay in one fold
cv = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
folds = list(cv.split(np.zeros(len(y)), y, groups))

oof, fold_f1 = {}, {}
for fs_name, cols in FEATURE_SETS.items():
    X = df[cols]
    for name in make_models():
        pred = np.empty(len(y), dtype=int); scores = []
        for tr, te in folds:
            m = fit(name, make_models()[name], X.iloc[tr], y[tr])
            pred[te] = m.predict(X.iloc[te])
            scores.append(f1_score(y[te], pred[te], labels=labels, average="macro", zero_division=0))
        oof[(fs_name, name)], fold_f1[(fs_name, name)] = pred, scores
        print(f"{fs_name:16s} {name:14s} macro-F1 per fold:", np.round(scores, 3))

rows, per_class = [], []
for (fs_name, name), pred in oof.items():
    f1c = f1_score(y, pred, labels=labels, average=None, zero_division=0)
    prc = precision_score(y, pred, labels=labels, average=None, zero_division=0)
    rcc = recall_score(y, pred, labels=labels, average=None, zero_division=0)
    fy, fp = field_level(pred)
    rows.append({"feature_set": fs_name, "model": name,
                 "overall_accuracy": accuracy_score(y, pred), "macro_f1": f1c.mean(),
                 "kappa": cohen_kappa_score(y, pred),
                 "fold_f1_mean": np.mean(fold_f1[(fs_name, name)]),
                 "fold_f1_std": np.std(fold_f1[(fs_name, name)]),
                 "field_accuracy": accuracy_score(fy, fp),
                 "field_macro_f1": f1_score(fy, fp, labels=labels, average="macro", zero_division=0),
                 **{f"F1_{c}": v for c, v in zip(classes, f1c)}})
    for c, p_, r_, f_ in zip(classes, prc, rcc, f1c):
        per_class.append({"feature_set": fs_name, "model": name, "class": c,
                          "precision": p_, "recall": r_, "f1": f_, "meets_target": f_ >= TARGET_F1})
comp = pd.DataFrame(rows).sort_values("macro_f1", ascending=False).round(4)
pc = pd.DataFrame(per_class).round(4)
comp.to_csv(RES / "model_comparison.csv", index=False)
pc.to_csv(RES / "per_class_metrics.csv", index=False)
print("\n", comp.to_string(index=False))

best_row = comp.iloc[0]
tree_row = comp[comp["model"].isin(TREE_MODELS)].iloc[0]
best_key = (best_row["feature_set"], best_row["model"])
tree_key = (tree_row["feature_set"], tree_row["model"])
print("\nBest overall:", best_key, "| best tree model (for SHAP):", tree_key)

pred_df = df[["field_id", "district", "crop_type", "fill_level"]].copy()
for (fs_name, name), pred in oof.items():
    pred_df[f"{fs_name} | {name}"] = le.inverse_transform(pred)
pred_df.to_csv(RES / "oof_predictions.csv", index=False)

chk = pred_df.assign(correct=(pred_df["crop_type"] == pred_df[f"{best_key[0]} | {best_key[1]}"]))
print("\nAccuracy by district (best model):\n", chk.groupby("district")["correct"].mean().round(3))
print("\nAccuracy by fill_level (0 = primary window, 3 = Aug-Sep fill):\n",
      chk.groupby("fill_level")["correct"].agg(["mean", "size"]).round(3))
print("\nPer-class F1, best model:\n",
      pc[(pc["feature_set"] == best_key[0]) & (pc["model"] == best_key[1])]
      [["class", "f1", "meets_target"]].to_string(index=False))

keys = [k for k in oof if k[0] == best_key[0]]
fig, axes = plt.subplots(1, len(keys), figsize=(4.6 * len(keys), 4.6), squeeze=False)
for ax, k in zip(axes[0], keys):
    cm = confusion_matrix(y, oof[k], labels=labels)
    cmn = cm / cm.sum(axis=1, keepdims=True)
    ax.imshow(cmn, vmin=0, vmax=1, cmap="Greys")
    ax.set_xticks(labels); ax.set_xticklabels(classes)
    ax.set_yticks(labels); ax.set_yticklabels(classes)
    for i in labels:
        for j in labels:
            ax.text(j, i, f"{cm[i, j]}\n{cmn[i, j]*100:.0f}%", ha="center", va="center",
                    color="white" if cmn[i, j] > 0.5 else "black", fontsize=8)
    ax.set_title(f"{k[1]} ({k[0]})", fontsize=9); ax.set_xlabel("Predicted"); ax.set_ylabel("Reference")
plt.tight_layout(); plt.savefig(RES / "confusion_matrices.png", dpi=200); plt.close()

for fs_name, name in {best_key, tree_key}:
    model = fit(name, make_models()[name], df[FEATURE_SETS[fs_name]], y)
    joblib.dump(model, MODELS / f"final_{slug(name)}_{slug(fs_name)}.joblib", compress=3)
(MODELS / "m3_model_meta.json").write_text(json.dumps({
    "classes": classes, "excluded_features": EXCLUDE,
    "best_model": best_key[1], "best_feature_set": best_key[0],
    "best_tree_model": tree_key[1], "best_tree_feature_set": tree_key[0],
    "best_tree_features": FEATURE_SETS[tree_key[0]],
    "best_tree_file": f"final_{slug(tree_key[1])}_{slug(tree_key[0])}.joblib",
    "cv": f"StratifiedGroupKFold({N_FOLDS}) grouped by field_id", "seed": SEED}, indent=2))