import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.models import list_public
from app.models.registry import REGISTRY
from app.schemas.matching import MatchingResponse
from app.services.pipeline import run_matching
from app.services.vector_store import get_vector_store

router = APIRouter()

PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
TEXT_CONTENT_TYPES = {"text/plain"}


def _safe_filename(filename: str | None) -> str:
    name = Path(filename or "upload.pdf").name
    return name or "upload.pdf"


def _validate_file(file: UploadFile, field_name: str) -> None:
    filename = _safe_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".txt"}:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a PDF or TXT file")


async def _save_file(file: UploadFile, target_dir: Path, field_name: str) -> tuple[Path, str]:
    _validate_file(file, field_name)
    original_name = _safe_filename(file.filename)
    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    target_path = target_dir / stored_name

    with target_path.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)
    await file.seek(0)
    return target_path, original_name


@router.get("/models")
def list_models() -> dict:
    return {
        "status": "success",
        "data": {
            "default": settings.default_model_id,
            "models": list_public(),
        },
    }


@router.post("/predict", response_model=MatchingResponse)
async def predict_matching(
    cv_files: Annotated[list[UploadFile], File(...)],
    jd_file: Annotated[UploadFile | None, File()] = None,
    jd_text: Annotated[str | None, Form()] = None,
    include_structured: Annotated[bool, Form()] = False,
    model_id: Annotated[str | None, Form()] = None,
) -> MatchingResponse:
    if not cv_files:
        raise HTTPException(status_code=400, detail="At least one CV file is required")

    clean_jd_text = jd_text.strip() if jd_text else None
    if bool(jd_file) == bool(clean_jd_text):
        raise HTTPException(status_code=400, detail="Provide exactly one of jd_file or jd_text")

    clean_model_id = model_id.strip() if model_id else None
    if clean_model_id and clean_model_id not in REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model_id: {clean_model_id!r}. Available: {sorted(REGISTRY)}",
        )

    request_dir = settings.tmp_dir / uuid.uuid4().hex
    request_dir.mkdir(parents=True, exist_ok=True)

    try:
        cv_paths: list[Path] = []
        cv_names: list[str] = []
        for file in cv_files:
            path, name = await _save_file(file, request_dir, "cv_files")
            cv_paths.append(path)
            cv_names.append(name)

        jd_path = None
        jd_name = None
        if jd_file:
            jd_path, jd_name = await _save_file(jd_file, request_dir, "jd_file")

        cv_is_text = [p.suffix.lower() == ".txt" for p in cv_paths]

        data = await run_in_threadpool(
            run_matching,
            cv_paths,
            cv_names,
            cv_is_text,
            jd_path,
            jd_name,
            clean_jd_text,
            include_structured,
            clean_model_id,
        )
        return MatchingResponse(status="success", data=data)
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        shutil.rmtree(request_dir, ignore_errors=True)


@router.post("/search-cvs")
async def search_cvs(
    jd_text: Annotated[str | None, Form()] = None,
    jd_file: Annotated[UploadFile | None, File()] = None,
    top_k: Annotated[int, Form()] = 10,
    min_score: Annotated[float, Form()] = 0.0,
    auto_index_missing: Annotated[bool, Form()] = True,
    rerank: Annotated[bool, Form()] = False,
    rerank_top_n: Annotated[int, Form()] = 5,
    model_id: Annotated[str | None, Form()] = None,
) -> dict:
    """Search CVs using semantic similarity with optional AI rerank."""
    from app.services.extraction import extract_jd_from_text
    from app.models import load_model as load_bi_model
    from app.models.cross_runtime import load_cross_model
    from app.models.inference import predict as bi_predict
    from app.models.cross_inference import cross_predict

    clean_jd_text = jd_text.strip() if jd_text else None
    clean_model_id = model_id.strip() if model_id else None

    # Validate input - auto-detect mode based on input
    has_jd_text = bool(clean_jd_text)
    has_jd_file = jd_file is not None
    mode = "text" if has_jd_text else ("file" if has_jd_file else None)

    if not mode:
        raise HTTPException(status_code=400, detail="jd_text or jd_file is required")

    request_dir = settings.tmp_dir / uuid.uuid4().hex
    request_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Extract JD
        if mode == "file":
            jd_path, jd_name = await _save_file(jd_file, request_dir, "jd_file")
            from app.services.extraction import upload_pdf as upload_jd_pdf, extract_jd_from_pdf
            jd_file_id = upload_jd_pdf(str(jd_path))
            jd_structured = extract_jd_from_pdf(jd_file_id)
            jd_source = jd_name
        else:  # mode == "text"
            jd_structured = extract_jd_from_text(clean_jd_text or "")
            jd_source = "text_input"

        # Get model entry for SBERT ID
        try:
            if clean_model_id:
                entry = REGISTRY[clean_model_id]
            else:
                entry = REGISTRY[settings.default_model_id]
            sbert_id = entry.sbert_id
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown model_id: {clean_model_id}")

        # Search vector store
        vector_store = get_vector_store()
        query_text = clean_jd_text or ""
        search_results = vector_store.search(
            query_text=query_text,
            sbert_id=sbert_id,
            top_k=top_k,
            min_score=min_score,
        )

        total_cvs = vector_store.count()
        returned = len(search_results)

        # If no results, return empty response
        if not search_results:
            return {
                "status": "success",
                "data": {
                    "total_cvs": total_cvs,
                    "returned": 0,
                    "results": [],
                    "jd_source": jd_source,
                    "model_used": sbert_id,
                    "rerank": None,
                }
            }

        # Run inference on search results
        results = []
        if rerank:
            # Load cross model for rerank
            cross_data = load_cross_model(clean_model_id)
            if cross_data:
                fusion_model, backbone, tokenizer, cross_entry = cross_data
                is_cross = True
            else:
                model, sbert, bi_entry = load_bi_model(clean_model_id)
                is_cross = False

        # Process results
        for idx, result in enumerate(search_results):
            cv_filename = result["filename"]
            cv_text = result["text"]

            # Extract CV from text
            from app.services.extraction import extract_cv_from_text
            cv_structured = extract_cv_from_text(cv_text)

            # Run inference
            if rerank:
                if is_cross:
                    cv_result = cross_predict(
                        cv_structured, jd_structured,
                        fusion_model, backbone, tokenizer, cross_entry
                    )
                else:
                    cv_result = bi_predict(
                        cv_structured, jd_structured,
                        model, sbert, bi_entry
                    )
            else:
                # Without rerank, just use similarity score
                cv_result = {
                    "score": round(result["score"] * 10, 2),
                    "confidence": round(result["score"], 4),
                    "match": result["score"] >= 0.5,
                    "label": "MATCHED" if result["score"] >= 0.5 else "MISMATCH",
                }

            results.append({
                "rank": idx + 1,
                "cv_file": cv_filename,
                "similarity_score": round(result["score"], 4),
                **cv_result,
            })

        # Apply rerank if enabled
        rerank_data = None
        if rerank and results:
            # Sort by AI score and take top rerank_top_n
            sorted_by_score = sorted(results, key=lambda x: x["score"], reverse=True)
            top_reranked = sorted_by_score[:rerank_top_n]

            # Re-rank with new indices
            for rank, item in enumerate(top_reranked, start=1):
                item["rank"] = rank

            rerank_data = {
                "results": top_reranked,
                "model_used": cross_entry.id if rerank and is_cross else sbert_id,
            }

            # If rerank, replace results with top reranked ones
            results = top_reranked

        return {
            "status": "success",
            "data": {
                "total_cvs": total_cvs,
                "returned": len(results),
                "results": results,
                "jd_source": jd_source,
                "model_used": sbert_id,
                "rerank": rerank_data,
            }
        }

    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        shutil.rmtree(request_dir, ignore_errors=True)


@router.post("/search-cvs/reindex-all")
async def reindex_all_cvs(
    model_id: Annotated[str | None, Form()] = None,
    force: Annotated[bool, Form()] = False,
) -> dict:
    """Reindex all CVs in the database with fresh embeddings."""
    from app.services.extraction import extract_cv_from_text
    from app.models import load_model as load_bi_model
    import json

    clean_model_id = model_id.strip() if model_id else None

    # Get model entry for SBERT ID
    try:
        if clean_model_id:
            entry = REGISTRY[clean_model_id]
        else:
            entry = REGISTRY[settings.default_model_id]
        sbert_id = entry.sbert_id
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Unknown model_id: {clean_model_id}")

    # Load CV database (expects JSON file with CVs)
    cv_db_path = settings.tmp_dir / "cv_database.json"
    if not cv_db_path.exists():
        raise HTTPException(status_code=404, detail="CV database not found. Please upload CVs first.")

    with open(cv_db_path, "r", encoding="utf-8") as f:
        cv_db = json.load(f)

    cvs = cv_db.get("cvs", [])
    if not cvs:
        raise HTTPException(status_code=404, detail="No CVs found in database")

    # Reindex
    vector_store = get_vector_store()
    result = vector_store.reindex_all(cvs, sbert_id)

    return {
        "status": "success",
        "data": {
            "total_cvs": result["total_cvs"],
            "successful": result["successful"],
            "failed": result["failed"],
            "model_used": sbert_id,
        }
    }


@router.post("/search-cvs/upload-cv")
async def upload_cv_for_indexing(
    cv_file: Annotated[UploadFile, File()],
    metadata: Annotated[str | None, Form()] = None,
) -> dict:
    """Upload a CV file for indexing."""
    import json
    from app.services.extraction import extract_cv_from_text
    from pydantic import BaseModel, Field

    class CVMetadata(BaseModel):
        filename: str
        text: str
        metadata: dict = Field(default_factory=dict)

    # Save and extract CV
    request_dir = settings.tmp_dir / uuid.uuid4().hex
    request_dir.mkdir(parents=True, exist_ok=True)

    try:
        cv_path, original_name = await _save_file(cv_file, request_dir, "cv_file")

        # Read CV text (for PDF, this would need extraction)
        suffix = cv_path.suffix.lower()
        if suffix == ".txt":
            cv_text = cv_path.read_text(encoding="utf-8", errors="replace")
        else:
            # For PDF, extract text
            from app.services.extraction import upload_pdf, extract_cv
            file_id = upload_pdf(str(cv_path))
            cv_struct = extract_cv(file_id)
            cv_text = " ".join([str(v) for v in cv_struct.values() if v and v != "missing_section"])

        # Parse metadata if provided
        meta = {}
        if metadata:
            try:
                meta = json.loads(metadata)
            except json.JSONDecodeError:
                pass
        meta["original_filename"] = original_name

        # Save to CV database
        cv_db_path = settings.tmp_dir / "cv_database.json"
        if cv_db_path.exists():
            with open(cv_db_path, "r", encoding="utf-8") as f:
                cv_db = json.load(f)
        else:
            cv_db = {"cvs": []}

        cv_entry = {
            "filename": original_name,
            "text": cv_text,
            "metadata": meta,
        }
        cv_db["cvs"].append(cv_entry)

        with open(cv_db_path, "w", encoding="utf-8") as f:
            json.dump(cv_db, f, ensure_ascii=False, indent=2)

        return {
            "status": "success",
            "data": {
                "filename": original_name,
                "text_length": len(cv_text),
                "total_cvs": len(cv_db["cvs"]),
            }
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        shutil.rmtree(request_dir, ignore_errors=True)


@router.get("/cv/{document_id}")
async def get_cv_document(
    document_id: int,
) -> dict:
    """Get a saved CV document by ID from the vector store."""
    from app.services.vector_store import get_vector_store

    vector_store = get_vector_store()
    doc = vector_store.get(str(document_id))

    if not doc:
        raise HTTPException(status_code=404, detail=f"CV document {document_id} not found")

    return {
        "status": "success",
        "data": {
            "id": document_id,
            "filename": doc.get("filename", ""),
            "text": doc.get("text", ""),
            "metadata": doc.get("metadata", {}),
        }
    }


@router.post("/cv-detail/heatmap")
async def get_cv_heatmap(
    cv_document_id: Annotated[int | None, Form()] = None,
    cv_file: Annotated[UploadFile | None, File()] = None,
    cv_text: Annotated[str | None, Form()] = None,
    cv_filename: Annotated[str | None, Form()] = None,
    jd_text: Annotated[str | None, Form()] = None,
    model_id: Annotated[str | None, Form()] = None,
) -> MatchingResponse:
    """Get heatmap data for a single CV vs JD combination."""
    from app.services.extraction import (
        extract_cv,
        extract_cv_from_text,
        extract_jd_from_text,
        upload_pdf,
    )
    from app.services.vector_store import get_vector_store
    from app.models import load_model as load_bi_model
    from app.models.inference import predict as bi_predict
    from app.models.cross_runtime import load_cross_model
    from app.models.cross_inference import cross_predict

    # Validate input
    if not cv_document_id and not cv_file and not cv_text:
        raise HTTPException(status_code=400, detail="Provide cv_document_id, cv_file, or cv_text")

    if not jd_text:
        raise HTTPException(status_code=400, detail="jd_text is required")

    request_dir = settings.tmp_dir / uuid.uuid4().hex
    request_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Extract CV
        if cv_text:
            cv_structured = extract_cv_from_text(cv_text)
            cv_display_name = cv_filename or "cv_text"
        elif cv_file:
            cv_path, cv_name = await _save_file(cv_file, request_dir, "cv_file")
            cv_structured = extract_cv(str(cv_path))
            cv_display_name = cv_name
        elif cv_document_id:
            # Look up CV from vector store
            vector_store = get_vector_store()
            doc = vector_store.get(str(cv_document_id))
            if not doc:
                raise HTTPException(status_code=404, detail=f"CV document {cv_document_id} not found in vector store")
            cv_text = doc.get("text", "")
            cv_structured = extract_cv_from_text(cv_text)
            cv_display_name = doc.get("filename", f"cv_{cv_document_id}")
        else:
            raise HTTPException(status_code=400, detail="No CV input provided")

        # Extract JD
        jd_structured = extract_jd_from_text(jd_text)

        # Load model
        cross_data = load_cross_model(model_id)
        if cross_data:
            fusion_model, backbone, tokenizer, entry = cross_data
            result = cross_predict(
                cv_structured,
                jd_structured,
                fusion_model,
                backbone,
                tokenizer,
                entry,
            )
        else:
            model, sbert, entry = load_bi_model(model_id)
            result = bi_predict(
                cv_structured,
                jd_structured,
                model,
                sbert,
                entry,
            )

        return MatchingResponse(
            status="success",
            data={
                "jd_file": "text_input",
                "results": [{
                    "rank": 1,
                    "cv_file": cv_display_name,
                    **result,
                }],
                "elapsed_seconds": 0.0,
                "model_used": entry.id,
            }
        )
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        shutil.rmtree(request_dir, ignore_errors=True)
