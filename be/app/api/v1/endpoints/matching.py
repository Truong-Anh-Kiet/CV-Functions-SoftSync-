from pathlib import Path
import re
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.document import Document
from app.services.ai_client import call_matching_ai_service
from app.services.cv_vector_search import (
    cosine_similarity,
    create_text_embedding,
    document_search_payload,
    extract_pdf_text,
    sanitize_extracted_text,
    ensure_document_file,
    extract_pdf_text,
    get_document_embedding,
    index_cv_document,
    parse_embedding,
)
from app.services.jd_cv_search import get_jd_analysis, search_ranked_cvs_from_jd
from app.services.document_storage import (
    StoredUpload,
    ensure_upload_dir,
    local_path_for,
    persist_document_from_local,
    preview_url_for,
    safe_filename,
    save_upload_file,
    validate_pdf_file,
)
from app.services.xai_highlight import create_highlighted_pdf

router = APIRouter()


def _document_payload(document) -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "category": document.category,
        "cloudinary_url": document.cloudinary_url,
    }


def _validate_matching_file(file: UploadFile, field_name: str) -> None:
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    validate_pdf_file(filename)


def _rerank_result_key(value: str | None) -> str:
    normalized = re.sub(r"(\.(pdf|txt))+$", "", value or "", flags=re.IGNORECASE)
    normalized = re.sub(r"[^0-9a-zA-Z]+", " ", normalized)
    return normalized.strip().lower()


def _align_search_rerank_results(rerank_payload: dict, cv_uploads: list[StoredUpload]) -> None:
    uploads_by_name = {_rerank_result_key(upload.filename): upload for upload in cv_uploads}
    for result in rerank_payload.get("results") or []:
        cv_file = result.get("cv_file")
        result["source_cv_file"] = cv_file
        matched_upload = uploads_by_name.get(_rerank_result_key(cv_file))
        if not matched_upload:
            continue
        result["cv_file"] = matched_upload.filename
        if matched_upload.profile_id is not None:
            result["document_id"] = matched_upload.profile_id


async def _call_ai_service(
    cv_uploads: list[StoredUpload],
    jd_upload: StoredUpload | None,
    jd_text: str | None,
    model_id: str | None = None,
) -> dict:
    return await call_matching_ai_service(cv_uploads, jd_upload, jd_text, model_id)


@router.get("/models")
async def list_models() -> dict:
    url = f"{settings.ai_service_url.rstrip('/')}/api/v1/matching/models"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"AI service unreachable: {exc}") from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"AI service error: {response.text}")
    return response.json()


@router.post("/jd-analysis")
async def analyze_jd(
    jd_file: Annotated[UploadFile | None, File()] = None,
    jd_text: Annotated[str | None, Form()] = None,
) -> dict:
    clean_jd_text = jd_text.strip() if jd_text else None
    if bool(jd_file) == bool(clean_jd_text):
        raise HTTPException(status_code=400, detail="Provide exactly one of jd_file or jd_text")

    if jd_file:
        _validate_matching_file(jd_file, "jd_file")
        stored_jd = save_upload_file(jd_file)
        clean_jd_text = extract_pdf_text(stored_jd.path)

    if not clean_jd_text:
        raise HTTPException(status_code=400, detail="JD content is empty")

    analysis = await get_jd_analysis(clean_jd_text)
    return {
        "status": "success",
        "data": analysis.model_dump(),
    }


@router.post("/search-cvs/from-jd")
async def search_cvs_from_jd_rules(
    jd_file: Annotated[UploadFile | None, File()] = None,
    jd_text: Annotated[str | None, Form()] = None,
    top_k: Annotated[int, Form()] = 20,
    min_score: Annotated[float, Form()] = 0.0,
    auto_index_missing: Annotated[bool, Form()] = True,
    rerank: Annotated[bool, Form()] = False,
    rerank_top_n: Annotated[int, Form()] = 10,
    model_id: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
) -> dict:
    clean_jd_text = jd_text.strip() if jd_text else None
    if bool(jd_file) == bool(clean_jd_text):
        raise HTTPException(status_code=400, detail="Provide exactly one of jd_file or jd_text")
    if top_k < 1 or top_k > 500:
        raise HTTPException(status_code=400, detail="top_k must be between 1 and 500")
    if rerank_top_n < 1 or rerank_top_n > top_k:
        raise HTTPException(status_code=400, detail="rerank_top_n must be between 1 and top_k")
    if min_score < 0 or min_score > 1:
        raise HTTPException(status_code=400, detail="min_score must be between 0 and 1")

    clean_model_id = model_id.strip() if model_id else None
    stored_jd = None
    if jd_file:
        _validate_matching_file(jd_file, "jd_file")
        stored_jd = save_upload_file(jd_file)
        clean_jd_text = extract_pdf_text(stored_jd.path)

    if not clean_jd_text:
        raise HTTPException(status_code=400, detail="JD content is empty")

    payload = await search_ranked_cvs_from_jd(
        db=db,
        jd_text=clean_jd_text,
        top_k=top_k,
        min_score=min_score,
        auto_index_missing=auto_index_missing,
        model_id=clean_model_id,
    )

    rerank_payload = None
    if rerank and payload.get("results"):
        candidate_ids = [item["candidate_id"] for item in payload["results"][:rerank_top_n]]
        documents = (
            db.query(Document)
            .filter(Document.id.in_([int(candidate_id) for candidate_id in candidate_ids]), Document.category == "CV")
            .all()
        )
        by_id = {str(document.id): document for document in documents}
        cv_uploads: list[StoredUpload] = []
        rerank_skipped: list[dict] = []

        for item in payload["results"][:rerank_top_n]:
            document = by_id.get(str(item["candidate_id"]))
            if not document:
                continue
            try:
                cv_path = await ensure_document_file(document)
            except Exception as exc:
                rerank_skipped.append({"filename": item.get("filename"), "reason": str(exc)})
                continue
            cv_uploads.append(
                StoredUpload(
                    filename=item.get("filename") or document.filename,
                    path=cv_path,
                    preview_url=preview_url_for(document.filename),
                    raw_text=document.raw_text,
                    profile_id=document.id,
                )
            )

        if cv_uploads:
            rerank_jd_text = None if stored_jd else clean_jd_text
            ai_response = await _call_ai_service(cv_uploads, stored_jd, rerank_jd_text, clean_model_id)
            rerank_payload = ai_response.get("data", ai_response)
            if isinstance(rerank_payload, dict):
                _align_search_rerank_results(rerank_payload, cv_uploads)
                if rerank_skipped:
                    rerank_payload["skipped"] = rerank_payload.get("skipped", []) + rerank_skipped
        elif rerank_skipped:
            rerank_payload = {"error": f"KhÃ´ng cÃ³ CV nÃ o Ä‘á»ƒ rerank: {rerank_skipped}"}

    payload["rerank"] = rerank_payload
    return {
        "status": "success",
        "data": payload,
    }


@router.post("/search-cvs")
async def search_cvs_by_jd(
    jd_file: Annotated[UploadFile | None, File()] = None,
    jd_text: Annotated[str | None, Form()] = None,
    top_k: Annotated[int, Form()] = 20,
    min_score: Annotated[float, Form()] = 0.0,
    auto_index_missing: Annotated[bool, Form()] = True,
    rerank: Annotated[bool, Form()] = False,
    rerank_top_n: Annotated[int, Form()] = 10,
    model_id: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
) -> dict:
    clean_jd_text = jd_text.strip() if jd_text else None
    if bool(jd_file) == bool(clean_jd_text):
        raise HTTPException(status_code=400, detail="Provide exactly one of jd_file or jd_text")
    if top_k < 1 or top_k > 500:
        raise HTTPException(status_code=400, detail="top_k must be between 1 and 500")
    if rerank_top_n < 1 or rerank_top_n > top_k:
        raise HTTPException(status_code=400, detail="rerank_top_n must be between 1 and top_k")
    if min_score < 0 or min_score > 1:
        raise HTTPException(status_code=400, detail="min_score must be between 0 and 1")

    clean_model_id = model_id.strip() if model_id else None
    stored_jd = None
    if jd_file:
        _validate_matching_file(jd_file, "jd_file")
        stored_jd = save_upload_file(jd_file)
        clean_jd_text = extract_pdf_text(stored_jd.path)

    if not clean_jd_text:
        raise HTTPException(status_code=400, detail="JD content is empty")

    jd_embedding_data = await create_text_embedding(clean_jd_text, clean_model_id)
    resolved_model_id = jd_embedding_data["model_id"]
    jd_vector = [float(value) for value in jd_embedding_data["embedding"]]

    documents = (
        db.query(Document)
        .filter(Document.category == "CV")
        .order_by(Document.created_at.desc(), Document.id.desc())
        .all()
    )

    results: list[dict] = []
    skipped: list[dict] = []
    indexed_missing = 0
    documents_by_id = {document.id: document for document in documents}

    for document in documents:
        embedding = get_document_embedding(db, document.id, resolved_model_id)
        if not embedding and auto_index_missing:
            try:
                await index_cv_document(db, document, resolved_model_id)
                indexed_missing += 1
                embedding = get_document_embedding(db, document.id, resolved_model_id)
            except Exception as exc:
                skipped.append(
                    {
                        "id": document.id,
                        "filename": document.filename,
                        "reason": str(exc),
                    }
                )
                continue

        if not embedding:
            skipped.append(
                {
                    "id": document.id,
                    "filename": document.filename,
                    "reason": f"not indexed for model {resolved_model_id}",
                }
            )
            continue

        try:
            cv_vector = parse_embedding(embedding)
        except ValueError as exc:
            skipped.append(
                {
                    "id": document.id,
                    "filename": document.filename,
                    "reason": str(exc),
                }
            )
            continue

        score = cosine_similarity(jd_vector, cv_vector)
        if score < min_score:
            continue

        results.append(document_search_payload(document, embedding, score))

    results.sort(key=lambda item: item["search_score"], reverse=True)
    shortlisted = results[:top_k]

    rerank_payload = None
    if rerank and shortlisted:
        rerank_candidates = shortlisted[:rerank_top_n]
        cv_uploads = []
        rerank_skipped = []
        for item in rerank_candidates:
            document = documents_by_id.get(item["id"])
            if not document:
                continue
            try:
                cv_path = await ensure_document_file(document)
            except Exception as exc:
                rerank_skipped.append({"filename": item["filename"], "reason": str(exc)})
                continue
            cv_uploads.append(
                StoredUpload(
                    filename=item["filename"],
                    path=cv_path,
                    preview_url=preview_url_for(item["filename"]),
                    raw_text=document.raw_text,
                    profile_id=document.id,
                )
            )

        if not cv_uploads:
            rerank_payload = {"error": f"Không có CV nào để rerank: {rerank_skipped}"}
        else:
            rerank_jd_text = None if stored_jd else clean_jd_text
            ai_response = await _call_ai_service(cv_uploads, stored_jd, rerank_jd_text, resolved_model_id)
            rerank_payload = ai_response.get("data", ai_response)
            if isinstance(rerank_payload, dict):
                _align_search_rerank_results(rerank_payload, cv_uploads)
            if rerank_skipped:
                if isinstance(rerank_payload, dict) and "skipped" not in rerank_payload:
                    rerank_payload["skipped"] = []
                elif isinstance(rerank_payload, dict):
                    rerank_payload["skipped"] = rerank_payload.get("skipped", []) + rerank_skipped

    return {
        "status": "success",
        "data": {
            "total_cvs": len(documents),
            "search_mode": "embedding",
            "embedding_model_id": resolved_model_id,
            "sbert_id": jd_embedding_data.get("sbert_id"),
            "embedding_dimension": jd_embedding_data.get("dimension", len(jd_vector)),
            "indexed_cvs": len(documents) - len(skipped),
            "indexed_missing": indexed_missing,
            "skipped_cvs": skipped,
            "returned": len(shortlisted),
            "top_k": top_k,
            "min_score": min_score,
            "auto_index_missing": auto_index_missing,
            "results": shortlisted,
            "rerank": rerank_payload,
        },
    }


@router.post("/search-cvs/reindex-all")
async def reindex_all_cvs(
    model_id: Annotated[str | None, Form()] = None,
    force: Annotated[bool, Form()] = False,
    db: Session = Depends(get_db),
) -> dict:
    clean_model_id = model_id.strip() if model_id else None
    documents = (
        db.query(Document)
        .filter(Document.category == "CV")
        .order_by(Document.created_at.desc(), Document.id.desc())
        .all()
    )

    indexed: list[dict] = []
    failed: list[dict] = []
    for document in documents:
        try:
            indexed.append(await index_cv_document(db, document, clean_model_id, force=force))
        except Exception as exc:
            failed.append(
                {
                    "id": document.id,
                    "filename": document.filename,
                    "reason": str(exc),
                }
            )

    return {
        "status": "success",
        "data": {
            "total_cvs": len(documents),
            "successful": len(indexed),
            "failed": len(failed),
            "indexed": indexed,
            "failures": failed,
        },
    }


@router.post("/search-cvs/{document_id}/index")
async def reindex_one_cv(
    document_id: int,
    model_id: Annotated[str | None, Form()] = None,
    force: Annotated[bool, Form()] = False,
    db: Session = Depends(get_db),
) -> dict:
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.category == "CV")
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="CV not found")

    clean_model_id = model_id.strip() if model_id else None
    try:
        result = await index_cv_document(db, document, clean_model_id, force=force)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"status": "success", "data": result}


@router.get("/search-cvs/{document_id}/content")
async def get_cv_content(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict:
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.category == "CV")
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="CV not found")

    try:
        path = await ensure_document_file(document)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Prefer stored raw_text (populated during indexing)
    if document.raw_text and document.raw_text.strip():
        return {"status": "success", "data": {"text": document.raw_text.strip()}}

    try:
        text = extract_pdf_text(path)
        return {"status": "success", "data": {"text": text}}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/search-cvs/{document_id}/structured")
async def get_cv_structured(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Return raw text + structured data for a CV.
    Calls the BE's own structuring endpoint, or falls back to plain text.
    """
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.category == "CV")
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="CV not found")

    try:
        path = await ensure_document_file(document)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    raw_text: str = ""

    # Prefer DB stored raw_text if available (already extracted on upload)
    if document.raw_text and document.raw_text.strip():
        raw_text = document.raw_text.strip()
    else:
        # Fallback: try to extract from PDF file on disk
        try:
            raw_text = extract_pdf_text(path)
        except Exception:
            raw_text = ""

    # If still empty, try to read raw bytes as text
    file_bytes: bytes = b""
    if not raw_text:
        try:
            with open(path, "rb") as f:
                file_bytes = f.read()
            if file_bytes:
                try:
                    raw_text = file_bytes.decode("utf-8", errors="replace").strip()
                except Exception:
                    pass
        except Exception:
            pass
    structured_data: dict | None = None
    model_used: str | None = None

    # Try BE's own structuring endpoint
    from io import BytesIO

    class FakeUploadFile:
        def __init__(self, filename: str, content: bytes):
            self.filename = filename
            self._buffer = BytesIO(content)

        async def read(self, n: int = -1) -> bytes:
            return self._buffer.read(n)

        async def seek(self, pos: int) -> None:
            self._buffer.seek(pos)

    try:
        from app.api.v1.endpoints.structuring import structure_cv
        fake_file = FakeUploadFile(document.filename, file_bytes)
        result = await structure_cv(file=fake_file, extract_raw_text=True)
        if result and result.structured_data:
            structured_data = result.structured_data
            model_used = result.model_used
    except Exception:
        pass

    # Fallback: plain text as raw_text field — signal no structured data
    if structured_data is None:
        structured_data = {}  # empty dict signals "show raw text only"
        model_used = "text-extraction"

    return {
        "status": "success",
        "data": {
            "text": raw_text,
            "structured": structured_data,
            "model_used": model_used,
        },
    }


@router.post("/cv-jd")
async def match_cv_jd(
    cv_files: Annotated[list[UploadFile], File(...)],
    jd_file: Annotated[UploadFile | None, File()] = None,
    jd_text: Annotated[str | None, Form()] = None,
    save_cv: Annotated[bool, Form()] = False,
    model_id: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
) -> dict:
    if not cv_files:
        raise HTTPException(status_code=400, detail="At least one CV file is required")

    clean_jd_text = jd_text.strip() if jd_text else None
    clean_model_id = model_id.strip() if model_id else None
    if bool(jd_file) == bool(clean_jd_text):
        raise HTTPException(status_code=400, detail="Provide exactly one of jd_file or jd_text")

    for file in cv_files:
        _validate_matching_file(file, "cv_files")
    if jd_file:
        _validate_matching_file(jd_file, "jd_file")

    # Always save locally so the AI service can read the bytes; only persist to
    # Cloudinary/DB when the user explicitly opts in via `save_cv`.
    stored_cvs: list[StoredUpload] = []
    cv_documents: list[dict] = []
    for file in cv_files:
        stored = save_upload_file(file)
        stored_cvs.append(stored)
        if save_cv:
            document = persist_document_from_local(db, stored.filename, "CV")
            payload = _document_payload(document)
            try:
                payload["search_index"] = await index_cv_document(db, document, clean_model_id)
            except Exception as exc:
                payload["search_index"] = {"status": "failed", "reason": str(exc)}
            cv_documents.append(payload)

    # JD is never persisted per product spec; we only keep it locally for the
    # AI service call and highlighting, then it can be cleaned up later.
    stored_jd = None
    jd_document = None
    if jd_file:
        stored_jd = save_upload_file(jd_file)

    ai_response = await _call_ai_service(stored_cvs, stored_jd, clean_jd_text, clean_model_id)
    matching_payload = ai_response.get("data", ai_response)
    results = matching_payload.get("results", [])

    cv_upload_by_name = {upload.filename: upload for upload in stored_cvs}
    all_view_matches = [
        match
        for result in results
        for match in result.get("view_matches", [])
    ]
    highlighted_jd_url = (
        create_highlighted_pdf(stored_jd.path, all_view_matches, "jd")
        if stored_jd and all_view_matches
        else None
    )

    for result in results:
        cv_upload = cv_upload_by_name.get(result.get("cv_file"))
        view_matches = result.get("view_matches", [])
        result["highlighted_cv_url"] = (
            create_highlighted_pdf(cv_upload.path, view_matches, "cv")
            if cv_upload and view_matches
            else None
        )
        result["highlighted_jd_url"] = highlighted_jd_url

    return {
        "status": "success",
        "data": {
            "documents": {
                "cvs": cv_documents,
                "jd": jd_document,
            },
            "matching": matching_payload,
        },
    }


@router.post("/cv-detail/heatmap")
async def get_cv_jd_heatmap(
    jd_text: Annotated[str | None, Form()] = None,
    jd_file: Annotated[UploadFile | None, File()] = None,
    cv_document_id: Annotated[int | None, Form()] = None,
    cv_file: Annotated[UploadFile | None, File()] = None,
    cv_text: Annotated[str | None, Form()] = None,
    cv_filename: Annotated[str | None, Form()] = None,
    model_id: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
) -> dict:
    """
    Get alignment heatmap for a single CV vs JD.
    Supports 3 modes:
    1. cv_document_id + jd_text/jd_file  → DB CV + JD
    2. cv_file + jd_text/jd_file         → uploaded CV + JD
    3. cv_text + jd_text                  → text CV + text JD (for web profiles)
    """
    clean_jd_text = jd_text.strip() if jd_text else None
    clean_model_id = model_id.strip() if model_id else None

    has_jd = bool(jd_file) or bool(clean_jd_text)
    has_cv = bool(cv_document_id) or bool(cv_file) or (bool(cv_text) and bool(cv_filename))

    if not has_jd:
        raise HTTPException(status_code=400, detail="jd_text or jd_file is required")
    if not has_cv:
        raise HTTPException(status_code=400, detail="cv_document_id, cv_file, or cv_text is required")

    cv_upload: StoredUpload | None = None

    # Mode 1: DB CV
    if cv_document_id:
        document = (
            db.query(Document)
            .filter(Document.id == cv_document_id, Document.category == "CV")
            .first()
        )
        if not document:
            raise HTTPException(status_code=404, detail="CV not found")
        cv_path = await ensure_document_file(document)
        cv_upload = StoredUpload(
            filename=document.filename,
            path=cv_path,
            preview_url=document.cloudinary_url or preview_url_for(document.filename),
            raw_text=document.raw_text,
        )

    # Mode 2: Uploaded CV file
    elif cv_file:
        cv_upload = save_upload_file(cv_file)

    # Mode 3: CV text (for web profiles)
    elif cv_text and cv_filename:
        ensure_upload_dir()
        from uuid import uuid4
        safe_name = safe_filename(cv_filename)
        path = local_path_for(f"{uuid4().hex[:8]}_{safe_name}")
        path.write_text(cv_text, encoding="utf-8")
        cv_upload = StoredUpload(
            filename=cv_filename,
            path=path,
            preview_url=preview_url_for(path.name),
        )

    if not cv_upload:
        raise HTTPException(status_code=400, detail="Could not process CV")

    jd_upload: StoredUpload | None = None
    jd_text_from_pdf: str | None = None
    if jd_file:
        jd_upload = save_upload_file(jd_file)
        # Extract text from JD PDF locally (don't send file to AI service)
        try:
            jd_text_from_pdf = extract_pdf_text(jd_upload.path)
            jd_text_from_pdf = sanitize_extracted_text(jd_text_from_pdf)
        except Exception:
            pass  # Let AI service handle it if extraction fails

    try:
        ai_response = await call_matching_ai_service(
            [cv_upload],
            jd_upload if not jd_text_from_pdf else None,
            clean_jd_text if not jd_upload else jd_text_from_pdf,
            clean_model_id,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"AI service unreachable: {exc}") from exc

    data = ai_response.get("data", ai_response)
    results = data.get("results", []) if isinstance(data, dict) else []

    return {
        "status": "success",
        "data": results[0] if results else None,
    }
