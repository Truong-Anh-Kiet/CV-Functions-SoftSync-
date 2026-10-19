"""
Cross-encoder loader.

Key optimizations vs. the naive per-model load:
  * The transformer backbone (e.g. bert-base-multilingual-cased, ~700MB) is
    loaded ONCE per backbone_id and SHARED across every fusion head that uses
    it. All 4 LamdaTrainable models use mBERT, so only one backbone lives in
    memory and switching heads is instant.
  * Only the tiny fusion head (≤1M params) is per-model.
  * Device is resolved centrally (auto GPU/CPU) via app.models.device.

Checkpoint format handled (LamdaTrainable): {"model": <state_dict>, "task_w": ...}
where <state_dict> has flat keys scorer.* / fusion.*. `task_w` is training-only
and discarded. Legacy formats are also accepted for forward-compat.
"""

import logging
import threading

import torch
from transformers import AutoModel, AutoTokenizer

from app.core.config import settings
from app.models.cross_registry import CROSS_REGISTRY
from app.models.device import get_device

logger = logging.getLogger("app.cross_runtime")

# backbone_id -> (backbone, tokenizer)   — shared across heads
_backbone_cache: dict[str, tuple] = {}
# entry.id -> (fusion_model, backbone, tokenizer, entry)
_head_cache: dict[str, tuple] = {}
_lock = threading.Lock()


def _extract_state_dict(raw):
    """Normalize the various checkpoint layouts to a flat scorer.*/fusion.* dict."""
    if not isinstance(raw, dict):
        return raw
    # LamdaTrainable: {"model": <state_dict>, "task_w": <state_dict>}
    if "model" in raw and isinstance(raw["model"], dict):
        return raw["model"]
    # Already flat?
    if any(k.startswith(("scorer.", "fusion.")) for k in raw):
        return raw
    # Legacy split: {"scorer": {...}, "fusion": {...}}
    if "scorer" in raw or "fusion" in raw:
        flat: dict = {}
        for k, v in (raw.get("scorer") or {}).items():
            flat[f"scorer.{k}"] = v
        for k, v in (raw.get("fusion") or {}).items():
            if k.startswith("scorer."):
                flat[f"scorer.{k[len('scorer.'):]}"] = v
            else:
                flat[f"fusion.{k}"] = v
        return flat
    return raw


def _load_checkpoint(path, device):
    try:
        raw = torch.load(path, map_location=device, weights_only=True)
    except Exception:
        # Fallback for older torch / non-tensor payloads (trusted local files).
        raw = torch.load(path, map_location=device, weights_only=False)
    return _extract_state_dict(raw)


def _get_backbone(backbone_id: str, device):
    """Load (once) and return the shared (backbone, tokenizer) for a backbone_id."""
    cached = _backbone_cache.get(backbone_id)
    if cached is not None:
        return cached
    tokenizer = AutoTokenizer.from_pretrained(backbone_id)
    backbone = AutoModel.from_pretrained(backbone_id).to(device).eval()
    for p in backbone.parameters():
        p.requires_grad = False
    _backbone_cache[backbone_id] = (backbone, tokenizer)
    logger.info("Loaded shared backbone %r on %s", backbone_id, device)
    return backbone, tokenizer


def _has_weights(entry) -> bool:
    ckpt_dir = settings.models_dir / entry.id
    return ckpt_dir.exists() and any(ckpt_dir.glob("*.pth"))


def load_cross_model(model_id: str):
    """Return (fusion_model, backbone, tokenizer, entry) for a cross-encoder id,
    or None if model_id is not a cross-encoder. Raises FileNotFoundError if the
    checkpoint is missing."""
    if model_id not in CROSS_REGISTRY:
        return None

    entry = CROSS_REGISTRY[model_id]
    device = get_device()

    with _lock:
        cached = _head_cache.get(entry.id)
        if cached is not None:
            return cached

        # 1. Fusion head (tiny, per-model).
        ckpt_dir = settings.models_dir / entry.id
        if not ckpt_dir.exists():
            raise FileNotFoundError(f"Model folder not found: {ckpt_dir}")
        pth_files = sorted(ckpt_dir.glob("*.pth"))
        if not pth_files:
            raise FileNotFoundError(f"No .pth file found in {ckpt_dir}")

        model = entry.architecture(**entry.constructor_kwargs).to(device)
        state = _load_checkpoint(pth_files[0], device)
        model.load_state_dict(state, strict=True)
        model.eval()

        # 2. Shared backbone (loaded once per backbone_id).
        backbone, tokenizer = _get_backbone(entry.backbone_id, device)

        _head_cache[entry.id] = (model, backbone, tokenizer, entry)
        logger.info("Cross model ready: %s (%s)", entry.id, entry.backbone_id)
        return _head_cache[entry.id]


def _warm_forward(model, backbone, tokenizer) -> None:
    """Run one tiny forward to trigger kernel/oneDNN init so the FIRST real
    request isn't cold (measured ~8s cold vs ~1.5s warm). Non-fatal."""
    try:
        device = get_device()
        with torch.inference_mode():
            enc = tokenizer(["warm"], ["warm"], return_tensors="pt",
                            padding=True, truncation=True, max_length=8).to(device)
            cls = backbone(**enc).last_hidden_state[:, 0, :]
            hidden = model.scorer.fc[0].in_features
            cls_full = torch.zeros(1, 50, hidden, device=device)
            cls_full[0, 0, :] = cls
            mask = torch.zeros(1, 50, device=device)
            mask[0, 0] = 1.0
            model(cls_full, mask)
    except Exception as exc:
        logger.warning("Warm forward failed (non-fatal): %s", exc)


def warmup() -> list[str]:
    """Preload the shared backbone(s) + every available cross head AND run one
    forward each so the first real request is not slowed by a cold load/kernel
    init. Missing checkpoints are skipped."""
    loaded: list[str] = []
    for key, entry in CROSS_REGISTRY.items():
        if not _has_weights(entry):
            logger.warning("Warm-up: no checkpoint for %s, skipping", entry.id)
            continue
        try:
            data = load_cross_model(key)
            if data:
                _warm_forward(data[0], data[1], data[2])
                loaded.append(entry.id)
        except Exception as exc:  # never let warm-up crash startup
            logger.warning("Warm-up failed for %s: %s", entry.id, exc)
    logger.info("Cross-encoder warm-up complete: %s", loaded or "none")
    return loaded


def clear_cross_cache():
    with _lock:
        _head_cache.clear()
        _backbone_cache.clear()
