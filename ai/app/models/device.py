"""
Single source of truth for the torch device + CPU runtime configuration.

`settings.device` controls selection:
  - "auto" (default): CUDA when available, otherwise CPU
  - "cpu" / "cuda": force a device (cuda falls back to CPU with a warning if
    no GPU / CUDA-enabled torch build is present)

This lets the same source code run unchanged on GPU and CPU demo machines.
Note: a `torch+cpu` build cannot use CUDA even on a GPU machine — install a
CUDA build of torch there.
"""

import logging
import os

import torch

from app.core.config import settings

logger = logging.getLogger("app.device")

_DEVICE: torch.device | None = None
_CONFIGURED = False


def get_device() -> torch.device:
    """Resolve (and cache) the torch device from settings.device."""
    global _DEVICE
    if _DEVICE is not None:
        return _DEVICE

    pref = (settings.device or "auto").strip().lower()
    if pref == "cpu":
        _DEVICE = torch.device("cpu")
    elif pref in ("cuda", "gpu"):
        if torch.cuda.is_available():
            _DEVICE = torch.device("cuda")
        else:
            logger.warning(
                "AI_DEVICE=%s requested but CUDA is unavailable "
                "(no GPU or torch is a +cpu build) — falling back to CPU.",
                pref,
            )
            _DEVICE = torch.device("cpu")
    else:  # auto / anything else
        _DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    return _DEVICE


def configure_torch_runtime() -> torch.device:
    """Configure torch for inference and return the active device.

    Idempotent: safe to call multiple times (only logs / sets threads once).
    """
    global _CONFIGURED
    dev = get_device()

    if not _CONFIGURED:
        if dev.type == "cpu":
            n = int(settings.torch_num_threads or 0)
            if n <= 0:
                # torch's default over-subscribes many-core CPUs and tanks BERT
                # latency (measured ~2.8x slower at 16 vs 8 threads on a 22-core box).
                # Cap to a sane default; override explicitly via TORCH_NUM_THREADS.
                n = min(os.cpu_count() or 8, 8)
            torch.set_num_threads(n)
            # Keep libraries (tokenizers, OMP) consistent with torch's threads.
            os.environ.setdefault("OMP_NUM_THREADS", str(n))

        gpu_name = torch.cuda.get_device_name(0) if dev.type == "cuda" else None
        logger.info(
            "Torch runtime ready: device=%s%s, cpu_threads=%d, backend=%s",
            dev.type,
            f" ({gpu_name})" if gpu_name else "",
            torch.get_num_threads(),
            settings.inference_backend,
        )
        _CONFIGURED = True

    return dev
