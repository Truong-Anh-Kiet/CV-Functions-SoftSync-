from dataclasses import dataclass, field
from typing import Type
import torch.nn as nn
from app.models import cross_architectures as cross_arch

@dataclass(frozen=True)
class CrossModelEntry:
    id: str
    display_name: str
    architecture: Type[nn.Module]
    constructor_kwargs: dict = field(default_factory=dict)
    backbone_id: str = ""
    weights_file: str = ""

# All 4 LamdaTrainable "best" models share the bert-base-multilingual-cased
# (mBERT) backbone → the backbone is loaded once and shared (see cross_runtime).
_MBERT = "bert-base-multilingual-cased"

CROSS_REGISTRY: dict[str, CrossModelEntry] = {
    "cross_weighted": CrossModelEntry(
        id="weighted_sum_cross_encoder",
        display_name="[Cross-Encoder] Weighted Sum (mBERT)",
        architecture=cross_arch.FusionWithScorerWrapper,
        constructor_kwargs={
            "hidden_dim": 768,
            "fusion_module": cross_arch.CrossFusion_Weighted(input_dim=100)
        },
        backbone_id=_MBERT,
        weights_file="weighted_sum_bert-base-multilingual-cased_LamdaTrainable.pth"
    ),
    "cross_mlp": CrossModelEntry(
        id="mlp_base_cross_encoder",
        display_name="[Cross-Encoder] MLP Base (mBERT)",
        architecture=cross_arch.FusionWithScorerWrapper,
        constructor_kwargs={
            "hidden_dim": 768,
            "fusion_module": cross_arch.CrossFusion_MLP(input_dim=100)
        },
        backbone_id=_MBERT,
        weights_file="mlp_bert-base-multilingual-cased_LamdaTrainable.pth"
    ),
    "cross_residual": CrossModelEntry(
        id="mlp_residual_cross_encoder",
        display_name="[Cross-Encoder] Residual MLP (mBERT)",
        architecture=cross_arch.FusionWithScorerWrapper,
        constructor_kwargs={
            "hidden_dim": 768,
            "fusion_module": cross_arch.CrossFusion_Residual(input_dim=100)
        },
        backbone_id=_MBERT,
        weights_file="residual_mlp_bert-base-multilingual-cased_LamdaTrainable.pth"
    ),
    "cross_attention": CrossModelEntry(
        id="attention_cross_encoder",
        display_name="[Cross-Encoder] Attention (mBERT)",
        architecture=cross_arch.FusionWithScorerWrapper,
        constructor_kwargs={
            "hidden_dim": 768,
            "fusion_module": cross_arch.CrossFusion_Attention(num_views=50)
        },
        backbone_id=_MBERT,
        weights_file="attention_bert-base-multilingual-cased_LamdaTrainable.pth"
    ),
}