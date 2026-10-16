"""Segmentation metrics computed from an accumulated confusion matrix.
Label convention (Sen1Floods11): 1 = water, 0 = not water, -1 = nodata (ignored)."""
import numpy as np


class ConfMat:
    def __init__(self):
        self.tp = self.fp = self.fn = self.tn = 0

    def update(self, pred, label):
        pred = np.asarray(pred).astype(bool)
        label = np.asarray(label)
        valid = label >= 0
        p, l = pred[valid], label[valid].astype(bool)
        self.tp += int(np.sum(p & l)); self.fp += int(np.sum(p & ~l))
        self.fn += int(np.sum(~p & l)); self.tn += int(np.sum(~p & ~l))
        return self

    def as_dict(self):
        return scores(self.tp, self.fp, self.fn, self.tn)


def scores(tp, fp, fn, tn):
    eps = 1e-9
    prec = tp / (tp + fp + eps); rec = tp / (tp + fn + eps)
    return {
        "iou": tp / (tp + fp + fn + eps),
        "f1": 2 * tp / (2 * tp + fp + fn + eps),
        "precision": prec, "recall": rec,
        "accuracy": (tp + tn) / (tp + fp + fn + tn + eps),
        # Accuracy is dominated by the dry majority class; report it, but never select models on it.
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def per_chip(preds, labels, ids):
    """Per-chip scores; chips with no valid water AND no predicted water are kept (IoU undefined -> NaN)."""
    out = []
    for p, l, i in zip(preds, labels, ids):
        d = ConfMat().update(p, l).as_dict()
        if d["tp"] + d["fp"] + d["fn"] == 0:
            d["iou"] = d["f1"] = float("nan")
        d["chip"] = i
        out.append(d)
    return out


def paired_bootstrap_diff(rows_a, rows_b, n=5000, seed=0):
    """Paired cluster bootstrap over chips of IoU(B) - IoU(A) on the SAME chips.
    Chips are spatially correlated within an event, so this is a descriptive robustness check of
    within-event variability, not a test that generalises across flood events."""
    assert [r["chip"] for r in rows_a] == [r["chip"] for r in rows_b]
    rng = np.random.default_rng(seed); k = len(rows_a); d = []
    A = np.array([[r["tp"], r["fp"], r["fn"]] for r in rows_a], float)
    B = np.array([[r["tp"], r["fp"], r["fn"]] for r in rows_b], float)
    iou = lambda M: M[0] / (M.sum() + 1e-9)
    for _ in range(n):
        i = rng.integers(0, k, k)
        d.append(iou(B[i].sum(0)) - iou(A[i].sum(0)))
    d = np.array(d)
    return {"diff": float(iou(B.sum(0)) - iou(A.sum(0))), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
            "p_b_better": float((d > 0).mean())}


def bootstrap_ci(chip_rows, n=2000, seed=0, groups=None):
    """Cluster bootstrap over chips (or over `groups`, e.g. events) of pooled IoU.
    Resampling pooled confusion counts, not averaging per-chip IoU, keeps the estimate consistent with the headline metric."""
    rng = np.random.default_rng(seed)
    keys = groups if groups is not None else list(range(len(chip_rows)))
    uniq = sorted(set(keys))
    idx = {k: [j for j, g in enumerate(keys) if g == k] for k in uniq}
    vals = []
    for _ in range(n):
        tp = fp = fn = 0
        for k in rng.choice(uniq, size=len(uniq), replace=True):
            for j in idx[k]:
                r = chip_rows[j]; tp += r["tp"]; fp += r["fp"]; fn += r["fn"]
        vals.append(tp / (tp + fp + fn + 1e-9))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))
