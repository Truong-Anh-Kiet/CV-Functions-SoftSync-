import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings

# Ensure app.* logs (device selection, warm-up) are visible even under uvicorn.
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s: [%(name)s] %(message)s"))
    _app_logger.addHandler(_handler)
_app_logger.setLevel(logging.INFO)
_app_logger.propagate = False

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure torch (auto GPU/CPU + CPU threads), then optionally warm up the
    # shared backbone + all cross heads so the first request has no cold load.
    from app.models.device import configure_torch_runtime

    device = configure_torch_runtime()
    logger.info("AI service starting: device=%s, backend=%s, default_model=%s",
                device.type, settings.inference_backend, settings.default_model_id)

    if settings.warmup_on_startup:
        try:
            import anyio

            from app.models.cross_runtime import warmup

            loaded = await anyio.to_thread.run_sync(warmup)
            logger.info("Warm-up preloaded: %s", loaded or "none (no checkpoints found)")
        except Exception as exc:  # never block startup on warm-up
            logger.warning("Warm-up failed; models will lazy-load on first request: %s", exc)

    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
