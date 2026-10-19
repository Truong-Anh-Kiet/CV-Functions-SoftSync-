import hashlib
import json
import math
from pathlib import Path

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.document_embedding import DocumentEmbedding
from app.services.document_storage import local_path_for, preview_url_for


async def ensure_document_file(document: Document) -> Path:
    path = local_path_for(document.filename)
    if path.exists():
        return path

    if not document.cloudinary_url:
        raise FileNotFoundError(f"Local CV file not found: {document.filename}")

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with httpx.AsyncClient(timeout=settings.ai_service_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(document.cloudinary_url)
    except httpx.RequestError as exc:
        raise FileNotFoundError(f"Cannot download CV file: {document.filename}: {exc}") from exc

    if response.status_code >= 400:
        raise FileNotFoundError(
            f"Cannot download CV file: {document.filename}: HTTP {response.status_code}"
        )

    path.write_bytes(response.content)
    return path


def extract_pdf_text(path: Path) -> str:
    if path.suffix.lower() != ".pdf":
        raise ValueError("CV search indexing currently supports PDF files only")

    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to index CV files") from exc

    text_parts: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            page_text = page.get_text("text")
            if page_text:
                text_parts.append(page_text)
    return sanitize_extracted_text("\n".join(text_parts))


def sanitize_extracted_text(text: str) -> str:
    # PostgreSQL text columns cannot store NUL bytes, and some PDFs extract
    # icon/font placeholders as "\x00". Remove them before hashing/embedding.
    return text.replace("\x00", "").strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def create_text_embedding(text: str, model_id: str | None = None) -> dict:
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Text is empty")

    url = f"{settings.ai_service_url.rstrip('/')}/api/v1/embeddings/text"
    payload = {"text": clean_text, "model_id": model_id}

    try:
        async with httpx.AsyncClient(timeout=settings.ai_service_timeout_seconds) as client:
            response = await client.post(url, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"AI embedding service unreachable: {exc}") from exc

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=502, detail=f"AI embedding service error: {detail}")

    return response.json().get("data", response.json())


def parse_embedding(row: DocumentEmbedding) -> list[float]:
    try:
        values = json.loads(row.embedding_json or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid embedding JSON for document_id={row.document_id}") from exc
    return [float(value) for value in values]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def document_preview_url(document: Document) -> str | None:
    if local_path_for(document.filename).exists():
        return preview_url_for(document.filename)
    return document.cloudinary_url


def document_search_payload(document: Document, embedding: DocumentEmbedding, score: float) -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "category": document.category,
        "cloudinary_url": document.cloudinary_url,
        "preview_url": document_preview_url(document),
        "created_at": document.created_at,
        "search_score": round(score, 6),
        "embedding_model_id": embedding.model_id,
        "sbert_id": embedding.sbert_id,
        "embedding_dimension": embedding.dimension,
        "indexed_at": embedding.updated_at or embedding.created_at,
        "text_length": len(embedding.source_text or ""),
    }


def get_document_embedding(
    db: Session,
    document_id: int,
    model_id: str,
) -> DocumentEmbedding | None:
    return (
        db.query(DocumentEmbedding)
        .filter(
            DocumentEmbedding.document_id == document_id,
            DocumentEmbedding.model_id == model_id,
        )
        .first()
    )


async def index_cv_document(
    db: Session,
    document: Document,
    model_id: str | None = None,
    force: bool = False,
) -> dict:
    if document.category != "CV":
        raise ValueError("Only CV documents can be indexed")

    path = await ensure_document_file(document)

    source_text = extract_pdf_text(path)
    if not source_text:
        source_text = document.raw_text or ""

    if not source_text:
        raise ValueError(f"Cannot extract text from CV: {document.filename}")

    # Always save raw_text to the document record (for fallback on corrupt PDFs)
    if source_text:
        document.raw_text = source_text
        db.add(document)

    digest = text_hash(source_text)
    if model_id and not force:
        existing = get_document_embedding(db, document.id, model_id)
        if existing and existing.text_hash == digest:
            return {
                "status": "already_indexed",
                "document_id": document.id,
                "model_id": existing.model_id,
                "dimension": existing.dimension,
            }

    embedding_data = await create_text_embedding(source_text, model_id)
    resolved_model_id = embedding_data["model_id"]
    vector = embedding_data["embedding"]

    existing = get_document_embedding(db, document.id, resolved_model_id)
    if existing:
        existing.sbert_id = embedding_data.get("sbert_id")
        existing.dimension = embedding_data.get("dimension", len(vector))
        existing.text_hash = digest
        existing.source_text = source_text
        existing.embedding_json = json.dumps(vector)
        action = "updated"
        embedding = existing
    else:
        embedding = DocumentEmbedding(
            document_id=document.id,
            model_id=resolved_model_id,
            sbert_id=embedding_data.get("sbert_id"),
            dimension=embedding_data.get("dimension", len(vector)),
            text_hash=digest,
            source_text=source_text,
            embedding_json=json.dumps(vector),
        )
        db.add(embedding)
        action = "created"

    try:
        db.commit()
        db.refresh(embedding)
    except Exception:
        db.rollback()
        raise

    return {
        "status": action,
        "document_id": document.id,
        "model_id": embedding.model_id,
        "dimension": embedding.dimension,
        "text_length": len(source_text),
    }


def delete_document_embeddings(db: Session, document_id: int) -> int:
    deleted = (
        db.query(DocumentEmbedding)
        .filter(DocumentEmbedding.document_id == document_id)
        .delete(synchronize_session=False)
    )
    return int(deleted or 0)
