import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shap

ROOT = Path(__file__).resolve().parents[1]
MODELS, RES = ROOT / "models", ROOT / "outputs" / "results"
TABLE = ROOT / "outputs" / "reference_dataset" / "M3_training_table_all_districts.csv"

meta = json.loads((MODELS / "m3_model_meta.json").read_text())
FEATURES, classes = meta["best_tree_features"], meta["classes"]
model = joblib.load(MODELS / meta["best_tree_file"])

df = pd.read_csv(TABLE)
X = df.sample(frac=1, random_state=42).groupby("crop_type").head(400)[FEATURES]   # speed only

if hasattr(model, "named_steps"):                       # Random Forest pipeline: impute first
    X = pd.DataFrame(model[:-1].transform(X), columns=FEATURES, index=X.index)
    est = model[-1]
else:
    est = model

sv = shap.TreeExplainer(est).shap_values(X)
if isinstance(sv, list):
    sv = np.stack(sv, axis=-1)                          # (samples, features, classes)
assert sv.ndim == 3 and sv.shape[2] == len(classes), sv.shape

imp = pd.DataFrame(np.abs(sv).mean(axis=0), index=FEATURES, columns=classes)
imp["All classes"] = imp.mean(axis=1)
imp = imp.sort_values("All classes", ascending=False)
imp.round(4).to_csv(RES / "shap_mean_abs.csv")
print(imp.head(15).round(4))
top = imp.head(15)

ax = top["All classes"][::-1].plot.barh(color="black", figsize=(6.5, 5.5))
ax.set_xlabel("Mean |SHAP value|"); ax.set_title(f"Top 15 features - {meta['best_tree_model']} ({meta['best_tree_feature_set']})")
plt.tight_layout(); plt.savefig(RES / "shap_importance_overall.png", dpi=200); plt.close()

greys = [str(v) for v in np.linspace(0.15, 0.8, len(classes))]
ax = top[classes][::-1].plot.barh(figsize=(7.5, 6.5), color=greys, edgecolor="black")
ax.set_xlabel("Mean |SHAP value|"); ax.set_title("Top 15 features by class")
plt.tight_layout(); plt.savefig(RES / "shap_importance_by_class.png", dpi=200); plt.close()

for k, c in enumerate(classes):
    try:
        shap.summary_plot(sv[:, :, k], X, show=False, max_display=15)
        plt.title(f"SHAP summary - {c}"); plt.tight_layout()
        plt.savefig(RES / f"shap_summary_{c}.png", dpi=200); plt.close()
    except Exception as e:
        print("summary plot failed for", c, e)
if "Tea" in classes and "elevation" in FEATURES:
    k = classes.index("Tea")
    shap.dependence_plot("elevation", sv[:, :, k], X, interaction_index=None, show=False)
    plt.title("SHAP dependence: elevation (Tea)"); plt.tight_layout()
    plt.savefig(RES / "shap_dependence_elevation_Tea.png", dpi=200); plt.close()