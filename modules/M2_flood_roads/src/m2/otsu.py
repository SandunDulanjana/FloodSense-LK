"""Classical SAR baselines. Water has low backscatter, so pixels BELOW the threshold are water."""
import numpy as np
from skimage.filters import threshold_otsu


def otsu_threshold(db, valid=None):
    v = db[np.isfinite(db)] if valid is None else db[valid & np.isfinite(db)]
    v = v[(v > -40) & (v < 5)]  # drop extreme outliers / zeros before histogramming
    return float(threshold_otsu(v)) if v.size > 100 else np.nan


def otsu_predict(db_band):
    """Per-image (per-chip or per-scene) automatic Otsu, as in Tiwari et al. (2020)."""
    t = otsu_threshold(db_band)
    return (db_band < t) if np.isfinite(t) else np.zeros_like(db_band, bool), t


def fixed_predict(db_band, t):
    """Global threshold tuned on training/validation data only (fairer than per-chip Otsu
    when a chip contains little or no water, where Otsu's bimodality assumption fails)."""
    return db_band < t
