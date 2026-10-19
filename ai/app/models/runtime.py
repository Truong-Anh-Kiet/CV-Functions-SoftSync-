"""
Lazy model loader with per-id cache.

Each (architecture, sbert) pair is loaded once on first request and cached for
the lifetime of the process. A lock guards the cache so two concurrent first
requests cannot trigger a double-load of the same weights.
"""

import os
import sys
import threading

import torch
import torch.nn as nn

from app.core.config import settings
from app.models.device import get_device
from app.models.registry import WEIGHTS_FILENAME, ModelEntry, get_entry


os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")


device = get_device()


_CACHE: dict[str, tuple[nn.Module, "SentenceTransformer", ModelEntry]] = {}
_LOCK = threading.Lock()


def _import_sentence_transformer():
    # torchao is an optional dependency that sentence-transformers tries to
    # import; on Windows it often fails to install. Pre-stub it so the import
    # short-circuits cleanly.
    if "torchao" not in sys.modules:
        sys.modules["torchao"] = None
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        raise RuntimeError(f"Failed to import sentence-transformers: {exc}") from exc
    return SentenceTransformer


def _torch_load(path):
    try:
        return torch.load(path, map_location=device, weights_only=False)
    except TypeError:
        return torch.load(path, map_location=device)


def load_model(model_id: str | None = None) -> tuple[nn.Module, "SentenceTransformer", ModelEntry]:
    """Load (or fetch from cache) the model + sbert encoder for a given id.

    Passing None or an empty string resolves to the configured default model.
    Raises KeyError for unknown ids and FileNotFoundError if the weights file
    is missing.
    """
    entry = get_entry(model_id)

    with _LOCK:
        cached = _CACHE.get(entry.id)
        if cached is not None:
            return cached

        ckpt_path = settings.models_dir / entry.id / entry.weights_file
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

        model = entry.architecture(**entry.constructor_kwargs).to(device)
        state = _torch_load(ckpt_path)
        # Some checkpoints might be wrapped in {"model_state": ...}; the new
        # ones are bare state_dict, but accept both for forward-compat.
        if isinstance(state, dict) and "model_state" in state:
            state = state["model_state"]
        model.load_state_dict(state, strict=True)
        model.eval()

        SentenceTransformer = _import_sentence_transformer()
        sbert = SentenceTransformer(entry.sbert_id).to(device)
        for param in sbert.parameters():
            param.requires_grad = False

        _CACHE[entry.id] = (model, sbert, entry)
        return _CACHE[entry.id]


def clear_cache() -> None:
    """Drop all cached models. Useful for tests."""
    with _LOCK:
        _CACHE.clear()
