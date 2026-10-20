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

from types import SimpleNamespace

import numpy as np
import onnxruntime as ort

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



class _OnnxBackbone:
    """Adapter để ONNX trả đầu ra tương thích với backbone PyTorch."""

    def __init__(self, model_path, device):
        self.device = torch.device(device)

        if self.device.type != "cpu":
            raise RuntimeError("ONNX backbone hiện chỉ hỗ trợ CPU.")

        options = ort.SessionOptions()
        options.intra_op_num_threads = max(
            1, settings.torch_num_threads or 1
        )
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        self.session = ort.InferenceSession(
            str(model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.input_names = {
            item.name for item in self.session.get_inputs()
        }

    def to(self, device):
        self.device = torch.device(device)
        if self.device.type != "cpu":
            raise RuntimeError("ONNX backbone chỉ hỗ trợ CPU.")
        return self

    def eval(self):
        return self

    def parameters(self):
        # ONNX không có tham số PyTorch để đóng băng.
        return iter(())

    def __call__(self, **inputs):
        feeds = {}

        for name, value in inputs.items():
            if name not in self.input_names:
                continue

            if torch.is_tensor(value):
                value = value.detach().cpu().numpy()

            feeds[name] = np.asarray(value, dtype=np.int64)

        if "input_ids" not in feeds:
            raise ValueError("Thiếu input_ids cho ONNX backbone.")

        if "attention_mask" in self.input_names:
            feeds.setdefault(
                "attention_mask",
                np.ones_like(feeds["input_ids"]),
            )

        if "token_type_ids" in self.input_names:
            feeds.setdefault(
                "token_type_ids",
                np.zeros_like(feeds["input_ids"]),
            )

        missing = self.input_names - feeds.keys()
        if missing:
            raise ValueError(
                f"Thiếu đầu vào ONNX: {sorted(missing)}"
            )

        outputs = self.session.run(None, feeds)
        hidden_state = torch.from_numpy(outputs[0]).to(self.device)

        return SimpleNamespace(last_hidden_state=hidden_state)



def _get_backbone(backbone_id: str, device):
    """Load once and return the shared backbone and tokenizer."""
    cached = _backbone_cache.get(backbone_id)
    if cached is not None:
        return cached

    if settings.inference_backend.strip().lower() == "onnx":
        if device.type != "cpu":
            raise RuntimeError("INFERENCE_BACKEND=onnx yêu cầu CPU.")

        model_path = (
            settings.models_dir
            / "mbert_onnx_int8"
            / "model_int8.onnx"
        )
        tokenizer_path = settings.models_dir / "mbert_tokenizer"

        if not model_path.is_file():
            raise FileNotFoundError(
                f"Không tìm thấy ONNX model: {model_path}"
            )

        if not tokenizer_path.is_dir():
            raise FileNotFoundError(
                f"Không tìm thấy tokenizer: {tokenizer_path}"
            )

        tokenizer = AutoTokenizer.from_pretrained(
            str(tokenizer_path),
            local_files_only=True,
        )
        backbone = _OnnxBackbone(model_path, device)

        logger.info("Loaded ONNX INT8 backbone on CPU")
    else:
        tokenizer = AutoTokenizer.from_pretrained(backbone_id)

        if device.type == "cpu":
            backbone = AutoModel.from_pretrained(
                backbone_id,
                torch_dtype=torch.float16,
                low_cpu_mem_usage=True,
            )
        else:
            backbone = AutoModel.from_pretrained(backbone_id)

        backbone = backbone.to(device).eval()

        for parameter in backbone.parameters():
            parameter.requires_grad = False

        logger.info(
            "Loaded shared PyTorch backbone %r on %s",
            backbone_id,
            device,
        )

    backbone = backbone.to(device).eval()
    _backbone_cache[backbone_id] = (backbone, tokenizer)

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
