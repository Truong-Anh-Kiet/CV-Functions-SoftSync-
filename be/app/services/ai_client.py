from contextlib import ExitStack
from pathlib import Path

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.services.document_storage import StoredUpload, UPLOAD_DIR


async def call_matching_ai_service(
    cv_uploads: list[StoredUpload],
    jd_upload: StoredUpload | None,
    jd_text: str | None,
    model_id: str | None = None,
    include_structured: bool = True,
) -> dict:
    url = f"{settings.ai_service_url.rstrip('/')}/api/v1/matching/predict"
    data: dict[str, str] = {"include_structured": "true" if include_structured else "false"}
    if jd_text:
        data["jd_text"] = jd_text
    if model_id:
        data["model_id"] = model_id

    with ExitStack() as stack:
        files = []
        for upload in cv_uploads:
            if upload.raw_text:
                text_filename = f"{Path(upload.filename).stem}.txt"
                text_path = UPLOAD_DIR / text_filename
                text_path.parent.mkdir(parents=True, exist_ok=True)
                text_path.write_text(upload.raw_text, encoding="utf-8")
                file_obj = stack.enter_context(text_path.open("rb"))
                files.append(("cv_files", (text_filename, file_obj, "text/plain")))
            else:
                try:
                    file_obj = stack.enter_context(upload.path.open("rb"))
                    files.append(("cv_files", (upload.filename, file_obj, "application/pdf")))
                except FileNotFoundError:
                    if upload.raw_text is None:
                        raise ValueError(f"Cannot read CV file and no raw_text available: {upload.filename}")

        if jd_upload:
            file_obj = stack.enter_context(jd_upload.path.open("rb"))
            files.append(("jd_file", (jd_upload.filename, file_obj, "application/pdf")))

        try:
            async with httpx.AsyncClient(timeout=settings.ai_service_timeout_seconds) as client:
                response = await client.post(url, data=data, files=files)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"AI service unreachable: {exc}") from exc

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=502, detail=f"AI service error: {detail}")

    return response.json()
