# ===== M1 Step 8: Deep models on 32x32 image patches (same sample + same spatial folds as Step 7) =====
# D1 SimpleCNN (scratch) | D2 ResNet18 random init | D3 ResNet18 ImageNet | D4 ResNet50 SSL4EO-S12 (S2 RGB MoCo)
# D5 Dual-Stream ResNet18 + concatenation (proposal Baseline 1) | D6 HSC-Attention prototype (proposed, cross-attention)
import os, json, time, glob, datetime, numpy as np, pandas as pd, torch, torch.nn as nn, torch.nn.functional as F
import torchvision, rasterio
from sklearn.metrics import f1_score, balanced_accuracy_score, cohen_kappa_score, roc_auc_score, accuracy_score
torch.backends.cudnn.benchmark = True
R = '/content/drive/MyDrive/M1_Research'; RES = f'{R}/results'; os.makedirs(RES, exist_ok=True)
DEV = 'cuda' if torch.cuda.is_available() else 'cpu'; print('device', DEV, torch.cuda.get_device_name(0) if DEV == 'cuda' else '')
SEED, K, EPOCHS, BS, P = 42, 10, 6, 256, 32

# ---- patches ----
samp = pd.read_parquet(f'{R}/M1_sample_with_folds.parquet')
files = sorted(glob.glob(f'{R}/M1_raster_stack_v1*.tif'))
if len(files) == 1:
    with rasterio.open(files[0]) as s: S = s.read().astype('float32')
else:
    from rasterio.merge import merge
    srcs = [rasterio.open(f) for f in files]; S = merge(srcs)[0].astype('float32')
S[8] = np.log1p(S[8])                                    # distance to river -> log scale
r0, c0 = samp.row.values - P // 2, samp.col.values - P // 2
idx_r = r0[:, None] + np.arange(P)[None, :]; idx_c = c0[:, None] + np.arange(P)[None, :]
X = np.stack([S[b][idx_r[:, :, None], idx_c[:, None, :]] for b in range(10)], 1).astype('float16')   # N,10,32,32
del S
y = samp.y.values.astype('int64'); fold = samp.fold.values
print('patch tensor', X.shape, X.dtype, f'{X.nbytes/1e9:.2f} GB')
VIS, HYD, RGB = [0, 1, 2, 3, 4], [5, 6, 7, 8, 9], [2, 1, 0]   # S2 bands | terrain bands | B4,B3,B2
XG = torch.tensor(X, device=DEV)                               # whole patch set on GPU (fp16, ~1 GB) for speed

# ---- models ----
def adapt_conv1(m, cin):
    w = m.conv1.weight.data; new = nn.Conv2d(cin, 64, 7, 2, 3, bias=False)
    with torch.no_grad():
        new.weight[:] = w.mean(1, keepdim=True).repeat(1, cin, 1, 1) * 3 / cin
        if cin >= 3: new.weight[:, :3] = w[:, [2, 1, 0]]     # S2 channels 0,1,2 = B2(blue),B3(green),B4(red)
    m.conv1 = new; return m
def resnet18(cin, pre):
    m = torchvision.models.resnet18(weights='IMAGENET1K_V1' if pre else None); return adapt_conv1(m, cin) if cin != 3 else m
class Up(nn.Module):
    def __init__(s, net, sel): super().__init__(); s.net, s.sel = net, sel
    def forward(s, x): return s.net(F.interpolate(x[:, s.sel], size=64, mode='bilinear', align_corners=False))
class SimpleCNN(nn.Module):
    def __init__(s, cin=10):
        super().__init__(); c = lambda i, o: nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU())
        s.f = nn.Sequential(c(cin, 32), c(32, 32), nn.MaxPool2d(2), c(32, 64), c(64, 64), nn.MaxPool2d(2), c(64, 128), nn.AdaptiveAvgPool2d(1))
        s.h = nn.Sequential(nn.Flatten(), nn.Dropout(0.3), nn.Linear(128, 3))
    def forward(s, x): return s.h(s.f(x))
def hydro_encoder(cin=5, d=256):      # 64x64 -> d x 4 x 4
    c = lambda i, o: nn.Sequential(nn.Conv2d(i, o, 3, 2, 1), nn.BatchNorm2d(o), nn.ReLU())
    return nn.Sequential(c(cin, 64), c(64, 128), c(128, 192), c(192, d))
def vis_trunk(cin=5):                 # ResNet18 up to layer3: 64x64 -> 256 x 4 x 4
    r = resnet18(cin, True); return nn.Sequential(r.conv1, r.bn1, r.relu, r.maxpool, r.layer1, r.layer2, r.layer3), r.layer4
class DualStreamConcat(nn.Module):    # proposal Baseline 1: early-fusion by simple concatenation
    def __init__(s):
        super().__init__(); s.v3, s.v4 = vis_trunk(); s.h = hydro_encoder()
        s.head = nn.Sequential(nn.Linear(512 + 256, 256), nn.ReLU(), nn.Dropout(0.3), nn.Linear(256, 3))
    def forward(s, x):
        x = F.interpolate(x, size=64, mode='bilinear', align_corners=False)
        v = s.v4(s.v3(x[:, VIS])).mean((2, 3)); h = s.h(x[:, HYD]).mean((2, 3))
        return s.head(torch.cat([v, h], 1))
class HSCAttention(nn.Module):        # proposed: visual tokens (Q) attend to hydro-terrain tokens (K,V)
    def __init__(s, d=256, heads=4):
        super().__init__(); s.v3, _ = vis_trunk(); s.h = hydro_encoder(d=d)
        s.pos = nn.Parameter(torch.zeros(1, 16, d)); nn.init.trunc_normal_(s.pos, std=0.02)
        s.att = nn.MultiheadAttention(d, heads, dropout=0.1, batch_first=True)
        s.n1, s.n2 = nn.LayerNorm(d), nn.LayerNorm(d); s.ffn = nn.Sequential(nn.Linear(d, 2 * d), nn.GELU(), nn.Linear(2 * d, d))
        s.head = nn.Sequential(nn.Linear(2 * d, 256), nn.ReLU(), nn.Dropout(0.3), nn.Linear(256, 3)); s.last_attn = None
    def forward(s, x):
        x = F.interpolate(x, size=64, mode='bilinear', align_corners=False)
        q = s.v3(x[:, VIS]).flatten(2).transpose(1, 2) + s.pos          # B,16,256 visual tokens
        kv = s.h(x[:, HYD]).flatten(2).transpose(1, 2) + s.pos          # B,16,256 hydro tokens
        a, w = s.att(q, kv, kv, need_weights=True); s.last_attn = w.detach()
        z = s.n1(q + a); z = s.n2(z + s.ffn(z))
        return s.head(torch.cat([z.mean(1), kv.mean(1)], 1))
def ssl4eo_resnet50():
    try:
        from torchgeo.models import ResNet50_Weights
        import timm
        w = ResNet50_Weights.SENTINEL2_RGB_MOCO
        m = timm.create_model('resnet50', in_chans=3, num_classes=3)
        sd_ = w.get_state_dict(progress=False); own = m.state_dict()
        sd_ = {k_: v_ for k_, v_ in sd_.items() if k_ in own and own[k_].shape == v_.shape}
        missing = m.load_state_dict(sd_, strict=False)
        print('   SSL4EO weights loaded; missing keys (head only expected):', missing.missing_keys[:4])
        return Up(m, RGB)
    except Exception as e:
        print('   SSL4EO load failed:', str(e)[:150]); return None
def build(name):
    if name == 'D1_SimpleCNN_scratch': return SimpleCNN()
    if name == 'D2_ResNet18_random':   return Up(nn.Sequential(resnet18(10, False)), list(range(10)))
    if name == 'D3_ResNet18_ImageNet': return Up(nn.Sequential(resnet18(10, True)), list(range(10)))
    if name == 'D4_ResNet50_SSL4EO':   return ssl4eo_resnet50()
    if name == 'D5_DualStream_Concat': return DualStreamConcat()
    if name == 'D6_HSC_Attention':     return HSCAttention()
def fix_head(m, name):                 # torchvision resnets have 1000-class fc -> replace with 3
    if name in ('D2_ResNet18_random', 'D3_ResNet18_ImageNet'): m.net[0].fc = nn.Linear(512, 3)
    return m
MODELS = ['D1_SimpleCNN_scratch', 'D2_ResNet18_random', 'D3_ResNet18_ImageNet', 'D4_ResNet50_SSL4EO', 'D5_DualStream_Concat', 'D6_HSC_Attention']
LR = {'D1_SimpleCNN_scratch': 1e-3, 'D2_ResNet18_random': 1e-3}

def metrics(yt, yp, prob):
    out = dict(macro_f1=f1_score(yt, yp, average='macro'), bal_acc=balanced_accuracy_score(yt, yp),
               acc=accuracy_score(yt, yp), qwk=cohen_kappa_score(yt, yp, weights='quadratic'))
    try: out['auc_high'] = roc_auc_score((yt == 2).astype(int), prob[:, 2])
    except ValueError: out['auc_high'] = np.nan
    return out

out_csv = f'{RES}/cv_deep.csv'; done = pd.read_csv(out_csv) if os.path.exists(out_csv) else pd.DataFrame()
oof_f = f'{RES}/oof_deep.npz'; oof = dict(np.load(oof_f)) if os.path.exists(oof_f) else {}
for name in MODELS:
    if name not in oof: oof[name] = np.zeros((len(y), 3), 'float32')
    for k in range(K):
        if len(done) and ((done.model == name) & (done.fold == k)).any(): continue     # resume support
        torch.manual_seed(SEED + k); np.random.seed(SEED + k)
        tr, te = np.where(fold != k)[0], np.where(fold == k)[0]
        sub = XG[torch.tensor(tr[::4], device=DEV)].float()              # per-fold normalisation from TRAIN blocks only
        mu_t = sub.mean((0, 2, 3)).view(1, -1, 1, 1); sd_t = sub.std((0, 2, 3)).view(1, -1, 1, 1) + 1e-6; del sub
        net = build(name)
        if net is None: break
        net = fix_head(net, name).to(DEV)
        opt = torch.optim.AdamW(net.parameters(), lr=LR.get(name, 3e-4), weight_decay=1e-4)
        steps = EPOCHS * int(np.ceil(len(tr) / BS)); sch = torch.optim.lr_scheduler.OneCycleLR(opt, LR.get(name, 3e-4), total_steps=steps)
        cw = torch.tensor(len(tr) / (3 * np.bincount(y[tr], minlength=3)), dtype=torch.float32, device=DEV)
        scaler = torch.amp.GradScaler('cuda', enabled=DEV == 'cuda'); t0 = time.time()
        for ep in range(EPOCHS):
            net.train(); perm = np.random.permutation(tr)
            for i in range(0, len(perm), BS):
                b = perm[i:i + BS]; xb = (XG[torch.tensor(b, device=DEV)].float() - mu_t) / sd_t; yb = torch.tensor(y[b], device=DEV)
                if np.random.rand() < .5: xb = xb.flip(3)
                if np.random.rand() < .5: xb = xb.flip(2)
                xb = torch.rot90(xb, np.random.randint(4), (2, 3))
                with torch.autocast(DEV, enabled=DEV == 'cuda'):
                    loss = F.cross_entropy(net(xb), yb, weight=cw)
                opt.zero_grad(set_to_none=True); scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); sch.step()
        fit_s = time.time() - t0
        net.eval(); probs = []; t0 = time.time()
        with torch.no_grad(), torch.autocast(DEV, enabled=DEV == 'cuda'):
            for i in range(0, len(te), 1024):
                b = te[i:i + 1024]; probs.append(F.softmax(net((XG[torch.tensor(b, device=DEV)].float() - mu_t) / sd_t).float(), 1).cpu().numpy())
        if DEV == 'cuda': torch.cuda.synchronize()
        inf_ms = (time.time() - t0) / len(te) * 1000 * 1000
        prob = np.concatenate(probs); oof[name][te] = prob
        r = dict(model=name, fold=k, n_test=len(te), fit_s=round(fit_s, 1), infer_ms_per_1000=round(inf_ms, 2),
                 params_M=round(sum(p.numel() for p in net.parameters()) / 1e6, 2), **metrics(y[te], prob.argmax(1), prob))
        done = pd.concat([done, pd.DataFrame([r])], ignore_index=True); done.to_csv(out_csv, index=False)
        np.savez_compressed(oof_f, **oof)
        print(f"{name} fold {k}: F1={r['macro_f1']:.3f} QWK={r['qwk']:.3f} AUC_high={r['auc_high']:.3f} ({fit_s:.0f}s)")
        if name == 'D6_HSC_Attention' and k == 0: torch.save(net.state_dict(), f'{RES}/hsc_attention_fold0.pt')
        if name == 'D5_DualStream_Concat' and k == 0: torch.save(net.state_dict(), f'{RES}/dualstream_fold0.pt')
        del net, opt; torch.cuda.empty_cache()
summ = done.groupby('model')[['macro_f1', 'bal_acc', 'qwk', 'auc_high', 'fit_s', 'infer_ms_per_1000', 'params_M']].agg(['mean', 'std']).round(4)
print('\n=== Deep models: spatial 10-fold CV (mean ± std) ==='); print(summ.to_string())
