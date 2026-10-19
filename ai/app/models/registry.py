"""
Unified registry of available CV-JD matching models.
Binds architectures (Bi and Cross), backbones, and specific weight files.
"""

from dataclasses import dataclass, field
from typing import Type
import torch.nn as nn

# Import Bi-Encoder architectures
from app.models.architectures import (
    AdvancedFusionMLP_Base,
    AdvancedFusionMLP_Residual,
    AttentionFusionModel,
    WeightedSumFusion,
)

# Import Cross-Encoder architectures
from app.models.cross_architectures import (
    FusionWithScorerWrapper,
    CrossFusion_MLP,
    CrossFusion_Residual,
    CrossFusion_Weighted,
    CrossFusion_Attention
)


WEIGHTS_FILENAME = "weights.pth"
DEFAULT_MODEL_ID = "cross_weighted"


@dataclass(frozen=True)
class ModelEntry:
    id: str
    display_name: str
    architecture: Type[nn.Module]
    constructor_kwargs: dict = field(default_factory=dict)
    sbert_id: str = ""        # HuggingFace ID cho backbone
    weights_file: str = "weights.pth" # Tên file .pth cụ thể
    is_cross: bool = False    # Flag phân biệt Bi vs Cross
    num_cv: int = 10
    num_jd: int = 5


REGISTRY: dict[str, ModelEntry] = {
    # ========================================================================
    # 1. BI-ENCODER MODELS (EXISTING)
    # ========================================================================
    "attention_gte_base": ModelEntry(
        id="attention_gte_base",
        display_name="[Bi-Encoder] Attention (gte-base)",
        architecture=AttentionFusionModel,
        constructor_kwargs={"num_views": 50, "d_model": 64, "nhead": 8},
        sbert_id="thenlper/gte-base",
    ),
    "mlp_base_gte_base": ModelEntry(
        id="mlp_base_gte_base",
        display_name="[Bi-Encoder] MLP Base (gte-base)",
        architecture=AdvancedFusionMLP_Base,
        constructor_kwargs={"input_dim": 50},
        sbert_id="thenlper/gte-base",
    ),
    "mlp_residual_bge_base": ModelEntry(
        id="mlp_residual_bge_base",
        display_name="[Bi-Encoder] MLP Residual (bge-base-en-v1.5)",
        architecture=AdvancedFusionMLP_Residual,
        constructor_kwargs={"input_dim": 50},
        sbert_id="BAAI/bge-base-en-v1.5",
    ),
    "weighted_sum_careerbert": ModelEntry(
        id="weighted_sum_careerbert",
        display_name="[Bi-Encoder] WeightedSum (careerbert-g)",
        architecture=WeightedSumFusion,
        constructor_kwargs={"input_dim": 50},
        sbert_id="lwolfrum2/careerbert-g",
    ),

    # ========================================================================
    # 2. CROSS-ENCODER MODELS (NEW - KAGGE SYNC)
    # ========================================================================
    "cross_weighted": ModelEntry(
        id="weighted_sum_cross_encoder",
        display_name="[Cross-Encoder] Weighted Sum (mBERT)",
        architecture=FusionWithScorerWrapper,
        constructor_kwargs={
            "hidden_dim": 768,
            "fusion_module": CrossFusion_Weighted(input_dim=100)
        },
        sbert_id="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        weights_file="weighted_sum_mbert_cased.pth",
        is_cross=True
    ),
    "cross_mlp": ModelEntry(
        id="mlp_base_cross_encoder",
        display_name="[Cross-Encoder] MLP Base (mBERT)",
        architecture=FusionWithScorerWrapper,
        constructor_kwargs={
            "hidden_dim": 768,
            "fusion_module": CrossFusion_MLP(input_dim=100)
        },
        sbert_id="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        weights_file="baseline_mlp_xlmr_base.pth",
        is_cross=True
    ),
    "cross_residual": ModelEntry(
        id="mlp_residual_cross_encoder",
        display_name="[Cross-Encoder] Residual MLP (mBERT)",
        architecture=FusionWithScorerWrapper,
        constructor_kwargs={
            "hidden_dim": 768,
            "fusion_module": CrossFusion_Residual(input_dim=100)
        },
        sbert_id="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        weights_file="residual_mlp_mbert_cased.pth",
        is_cross=True
    ),
    "cross_attention": ModelEntry(
        id="attention_cross_encoder",
        display_name="[Cross-Encoder] Attention (mBERT)",
        architecture=FusionWithScorerWrapper,
        constructor_kwargs={
            "hidden_dim": 768,
            "fusion_module": CrossFusion_Attention(num_views=50)
        },
        sbert_id="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        weights_file="attention_xlmr_base.pth",
        is_cross=True
    ),
}


def resolve_id(model_id: str | None) -> str:
    """Return the requested model_id, or the configured default if empty/None.
    Also resolves internal entry.id values back to their registry key (alias support)."""
    from app.core.config import settings

    if model_id is None or model_id == "":
        return settings.default_model_id

    # If it's a known REGISTRY key, return as-is
    if model_id in REGISTRY:
        return model_id

    # Reverse lookup: if it's an entry.id (internal ID), find the matching registry key
    for key, entry in REGISTRY.items():
        if entry.id == model_id:
            return key

    # Fall through to let get_entry raise KeyError with the proper message
    return model_id


def get_entry(model_id: str | None) -> ModelEntry:
    """Resolve and validate a model_id; raises KeyError for unknown ids."""
    resolved = resolve_id(model_id)
    if resolved not in REGISTRY:
        raise KeyError(f"Unknown model_id: {resolved!r}. Available: {sorted(REGISTRY)}")
    return REGISTRY[resolved]


def _weights_available(entry: ModelEntry) -> bool:
    """True if a checkpoint (.pth) exists for this entry on disk."""
    from app.core.config import settings

    ckpt_dir = settings.models_dir / entry.id
    return ckpt_dir.exists() and any(ckpt_dir.glob("*.pth"))


def list_public() -> list[dict]:
    """Public-safe representation for the /models endpoint.

    Exposes the deployed & verified cross-encoder models that have weights on
    disk, so the frontend dropdown never offers a model that would 503. Legacy
    bi-encoder entries are kept in the registry (still selectable via direct
    API call) but hidden from the UI. To surface a bi-encoder, drop the
    `entry.is_cross` condition below.
    """
    return [
        {
            "id": key,
            "display_name": entry.display_name,
            "sbert_id": entry.sbert_id,
            "is_cross": entry.is_cross,
        }
        for key, entry in REGISTRY.items()
        if entry.is_cross and _weights_available(entry)
    ]