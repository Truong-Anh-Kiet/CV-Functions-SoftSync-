from pathlib import Path
import re
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.schemas.vietnamworks import VietnamWorksProfileResponse, VietnamWorksSearchResponse
from app.services.ai_client import call_matching_ai_service
from app.services.cv_vector_search import extract_pdf_text
from app.services.document_storage import (
    StoredUpload,
    ensure_upload_dir,
    local_path_for,
    preview_url_for,
    safe_filename,
    save_upload_file,
    validate_pdf_file,
)
from app.services.vietnamworks import (
    VietnamWorksAuthError,
    VietnamWorksError,
    get_vietnamworks_client,
)

router = APIRouter()


def _matching_filename(profile: dict) -> str:
    base_name = " - ".join(
        value
        for value in [
            str(profile.get("title") or "").strip(),
            str(profile.get("candidate_name") or "").strip(),
        ]
        if value
    ) or str(profile.get("id") or "vietnamworks-cv")
    return safe_filename(f"{base_name}.pdf")


def _store_vietnamworks_file(profile: dict, file_data: dict) -> StoredUpload:
    ensure_upload_dir()
    filename = _matching_filename(profile)
    stem = Path(filename).stem
    suffix = Path(filename).suffix or ".pdf"
    unique_filename = safe_filename(f"{stem}-{uuid4().hex[:8]}{suffix}")
    path = local_path_for(unique_filename)
    path.write_bytes(file_data["content"])
    return StoredUpload(
        filename=filename,
        path=path,
        preview_url=preview_url_for(unique_filename),
        profile_id=profile.get("id"),
    )


def _rerank_result_key(value: str | None) -> str:
    normalized = re.sub(r"(\.(pdf|txt))+$", "", value or "", flags=re.IGNORECASE)
    normalized = re.sub(r"[^0-9a-zA-Z]+", " ", normalized)
    return normalized.strip().lower()


def _align_rerank_filenames(rerank_payload: dict, stored_uploads: list[StoredUpload]) -> None:
    # Build mapping by profile_id and by normalized filename
    profile_ids = {upload.profile_id: upload for upload in stored_uploads if upload.profile_id}
    display_names = {_rerank_result_key(upload.filename): Path(upload.filename).stem for upload in stored_uploads}
    
    for result in rerank_payload.get("results") or []:
        cv_file = result.get("cv_file")
        result["source_cv_file"] = cv_file
        
        # Try to match by profile_id first
        matched_upload = None
        for upload in stored_uploads:
            if upload.profile_id and cv_file and upload.profile_id in cv_file:
                matched_upload = upload
                break
        
        # Fallback to filename matching
        if not matched_upload:
            display_name = display_names.get(_rerank_result_key(cv_file))
            if display_name:
                result["cv_file"] = display_name
            matched_upload = next((u for u in stored_uploads if display_names.get(_rerank_result_key(u.filename)) == display_name), None)
        
        # Store profile_id for frontend matching
        if matched_upload and matched_upload.profile_id:
            result["profile_id"] = matched_upload.profile_id


@router.get("/profiles", response_model=VietnamWorksSearchResponse)
def search_vietnamworks_profiles(
    query: str | None = Query(default=None, description="Text keyword for VietnamWorks profile search"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    try:
        data = get_vietnamworks_client().search_profiles(query=query, page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VietnamWorksAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VietnamWorksError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@router.post("/profiles/search-jd", response_model=VietnamWorksSearchResponse)
async def search_vietnamworks_profiles_by_jd(
    jd_file: Annotated[UploadFile | None, File()] = None,
    jd_text: Annotated[str | None, Form()] = None,
    page: Annotated[int, Form(ge=1)] = 1,
    page_size: Annotated[int, Form(ge=1, le=100)] = 20,
) -> dict:
    clean_jd_text = jd_text.strip() if jd_text else None
    if bool(jd_file) == bool(clean_jd_text):
        raise HTTPException(status_code=400, detail="Provide exactly one of jd_file or jd_text")

    if jd_file:
        filename = Path(jd_file.filename or "").name
        if not filename:
            raise HTTPException(status_code=400, detail="jd_file is required")
        validate_pdf_file(filename)
        stored_jd = save_upload_file(jd_file)
        try:
            clean_jd_text = extract_pdf_text(stored_jd.path)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not clean_jd_text:
        raise HTTPException(status_code=400, detail="JD content is empty")

    try:
        data = get_vietnamworks_client().search_profiles_by_jd(
            jd_text=clean_jd_text,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VietnamWorksAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VietnamWorksError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@router.post("/profiles/search-match")
async def search_and_match_vietnamworks_profiles(
    jd_file: Annotated[UploadFile | None, File()] = None,
    jd_text: Annotated[str | None, Form()] = None,
    query: Annotated[str | None, Form()] = None,
    page: Annotated[int, Form(ge=1)] = 1,
    page_size: Annotated[int, Form(ge=1, le=100)] = 20,
    min_score: Annotated[float, Form()] = 0.0,
    rerank: Annotated[bool, Form()] = False,
    rerank_top_n: Annotated[int, Form()] = 10,
    model_id: Annotated[str | None, Form()] = None,
) -> dict:
    clean_query = query.strip() if query else None
    clean_jd_text = jd_text.strip() if jd_text else None
    if jd_file and clean_jd_text:
        raise HTTPException(status_code=400, detail="Provide jd_file or jd_text, not both")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="page_size must be between 1 and 100")
    if rerank_top_n < 1 or rerank_top_n > page_size:
        raise HTTPException(status_code=400, detail="rerank_top_n must be between 1 and page_size")
    if min_score < 0 or min_score > 1:
        raise HTTPException(status_code=400, detail="min_score must be between 0 and 1")

    stored_jd = None
    if jd_file:
        filename = Path(jd_file.filename or "").name
        if not filename:
            raise HTTPException(status_code=400, detail="jd_file is required")
        validate_pdf_file(filename)
        stored_jd = save_upload_file(jd_file)
        try:
            clean_jd_text = extract_pdf_text(stored_jd.path)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if rerank and not clean_jd_text and not stored_jd:
        raise HTTPException(status_code=400, detail="JD text or JD file is required when AI rerank is enabled")

    try:
        client = get_vietnamworks_client()
        if clean_jd_text and not clean_query:
            data = client.search_profiles_by_jd(jd_text=clean_jd_text, page=page, page_size=page_size)
        else:
            data = client.search_profiles(query=clean_query or clean_jd_text, page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VietnamWorksAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VietnamWorksError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    skipped: list[dict] = []
    rerank_payload = None
    if rerank and data.get("items"):
        stored_uploads: list[StoredUpload] = []
        for profile in data["items"][:rerank_top_n]:
            try:
                detail = client.get_profile(profile_id=profile["id"], profile_url=profile.get("profile_url"))
                file_data = client.get_profile_file(profile_id=detail["id"], profile_url=detail.get("profile_url"))
                stored_uploads.append(_store_vietnamworks_file(detail, file_data))
            except (LookupError, ValueError, VietnamWorksAuthError, VietnamWorksError) as exc:
                skipped.append(
                    {
                        "id": profile.get("id"),
                        "filename": _matching_filename(profile),
                        "reason": str(exc),
                    }
                )

        if stored_uploads:
            rerank_jd_text = None if stored_jd else clean_jd_text
            ai_response = await call_matching_ai_service(stored_uploads, stored_jd, rerank_jd_text, model_id)
            rerank_payload = ai_response.get("data", ai_response)
            _align_rerank_filenames(rerank_payload, stored_uploads)

    return {
        "status": "success",
        "data": {
            **data,
            "min_score": min_score,
            "rerank": rerank_payload,
            "skipped_cvs": skipped,
        },
    }


@router.get("/profiles/{profile_id}", response_model=VietnamWorksProfileResponse)
def get_vietnamworks_profile(
    profile_id: str,
    profile_url: str | None = Query(default=None, description="Fallback VietnamWorks profile URL if profile_id is not a resume id"),
) -> dict:
    try:
        data = get_vietnamworks_client().get_profile(profile_id=profile_id, profile_url=profile_url)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VietnamWorksAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VietnamWorksError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "success", "data": data}


@router.get("/profiles/{profile_id}/file")
def get_vietnamworks_profile_file(
    profile_id: str,
    profile_url: str | None = Query(default=None, description="Fallback VietnamWorks profile URL if profile_id is not a resume id"),
) -> Response:
    try:
        data = get_vietnamworks_client().get_profile_file(profile_id=profile_id, profile_url=profile_url)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VietnamWorksAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VietnamWorksError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    filename = str(data["filename"]).replace('"', "")
    return Response(
        content=data["content"],
        media_type=str(data["content_type"]),
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
