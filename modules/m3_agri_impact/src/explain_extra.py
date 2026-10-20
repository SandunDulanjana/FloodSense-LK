"""
M3 extra explainability (XAI) outputs.

Run after train_evaluate.py (needs models/m3_model_meta.json and the saved model):
    python src/explain_extra.py
Outputs go to outputs/results/extra_xai/
"""
import json
import warnings
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import partial_dependence
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------ settings
ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
TABLE = ROOT / "outputs" / "reference_dataset" / "M3_training_table_all_districts.csv"
OUT = ROOT / "outputs" / "results" / "extra_xai"; OUT.mkdir(parents=True, exist_ok=True)

SEED = 42
N_PER_CLASS = 500          # pixels per class used for SHAP (speed only)
TOP_N = 15
PERM_REPEATS = 3
CLASS_COLORS = {"Other": "#7f7f7f", "Paddy": "#2a9d8f", "Tea": "#c8553d"}
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 9})

meta = json.loads((MODELS / "m3_model_meta.json").read_text())
FEATURES, classes = meta["best_tree_features"], meta["classes"]
model = joblib.load(MODELS / meta["best_tree_file"])
print("Explaining:", meta["best_tree_model"], "|", meta["best_tree_feature_set"], f"({len(FEATURES)} features)")

df = pd.read_csv(TABLE)
le = LabelEncoder().fit(classes)
df["y"] = le.transform(df["crop_type"])


def group_of(f):
    if f in ("elevation", "slope", "aspect"):
        return "Terrain"
    if f in ("NDVI", "NDWI"):
        return "Indices (composite)"
    if f.startswith("B") and f[1:2].isdigit():
        return "Spectral bands"
    if f.startswith("NDVI_20"):
        return "Monthly NDVI"
    if f.startswith("NDWI_20"):
        return "Monthly NDWI"
    return "Time-series summary"


GROUPS = {}
for f in FEATURES:
    GROUPS.setdefault(group_of(f), []).append(f)

# ------------------------------------------------------------------ balanced sample for SHAP
idx = (df.sample(frac=1, random_state=SEED).groupby("crop_type").head(N_PER_CLASS).index)
S = df.loc[idx].reset_index(drop=True)
X = S[FEATURES]
if hasattr(model, "named_steps"):                       # pipeline: impute, then explain the forest
    Xm = pd.DataFrame(model[:-1].transform(X), columns=FEATURES)
    est = model[-1]
else:
    Xm, est = X.copy(), model

explainer = shap.TreeExplainer(est)
sv = explainer.shap_values(Xm)
if isinstance(sv, list):
    sv = np.stack(sv, axis=-1)
ev = np.atleast_1d(explainer.expected_value)
assert sv.ndim == 3 and sv.shape[2] == len(classes), sv.shape
proba = est.predict_proba(Xm)
pred = proba.argmax(1)
print(f"SHAP computed for {len(S)} pixels")

mean_abs = pd.DataFrame(np.abs(sv).mean(0), index=FEATURES, columns=classes)
mean_abs["All classes"] = mean_abs.mean(1)
mean_abs = mean_abs.sort_values("All classes", ascending=False)
top = mean_abs.head(TOP_N)
top_feats = list(mean_abs.index[:TOP_N])

# ------------------------------------------------------------------ 1. beeswarm per class
for k, c in enumerate(classes):
    shap.summary_plot(sv[:, :, k], Xm, show=False, max_display=20)
    plt.title(f"SHAP beeswarm - {c}  (red = high feature value)")
    plt.tight_layout(); plt.savefig(OUT / f"shap_beeswarm_{c}.png", dpi=200); plt.close()

# ------------------------------------------------------------------ 2. stacked importance by class
fig, ax = plt.subplots(figsize=(7.5, 6))
bottom = np.zeros(len(top))
for c in classes:
    vals = top[c].values[::-1]
    ax.barh(range(len(top)), vals, left=bottom, label=c, color=CLASS_COLORS.get(c))
    bottom += vals
ax.set_yticks(range(len(top))); ax.set_yticklabels(top.index[::-1])
ax.set_xlabel("Mean |SHAP value|, stacked by class"); ax.legend()
ax.set_title(f"Top {TOP_N} features and the class they help most")
plt.tight_layout(); plt.savefig(OUT / "shap_stacked_by_class.png", dpi=200); plt.close()

# ------------------------------------------------------------------ 3. feature-group importance
grp = pd.DataFrame({g: np.abs(sv[:, [FEATURES.index(f) for f in fs], :]).sum(1).mean(0)
                    for g, fs in GROUPS.items()}, index=classes).T
grp["All classes"] = grp.mean(1)
grp_share = grp.div(grp.sum(0), axis=1) * 100
grp_share.round(1).to_csv(OUT / "shap_feature_group_share.csv")
fig, ax = plt.subplots(figsize=(8, 4.2))
cols = list(grp_share.columns)
left = np.zeros(len(cols))
palette = ["#4c6a92", "#2a9d8f", "#e9a03b", "#c8553d", "#8e6bbf", "#7f7f7f"]
for i, g in enumerate(grp_share.index):
    ax.barh(cols, grp_share.loc[g].values, left=left, label=g, color=palette[i % len(palette)])
    for j, v in enumerate(grp_share.loc[g].values):
        if v > 6:
            ax.text(left[j] + v / 2, j, f"{v:.0f}%", ha="center", va="center", color="white", fontsize=8)
    left += grp_share.loc[g].values
ax.set_xlabel("Share of total |SHAP| (%)"); ax.set_title("Which kind of information does the model use?")
ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
plt.tight_layout(); plt.savefig(OUT / "shap_feature_groups.png", dpi=200); plt.close()

# ------------------------------------------------------------------ 4. SHAP by district (is terrain a district proxy?)
per_pix = np.abs(sv).mean(2)                              # (samples, features), averaged over classes
by_dist = pd.DataFrame(per_pix, columns=FEATURES).groupby(S["district"].values).mean().T
by_dist = by_dist.loc[top_feats[:12]]
fig, ax = plt.subplots(figsize=(5.6, 5))
ax.imshow(by_dist.values, cmap="Oranges", aspect="auto")
ax.set_xticks(range(by_dist.shape[1])); ax.set_xticklabels(by_dist.columns)
ax.set_yticks(range(by_dist.shape[0])); ax.set_yticklabels(by_dist.index)
for i in range(by_dist.shape[0]):
    for j in range(by_dist.shape[1]):
        ax.text(j, i, f"{by_dist.values[i, j]:.3f}", ha="center", va="center", fontsize=8)
ax.set_title("Mean |SHAP| by district\n(same feature, different weight = district effect)")
plt.tight_layout(); plt.savefig(OUT / "shap_by_district.png", dpi=200); plt.close()

# ------------------------------------------------------------------ 5. dependence plots
for k, c in enumerate(classes):
    feats = list(pd.Series(np.abs(sv[:, :, k]).mean(0), index=FEATURES).sort_values(ascending=False).index[:4])
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.5))
    for ax, f in zip(axes.ravel(), feats):
        shap.dependence_plot(f, sv[:, :, k], Xm, ax=ax, show=False, interaction_index="auto")
        ax.set_title(f"{f}", fontsize=10)
    fig.suptitle(f"How the top features push predictions toward {c}", y=1.0)
    plt.tight_layout(); plt.savefig(OUT / f"shap_dependence_{c}.png", dpi=200); plt.close()

# ------------------------------------------------------------------ 6. single-pixel explanations (waterfall)
rng = np.random.default_rng(SEED)
for k, c in enumerate(classes):
    cand = {"confident_correct": np.where((S["y"] == k) & (pred == k))[0],
            "misclassified": np.where((S["y"] == k) & (pred != k))[0]}
    for kind, ids in cand.items():
        if len(ids) == 0:
            continue
        i = ids[np.argmax(proba[ids, k])] if kind == "confident_correct" else rng.choice(ids)
        expl = shap.Explanation(values=sv[i, :, k], base_values=ev[k],
                                data=Xm.iloc[i].values, feature_names=FEATURES)
        shap.plots.waterfall(expl, max_display=12, show=False)
        plt.title(f"{kind.replace('_', ' ')} | true {c}, predicted {classes[pred[i]]} "
                  f"(P={proba[i, k]:.2f}) | {S.loc[i, 'district']}", fontsize=9)
        plt.tight_layout(); plt.savefig(OUT / f"shap_waterfall_{c}_{kind}.png", dpi=200); plt.close()

# ------------------------------------------------------------------ 7. partial dependence (model-level, per class)
Xpd = df[FEATURES].sample(min(3000, len(df)), random_state=SEED)
pd_feats = [f for f in top_feats if f in FEATURES][:6]
fig, axes = plt.subplots(2, 3, figsize=(13, 7))
for ax, f in zip(axes.ravel(), pd_feats):
    r = partial_dependence(model, Xpd, [f], kind="average", grid_resolution=30,
                           response_method="predict_proba")
    grid, avg = r["grid_values"][0], r["average"]
    for k, c in enumerate(classes):
        ax.plot(grid, avg[k], color=CLASS_COLORS.get(c), label=c, lw=2)
    ax.set_xlabel(f); ax.set_ylabel("Predicted probability")
axes[0, 0].legend()
fig.suptitle("Partial dependence: average predicted probability as one feature changes")
plt.tight_layout(); plt.savefig(OUT / "partial_dependence_top_features.png", dpi=200); plt.close()

# ------------------------------------------------------------------ 8. permutation importance on held-out fields
print("Permutation importance on held-out fields (a few minutes)...")
cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
y_all, g_all = df["y"].values, df["field_id"].values
rng = np.random.default_rng(SEED)
single, grouped = [], []
for tr, te in cv.split(np.zeros(len(df)), y_all, g_all):
    m = make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                      RandomForestClassifier(n_estimators=200, min_samples_leaf=3,
                                             class_weight="balanced_subsample", n_jobs=-1, random_state=SEED))
    m.fit(df.loc[tr, FEATURES], y_all[tr])
    Xte, yte = df.loc[te, FEATURES].reset_index(drop=True), y_all[te]
    base = f1_score(yte, m.predict(Xte), average="macro")

    def drop_for(cols):
        d = []
        for _ in range(PERM_REPEATS):
            Xp = Xte.copy()
            perm = rng.permutation(len(Xp))
            Xp[cols] = Xp[cols].values[perm]               # shuffle rows jointly for the columns
            d.append(base - f1_score(yte, m.predict(Xp), average="macro"))
        return np.mean(d)

    single.append({f: drop_for([f]) for f in FEATURES})
    grouped.append({g: drop_for(fs) for g, fs in GROUPS.items()})
single = pd.DataFrame(single); grouped = pd.DataFrame(grouped)
pi = pd.DataFrame({"mean_drop": single.mean(), "std_over_folds": single.std(ddof=0)}).sort_values("mean_drop", ascending=False)
pg = pd.DataFrame({"mean_drop": grouped.mean(), "std_over_folds": grouped.std(ddof=0)}).sort_values("mean_drop", ascending=False)
pi.round(4).to_csv(OUT / "permutation_importance_features.csv")
pg.round(4).to_csv(OUT / "permutation_importance_groups.csv")

fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), gridspec_kw={"width_ratios": [1.5, 1]})
t = pi.head(TOP_N)[::-1]
axes[0].barh(t.index, t["mean_drop"], xerr=t["std_over_folds"], color="#4c6a92", capsize=2)
axes[0].set_xlabel("Drop in macro-F1 when the feature is shuffled")
axes[0].set_title(f"Permutation importance, top {TOP_N} (held-out fields)")
t = pg[::-1]
axes[1].barh(t.index, t["mean_drop"], xerr=t["std_over_folds"], color="#e9a03b", capsize=2)
axes[1].set_xlabel("Drop in macro-F1 when the whole group is shuffled")
axes[1].set_title("Permutation importance by feature group")
plt.tight_layout(); plt.savefig(OUT / "permutation_importance.png", dpi=200); plt.close()

# ------------------------------------------------------------------ 9. how the classes look (data view)
month_cols_ndvi = sorted(c for c in df.columns if c.startswith("NDVI_20"))
month_cols_ndwi = sorted(c for c in df.columns if c.startswith("NDWI_20"))
if month_cols_ndvi:
    labels_m = [c[-2:] for c in month_cols_ndvi]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, cols_, name in zip(axes, [month_cols_ndvi, month_cols_ndwi], ["NDVI", "NDWI"]):
        for c in classes:
            sub = df.loc[df["crop_type"] == c, cols_]
            mu, sd = sub.mean(), sub.std()
            ax.plot(labels_m, mu.values, marker="o", color=CLASS_COLORS.get(c), label=c)
            ax.fill_between(labels_m, (mu - sd).values, (mu + sd).values, color=CLASS_COLORS.get(c), alpha=0.15)
        ax.set_xlabel("Month (2025)"); ax.set_ylabel(f"Mean {name} (band = +-1 std)")
        ax.set_title(f"Monthly {name} profile by class (pre-flood)")
    axes[0].legend(); plt.tight_layout()
    plt.savefig(OUT / "class_profiles_monthly.png", dpi=200); plt.close()

    dists = sorted(df["district"].unique())
    fig, axes = plt.subplots(1, len(dists), figsize=(5 * len(dists), 3.8), sharey=True)
    for ax, d in zip(np.atleast_1d(axes), dists):
        for c in classes:
            sub = df.loc[(df["crop_type"] == c) & (df["district"] == d), month_cols_ndvi]
            if len(sub) > 20:
                ax.plot(labels_m, sub.mean().values, marker="o", color=CLASS_COLORS.get(c), label=c)
        ax.set_title(d); ax.set_xlabel("Month (2025)")
    np.atleast_1d(axes)[0].set_ylabel("Mean NDVI"); np.atleast_1d(axes)[0].legend()
    plt.tight_layout(); plt.savefig(OUT / "class_profiles_by_district.png", dpi=200); plt.close()

fig, axes = plt.subplots(1, 3, figsize=(13, 4))
for ax, f in zip(axes, [x for x in ["elevation", "slope", "NDVI"] if x in df.columns]):
    data, tick = [], []
    for d in sorted(df["district"].unique()):
        for c in classes:
            v = df.loc[(df["district"] == d) & (df["crop_type"] == c), f].dropna()
            if len(v) > 20:
                data.append(v.values); tick.append(f"{d[:3]}\n{c}")
    bp = ax.boxplot(data, showfliers=False, patch_artist=True)
    ax.set_xticklabels(tick)
    for patch, t_ in zip(bp["boxes"], tick):
        patch.set_facecolor(CLASS_COLORS.get(t_.split("\n")[1], "#ccc")); patch.set_alpha(0.7)
    ax.set_title(f"{f} by district and class"); ax.tick_params(axis="x", labelsize=7)
plt.tight_layout(); plt.savefig(OUT / "terrain_and_ndvi_by_district_class.png", dpi=200); plt.close()

# ------------------------------------------------------------------ tables
mean_abs.round(4).to_csv(OUT / "shap_mean_abs_all.csv")
print(f"\nDone. Files are in {OUT}")
print("\nTop features by SHAP:\n", mean_abs.head(10).round(4))
print("\nFeature-group share of SHAP (%):\n", grp_share.round(1))
print("\nPermutation importance by group:\n", pg.round(4))
