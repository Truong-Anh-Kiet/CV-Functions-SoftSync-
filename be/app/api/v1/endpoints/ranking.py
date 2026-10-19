from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document import Document
from app.services.ai_client import call_matching_ai_service
from app.services.cv_vector_search import ensure_document_file
from app.services.document_storage import (
    StoredUpload,
    preview_url_for,
    save_upload_file,
    validate_pdf_file,
)

router = APIRouter()


def _parse_saved_cv_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    ids: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            ids.append(int(token))
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"saved_cv_ids has invalid value: {token!r}",
            ) from exc
    return ids


def _validate_matching_file(file: UploadFile, field_name: str) -> None:
    from pathlib import Path

    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    validate_pdf_file(filename)


@router.post("/rank")
async def rank_cvs(
    cv_files: Annotated[list[UploadFile], File()] = [],
    saved_cv_ids: Annotated[str | None, Form()] = None,
    jd_file: Annotated[UploadFile | None, File()] = None,
    jd_text: Annotated[str | None, Form()] = None,
    model_id: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
) -> dict:
    saved_ids = _parse_saved_cv_ids(saved_cv_ids)

    if not cv_files and not saved_ids:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one CV via cv_files or saved_cv_ids",
        )

    clean_jd_text = jd_text.strip() if jd_text else None
    clean_model_id = model_id.strip() if model_id else None
    if bool(jd_file) == bool(clean_jd_text):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of jd_file or jd_text",
        )

    for file in cv_files:
        _validate_matching_file(file, "cv_files")
    if jd_file:
        _validate_matching_file(jd_file, "jd_file")

    stored_cvs: list[StoredUpload] = []
    # source_meta keyed by stored filename → {id?, cloudinary_url?, preview_url}
    source_meta: dict[str, dict] = {}

    # 1. Uploaded CVs → save locally
    for file in cv_files:
        stored = save_upload_file(file)
        stored_cvs.append(stored)
        source_meta[stored.filename] = {
            "id": None,
            "cloudinary_url": None,
            "preview_url": stored.preview_url,
            "source": "uploaded",
        }

    # 2. Saved CVs → fetch Document rows and ensure local file
    if saved_ids:
        documents = (
            db.query(Document)
            .filter(Document.id.in_(saved_ids), Document.category == "CV")
            .all()
        )
        found_ids = {doc.id for doc in documents}
        missing = [pk for pk in saved_ids if pk not in found_ids]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Saved CV ids not found: {missing}",
            )

        for document in documents:
            # Matching pipeline only supports PDF; saved DOCX would fail with
            # an opaque 502 from the AI service — block here with a clear error.
            validate_pdf_file(document.filename)
            try:
                path = await ensure_document_file(document)
            except FileNotFoundError as exc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Cannot access saved CV {document.filename}: {exc}",
                ) from exc

            stored = StoredUpload(
                filename=document.filename,
                path=path,
                preview_url=preview_url_for(document.filename),
            )
            stored_cvs.append(stored)
            source_meta[document.filename] = {
                "id": document.id,
                "cloudinary_url": document.cloudinary_url,
                "preview_url": preview_url_for(document.filename),
                "source": "saved",
            }

    # 3. JD: only saved locally if PDF; never persisted to Cloudinary here.
    stored_jd = None
    if jd_file:
        stored_jd = save_upload_file(jd_file)

    # 4. Call AI service (parallel extraction is done in the AI side).
    ai_response = await call_matching_ai_service(
        stored_cvs,
        stored_jd,
        clean_jd_text,
        clean_model_id,
    )
    matching_payload = ai_response.get("data", ai_response)
    results = matching_payload.get("results", [])

    # 5. Decorate each result with its source metadata (skip highlighted PDF
    # generation — keep this endpoint fast; the FE can render the heatmap +
    # XAI from view_matches & alignment_matrix already in the response).
    for result in results:
        meta = source_meta.get(result.get("cv_file")) or {}
        result["cv_id"] = meta.get("id")
        result["cv_source"] = meta.get("source")
        result["cv_preview_url"] = meta.get("preview_url")
        result["cv_cloudinary_url"] = meta.get("cloudinary_url")

    return {
        "status": "success",
        "data": matching_payload,
    }
