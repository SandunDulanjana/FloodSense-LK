"""Sen1Floods11 S1Hand loading and the SAR normalisation used throughout M2.

Normalisation follows the Sen1Floods11 baseline (Bonafilia et al., CVPRW 2020):
dB clipped to [-50, 1], scaled to [0, 1] by (x+50)/51, then standardised with the hand-labelled
training-set statistics mean=[0.6851, 0.5235], std=[0.0820, 0.1102] (VV, VH).
The SAME function is applied to Sri Lankan GEE S1_GRD dB chips, so no distribution shift is introduced by preprocessing."""
import os, glob
import numpy as np
import rasterio
import torch
from torch.utils.data import Dataset

MEAN = np.array([0.6851, 0.5235], dtype=np.float32)
STD = np.array([0.0820, 0.1102], dtype=np.float32)


def normalise_db(x):
    """x: (2,H,W) VV,VH in dB (NaN allowed). Returns normalised float32 and a nodata mask."""
    x = x.astype(np.float32)
    nod = ~np.isfinite(x).all(0)
    x = np.nan_to_num(x, nan=-50.0)
    x = (np.clip(x, -50, 1) + 50) / 51
    x = (x - MEAN[:, None, None]) / STD[:, None, None]
    return x, nod


def read_split(csv_path):
    """Official split CSVs list '<chip>_S1Hand.tif,<chip>_LabelHand.tif' per line."""
    rows = []
    for line in open(csv_path):
        line = line.strip()
        if line:
            s1, lab = [p.strip() for p in line.split(",")[:2]]
            rows.append((s1, lab))
    return rows


class S1Chips(Dataset):
    def __init__(self, pairs, s1_dir, lab_dir, crop=None, augment=False, cache=True):
        self.items = []
        for s1, lab in pairs:
            with rasterio.open(os.path.join(s1_dir, s1)) as r:
                x = r.read()
            with rasterio.open(os.path.join(lab_dir, lab)) as r:
                y = r.read(1).astype(np.int8)
            x, nod = normalise_db(x)
            y[nod] = -1
            self.items.append((x, y, s1.replace("_S1Hand.tif", "")))
        self.crop, self.augment = crop, augment

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        x, y, cid = self.items[i]
        if self.crop:
            H, W = y.shape; c = self.crop
            r0 = np.random.randint(0, H - c + 1); c0 = np.random.randint(0, W - c + 1)
            x, y = x[:, r0:r0 + c, c0:c0 + c], y[r0:r0 + c, c0:c0 + c]
        if self.augment:
            if np.random.rand() < .5: x, y = x[:, :, ::-1], y[:, ::-1]
            if np.random.rand() < .5: x, y = x[:, ::-1, :], y[::-1, :]
        return torch.from_numpy(x.copy()), torch.from_numpy(y.copy().astype(np.int64)), cid


def event_of(chip_id):
    return chip_id.split("_")[0]


def filter_pairs(pairs, include=None, exclude=None):
    """Select split rows by event name (e.g. exclude=['Sri-Lanka'] for the global-only model)."""
    out = []
    for s1, lab in pairs:
        ev = event_of(s1.replace("_S1Hand.tif", ""))
        if include is not None and ev not in include: continue
        if exclude is not None and ev in exclude: continue
        out.append((s1, lab))
    return out
