"""Training / evaluation loop shared by all M2 deep models. One config dict = one experiment."""
import json, os, time, random
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import segmentation_models_pytorch as smp
from .metrics import ConfMat


def seed_all(s):
    random.seed(s); np.random.seed(s); torch.manual_seed(s); torch.cuda.manual_seed_all(s)
    torch.backends.cudnn.deterministic = True; torch.backends.cudnn.benchmark = False


def build_model(arch="Unet", encoder="resnet34", weights="imagenet", in_ch=2):
    cls = {"Unet": smp.Unet, "UnetPlusPlus": smp.UnetPlusPlus, "DeepLabV3Plus": smp.DeepLabV3Plus}[arch]
    return cls(encoder_name=encoder, encoder_weights=weights, in_channels=in_ch, classes=1)


def masked_loss(logits, y, kind="bce_dice", pos_weight=1.0):
    valid = (y >= 0).float(); t = y.clamp(min=0).float()
    logits = logits[:, 0]
    bce = F.binary_cross_entropy_with_logits(logits, t, weight=valid,
                                             pos_weight=torch.tensor(pos_weight, device=logits.device), reduction="sum")
    bce = bce / valid.sum().clamp(min=1)
    if kind == "bce":
        return bce
    p = torch.sigmoid(logits) * valid
    dice = 1 - (2 * (p * t).sum() + 1) / (p.sum() + (t * valid).sum() + 1)
    return bce + dice


@torch.no_grad()
def evaluate(model, loader, device, thr=0.5, return_probs=False):
    model.eval(); cm = ConfMat(); probs = []
    for x, y, cid in loader:
        x = x.to(device)
        H, W = x.shape[-2:]
        ph, pw = (32 - H % 32) % 32, (32 - W % 32) % 32
        lo = model(F.pad(x, (0, pw, 0, ph), mode="reflect"))[..., :H, :W]
        p = torch.sigmoid(lo)[:, 0].cpu().numpy()
        for pi, yi, ci in zip(p, y.numpy(), cid):
            cm.update(pi >= thr, yi)
            if return_probs: probs.append((ci, pi.astype(np.float16), yi.astype(np.int8)))
    return (cm.as_dict(), probs) if return_probs else cm.as_dict()


def fit(cfg, train_loader, val_loader, out_dir, model=None):
    """cfg keys: exp_id, arch, encoder, weights, lr, wd, epochs, loss, pos_weight, freeze_encoder_epochs, seed, patience"""
    os.makedirs(out_dir, exist_ok=True)
    seed_all(cfg["seed"])
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = (model or build_model(cfg["arch"], cfg["encoder"], cfg["weights"])).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=cfg["wd"])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg["epochs"])
    best, bad, hist, t0 = -1, 0, [], time.time()
    for ep in range(cfg["epochs"]):
        frz = ep < cfg.get("freeze_encoder_epochs", 0)
        for p in model.encoder.parameters(): p.requires_grad = not frz
        model.train(); tl, n = 0.0, 0
        for x, y, _ in train_loader:
            x, y = x.to(dev), y.to(dev)
            loss = masked_loss(model(x), y, cfg["loss"], cfg["pos_weight"])
            opt.zero_grad(); loss.backward(); opt.step()
            tl += loss.item() * len(x); n += len(x)
        sched.step()
        vm = evaluate(model, val_loader, dev)
        vl = val_loss(model, val_loader, dev, cfg)
        hist.append({"epoch": ep + 1, "train_loss": tl / n, "val_loss": vl, **{f"val_{k}": vm[k] for k in ("iou", "f1", "precision", "recall")}})
        print(f"[{cfg['exp_id']}] ep{ep+1:03d} tl={tl/n:.4f} vl={vl:.4f} vIoU={vm['iou']:.4f} vF1={vm['f1']:.4f}")
        if vm["iou"] > best:
            best, bad = vm["iou"], 0
            torch.save(model.state_dict(), f"{out_dir}/best.pt")
        else:
            bad += 1
            if bad >= cfg.get("patience", 1e9): break
    json.dump(hist, open(f"{out_dir}/history.json", "w"), indent=1)
    model.load_state_dict(torch.load(f"{out_dir}/best.pt", map_location=dev))
    return model, hist, time.time() - t0


@torch.no_grad()
def val_loss(model, loader, dev, cfg):
    model.eval(); s, n = 0.0, 0
    for x, y, _ in loader:
        x, y = x.to(dev), y.to(dev)
        H, W = x.shape[-2:]; ph, pw = (32 - H % 32) % 32, (32 - W % 32) % 32
        lo = model(F.pad(x, (0, pw, 0, ph), mode="reflect"))[..., :H, :W]
        s += masked_loss(lo, y, cfg["loss"], cfg["pos_weight"]).item() * len(x); n += len(x)
    return s / max(n, 1)
