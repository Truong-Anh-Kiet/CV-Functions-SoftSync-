import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.core.config import settings

# Import logic Bi-Encoder (Cũ)
from app.models import load_model as load_bi_model
from app.models.inference import predict as bi_predict

# Import logic Cross-Encoder (Mới - Dành cho 4 model mBERT/XLM-R)
from app.models.cross_runtime import load_cross_model
from app.models.cross_inference import cross_predict

from app.services import extract_cache
from app.services.extraction import (
    _extract_pdf_text,
    extract_cv_from_text,
    extract_jd_from_text,
)

logger = logging.getLogger("app.pipeline")


def _extract_one_cv(path: Path, is_text: bool) -> dict:
    # Cache by raw content so an identical CV re-run skips all OpenAI calls.
    if is_text:
        text = path.read_text(encoding="utf-8", errors="replace")
        content = text.encode("utf-8")
        cached = extract_cache.get("cv", content)
        if cached is not None:
            return cached
        result = extract_cv_from_text(text)
    else:
        content = path.read_bytes()
        cached = extract_cache.get("cv", content)
        if cached is not None:
            return cached
        text = _extract_pdf_text(path)
        if not text:
            raise ValueError(f"No text could be extracted from PDF: {path.name}")
        result = extract_cv_from_text(text)
    extract_cache.put("cv", content, result)
    return result


def _extract_jd_pdf(path: Path) -> dict:
    content = path.read_bytes()
    cached = extract_cache.get("jd", content)
    if cached is not None:
        return cached
    text = _extract_pdf_text(path)
    if not text:
        raise ValueError(f"No text could be extracted from PDF: {path.name}")
    result = extract_jd_from_text(text)
    extract_cache.put("jd", content, result)
    return result


def _extract_jd_text(jd_text: str) -> dict:
    content = jd_text.encode("utf-8")
    cached = extract_cache.get("jd", content)
    if cached is not None:
        return cached
    result = extract_jd_from_text(jd_text)
    extract_cache.put("jd", content, result)
    return result


def run_matching(
    cv_pdf_paths: list[Path],
    cv_names: list[str],
    cv_is_text: list[bool],
    jd_pdf_path: Path | None = None,
    jd_name: str | None = None,
    jd_text: str | None = None,
    include_structured: bool = False,
    model_id: str | None = None,
) -> dict:
    if not cv_pdf_paths:
        raise ValueError("At least one CV PDF is required")
    if bool(jd_pdf_path) == bool(jd_text):
        raise ValueError("Provide exactly one of jd_pdf_path or jd_text")

    started_at = time.time()

    # --- BƯỚC 1: PHÂN LUỒNG LOAD MODEL (FLEXIBLE BI VS CROSS) ---
    selected_model_id = model_id or settings.default_model_id
    cross_data = load_cross_model(selected_model_id)
    if cross_data:
        fusion_model, backbone, tokenizer, entry = cross_data
        is_cross_pipeline = True
    else:
        model, sbert, entry = load_bi_model(selected_model_id)
        is_cross_pipeline = False

    # --- BƯỚC 2: TRÍCH XUẤT SONG SONG (CV + JD) ---
    # OpenAI calls are I/O-bound; running them in a thread pool gives ~Nx
    # speedup over the original sequential loop without changing semantics.
    extract_start = time.time()
    max_workers = max(1, int(settings.extraction_concurrency))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        cv_futures = [pool.submit(_extract_one_cv, path, is_text) for path, is_text in zip(cv_pdf_paths, cv_is_text)]
        jd_future = pool.submit(_extract_jd_pdf, jd_pdf_path) if jd_pdf_path else None

        cv_structs = [future.result() for future in cv_futures]
        if jd_future is not None:
            jd_structured = jd_future.result()
            jd_source = jd_name or jd_pdf_path.name
        else:
            jd_structured = _extract_jd_text(jd_text or "")
            jd_source = "text_input"
    extraction_seconds = round(time.time() - extract_start, 2)

    # --- BƯỚC 3: INFERENCE TUẦN TỰ (torch model dùng chung, giữ thread-safety) ---
    inference_start = time.time()
    results = []
    for cv_structured, display_name in zip(cv_structs, cv_names):
        if is_cross_pipeline:
            result = cross_predict(
                cv_structured,
                jd_structured,
                fusion_model,
                backbone,
                tokenizer,
                entry,
            )
        else:
            result = bi_predict(
                cv_structured,
                jd_structured,
                model,
                sbert,
                entry,
            )

        row = {
            "rank": 0,
            "cv_file": display_name,
            **result,
        }

        if include_structured:
            row["cv_structured"] = cv_structured
            row["jd_structured"] = jd_structured

        results.append(row)
    inference_seconds = round(time.time() - inference_start, 2)

    # --- BƯỚC 5: SẮP XẾP VÀ TRẢ KẾT QUẢ ---
    results.sort(key=lambda item: item["score"], reverse=True)
    for index, item in enumerate(results, start=1):
        item["rank"] = index

    elapsed_seconds = round(time.time() - started_at, 2)
    logger.info(
        "matching done: %d CV(s) | extraction=%.2fs inference=%.2fs total=%.2fs | model=%s",
        len(cv_names), extraction_seconds, inference_seconds, elapsed_seconds, entry.id,
    )

    return {
        "jd_file": jd_source,
        "results": results,
        "elapsed_seconds": elapsed_seconds,
        "extraction_seconds": extraction_seconds,
        "inference_seconds": inference_seconds,
        "model_used": entry.id,
    }
