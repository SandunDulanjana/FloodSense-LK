"""Loader for the official Sen1Floods11 checkpoints (gs://sen1floods11/v1.1/checkpoints/*.cp).
Verified 2026-10-24: torchvision FCN-ResNet50, conv1 [64,2,7,7], classifier.4 [2,512,1,1], no aux head.
The state dict has norm weights/biases but NO running_mean/var -> the norm layers are GroupNorm (as stated in
Bonafilia et al. 2020), merely keeping torchvision's 'bn*' names. We therefore convert every BatchNorm2d to GroupNorm.
The group count is not stored in the weights; it is verified empirically in M2-02 against the official validation split.
Class index 1 = water. Inputs use the same normalisation as m2.data.normalise_db."""
import torch, torch.nn as nn
from torchvision.models.segmentation import fcn_resnet50

DEFAULT_GROUPS = 16


def bn_to_gn(module, groups):
    for name, child in module.named_children():
        if isinstance(child, nn.BatchNorm2d):
            setattr(module, name, nn.GroupNorm(groups, child.num_features, eps=child.eps, affine=True))
        else:
            bn_to_gn(child, groups)
    return module


class FCNWater(nn.Module):
    """Wraps the 2-class FCN so it returns a single water logit (logit1 - logit0), matching smp models."""
    def __init__(self, ckpt_path=None, groups=None):
        super().__init__()
        m = fcn_resnet50(weights=None, weights_backbone=None, num_classes=2, aux_loss=False)
        m.backbone.conv1 = nn.Conv2d(2, 64, kernel_size=7, stride=2, padding=3, bias=False)
        bn_to_gn(m, groups or DEFAULT_GROUPS)
        if ckpt_path:
            sd = torch.load(ckpt_path, map_location="cpu", weights_only=False)
            if not isinstance(sd, dict): sd = sd.state_dict()
            m.load_state_dict(sd, strict=True)
        self.m = m
        self.encoder = m.backbone  # so freeze logic in train.fit works

    def forward(self, x):
        out = self.m(x)["out"]
        return (out[:, 1] - out[:, 0]).unsqueeze(1)
