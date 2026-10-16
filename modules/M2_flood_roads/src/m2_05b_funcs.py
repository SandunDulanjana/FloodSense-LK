# M2-05b functions (draft rule, review panel, export). Loaded by m2_05b_draft_labels.py; re-run with %run -i after edits.
import os, json, numpy as np, matplotlib.pyplot as plt
from scipy import ndimage as ndi
DEF = dict(t=-15.0, d=3.0, m=0.0, f=0.3, s=15.0, a=8, g=2.0, uc=True, box=[], wbox=[], dbox=[])
SAVE = False
os.makedirs(f'{KIT}/review_panels', exist_ok=True)

def draft(i):
    """Object-based: grow dark regions (seed VV < t, extent VV < t+g, 8-connected); a region is WATER if its mean darkening vs 26 Nov
    >= d dB, or >= 50% JRC-permanent, or >= f of it is S2 water (MNDWI > m); dark regions failing all tests (>= a px) are UNSURE."""
    B = BASE[i]; p = {**DEF, **OV.get(i, {})}
    dv = B['vvpre'] - B['vv']; perm = B['jrc'] > 50; s2w = np.nan_to_num(B['mndwi'], nan=-1) > p['m']
    ext = B['vv'] < p['t'] + p['g']; seed = B['vv'] < p['t']
    lab_, n = ndi.label(ext, structure=np.ones((3, 3)))
    ids = np.arange(1, n + 1)
    has_seed = ndi.maximum(seed, lab_, ids) > 0; size = ndi.sum(ext, lab_, ids)
    mdv = ndi.mean(dv, lab_, ids); fperm = ndi.mean(perm, lab_, ids); fs2 = ndi.mean(s2w, lab_, ids)
    is_w = has_seed & (size >= p['a']) & ((mdv >= p['d']) | (fperm >= 0.5) | (fs2 >= p['f']))
    is_u = has_seed & (size >= p['a']) & ~is_w
    water = np.isin(lab_, ids[is_w]); uns = np.isin(lab_, ids[is_u])
    holes = ndi.binary_fill_holes(water) & ~water; hl, nh = ndi.label(holes)
    if nh: hs = ndi.sum(holes, hl, range(1, nh + 1)); water |= np.isin(hl, np.where(hs < p['a'])[0] + 1)
    for r0, r1, c0, c1 in p['wbox']: water[r0:r1, c0:c1] |= ext[r0:r1, c0:c1]          # manual: dark pixels in box are water
    for r0, r1, c0, c1 in p['dbox']: water[r0:r1, c0:c1] = False; uns[r0:r1, c0:c1] = False   # manual: not water
    uns |= ((B['slope'] > p['s']) & seed & ~perm & ~water) | (s2w & ~water) | (B['cloud'] & ext & ~water)
    if p['uc']: uns |= B['cloud'] & (B['wc'] == 50) & ~water                       # built-up under S2 cloud: no evidence -> unsure
    uns &= ~water | ((B['slope'] > p['s']) & ~perm)
    for r0, r1, c0, c1 in p['box']: uns[r0:r1, c0:c1] = True
    lab = np.zeros((C, C), np.int16); lab[water] = 1; lab[uns] = -1; lab[~B['valid']] = -1
    return lab, p

def show(i):
    B = BASE[i]; lab, p = draft(i)
    st = lambda a, lo, hi: np.clip((np.nan_to_num(a, nan=lo) - lo) / (hi - lo), 0, 1)
    chg = np.dstack([st(B['rawpre'], -25, 0), st(B['raw'], -25, 0), st(B['raw'], -25, 0)])
    ov = np.dstack([st(B['raw'], -25, 0)] * 3); ov[lab == 1] = [0.1, 0.4, 1.0]; ov[lab == -1] = [1.0, 0.85, 0.0]
    mw = np.dstack([st(B['mndwi'], -0.5, 0.5)] * 3); mw[np.isnan(B['mndwi'])] = [0.6, 0.0, 0.6]
    fig, ax = plt.subplots(2, 3, figsize=(21, 14.5)); ax = ax.ravel()
    for a_, im, ttl in zip(ax, [st(B['raw'], -25, 0), chg, ov, st(B['rgb'], 0, 2500), st(B['fc'], 0, 4000), mw],
                           ['S1 VV 2 Dec', 'change R=26Nov G=B=2Dec', 'DRAFT blue=water yellow=unsure', 'S2 30 Nov true colour', 'S2 SWIR/NIR/red', 'S2 MNDWI (white=water, purple=cloud)']):
        a_.imshow(im, cmap='gray' if im.ndim == 2 else None, interpolation='nearest'); a_.set_title(ttl, fontsize=13)
        a_.set_xticks(range(0, 257, 32)); a_.set_yticks(range(0, 257, 32)); a_.tick_params(labelsize=9); a_.grid(alpha=.3)
    lc = CH[i]['lc']; fig.suptitle(f"{i}: {B['cid']} ({lc}, in_survey={CH[i]['in_survey']}) water {np.mean(lab==1):.1%} unsure {np.mean(lab==-1):.1%} | {p}", fontsize=13)
    plt.tight_layout()
    if SAVE: fig.savefig(f'{KIT}/review_panels/{B["cid"]}_review.png', dpi=60)
    plt.show()

def export():
    import geopandas as gpd
    from rasterio import features
    from shapely.geometry import shape
    W, U, rows = [], [], []
    for i in range(len(CH)):
        lab, p = draft(i); T = BASE[i]['T']; cid = BASE[i]['cid']
        for val, lst in [(1, W), (-1, U)]:
            for g, v in features.shapes(lab, mask=(lab == val), transform=T):
                lst.append({'chip_id': cid, 'note': 'AI-drafted (D24)', 'geometry': shape(g)})
        rows.append({'chip_id': cid, 'water_frac': round(float((lab == 1).mean()), 4), 'unsure_frac': round(float((lab == -1).mean()), 4), 'water_px': int((lab == 1).sum()), 'unsure_px': int((lab == -1).sum()), 'params': p})
    gp = f'{KIT}/KEL_labels.gpkg'
    tpl = f'{KIT}/KEL_labels_empty_template.gpkg'
    if os.path.exists(gp):
        if not os.path.exists(tpl): os.replace(gp, tpl)
        else: os.remove(gp)
    gpd.GeoDataFrame(W, crs=32644).to_file(gp, layer='water', driver='GPKG')
    gpd.GeoDataFrame(U, crs=32644).to_file(gp, layer='unsure', driver='GPKG')
    json.dump({'protocol': 'D24 AI-drafted, image-based, model-independent', 'defaults': DEF, 'overrides': {str(k): v for k, v in OV.items()},
               'per_chip': rows}, open(f'{KIT}/draft_label_params.json', 'w'), indent=1, default=str)
    print('wrote', gp, len(W), 'water polygons,', len(U), 'unsure polygons'); return rows
def save_panels():
    global SAVE
    SAVE = True; show_ = plt.show; plt.show = lambda: plt.close('all')
    try:
        for i in range(len(CH)): show(i)
    finally:
        SAVE = False; plt.show = show_
    print('review panels saved to', f'{KIT}/review_panels')

def showall(ids):
    for i in ids: show(i)

# ---- per-chip review overrides (filled in during visual review; every entry has a reason)
OVR = {7: dict(dbox=[[118, 142, 52, 78]], reason='KEL_07: isolated 8-10 px blob on forested hillslope; no S2 water, no darkening pattern -> not water')}
OV = {i: dict(OVR.get(i, {})) for i in range(len(CH))}
print('ready: show(i), showall(ids), export(); overrides:', {k: v for k, v in OV.items() if v})
