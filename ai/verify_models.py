"""Verify each registered model loads its weights with strict=True.

Run from the ai/ directory:
    python verify_models.py
"""

import sys
import traceback

import torch

from app.core.config import settings
from app.models.architectures import (
    AdvancedFusionMLP_Base,
    AdvancedFusionMLP_Residual,
    AttentionFusionModel,
    WeightedSumFusion,
)
from app.models.registry import REGISTRY, WEIGHTS_FILENAME


def main() -> int:
    print(f"models_dir: {settings.models_dir.resolve()}")
    print(f"default_model_id: {settings.default_model_id}\n")

    failures = 0
    for model_id, entry in REGISTRY.items():
        weight_path = settings.models_dir / model_id / WEIGHTS_FILENAME
        print(f"[{model_id}] -> {weight_path}")
        if not weight_path.exists():
            print(f"  MISSING weights.pth")
            failures += 1
            continue

        try:
            try:
                state = torch.load(weight_path, map_location="cpu", weights_only=False)
            except TypeError:
                state = torch.load(weight_path, map_location="cpu")
            if isinstance(state, dict) and "model_state" in state:
                state = state["model_state"]

            model = entry.architecture(**entry.constructor_kwargs)
            missing, unexpected = model.load_state_dict(state, strict=False)

            if missing or unexpected:
                print(f"  MISMATCH")
                if missing:
                    print(f"    missing keys: {missing}")
                if unexpected:
                    print(f"    unexpected keys: {unexpected}")
                failures += 1
            else:
                # Now retry strict to confirm
                model = entry.architecture(**entry.constructor_kwargs)
                model.load_state_dict(state, strict=True)
                model.eval()
                with torch.no_grad():
                    dummy = torch.randn(2, 50)
                    out = model(dummy)
                print(f"  OK  arch={entry.architecture.__name__}  output_shape={tuple(out.shape)}  sample_range=[{out.min().item():.4f}, {out.max().item():.4f}]")
        except Exception as exc:
            print(f"  ERROR {type(exc).__name__}: {exc}")
            traceback.print_exc()
            failures += 1

    print()
    if failures:
        print(f"FAILURE: {failures} / {len(REGISTRY)} models had problems.")
        return 1
    print(f"SUCCESS: all {len(REGISTRY)} models load cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
