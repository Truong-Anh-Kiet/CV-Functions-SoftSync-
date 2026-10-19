from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document import Document
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListResponse,
    RenameDocumentRequest,
)
from app.services.document_storage import (
    delete_cloudinary_raw_asset,
    delete_local_file,
    local_path_for,
    persist_document_from_local,
    preview_url_for,
    rename_local_file,
    safe_filename,
    save_upload_file,
    validate_supported_file,
)
from app.services.cv_vector_search import delete_document_embeddings, index_cv_document

router = APIRouter()


def _document_payload(document: Document) -> dict:
    local_preview_url = preview_url_for(document.filename)
    preview_url = local_preview_url if local_path_for(document.filename).exists() else document.cloudinary_url
    return {
        "id": document.id,
        "filename": document.filename,
        "category": document.category,
        "url": document.cloudinary_url or local_preview_url,
        "cloudinary_url": document.cloudinary_url,
        "preview_url": preview_url,
        "created_at": document.created_at,
    }


def _get_cv_or_404(db: Session, document_id: int) -> Document:
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.category == "CV")
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Khong tim thay CV")
    return document


def _normalize_renamed_cv_filename(new_filename: str, current_filename: str) -> str:
    clean_filename = safe_filename(new_filename)
    current_extension = Path(current_filename).suffix
    new_extension = Path(clean_filename).suffix

    if not new_extension:
        clean_filename = f"{clean_filename}{current_extension}"
        new_extension = current_extension

    validate_supported_file(clean_filename)
    if new_extension.lower() != current_extension.lower():
        raise HTTPException(status_code=400, detail="Khong duoc doi dinh dang file CV")
    return clean_filename


@router.post("/preview")
async def preview_file(file: UploadFile = File(...)) -> dict:
    stored = save_upload_file(file)
    return {
        "status": "success",
        "data": {
            "filename": stored.filename,
            "preview_url": stored.preview_url,
        },
    }


@router.get("/cvs", response_model=DocumentListResponse)
def list_cvs(db: Session = Depends(get_db)) -> dict:
    documents = (
        db.query(Document)
        .filter(Document.category == "CV")
        .order_by(Document.created_at.desc(), Document.id.desc())
        .all()
    )
    return {
        "status": "success",
        "data": [_document_payload(document) for document in documents],
    }


@router.get("/cvs/{document_id}", response_model=DocumentDetailResponse)
def get_cv(document_id: int, db: Session = Depends(get_db)) -> dict:
    document = _get_cv_or_404(db, document_id)
    return {"status": "success", "data": _document_payload(document)}


@router.patch("/cvs/{document_id}/rename", response_model=DocumentDetailResponse)
def rename_cv(
    document_id: int,
    payload: RenameDocumentRequest,
    db: Session = Depends(get_db),
) -> dict:
    document = _get_cv_or_404(db, document_id)
    new_filename = _normalize_renamed_cv_filename(payload.filename, document.filename)

    duplicated = (
        db.query(Document)
        .filter(
            Document.id != document.id,
            Document.category == "CV",
            Document.filename == new_filename,
        )
        .first()
    )
    if duplicated:
        raise HTTPException(status_code=409, detail="Ten CV da ton tai")

    if new_filename != document.filename:
        rename_local_file(document.filename, new_filename)
        document.filename = new_filename
        db.commit()
        db.refresh(document)

    return {"status": "success", "data": _document_payload(document)}


@router.delete("/cvs/{document_id}")
def delete_cv(document_id: int, db: Session = Depends(get_db)) -> dict:
    document = _get_cv_or_404(db, document_id)

    delete_document_embeddings(db, document.id)
    delete_local_file(document.filename)
    delete_cloudinary_raw_asset(document.cloudinary_url)
    db.delete(document)
    db.commit()

    return {"status": "success", "message": "Da xoa CV thanh cong"}


@router.post("/confirm-save")
async def confirm_save(
    filename: str = Body(..., embed=True),
    category: str = Body(..., embed=True),
    db: Session = Depends(get_db),
) -> dict:
    document = persist_document_from_local(db, filename, category)
    document_id = document.id
    document_url = document.cloudinary_url
    document_category = document.category
    search_index = {"status": "skipped", "reason": "Only CV documents are indexed"}
    if document_category == "CV":
        try:
            search_index = await index_cv_document(db, document)
        except Exception as exc:
            db.rollback()
            search_index = {"status": "failed", "reason": str(exc)}

    return {
        "status": "success",
        "message": f"Da luu {category} thanh cong",
        "data": {
            "id": document_id,
            "url": document_url,
            "search_index": search_index,
        },
    }
