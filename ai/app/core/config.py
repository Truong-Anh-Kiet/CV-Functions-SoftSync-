from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo path: .../ai  (config.py is at .../ai/app/core/config.py)
_AI_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = Field(default="AIP491 AI Service", validation_alias="APP_NAME_AI")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="OPENAI_BASE_URL",
    )
    openai_model: str = Field(default="gpt-5.5", validation_alias="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=1200, validation_alias="OPENAI_MAX_TOKENS")

    models_dir: Path = Field(
        default_factory=lambda: _AI_ROOT / "checkpoints",
        validation_alias="MODELS_DIR",
    )
    default_model_id: str = Field(default="cross_weighted", validation_alias="DEFAULT_MODEL_ID")

    tmp_dir: Path = Field(
        default_factory=lambda: _AI_ROOT / "tmp",
        validation_alias="TMP_DIR",
    )
    cors_origins: list[str] = ["*"]

    extraction_concurrency: int = Field(default=5, validation_alias="EXTRACTION_CONCURRENCY")

    # --- Inference runtime -------------------------------------------------
    # Device selection for torch inference. "auto" uses CUDA when available,
    # otherwise CPU. Force with "cpu" / "cuda" for portable demos.
    device: str = Field(default="auto", validation_alias="AI_DEVICE")
    # CPU thread count for torch. 0 = auto (capped at ~8; torch's own default
    # over-subscribes many-core CPUs and is ~2.8x slower for this model). Set a
    # positive value to override for your machine's physical core count.
    torch_num_threads: int = Field(default=0, validation_alias="TORCH_NUM_THREADS")
    # Skip running the backbone on empty (masked) CV/JD view pairs. The final
    # score / prediction / masked-heatmap stay bit-identical; only the *raw*
    # heatmap values at missing-section cells change (display-only). ~1.5x on CPU.
    skip_empty_view_pairs: bool = Field(default=True, validation_alias="SKIP_EMPTY_VIEW_PAIRS")
    # Length-bucketed inference: sort the view pairs by token length and run the
    # backbone in chunks of this size, so a single long view doesn't pad every
    # pair to its length. Output-identical; ~3.2x on CPU for real CVs (measured
    # best at 5-6; drops off by 8+). 0 = off (single padded batch).
    inference_pair_chunk: int = Field(default=6, validation_alias="INFERENCE_PAIR_CHUNK")
    # Backbone execution backend: "torch" (default, portable) or "onnx"
    # (Phase 2, CPU-only, FP32; auto-falls back to torch if unavailable).
    inference_backend: str = Field(default="torch", validation_alias="INFERENCE_BACKEND")
    # Warm-up all cross-encoder heads (+ shared backbone) at startup so the
    # first request is not slowed by a cold load.
    warmup_on_startup: bool = Field(default=True, validation_alias="WARMUP_ON_STARTUP")
    # Cache OpenAI extraction results by content hash → re-running the SAME
    # CV/JD skips all OpenAI calls (instant re-runs; great for demo iteration).
    extraction_cache: bool = Field(default=True, validation_alias="EXTRACTION_CACHE")

    @field_validator("models_dir", "tmp_dir")
    @classmethod
    def _resolve_under_ai_root(cls, v: Path) -> Path:
        # Make relative paths (e.g. MODELS_DIR="./checkpoints" in .env) resolve
        # against the repo root instead of the current working directory, so the
        # app finds its checkpoints no matter where uvicorn is launched from.
        return v if v.is_absolute() else (_AI_ROOT / v).resolve()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
