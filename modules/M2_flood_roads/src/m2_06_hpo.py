# M2-06: controlled hyperparameter study (pre-registered as D25). Validation data only; Kelani is NOT evaluated.
# Colab (T4 GPU):  %run -i /content/drive/MyDrive/M2_flood_roads/src/m2_06_hpo.py      (resumable: finished runs are skipped)
import os, sys, json, time, datetime, platform, urllib.request, concurrent.futures as cf
import numpy as np, pandas as pd, torch
ROOT = '/content/drive/MyDrive/M2_flood_roads'; OUT = f'{ROOT}/outputs/M2_06'; os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, f'{ROOT}/src')
from m2 import data as Dm, train as T
from torch.utils.data import DataLoader
dev = 'cuda' if torch.cuda.is_available() else 'cpu'; print('device', dev, torch.cuda.get_device_name(0) if dev == 'cuda' else '')
assert dev == 'cuda', 'Switch the runtime to a GPU (T4) before running the study.'

# ---- data: Sen1Floods11 v1.1 hand-labelled chips + official splits, public HTTPS (no sign-in needed)
D = '/content/s1f11'; U = 'https://storage.googleapis.com/sen1floods11/v1.1'
for sub in ['splits/flood_handlabeled', 'S1Hand', 'LabelHand']: os.makedirs(f'{D}/{sub}', exist_ok=True)
def get(url, dst):
    if not os.path.exists(dst) or os.path.getsize(dst) == 0: urllib.request.urlretrieve(url, dst)
for k in ['train', 'valid', 'test', 'bolivia']:
    get(f'{U}/splits/flood_handlabeled/flood_{k}_data.csv', f'{D}/splits/flood_handlabeled/flood_{k}_data.csv')
off = {k: Dm.read_split(f'{D}/splits/flood_handlabeled/flood_{k}_data.csv') for k in ['train', 'valid', 'test', 'bolivia']}
jobs = [(f'{U}/data/flood_events/HandLabeled/S1Hand/{s1}', f'{D}/S1Hand/{s1}') for v in off.values() for s1, _ in v] + \
       [(f'{U}/data/flood_events/HandLabeled/LabelHand/{lb}', f'{D}/LabelHand/{lb}') for v in off.values() for _, lb in v]
with cf.ThreadPoolExecutor(16) as ex: list(ex.map(lambda j: get(*j), jobs))
print(len(os.listdir(f'{D}/S1Hand')), 'S1 chips,', len(os.listdir(f'{D}/LabelHand')), 'labels')
LK = ['Sri-Lanka']
SPL = {'a_train': off['train'], 'a_valid': off['valid'],
       'g_valid': Dm.filter_pairs(off['valid'], exclude=LK), 'l_valid': Dm.filter_pairs(off['valid'], include=LK),
       'l_test': Dm.filter_pairs(off['test'], include=LK)}
ref = json.load(open(f'{ROOT}/outputs/M2_02/splits_D16.json'))          # same splits as M2-02
for k in SPL: assert sorted(a for a, _ in SPL[k]) == sorted(ref[k]), f'split {k} differs from M2-02'
DS = {k: Dm.S1Chips(v, f'{D}/S1Hand', f'{D}/LabelHand') for k, v in SPL.items()}
DS['a_train'].crop, DS['a_train'].augment = 256, True
EL = {k: DataLoader(DS[k], batch_size=4, shuffle=False, num_workers=2) for k in ['a_valid', 'g_valid', 'l_valid', 'l_test']}
print({k: len(v) for k, v in DS.items()})

# ---- D25 design: one factor at a time around the selected E04 configuration
BASE = dict(arch='Unet', encoder='resnet34', weights='imagenet', lr=5e-4, wd=1e-2, epochs=60, loss='bce_dice',
            pos_weight=1.0, freeze_encoder_epochs=0, patience=15, batch=16, crop=256, train='a_train', select='a_valid')
CONFIGS = {'C0_base': {}, 'C1_lr1e-4': {'lr': 1e-4}, 'C2_lr3e-4': {'lr': 3e-4}, 'C3_lr1e-3': {'lr': 1e-3},
           'C4_loss_bce': {'loss': 'bce'}, 'C5_posw2': {'pos_weight': 2.0}, 'C6_freeze5': {'freeze_encoder_epochs': 5},
           'C7_unetpp': {'arch': 'UnetPlusPlus'}, 'C8_deeplabv3p': {'arch': 'DeepLabV3Plus'}}
SEEDS = [42, 7]
import segmentation_models_pytorch as smp, torchvision
ENV = {'torch': torch.__version__, 'smp': smp.__version__, 'torchvision': torchvision.__version__, 'gpu': torch.cuda.get_device_name(0),
       'python': platform.python_version()}
RES = f'{OUT}/hpo_results.csv'
done = set(pd.read_csv(RES).exp_id) if os.path.exists(RES) else set()
for cid, ov in CONFIGS.items():
    for s in SEEDS:
        exp = f'HPO_{cid}_s{s}'
        if exp in done: print('skip', exp); continue
        cfg = {**BASE, **ov, 'exp_id': exp, 'seed': s}
        TL = DataLoader(DS['a_train'], batch_size=cfg['batch'], shuffle=True, num_workers=2, drop_last=True,
                        generator=torch.Generator().manual_seed(s))
        model, hist, secs = T.fit(cfg, TL, EL['a_valid'], f'/content/ckpt/{exp}')
        m = {k: T.evaluate(model, EL[k], dev) for k in EL}
        row = {'exp_id': exp, 'config': cid, 'seed': s, 'epochs_run': len(hist), 'best_epoch': int(np.argmax([h['val_iou'] for h in hist])) + 1,
               'train_min': round(secs / 60, 2), **{f'{k}_{q}': round(m[k][q], 4) for k in m for q in ('iou', 'f1', 'precision', 'recall')}}
        pd.DataFrame([row]).to_csv(RES, mode='a', header=not os.path.exists(RES), index=False)
        json.dump(hist, open(f'{OUT}/hist_{exp}.json', 'w'))
        open(f'{ROOT}/outputs/experiments.jsonl', 'a').write(json.dumps({'utc': datetime.datetime.now(datetime.UTC).isoformat(), 'notebook': 'M2_06',
             'config': cfg, 'env': ENV, 'train_min': row['train_min'], 'results': row}, default=str) + '\n')
        print('DONE', exp, {k: row[f'{k}_iou'] for k in EL})

# ---- D25 decision rule (validation only)
R = pd.read_csv(RES)
S = R.groupby('config').agg(a_valid_mean=('a_valid_iou', 'mean'), a_valid_sd=('a_valid_iou', 'std'), a_valid_min=('a_valid_iou', 'min'),
                            l_valid_mean=('l_valid_iou', 'mean'), g_valid_mean=('g_valid_iou', 'mean'),
                            l_test_mean_info=('l_test_iou', 'mean'), minutes=('train_min', 'sum')).reindex(CONFIGS).round(4)
b = S.loc['C0_base']; spread = float(R[R.config == 'C0_base'].a_valid_iou.max() - R[R.config == 'C0_base'].a_valid_iou.min())
margin = max(0.01, spread)
S['gain_vs_base'] = (S.a_valid_mean - b.a_valid_mean).round(4); S['improves'] = S.gain_vs_base > margin
S.to_csv(f'{OUT}/hpo_summary.csv')
best = S.a_valid_mean.idxmax()
dec = {'rule': 'D25: improvement only if mean a_valid IoU gain > max(0.01, C0 seed spread)', 'margin': round(margin, 4),
       'base_a_valid_mean': float(b.a_valid_mean), 'best_config': best, 'best_gain': float(S.loc[best, 'gain_vs_base']),
       'improving_configs': S.index[S.improves].tolist(),
       'recommended': best if bool(S.loc[best, 'improves']) else 'C0_base (no factor exceeded the margin)',
       'kelani_evaluated': False, 'utc': datetime.datetime.now(datetime.UTC).isoformat()}
json.dump(dec, open(f'{OUT}/hpo_decision.json', 'w'), indent=1)
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
order = [c for c in CONFIGS if c in S.index]
ax[0].bar(range(len(order)), S.loc[order, 'a_valid_mean'], yerr=S.loc[order, 'a_valid_sd'].fillna(0), color=['#888' if c == 'C0_base' else '#3b6ea8' for c in order])
ax[0].axhspan(b.a_valid_mean - margin, b.a_valid_mean + margin, color='orange', alpha=.2, label='base ± margin')
ax[0].set_xticks(range(len(order))); ax[0].set_xticklabels(order, rotation=45, ha='right', fontsize=8); ax[0].set_ylabel('IoU, official validation (mean of 2 seeds)')
lo = S.loc[order, 'a_valid_mean'].min() - .05; ax[0].set_ylim(max(0, lo), min(1, S.loc[order, 'a_valid_mean'].max() + .05)); ax[0].legend(fontsize=8)
for cid in ['C0_base', 'C1_lr1e-4', 'C3_lr1e-3']:
    for s in SEEDS:
        f = f'{OUT}/hist_HPO_{cid}_s{s}.json'
        if os.path.exists(f): h = json.load(open(f)); ax[1].plot([e['val_iou'] for e in h], label=f'{cid} s{s}', lw=1)
ax[1].set_xlabel('epoch'); ax[1].set_ylabel('validation IoU'); ax[1].legend(fontsize=7)
fig.tight_layout(); fig.savefig(f'{OUT}/hpo_summary.png', dpi=150)
print(S.to_string()); print(json.dumps(dec, indent=1)); print('DONE M2_06')
