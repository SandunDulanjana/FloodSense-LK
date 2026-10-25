# ===== M1 Step 12: Model optimisation — nested spatial CV architecture + hyperparameter search, ablations =====
# Novelty component: HSC-Attention is optimised over ARCHITECTURE (cross-attention depth, heads, width, token grid,
# FFN activation, bidirectional attention, visual-stream initialisation) and TRAINING hyperparameters, with
# Optuna TPE inside NESTED spatial cross-validation, so that the outer test folds are never used to choose settings.
# Baseline 1 (D5 Dual-Stream concat) gets the same procedure (fair comparison, required by the proposal).
#
# PHASES (all resumable — results are saved after every fold / trial to Drive):
#   tune     : for each outer fold k, tune on inner split (val = fold k+1, train = other 8 folds, 50% subsample),
#              then refit best config on all 9 outer-train folds and test once on fold k.
#   default  : re-run the default (Step 8) configs with this same code -> clean paired comparison.
#   ablate   : with the per-fold tuned D6 config: A1 No-DEM, A2 No-Cross-Attention, A3 Visual-only.
#   stats    : Friedman, Wilcoxon + Holm (planned comparisons), bootstrap CI, parameter importance, dump.
#   final    : choose final config by the same procedure on the whole sample, train on all 50k, predict all buildings,
#              rebuild the web demo data.
import os, sys, json, time, glob, shutil, subprocess, datetime, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
try:
    import optuna
except ImportError:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'optuna'], check=True); import optuna
import torch, torch.nn as nn, torch.nn.functional as F, torchvision
from sklearn.metrics import f1_score, balanced_accuracy_score, cohen_kappa_score, roc_auc_score, accuracy_score
optuna.logging.set_verbosity(optuna.logging.WARNING)
TEST = bool(os.environ.get('M1_TEST'))                     # local smoke test on synthetic data (CPU)
PHASES = os.environ.get('M1_PHASES', 'tune,default,ablate,stats,final').split(',')
torch.backends.cudnn.benchmark = True
R = os.environ.get('M1_ROOT', '/content/drive/MyDrive/M1_Research'); RES = f'{R}/results'; TUN = f'{RES}/tuning'
os.makedirs(TUN, exist_ok=True)
DEV = 'cuda' if torch.cuda.is_available() else 'cpu'
SEED, K, BS, P = 42, 10, 256, 32
N_TRIALS = {'D6': 14, 'D5': 8}; INNER_FRAC = 0.5
if TEST: N_TRIALS = {'D6': 2, 'D5': 2}
print('device', DEV, torch.cuda.get_device_name(0) if DEV == 'cuda' else '', '| optuna', optuna.__version__, '| torch', torch.__version__)

# ---------------- data: identical patches, labels and spatial folds to Steps 6-8 ----------------
if TEST:
    rng = np.random.default_rng(0); N = 1500
    X = rng.normal(size=(N, 10, P, P)).astype('float16'); y = rng.integers(0, 3, N); fold = rng.integers(0, K, N)
    X[y == 2, 7] -= 1.0                                     # make class 2 learnable from "HAND"
else:
    import rasterio
    samp = pd.read_parquet(f'{R}/M1_sample_with_folds.parquet')
    files = sorted(glob.glob(f'{R}/M1_raster_stack_v1*.tif'))
    with rasterio.open(files[0]) as s: S = np.nan_to_num(s.read().astype('float32'))
    S[8] = np.log1p(S[8])                                   # distance to river -> log scale (as Step 8)
    r0, c0 = samp.row.values - P // 2, samp.col.values - P // 2
    ir = r0[:, None] + np.arange(P)[None, :]; ic = c0[:, None] + np.arange(P)[None, :]
    X = np.stack([S[b][ir[:, :, None], ic[:, None, :]] for b in range(10)], 1).astype('float16'); del S
    y = samp.y.values.astype('int64'); fold = samp.fold.values
XG = torch.tensor(X, device=DEV); y = np.asarray(y, 'int64'); fold = np.asarray(fold)
VIS, HYD = [0, 1, 2, 3, 4], [5, 6, 7, 8, 9]                 # B2 B3 B4 B8 B11 | dem slope hand dist_river bmask
HYD_NODEM = [8, 9]                                          # ablation A1: remove all DEM-derived bands (dem, slope, HAND)
print('patches', tuple(X.shape), '| class counts', np.bincount(y, minlength=3).tolist())

# ---------------- configurable models ----------------
ACT = {'relu': nn.ReLU, 'gelu': nn.GELU, 'silu': nn.SiLU}
def adapt_conv1(m, cin):
    w = m.conv1.weight.data; new = nn.Conv2d(cin, 64, 7, 2, 3, bias=False)
    with torch.no_grad():
        new.weight[:] = w.mean(1, keepdim=True).repeat(1, cin, 1, 1) * 3 / cin
        if cin >= 3: new.weight[:, :3] = w[:, [2, 1, 0]]
    m.conv1 = new; return m
def resnet18(cin, pre):
    m = torchvision.models.resnet18(weights='IMAGENET1K_V1' if (pre and not TEST) else None); return adapt_conv1(m, cin)
def hydro_encoder(cin, d, grid):                            # 64x64 -> d x grid x grid (ReLU, as Step 8)
    c = lambda i, o: nn.Sequential(nn.Conv2d(i, o, 3, 2, 1), nn.BatchNorm2d(o), nn.ReLU())
    w = [64, 128, 192, d] if grid == 4 else [64, 128, d]
    return nn.Sequential(*[c(i, o) for i, o in zip([cin] + w[:-1], w)])

class XBlock(nn.Module):                                    # post-norm cross-attention block (same form as Step 8)
    def __init__(s, d, heads, drop, ffn_act, ffn_ratio=2):
        super().__init__(); s.att = nn.MultiheadAttention(d, heads, dropout=drop, batch_first=True)
        s.n1, s.n2 = nn.LayerNorm(d), nn.LayerNorm(d)
        s.ffn = nn.Sequential(nn.Linear(d, ffn_ratio * d), ACT[ffn_act](), nn.Linear(ffn_ratio * d, d))
    def forward(s, q, kv):
        a, w = s.att(q, kv, kv, need_weights=True); z = s.n1(q + a); return s.n2(z + s.ffn(z)), w

class HSCv2(nn.Module):
    """HSC-Attention with a configurable architecture. Default cfg reproduces the Step 8 D6 model."""
    def __init__(s, d=256, heads=4, layers=1, ffn_act='gelu', attn_drop=0.1, head_drop=0.3, head_act='relu',
                 bidir=False, grid=4, vis_init='imagenet', fusion='xattn', hyd=tuple(HYD), **_):
        super().__init__(); s.fusion, s.bidir, s.hyd = fusion, bidir, list(hyd)
        r = resnet18(len(VIS), vis_init == 'imagenet')
        s.vis = nn.Sequential(r.conv1, r.bn1, r.relu, r.maxpool, r.layer1, r.layer2, *([r.layer3] if grid == 4 else []))
        cv = 256 if grid == 4 else 128
        s.proj = nn.Identity() if cv == d else nn.Conv2d(cv, d, 1)
        s.pos = nn.Parameter(torch.zeros(1, grid * grid, d)); nn.init.trunc_normal_(s.pos, std=0.02)
        if fusion != 'vis_only': s.h = hydro_encoder(len(s.hyd), d, grid)
        if fusion == 'xattn':
            s.blocks = nn.ModuleList([XBlock(d, heads, attn_drop, ffn_act) for _ in range(layers)])
            if bidir: s.rblocks = nn.ModuleList([XBlock(d, heads, attn_drop, ffn_act) for _ in range(layers)])
        hin = d if fusion == 'vis_only' else 2 * d
        s.head = nn.Sequential(nn.Linear(hin, 256), ACT[head_act](), nn.Dropout(head_drop), nn.Linear(256, 3)); s.last_attn = None
    def forward(s, x):
        x = F.interpolate(x, size=64, mode='bilinear', align_corners=False)
        q = s.proj(s.vis(x[:, VIS])).flatten(2).transpose(1, 2) + s.pos
        if s.fusion == 'vis_only': return s.head(q.mean(1))
        kv = s.h(x[:, s.hyd]).flatten(2).transpose(1, 2) + s.pos
        if s.fusion == 'concat': return s.head(torch.cat([q.mean(1), kv.mean(1)], 1))
        for i, b in enumerate(s.blocks):
            qn, w = b(q, kv)
            if s.bidir: kv, _ = s.rblocks[i](kv, q)
            q = qn
        s.last_attn = w.detach(); return s.head(torch.cat([q.mean(1), kv.mean(1)], 1))

class DualStreamV2(nn.Module):
    """Baseline 1 (proposal): dual-stream ResNet18 + hydro CNN, global pooling + concatenation. Default = Step 8 D5."""
    def __init__(s, head_hidden=256, head_act='relu', head_drop=0.3, vis_init='imagenet', **_):
        super().__init__(); r = resnet18(len(VIS), vis_init == 'imagenet')
        s.vis = nn.Sequential(r.conv1, r.bn1, r.relu, r.maxpool, r.layer1, r.layer2, r.layer3, r.layer4)
        s.h = hydro_encoder(len(HYD), 256, 4)
        s.head = nn.Sequential(nn.Linear(512 + 256, head_hidden), ACT[head_act](), nn.Dropout(head_drop), nn.Linear(head_hidden, 3))
    def forward(s, x):
        x = F.interpolate(x, size=64, mode='bilinear', align_corners=False)
        return s.head(torch.cat([s.vis(x[:, VIS]).mean((2, 3)), s.h(x[:, HYD]).mean((2, 3))], 1))

DEFAULT = {'D6': dict(lr=3e-4, wd=1e-4, epochs=6, head_drop=0.3, d=256, heads=4, layers=1, ffn_act='gelu',
                      grid=4, bidir=False, vis_init='imagenet'),
           'D5': dict(lr=3e-4, wd=1e-4, epochs=6, head_drop=0.3, head_hidden=256, head_act='relu', vis_init='imagenet')}
def space(trial, m):
    c = dict(lr=trial.suggest_float('lr', 1e-4, 2e-3, log=True), wd=trial.suggest_float('wd', 1e-5, 1e-2, log=True),
             epochs=trial.suggest_categorical('epochs', [6, 10, 14]), head_drop=trial.suggest_float('head_drop', 0.1, 0.5),
             vis_init=trial.suggest_categorical('vis_init', ['imagenet', 'random']))
    if m == 'D6':
        c.update(d=trial.suggest_categorical('d', [128, 256]), heads=trial.suggest_categorical('heads', [2, 4, 8]),
                 layers=trial.suggest_categorical('layers', [1, 2, 3]), ffn_act=trial.suggest_categorical('ffn_act', ['gelu', 'relu', 'silu']),
                 grid=trial.suggest_categorical('grid', [4, 8]), bidir=trial.suggest_categorical('bidir', [False, True]))
    else:
        c.update(head_hidden=trial.suggest_categorical('head_hidden', [128, 256, 512]),
                 head_act=trial.suggest_categorical('head_act', ['relu', 'gelu', 'silu']))
    return c
def build(m, cfg): return (HSCv2 if m == 'D6' else DualStreamV2)(**cfg)

def metrics(yt, yp, prob):
    out = dict(macro_f1=f1_score(yt, yp, average='macro'), bal_acc=balanced_accuracy_score(yt, yp),
               acc=accuracy_score(yt, yp), qwk=cohen_kappa_score(yt, yp, weights='quadratic'))
    try: out['auc_high'] = roc_auc_score((yt == 2).astype(int), prob[:, 2])
    except ValueError: out['auc_high'] = np.nan
    return out

def train_eval(m, cfg, tr, te, seed):
    """Train on index set tr (normalisation from tr only), return softmax probs on te + timings. Same recipe as Step 8."""
    torch.manual_seed(seed); np.random.seed(seed)
    sub = XG[torch.tensor(tr[::4], device=DEV)].float(); mu = sub.mean((0, 2, 3)).view(1, -1, 1, 1)
    sd = sub.std((0, 2, 3)).view(1, -1, 1, 1) + 1e-6; del sub
    net = build(m, cfg).to(DEV); ep_n = 1 if TEST else cfg['epochs']
    opt = torch.optim.AdamW(net.parameters(), lr=cfg['lr'], weight_decay=cfg['wd'])
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, cfg['lr'], total_steps=ep_n * int(np.ceil(len(tr) / BS)))
    cw = torch.tensor(len(tr) / (3 * np.maximum(np.bincount(y[tr], minlength=3), 1)), dtype=torch.float32, device=DEV)
    scaler = torch.amp.GradScaler('cuda', enabled=DEV == 'cuda'); t0 = time.time()
    for ep in range(ep_n):
        net.train(); perm = np.random.permutation(tr)
        for i in range(0, len(perm), BS):
            b = perm[i:i + BS]; xb = (XG[torch.tensor(b, device=DEV)].float() - mu) / sd; yb = torch.tensor(y[b], device=DEV)
            if np.random.rand() < .5: xb = xb.flip(3)
            if np.random.rand() < .5: xb = xb.flip(2)
            xb = torch.rot90(xb, np.random.randint(4), (2, 3))
            with torch.autocast(DEV, enabled=DEV == 'cuda'): loss = F.cross_entropy(net(xb), yb, weight=cw)
            opt.zero_grad(set_to_none=True); scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); sch.step()
    fit_s = time.time() - t0; net.eval(); probs = []; t0 = time.time()
    with torch.no_grad(), torch.autocast(DEV, enabled=DEV == 'cuda'):
        for i in range(0, len(te), 1024):
            b = te[i:i + 1024]; probs.append(F.softmax(net((XG[torch.tensor(b, device=DEV)].float() - mu) / sd).float(), 1).cpu().numpy())
    if DEV == 'cuda': torch.cuda.synchronize()
    inf = (time.time() - t0) / max(len(te), 1) * 1e6
    npar = sum(p.numel() for p in net.parameters()) / 1e6
    return np.concatenate(probs), fit_s, inf, npar, net, (mu, sd)

# ---------------- persistence helpers ----------------
OUT = f'{TUN}/outer_results.csv'; OOF = f'{TUN}/oof_optimised.npz'; BP = f'{TUN}/best_params.json'
def load_csv(p): return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()
def done(df, model, k): return len(df) > 0 and ((df.model == model) & (df.fold == k)).any()
def save_row(r, prob, te, model):
    df = pd.concat([load_csv(OUT), pd.DataFrame([r])], ignore_index=True); df.to_csv(OUT, index=False)
    oof = dict(np.load(OOF)) if os.path.exists(OOF) else {}
    if model not in oof: oof[model] = np.zeros((len(y), 3), 'float32')
    oof[model][te] = prob; np.savez_compressed(OOF, **oof)
def jload(p, d): return json.load(open(p)) if os.path.exists(p) else d
def jsave(o, p): json.dump(o, open(p, 'w'), indent=2, default=float)

def run_study(m, name, tr_in, va_in, seed):
    """Optuna TPE study, default config enqueued as trial 0 (warm start). SQLite kept locally, copied to Drive."""
    local, remote = f'/tmp/{name}.db', f'{TUN}/{name}.db'
    if os.path.exists(remote) and not os.path.exists(local): shutil.copy(remote, local)
    st = optuna.create_study(study_name=name, storage=f'sqlite:///{local}', direction='maximize', load_if_exists=True,
                             sampler=optuna.samplers.TPESampler(seed=seed, n_startup_trials=5, multivariate=True))
    if len(st.trials) == 0: st.enqueue_trial(DEFAULT[m])
    def obj(trial):
        cfg = space(trial, m); prob, fit_s, _, npar, net, _ = train_eval(m, cfg, tr_in, va_in, seed)
        del net; torch.cuda.empty_cache() if DEV == 'cuda' else None
        trial.set_user_attr('fit_s', fit_s); trial.set_user_attr('params_M', npar)
        return f1_score(y[va_in], prob.argmax(1), average='macro')
    def cb(study, trial):
        shutil.copy(local, remote)
        print(f'   {name} trial {trial.number}: valF1={trial.value if trial.value is not None else float("nan"):.4f} '
              f'{trial.params} ({trial.user_attrs.get("fit_s", 0):.0f}s)', flush=True)
    left = N_TRIALS[m] - len([t for t in st.trials if t.state.name == 'COMPLETE'])
    if left > 0: st.optimize(obj, n_trials=left, callbacks=[cb], catch=(RuntimeError,))
    st.trials_dataframe().to_csv(f'{TUN}/trials_{name}.csv', index=False); shutil.copy(local, remote)
    full = DEFAULT[m].copy(); full.update(st.best_params); return st, full

def inner_split(k, frac=INNER_FRAC):
    kv = (k + 1) % K; tr = np.where((fold != k) & (fold != kv))[0]; va = np.where(fold == kv)[0]
    rs = np.random.default_rng(SEED + k); tr = np.sort(rs.choice(tr, int(len(tr) * frac), replace=False))
    return tr, va

def outer_eval(model_tag, m, cfg, k, extra=None):
    tr, te = np.where(fold != k)[0], np.where(fold == k)[0]
    prob, fit_s, inf, npar, net, _ = train_eval(m, cfg, tr, te, SEED + k); del net
    r = dict(model=model_tag, fold=k, n_test=len(te), fit_s=round(fit_s, 1), infer_ms_per_1000=round(inf, 2),
             params_M=round(npar, 2), **metrics(y[te], prob.argmax(1), prob), **(extra or {}))
    save_row(r, prob, te, model_tag)
    print(f'>> {model_tag} fold {k}: F1={r["macro_f1"]:.4f} AUC_high={r["auc_high"]:.4f} ({fit_s:.0f}s)', flush=True)
    if DEV == 'cuda': torch.cuda.empty_cache()
    return r

# ================= PHASE tune =================
if 'tune' in PHASES:
    best = jload(BP, {})
    for m in ['D6', 'D5']:
        tag = f'{m}_tuned'
        for k in range(K):
            if done(load_csv(OUT), tag, k): continue
            t0 = time.time(); tr_in, va_in = inner_split(k)
            st, cfg = run_study(m, f'{m}_outer{k}', tr_in, va_in, SEED + k)
            best[f'{m}_fold{k}'] = dict(cfg=cfg, inner_val_f1=st.best_value,
                                        default_inner_val_f1=st.trials[0].value, n_trials=len(st.trials)); jsave(best, BP)
            outer_eval(tag, m, cfg, k, dict(inner_val_f1=round(st.best_value, 4)))
            print(f'== {tag} outer fold {k} done in {(time.time()-t0)/60:.1f} min | best cfg {cfg}', flush=True)

# ================= PHASE default (same code, Step 8 defaults) =================
if 'default' in PHASES:
    for m in ['D6', 'D5']:
        for k in range(K):
            if not done(load_csv(OUT), f'{m}_default', k): outer_eval(f'{m}_default', m, DEFAULT[m], k)

# ================= PHASE ablate (per-fold tuned D6 config, one component removed) =================
if 'ablate' in PHASES:
    best = jload(BP, {})
    AB = {'A1_NoDEM': dict(hyd=tuple(HYD_NODEM)), 'A2_NoCrossAttention': dict(fusion='concat'), 'A3_VisualOnly': dict(fusion='vis_only')}
    for tag, change in AB.items():
        for k in range(K):
            if done(load_csv(OUT), tag, k) or f'D6_fold{k}' not in best: continue
            cfg = dict(best[f'D6_fold{k}']['cfg']); cfg.update(change); outer_eval(tag, 'D6', cfg, k)

# ================= PHASE stats =================
if 'stats' in PHASES:
    from scipy.stats import friedmanchisquare, wilcoxon, rankdata
    df = load_csv(OUT); piv = df.pivot_table(index='fold', columns='model', values='macro_f1').dropna(axis=1)
    old = pd.concat([load_csv(f'{RES}/cv_tabular.csv'), load_csv(f'{RES}/cv_deep.csv')], ignore_index=True)
    keep = [c for c in ['D6_tuned', 'D5_tuned'] if c in piv]      # Friedman: Step 7-8 models + the two tuned models
    allp = piv[keep].join(old.pivot_table(index='fold', columns='model', values='macro_f1'), how='inner').dropna(axis=1) if len(old) else piv[keep]
    summ = df.groupby('model')[['macro_f1', 'bal_acc', 'qwk', 'auc_high', 'fit_s', 'infer_ms_per_1000', 'params_M']].agg(['mean', 'std']).round(4)
    print('\n=== Optimisation results: outer spatial 10-fold CV ==='); print(summ.to_string())
    def holm(ps):
        o = np.argsort(ps); adj = np.empty(len(ps)); run = 0
        for i, j in enumerate(o): run = max(run, min(1, (len(ps) - i) * ps[j])); adj[j] = run
        return adj
    plan = [('D6_tuned', 'D6_default'), ('D5_tuned', 'D5_default'), ('D6_tuned', 'D5_tuned'),
            ('D6_tuned', 'A1_NoDEM'), ('D6_tuned', 'A2_NoCrossAttention'), ('D6_tuned', 'A3_VisualOnly')]
    plan = [p for p in plan if p[0] in piv and p[1] in piv]; W = []
    for a, b in plan:
        d = piv[a] - piv[b]
        p = wilcoxon(piv[a], piv[b], zero_method='zsplit').pvalue if np.any(d != 0) else 1.0
        W.append(dict(a=a, b=b, mean_diff=float(d.mean()), wins=int((d > 0).sum()), p=float(p)))
    for w, pa in zip(W, holm([w['p'] for w in W])): w['p_holm'] = float(pa); w['significant_0.05'] = bool(pa < 0.05)
    fr = friedmanchisquare(*[allp[c] for c in allp.columns]) if allp.shape[1] >= 3 else type('F', (), dict(statistic=np.nan, pvalue=np.nan))()
    rk = allp.apply(lambda r: rankdata(-r.values), axis=1, result_type='expand')
    rk.columns = allp.columns; mean_rank = rk.mean().sort_values()
    kk, nn_ = len(allp.columns), len(allp); q = {2: 1.960, 3: 2.343, 4: 2.569, 5: 2.728, 6: 2.850, 7: 2.949, 8: 3.031, 9: 3.102, 10: 3.164, 11: 3.219, 12: 3.268, 13: 3.313, 14: 3.354}[kk]
    CD = q * np.sqrt(kk * (kk + 1) / (6 * nn_))
    oof = dict(np.load(OOF)); rng = np.random.default_rng(SEED); blk = fold   # block bootstrap over folds (cluster) for pooled CI
    ci = {}
    for mname in [c for c in ['D6_tuned', 'D6_default', 'D5_tuned'] if c in oof]:
        pr = oof[mname].argmax(1); bs = []
        for _ in range(1000):
            ks = rng.choice(K, K, replace=True); ii = np.concatenate([np.where(blk == j)[0] for j in ks])
            bs.append(f1_score(y[ii], pr[ii], average='macro'))
        ci[mname] = dict(pooled=float(f1_score(y, pr, average='macro')), lo=float(np.percentile(bs, 2.5)), hi=float(np.percentile(bs, 97.5)))
    best = jload(BP, {}); imp = {}; choice = {}
    for m in ['D6', 'D5']:
        acc = []
        for k in range(K):
            f = f'{TUN}/{m}_outer{k}.db'
            if not os.path.exists(f): continue
            st = optuna.load_study(study_name=f'{m}_outer{k}', storage=f'sqlite:///{f}')
            try: acc.append(optuna.importance.get_param_importances(st))
            except Exception as e: print('importance failed', m, k, e)
        if acc: imp[m] = pd.DataFrame(acc).fillna(0).mean().sort_values(ascending=False).round(4).to_dict()
        cf = pd.DataFrame([v['cfg'] for kx, v in best.items() if kx.startswith(m + '_fold')])
        choice[m] = {c: cf[c].astype(str).value_counts().to_dict() for c in cf.columns} if len(cf) else {}
    gain = {m: dict(inner_default=float(np.mean([v['default_inner_val_f1'] for kx, v in best.items() if kx.startswith(m + '_fold')])),
                    inner_best=float(np.mean([v['inner_val_f1'] for kx, v in best.items() if kx.startswith(m + '_fold')])))
            for m in ['D6', 'D5'] if any(kx.startswith(m + '_fold') for kx in best)}
    # reproducibility check: same default config with Step 8 code vs this code
    repro = {}
    for a, b in [('D6_default', 'D6_HSC_Attention'), ('D5_default', 'D5_DualStream_Concat')]:
        if a in piv and b in allp: repro[a] = dict(this_code=float(piv[a].mean()), step8=float(allp[b].mean()))
    OS = dict(generated=datetime.datetime.now().isoformat(timespec='minutes'), n_trials=N_TRIALS, inner_frac=INNER_FRAC,
              summary={c: summ.loc[c].to_dict() for c in summ.index},
              folds={c: piv[c].round(5).tolist() for c in piv.columns}, wilcoxon=W,
              friedman_all=dict(chi2=float(fr.statistic), p=float(fr.pvalue), k=kk, n=nn_, CD=float(CD),
                                mean_rank={c: float(v) for c, v in mean_rank.items()}),
              bootstrap_ci=ci, importance=imp, choices=choice, inner_gain=gain, reproducibility=repro, best_params=best)
    OS['summary'] = {m: {f'{a}_{b}': v for (a, b), v in d.items()} for m, d in OS['summary'].items()}
    jsave(OS, f'{TUN}/optimisation_summary.json')
    print('\nWilcoxon (Holm):'); [print(f"  {w['a']} vs {w['b']}: diff={w['mean_diff']:+.4f} wins={w['wins']}/10 p={w['p']:.4f} p_holm={w['p_holm']:.4f}") for w in W]
    print(f'Friedman over {kk} models: chi2={fr.statistic:.2f} p={fr.pvalue:.2e}; CD={CD:.2f}')
    print('Mean ranks:', {c: round(float(v), 2) for c, v in mean_rank.items()})
    print('Param importance:', imp); print('Inner gain:', gain); print('Reproducibility:', repro); print('CI:', ci)
    print('M1OPT_START' + json.dumps(OS, default=float) + 'M1OPT_END')

# ================= PHASE final: choose config on whole sample, train on all 50k, predict all buildings, demo =================
if 'final' in PHASES:
    OS = jload(f'{TUN}/optimisation_summary.json', {}); piv = load_csv(OUT).pivot_table(index='fold', columns='model', values='macro_f1')
    m = 'D6' if piv.get('D6_tuned', pd.Series([0])).mean() >= piv.get('D5_tuned', pd.Series([0])).mean() else 'D5'
    tuned_better = piv.get(f'{m}_tuned', pd.Series([0])).mean() >= piv.get(f'{m}_default', pd.Series([0])).mean()
    fin = jload(f'{TUN}/final_config.json', None)
    if fin is None:
        if tuned_better:   # same selection procedure applied to all data: inner val = fold 0, train = folds 1..9 (50%)
            kv = 0; tr = np.where(fold != kv)[0]; tr = np.sort(np.random.default_rng(SEED).choice(tr, int(len(tr) * INNER_FRAC), replace=False))
            st, cfg = run_study(m, f'{m}_final', tr, np.where(fold == kv)[0], SEED)
        else: cfg = DEFAULT[m]
        fin = dict(model=m, cfg=cfg, tuned=bool(tuned_better)); jsave(fin, f'{TUN}/final_config.json')
    print('FINAL model:', fin)
    if not TEST:
        import rasterio, base64, io
        from PIL import Image
        allidx = np.arange(len(y)); _, _, _, _, net, (mu, sd) = train_eval(fin['model'], fin['cfg'], allidx, allidx[:1], SEED)
        torch.save(dict(state=net.state_dict(), cfg=fin, mu=mu.cpu(), sd=sd.cpu()), f'{RES}/final_model_optimised.pt'); net.eval()
        full = pd.read_parquet(f'{R}/M1_buildings_dataset_v2.parquet'); CFG = json.load(open(f'{R}/records/step07_label_config.json'))
        dd = full.LABEL_dist_to_flood_m.values; full['y'] = np.where(dd <= CFG['high_m'], 2, np.where(dd <= CFG['medium_m'], 1, 0))
        files = sorted(glob.glob(f'{R}/M1_raster_stack_v1*.tif'))
        with rasterio.open(files[0]) as s: S = np.nan_to_num(s.read().astype('float32'))
        S[8] = np.log1p(S[8])
        def patches(df_):
            r0, c0 = df_.row.values - P // 2, df_.col.values - P // 2
            ir = r0[:, None] + np.arange(P)[None, :]; ic = c0[:, None] + np.arange(P)[None, :]
            return np.stack([S[b][ir[:, :, None], ic[:, None, :]] for b in range(10)], 1).astype('float16')
        probs = []; t1 = time.time()
        with torch.no_grad(), torch.autocast(DEV, enabled=DEV == 'cuda'):
            for i in range(0, len(full), 20000):
                xb = torch.tensor(patches(full.iloc[i:i + 20000]), device=DEV)
                for j in range(0, len(xb), 2048): probs.append(F.softmax(net((xb[j:j + 2048].float() - mu) / sd).float(), 1).cpu().numpy())
        if DEV == 'cuda': torch.cuda.synchronize()
        prob = np.concatenate(probs); t_inf = time.time() - t1; del S
        full['pred'] = prob.argmax(1); full['p_high'] = prob[:, 2]
        samp = pd.read_parquet(f'{R}/M1_sample_with_folds.parquet'); ins = full.bid.isin(samp.bid)
        unseen_f1 = f1_score(full.y[~ins], full.pred[~ins], average='macro')
        print(f'Predicted {len(full):,} buildings in {t_inf:.1f}s ({t_inf/len(full)*1e6:.1f} ms per 1000); macro-F1 on non-sample buildings = {unseen_f1:.3f}')
        print('pred counts', np.bincount(full.pred, minlength=3).tolist(), '| SAR counts', np.bincount(full.y, minlength=3).tolist())
        full[['bid', 'lon', 'lat', 'y', 'pred', 'p_high', 'LABEL_dist_to_flood_m', 'X_hand_m', 'X_dem_m']].to_parquet(f'{RES}/predictions_all_buildings_optimised.parquet', index=False)
        jsave(dict(model=f"{fin['model']}_{'tuned' if fin['tuned'] else 'default'}", cfg=fin['cfg'], infer_s=t_inf, ms_per_1000=t_inf / len(full) * 1e6,
                   unseen_f1=unseen_f1, pred_counts=np.bincount(full.pred, minlength=3).tolist(), sar_counts=np.bincount(full.y, minlength=3).tolist(),
                   n=len(full)), f'{TUN}/final_model_record.json')
        # ---- rebuild demo data.js (keeps original images); old file kept as results/demo_data_step10_backup.js ----
        DEMO = f'{R}/demo'; dj = f'{DEMO}/assets/data.js'
        bk = f'{RES}/demo_data_step10_backup.js'          # backup kept OUTSIDE the demo folder (not zipped)
        if os.path.exists(dj) and not os.path.exists(bk): shutil.copy(dj, bk)
        old = open(bk).read(); meta = json.loads(old.split('window.M1META=', 1)[1].rstrip().rstrip(';'))
        data = dict(lon=np.round(full.lon.values, 5).tolist(), lat=np.round(full.lat.values, 5).tolist(), y=full.y.astype(int).tolist(),
                    p=full.pred.astype(int).tolist(), ph=np.round(full.p_high.values * 100).astype(int).tolist(),
                    hand=np.round(full.X_hand_m.values, 1).tolist(), dist=np.round(np.minimum(full.LABEL_dist_to_flood_m.values, 9999)).astype(int).tolist())
        tag = f"{fin['model']}_HSC_Attention_optimised" if fin['model'] == 'D6' else 'D5_DualStream_optimised'
        os_sum = OS.get('summary', {})
        extra_rows = [dict(model=k2, macro_f1_mean=v.get('macro_f1_mean'), macro_f1_std=v.get('macro_f1_std'), auc_high_mean=v.get('auc_high_mean'))
                      for k2, v in os_sum.items()]
        meta.update(best=tag, generated=datetime.datetime.now().isoformat(timespec='minutes'), infer_ms_per_1000=round(t_inf / len(full) * 1e6, 2),
                    optimisation=dict(rows=extra_rows, wilcoxon=OS.get('wilcoxon', []), final_cfg=fin['cfg']))
        with open(dj, 'w') as f:
            f.write('window.M1DATA=' + json.dumps(data, separators=(',', ':')) + ';\nwindow.M1META=' + json.dumps(meta, default=float) + ';')
        if os.path.exists(f'{R}/M1_demo.zip') and not os.path.exists(f'{R}/M1_demo_step10_backup.zip'): shutil.copy(f'{R}/M1_demo.zip', f'{R}/M1_demo_step10_backup.zip')
        shutil.make_archive(f'{R}/M1_demo', 'zip', DEMO)
        print('Demo rebuilt:', dj, round(os.path.getsize(dj) / 1e6, 1), 'MB; zip', f'{R}/M1_demo.zip')
print('STEP 12 DONE phases', PHASES)
