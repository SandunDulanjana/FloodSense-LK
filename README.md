# FloodSense-LK
AI-Powered Flood Disaster Impact Assessment and Decision Support System Sri Lanka 


# AI-Powered Flood Disaster Impact Assessment and Decision Support System for Sri Lanka

**Project ID:** J26-DS-360
**Institute:** Sri Lanka Institute of Information Technology (SLIIT), Faculty of Computing
**Degree:** B.Sc. (Hons) in Information Technology, Specialized in Data Science

---

## 1. Project Overview

Floods affect more than 200,000 people in Sri Lanka every year. Today, the damage assessment is done by hand and takes 2 to 4 weeks. This project builds a system that gives disaster officers fast and clear information about housing, roads, farms, and which districts need help first.

The system has four research components (modules). Each member owns one module. All modules are joined in one shared dashboard.

| Module | Component | Owner | Student ID | GitHub Username |
|--------|-----------|-------|------------|-----------------|
| M1 | Predictive Building Damage Assessment (HSC-Attention Transformer) | J.A.S. Dulanjana | IT23401112 | `SandunDulanjana` |
| M2 | Sentinel-1 SAR Flood Segmentation and Flood-Aware Road Accessibility / Alternative Route | B.L.L.N. Bowaththa | IT23296350 | `@your-username` |
| M3 | Agricultural and Livelihood Impact Assessment | H. Kaveesha Divyanjalee | IT23168022 | `@your-username` |
| M4 | Predictive Flood Extent Mapping, SLDI and Disaster Prioritization | M.A.M. Eyaas | IT23249066 | `@your-username` |

**Supervisor:** Mr. Jeewaka Perera
**Co-supervisor:** Mr. Chamidu Rathsara

---

## 2. How the System Works (Simple View)

```
 Rainfall, river level, DEM
            |
            v
   M4: flood probability + predicted flood extent (GeoTIFF)
            |
   +--------+---------+----------+
   v                  v          v
  M1 buildings      M2 roads    M3 crops
   |                  |          |
   +--------+---------+----------+
            v
   M4: SLDI (Sri Lanka Disaster Index) = district ranking
            v
   Shared Dashboard (Plotly Dash / Folium)
```

- Data moves in **one direction only**. This avoids loops between modules.
- Modules do **not** import each other's code. They exchange **files** that follow the formats in `contracts/`.

---

## 3. Repository Folder Structure

**Every member must use exactly these folder names.** Do not rename or move them.

```
flood-impact-system/
├── README.md
├── .gitignore
├── .env.example
├── .github/
│   ├── CODEOWNERS
│   ├── pull_request_template.md
│   └── workflows/
│       ├── m1_checks.yml
│       ├── m2_checks.yml
│       ├── m3_checks.yml
│       ├── m4_checks.yml
│       └── integration_checks.yml
│
├── modules/                          # Each member works ONLY inside their own folder
│   ├── m1_building_damage/           # Owner: Dulanjana
│   ├── m2_road_accessibility/        # Owner: Bowaththa
│   ├── m3_agri_impact/               # Owner: Kaveesha Divyanjalee
│   └── m4_flood_prediction_sldi/     # Owner: Eyaas
│       ├── README.md
│       ├── requirements.txt
│       ├── configs/
│       ├── src/
│       ├── notebooks/
│       ├── tests/
│       ├── outputs/
│       └── models/
│
├── contracts/                        # Shared agreement between modules
│   ├── README.md
│   ├── crs_and_grid.md
│   ├── schemas/
│   └── examples/
│
├── shared/                           # Small common helpers (team lead only)
│   └── geo_utils/
│
├── dashboard/                        # Plotly Dash / Folium app (joint work)
│   ├── app/
│   ├── requirements.txt
│   └── README.md
│
├── integration/                      # Joins all module outputs, runs SLDI pipeline
│   ├── pipeline/
│   └── tests/
│
├── data/                             # NOT stored in Git
│   ├── raw/
│   ├── processed/
│   └── README.md
│
├── docs/
│   ├── proposals/
│   ├── architecture/
│   └── decision_log.md
│
└── scripts/
```

### What goes inside each folder

| Folder | Purpose | Who can edit |
|--------|---------|--------------|
| `modules/m1_building_damage/` | All M1 code, notebooks, tests, configs | Dulanjana only |
| `modules/m2_road_accessibility/` | All M2 code, notebooks, tests, configs | Bowaththa only |
| `modules/m3_agri_impact/` | All M3 code, notebooks, tests, configs | Kaveesha only |
| `modules/m4_flood_prediction_sldi/` | All M4 code, notebooks, tests, configs | Eyaas only |
| `contracts/` | File formats shared by all modules | Anyone, but **all 4 members must approve** |
| `shared/` | Small helper functions (CRS conversion, file reading) | Team lead, by PR |
| `dashboard/` | The shared web dashboard | Dashboard owner, by PR |
| `integration/` | Code that joins module outputs | Team lead, by PR |
| `data/` | Local data only. Never pushed to Git | Everyone (local only) |
| `docs/` | Proposals, diagrams, decision log | Anyone, by PR |
| `scripts/` | Setup helper scripts | Team lead, by PR |

### What goes inside each module folder

| Subfolder / file | Purpose |
|------------------|---------|
| `README.md` | What the module does, inputs, outputs, how to run it |
| `requirements.txt` | Python libraries for this module only |
| `configs/` | Settings: paths, thresholds, random seeds |
| `src/` | Python source code |
| `notebooks/` | Experiments and exploration |
| `tests/` | Tests for this module only |
| `outputs/` | Result files (ignored by Git) |
| `models/` | Trained model weights (ignored by Git) |

---

## 4. Golden Rules (Everyone Must Follow)

1. **Work only in your own module folder.** You may edit only `modules/mX_.../` for your module. Any change outside it needs a Pull Request (PR) and approval.
2. **No cross-imports.** Never write `import` from another module's code. Read the other module's **output file** using the format in `contracts/`.
3. **Never push directly to `main`.** Always create a branch and open a PR.
4. **Contracts change only by team agreement.** If you change a file format, all 4 members must approve the PR.
5. **No big files in Git.** Satellite images, datasets, rasters, and trained models stay out of Git (see Section 8).
6. **No secrets in Git.** API keys, tokens, and passwords go in a local `.env` file. Never commit `.env`.
7. **Each module has its own `requirements.txt`.** One member's library versions must not break another member's work.
8. **Publish a stub early.** In week one, each member adds a small fake output file in `contracts/examples/` so others can build against it.
9. **Keep PRs small.** Merge small changes often. Do not keep a branch open for weeks.

---

## 5. Step-by-Step: Create Your Module Folder (First Time)

Do this **once**, at the start. Use your own module name.

**Step 1: Clone the repository**

```bash
git clone https://github.com/<organization-or-username>/flood-impact-system.git
cd flood-impact-system
```

**Step 2: Create your own branch**

```bash
git checkout -b m1/setup-module-folder
```

Branch prefix for each member: `m1/`, `m2/`, `m3/`, `m4/`.

**Step 3: Create your folders** (example for M1; change the name for your module)

```bash
MODULE=modules/m1_building_damage

mkdir -p $MODULE/{configs,src,notebooks,tests,outputs,models}
touch $MODULE/README.md $MODULE/requirements.txt
touch $MODULE/outputs/.gitkeep $MODULE/models/.gitkeep
```

**Folder names to use:**

| Member | Replace `MODULE=` with |
|--------|------------------------|
| M1 Dulanjana | `modules/m1_building_damage` |
| M2 Bowaththa | `modules/m2_road_accessibility` |
| M3 Kaveesha | `modules/m3_agri_impact` |
| M4 Eyaas | `modules/m4_flood_prediction_sldi` |

**Step 4: Fill your module `README.md`** using the template in Section 9.

**Step 5: Commit and push**

```bash
git add modules/m1_building_damage
git commit -m "m1: add module folder structure"
git push -u origin m1/setup-module-folder
```

**Step 6:** Open a Pull Request on GitHub into `main`. Ask the team lead to review.

> Git does not save empty folders. The `.gitkeep` file makes sure the folder is saved.

---

## 6. Daily Working Rules

### Branch names

```
m1/feature-patch-extraction
m2/fix-dijkstra-weight
m3/feature-ndvi-damage
m4/feature-hand-computation
docs/update-decision-log
contracts/update-extent-schema
```

### Commit message format

```
<module>: <short message>
```

Examples:

```
m1: add 64x64 patch cropping
m2: fix road risk score calculation
m3: add LightGBM comparison
m4: add HAND surface derivation
contracts: update extent raster schema
```

### Pull Request (PR) rules

- Use the PR template. Explain **what** you changed and **why**.
- At least **1 approval** is needed before merge.
- All automatic checks must pass.
- Do not merge your own PR without a review.
- Before you open a PR, update your branch:

```bash
git fetch origin
git merge origin/main
```

---

## 7. Contracts (Shared File Formats)

The `contracts/` folder is the **only** way modules talk to each other.

| Item | Rule |
|------|------|
| Coordinate system (CRS) | **ONE CRS for all modules.** Write the final decision in `contracts/crs_and_grid.md` before coding starts. |
| Raster resolution and grid | Align to the Sentinel-1/2 grid (see `crs_and_grid.md`) |
| Nodata value | Write one value in `crs_and_grid.md` (M4 proposes `255` for the extent raster) |
| Predicted flood extent (M4 → M1, M2, M3) | Cloud-optimised GeoTIFF. File name: `extent_<district>_<eventdate>_<modelversion>.tif` |
| Vector outputs (M1, M2, M3 → M4 / dashboard) | GeoJSON, with common fields: `district`, `event_id`, `date`, `module`, `model_version` |
| Table outputs | CSV or JSON, using the same `district` and `event_id` fields |

**Output ownership**

| Module | Produces | Used by |
|--------|----------|---------|
| M4 | Predicted flood extent raster, flood probability | M1, M2, M3 |
| M1 | Building damage GeoJSON | M4 (SLDI), dashboard |
| M2 | Road risk / accessibility layer, safer route | M4 (SLDI), dashboard |
| M3 | Crop map, crop damage, livelihood impact (GeoJSON / CSV / JSON) | M4 (SLDI), dashboard |
| M4 | SLDI district ranking | Dashboard |

**Open decisions to close first** (write the answers in `contracts/`):

1. One CRS for all modules (M1 plans WGS84 / UTM Zone 44N; M4 has not fixed it yet).
2. One output format for M2. Decide: continuous road risk score or Flooded / Passable label, so M4's SLDI can read it.

---

## 8. Data and Large Files Policy

**Never commit** satellite images, datasets, rasters, or model weights.

| File type | Where to keep it |
|-----------|------------------|
| xBD, SpaceNet 8, Sen1Floods11 | Download from the official source (see `data/README.md`) |
| Sentinel-1 / Sentinel-2 | Google Earth Engine or Copernicus (download locally) |
| SRTM DEM, OSM, ESA WorldCover | Download locally |
| Trained models (`.pt`, `.pth`) | Google Drive / AWS S3 (share the link in your module README) |
| Small samples for testing | `contracts/examples/` (keep files small, under 5 MB) |

Write exact download steps and dataset links in `data/README.md`.

### `.gitignore` (minimum content)

```
# Data and large files
data/raw/*
data/processed/*
!data/raw/.gitkeep
!data/processed/.gitkeep
modules/*/outputs/*
modules/*/models/*
!modules/*/outputs/.gitkeep
!modules/*/models/.gitkeep
*.tif
*.tiff
*.pt
*.pth
*.ckpt
*.h5
*.zip

# Secrets
.env

# Python
__pycache__/
*.pyc
.venv/
venv/
.ipynb_checkpoints/

# OS / editor
.DS_Store
.vscode/
.idea/
```

> Small sample files in `contracts/examples/` must be added with `git add -f` if they match a blocked type such as `.tif`.

---

## 9. Template for Your Module `README.md`

Copy this into `modules/mX_.../README.md` and fill it in.

```markdown
# M? - <Component Title>

**Owner:** <Name> (<Student ID>)

## What this module does
(2 to 4 simple sentences)

## Inputs
| Input | Format | Source |
|-------|--------|--------|

## Outputs
| Output | Format | File name pattern | Used by |
|--------|--------|-------------------|---------|

## How to set up
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

## How to run
(commands)

## How to run tests
pytest tests/

## Models and data links
(Google Drive / S3 links. Never commit the files.)

## Status
(Not started / In progress / Done)
```

---

## 10. Environment Setup (Each Member)

- Python 3.10 or newer
- Create a **separate virtual environment per module**
- Install only your module's `requirements.txt`
- Copy `.env.example` to `.env` and fill in your own keys (never commit `.env`)

```bash
cd modules/m1_building_damage
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 11. Repository Protection (Team Lead Sets Once)

In GitHub: **Settings → Branches → Add rule for `main`**

- Require a pull request before merging
- Require at least 1 approval
- Require review from Code Owners
- Require status checks to pass
- Do not allow direct pushes or force pushes

`.github/CODEOWNERS` (replace with real usernames):

```
/modules/m1_building_damage/        @m1-username
/modules/m2_road_accessibility/     @m2-username
/modules/m3_agri_impact/            @m3-username
/modules/m4_flood_prediction_sldi/  @m4-username
/contracts/                         @m1-username @m2-username @m3-username @m4-username
/shared/                            @team-lead-username
/dashboard/                         @dashboard-owner-username
/integration/                       @team-lead-username
```

---

## 12. Integration Plan

1. Each member finishes a stub output in `contracts/examples/`.
2. The dashboard and `integration/` use only the stub files first.
3. Each member replaces the stub with real output when the model is ready.
4. Integration tests in `integration/tests/` run on the contract examples.
5. Final merge into `main` only after all checks pass.

---

## 13. Team Checklist

Each member ticks these items:

- [ ] I cloned the repository
- [ ] I created my module folder with the exact names above
- [ ] I filled my module `README.md`
- [ ] I created my own `requirements.txt`
- [ ] I added a stub output to `contracts/examples/`
- [ ] I work only on my own branch (`mX/...`)
- [ ] I never commit data, models, or `.env`
- [ ] All 4 members agreed on CRS and M2 output format

---

## 14. Simple Words Explained

| Term | Meaning |
|------|---------|
| Repository (repo) | The project folder stored on GitHub |
| Branch | Your own copy of the work, safe from others |
| Pull Request (PR) | A request to merge your branch into `main` after a review |
| `main` | The stable, official version of the project |
| CODEOWNERS | A GitHub file that forces the right person to approve changes in a folder |
| CRS | Coordinate Reference System: the map projection used by all layers |
| Contract | A written agreement about file names, formats, and fields between modules |
| Stub | A fake sample output with the correct format, used for early testing |
| GeoTIFF | A map image file with location information |
| GeoJSON | A text file that stores map shapes and their attributes |
| SLDI | Sri Lanka Disaster Index: the district priority score |
| Git LFS / DVC | Tools to store large files outside normal Git history |

---

## 15. Contact

Questions about the folder structure or contracts: ask the team lead before changing anything outside your module.
