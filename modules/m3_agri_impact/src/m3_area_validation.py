"""
M3 - compare the satellite crop AREAS per district with official district statistics.

Needs:  outputs/results/map/area_by_district.csv        (made by m3_final_map.py)
        data/reference/district_reference_areas.csv     (YOU fill this from official sources)

Reference file columns:  district, paddy_ha_ref, tea_ha_ref, season_or_year, source
Leave a cell empty when you have no figure; that crop is skipped for that district.
Suggested sources (check the season/year you use and write it in the file):
  paddy: Department of Census and Statistics, Paddy Statistics, sown/harvested extent by district
  tea  : Tea Small Holdings Development Authority / Sri Lanka Tea Board district tea extent

Run:  python src/m3_area_validation.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
AREAS = ROOT / "outputs" / "results" / "map" / "area_by_district.csv"
REF = ROOT / "data" / "reference" / "district_reference_areas.csv"
OUT = ROOT / "outputs" / "results" / "map"
TARGET = 0.80                       # proposal target: >= 80% agreement where comparable data exist

if not REF.exists():
    REF.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"district": ["Ratnapura", "Colombo", "Gampaha"], "paddy_ha_ref": [np.nan] * 3,
                  "tea_ha_ref": [np.nan] * 3, "season_or_year": [""] * 3, "source": [""] * 3}
                 ).to_csv(REF, index=False)
    raise SystemExit(f"Template created: {REF}\nFill in the official hectares, then run this script again.")

sat = pd.read_csv(AREAS)
ref = pd.read_csv(REF)
rows = []
for _, r in ref.iterrows():
    for crop, col in (("Paddy", "paddy_ha_ref"), ("Tea", "tea_ha_ref")):
        if pd.isna(r[col]):
            continue
        s = sat[(sat["district"] == r["district"]) & (sat["class"] == crop)]
        if s.empty:
            continue
        s_ha = float(s["area_ha"].iloc[0]); ref_ha = float(r[col])
        rows.append({"district": r["district"], "crop": crop, "satellite_ha": s_ha, "reference_ha": ref_ha,
                     "difference_ha": round(s_ha - ref_ha, 1),
                     "difference_pct": round(100 * (s_ha - ref_ha) / ref_ha, 1),
                     "agreement_pct": round(100 * max(0.0, 1 - abs(s_ha - ref_ha) / ref_ha), 1),
                     "meets_80pct": (1 - abs(s_ha - ref_ha) / ref_ha) >= TARGET,
                     "reference_period": r.get("season_or_year", ""), "reference_source": r.get("source", "")})
if not rows:
    raise SystemExit("No reference values filled in yet.")
res = pd.DataFrame(rows)
res.to_csv(OUT / "area_validation.csv", index=False)
print(res[["district", "crop", "satellite_ha", "reference_ha", "difference_pct", "agreement_pct", "meets_80pct"]]
      .to_string(index=False))
for crop, g in res.groupby("crop"):
    print(f"\n{crop}: mean absolute % error = {g['difference_pct'].abs().mean():.1f}% over {len(g)} districts")

crops = list(res["crop"].unique())
fig, axes = plt.subplots(1, len(crops), figsize=(5.2 * len(crops), 4.2), squeeze=False)
for ax, crop in zip(axes[0], crops):
    g = res[res["crop"] == crop]; x = np.arange(len(g))
    ax.bar(x - 0.2, g["reference_ha"], 0.4, label="Official statistics", color="#e9a03b")
    ax.bar(x + 0.2, g["satellite_ha"], 0.4, label="M3 satellite map", color="#4c6a92")
    for i, (a, b) in enumerate(zip(g["reference_ha"], g["satellite_ha"])):
        ax.text(i + 0.2, b, f"{100 * (b - a) / a:+.0f}%", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(g["district"]); ax.set_ylabel("Hectares")
    ax.set_title(f"{crop} area by district"); ax.legend(fontsize=8)
plt.tight_layout(); plt.savefig(OUT / "area_validation.png", dpi=200); plt.close()
print("\nSaved", OUT / "area_validation.csv", "and area_validation.png")
print("Remember: official figures are sown/planted extents for a season or year; a single pre-flood\n"
      "image and the land-cover mask will not match them exactly. Explain differences, do not hide them.")
