import shutil
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.schemas.jd_search import JDAnalysisResponse
from app.services.extraction import analyze_jd_file, analyze_jd_text

router = APIRouter()


def _safe_filename(filename: str | None) -> str:
    name = Path(filename or "upload.pdf").name
    return name or "upload.pdf"


def _validate_file(file: UploadFile, field_name: str) -> None:
    filename = _safe_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail=f"{field_name} must be a PDF file")


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


@router.post("/analyze-text", response_model=JDAnalysisResponse)
async def analyze_text(
    jd_text: Annotated[str, Form()],
) -> JDAnalysisResponse:
    clean_text = jd_text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="jd_text is required")

    try:
        data = analyze_jd_text(clean_text)
        return JDAnalysisResponse(status="success", data=data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/analyze-file", response_model=JDAnalysisResponse)
async def analyze_file(
    file: Annotated[UploadFile, File(...)],
) -> JDAnalysisResponse:
    request_dir = settings.tmp_dir / uuid.uuid4().hex
    request_dir.mkdir(parents=True, exist_ok=True)

    try:
        path, _ = await _save_file(file, request_dir, "file")
        data = analyze_jd_file(path)
        return JDAnalysisResponse(status="success", data=data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        shutil.rmtree(request_dir, ignore_errors=True)
