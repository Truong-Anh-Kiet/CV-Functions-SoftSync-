import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document


def _resolve_upload_dir() -> Path:
    path = Path(settings.upload_dir)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent.parent / path
    return path


UPLOAD_DIR = _resolve_upload_dir()
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}


@dataclass(frozen=True)
class StoredUpload:
    filename: str
    path: Path
    preview_url: str
    raw_text: str | None = None
    profile_id: str | int | None = None


def ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def safe_filename(filename: str | None) -> str:
    raw_name = Path(filename or "upload.pdf").name
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", raw_name).strip()
    return cleaned or "upload.pdf"


def validate_supported_file(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="File khong ho tro. Chi nhan PDF, DOC, DOCX",
        )


def validate_pdf_file(filename: str) -> None:
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="CV-JD Matching chi ho tro file PDF")


def preview_url_for(filename: str) -> str:
    base_url = settings.backend_public_url.rstrip("/")
    return f"{base_url}/static/{quote(filename)}"


def local_path_for(filename: str) -> Path:
    return UPLOAD_DIR / safe_filename(filename)


def delete_local_file(filename: str) -> bool:
    path = local_path_for(filename)
    if not path.exists():
        return False
    path.unlink()
    return True


def rename_local_file(old_filename: str, new_filename: str) -> bool:
    old_path = local_path_for(old_filename)
    new_path = local_path_for(new_filename)
    if old_path == new_path or not old_path.exists():
        return False
    if new_path.exists():
        raise HTTPException(status_code=409, detail="File moi da ton tai")
    old_path.rename(new_path)
    return True


def save_upload_file(file: UploadFile) -> StoredUpload:
    ensure_upload_dir()
    filename = safe_filename(file.filename)
    validate_supported_file(filename)

    path = local_path_for(filename)
    with path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    file.file.seek(0)

    return StoredUpload(
        filename=filename,
        path=path,
        preview_url=preview_url_for(filename),
    )


def init_cloudinary() -> None:
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


def _cloudinary_configured() -> bool:
    return bool(
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
    )


def _cloudinary_public_id_from_url(cloudinary_url: str | None) -> str | None:
    if not cloudinary_url:
        return None

    path = urlparse(cloudinary_url).path
    marker = "/upload/"
    if marker not in path:
        return None

    public_path = path.split(marker, 1)[1].lstrip("/")
    parts = public_path.split("/")
    if parts and parts[0].startswith("v") and parts[0][1:].isdigit():
        parts = parts[1:]

    public_id = "/".join(unquote(part) for part in parts).strip("/")
    return public_id or None


def delete_cloudinary_raw_asset(cloudinary_url: str | None) -> bool:
    if not _cloudinary_configured():
        return False

    public_id = _cloudinary_public_id_from_url(cloudinary_url)
    if not public_id:
        return False

    try:
        init_cloudinary()
        result = cloudinary.uploader.destroy(
            public_id,
            resource_type="raw",
            invalidate=True,
        )
        return result.get("result") in {"ok", "not found"}
    except Exception:
        return False


def persist_document_from_local(db: Session, filename: str, category: str) -> Document:
    init_cloudinary()

    clean_filename = safe_filename(filename)
    path = local_path_for(clean_filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Khong tim thay file tam de luu")

    try:
        result = cloudinary.uploader.upload(
            str(path),
            folder=f"hr_system/{category.lower()}s",
            resource_type="raw",
        )
        cloudinary_url = result.get("secure_url")
        if not cloudinary_url:
            raise RuntimeError("Cloudinary did not return secure_url")

        document = Document(
            filename=clean_filename,
            cloudinary_url=cloudinary_url,
            category=category.upper(),
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        if category.upper() == "CV":
            try:
                from app.services.cv_vector_search import extract_pdf_text
                if path.exists():
                    source_text = extract_pdf_text(path)
                    if source_text:
                        document.raw_text = source_text
                        db.add(document)
                        db.commit()
                        db.refresh(document)
            except Exception:
                pass

        return document
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        message = str(exc)
        if "Invalid Signature" in message:
            raise HTTPException(
                status_code=401,
                detail="Loi xac thuc Cloudinary. Kiem tra CLOUDINARY_API_KEY va CLOUDINARY_API_SECRET",
            ) from exc
        raise HTTPException(status_code=500, detail=message) from exc
