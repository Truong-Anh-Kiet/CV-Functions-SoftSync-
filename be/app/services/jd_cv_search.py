import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.schemas.cv_search import CandidateScoreBreakdown, CvSearchCandidate, JdAnalysisPayload
from app.services.cv_vector_search import (
    cosine_similarity,
    create_text_embedding,
    document_preview_url,
    ensure_document_file,
    extract_pdf_text,
    get_document_embedding,
    index_cv_document,
    parse_embedding,
)

TITLE_SYNONYMS = {
    "backend developer": {"backend developer", "java developer", "backend engineer", "software engineer backend", "java backend developer"},
    "frontend developer": {"frontend developer", "react developer", "reactjs developer", "web frontend developer", "frontend engineer"},
    "qa engineer": {"qa engineer", "test engineer", "quality assurance engineer", "automation tester", "software tester"},
    "data analyst": {"data analyst", "business analyst", "bi analyst"},
    "big data engineer": {"big data engineer", "data engineer", "big data developer", "data platform engineer", "data pipeline engineer"},
    "data security specialist": {
        "senior data security specialist",
        "data security specialist",
        "information security specialist",
        "cyber security specialist",
        "security engineer",
        "cloud security engineer",
        "security analyst",
    },
    "ai engineer": {"ai engineer", "ml engineer", "machine learning engineer", "nlp engineer"},
    "full-stack developer": {"full-stack developer", "full stack developer", "software engineer full stack"},
}

SKILL_SYNONYMS = {
    "node.js": {"node.js", "nodejs", "node"},
    "react": {"react", "reactjs", "react.js"},
    "spring boot": {"spring boot", "springboot"},
    "postgresql": {"postgresql", "postgres", "postgre"},
    "rest api": {"rest api", "restful api", "api"},
}

LOCATION_SYNONYMS = {
    "ho chi minh city": {"ho chi minh city", "ho chi minh", "hcm", "tp hcm", "tphcm", "sai gon", "saigon"},
    "ha noi": {"ha noi", "hanoi", "hn"},
    "da nang": {"da nang", "danang"},
}

COMMON_SKILLS = [
    "Java", "Spring Boot", "Spring", "MySQL", "PostgreSQL", "Redis", "Docker", "AWS",
    "React", "TypeScript", "JavaScript", "Python", "FastAPI", "Django", "Node.js",
    "REST API", "Microservices", "Kubernetes", "GCP", "Azure", "MongoDB", "SQL",
    "PyTorch", "TensorFlow", "LangChain", "NLP", "LLM", "Tableau", "Power BI",
]


@dataclass
class CandidateProfile:
    candidate_name: str
    current_job_title: Optional[str]
    desired_job_title: Optional[str]
    experience_years: Optional[float]
    location: Optional[str]
    work_mode: str
    skills: list[str]
    last_updated_date: Optional[str]
    willing_to_relocate: bool
    open_to_remote: bool


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.lower()
    value = re.sub(r"[^a-z0-9\+\#\.\s-]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_skill(skill: str) -> str:
    cleaned = normalize_text(skill)
    for canonical, aliases in SKILL_SYNONYMS.items():
        if cleaned in aliases:
            return canonical
    return cleaned


def normalize_title(title: str | None) -> str:
    cleaned = normalize_text(title)
    for canonical, aliases in TITLE_SYNONYMS.items():
        if cleaned in aliases:
            return canonical
    return cleaned


def normalize_location(location: str | None) -> str:
    cleaned = normalize_text(location)
    for canonical, aliases in LOCATION_SYNONYMS.items():
        if cleaned in aliases or any(alias in cleaned for alias in aliases):
            return canonical
    return cleaned


def extract_location_area(location: str | None) -> str:
    cleaned = normalize_text(location)
    if not cleaned:
        return ""

    cleaned = re.sub(r"\b(viet nam|vietnam)\b", " ", cleaned)
    for aliases in LOCATION_SYNONYMS.values():
        for alias in sorted(aliases, key=len, reverse=True):
            cleaned = re.sub(rf"\b{re.escape(alias)}\b", " ", cleaned)

    area_patterns = [
        r"\bdistrict\s*\d+\b",
        r"\bquan\s*\d+\b",
        r"\bq\s*\d+\b",
        r"\bhuyen\s+[a-z0-9\s]+\b",
        r"\bthi xa\s+[a-z0-9\s]+\b",
        r"\btp\s+[a-z0-9\s]+\b",
        r"\bthanh pho\s+[a-z0-9\s]+\b",
        r"\bnorth\b",
        r"\bsouth\b",
        r"\beast\b",
        r"\bwest\b",
        r"\bcentral\b",
    ]
    for pattern in area_patterns:
        match = re.search(pattern, cleaned)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()

    tokens = [token for token in re.split(r"[,/-]", cleaned) if token.strip()]
    if tokens:
        return tokens[0].strip()
    return ""


def detect_candidate_name(raw_text: str, filename: str) -> str:
    for line in raw_text.splitlines()[:6]:
        candidate = line.strip()
        if not candidate or "@" in candidate:
            continue
        if len(candidate.split()) >= 2 and len(candidate) <= 60 and not re.search(r"\d{4}", candidate):
            return candidate
    return Path(filename).stem.replace("_", " ").replace("-", " ").strip()


def detect_job_title(raw_text: str) -> Optional[str]:
    patterns = [
        r"(senior data security specialist|data security specialist|information security specialist|cyber security specialist|security engineer|cloud security engineer|security analyst|backend developer|frontend developer|full[- ]stack developer|java developer|react developer|qa engineer|data analyst|ai engineer|software engineer)",
    ]
    lowered = normalize_text(raw_text)
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return match.group(1).title().replace("Qa", "QA").replace("Ai", "AI")
    return None


def detect_years_experience(raw_text: str) -> Optional[float]:
    lowered = normalize_text(raw_text)
    patterns = [
        r"(\d+(?:\.\d+)?)\+?\s+(?:years|year|nam)\s+(?:of\s+)?experience",
        r"(\d+(?:\.\d+)?)\+?\s+(?:years|year|nam)\s+kinh nghiem",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return float(match.group(1))

    years = [int(value) for value in re.findall(r"\b(20\d{2}|19\d{2})\b", raw_text)]
    current_year = datetime.now(timezone.utc).year
    plausible = [year for year in years if 1990 <= year <= current_year]
    if plausible:
        inferred = current_year - min(plausible)
        if 0 <= inferred <= 35:
            return float(inferred)
    return None


def detect_location(raw_text: str) -> Optional[str]:
    lowered = normalize_text(raw_text)
    for canonical, aliases in LOCATION_SYNONYMS.items():
        if any(alias in lowered for alias in aliases):
            return canonical.title()
    return None


def detect_salary_text(raw_text: str) -> Optional[str]:
    compact_text = re.sub(r"\s+", " ", raw_text).strip()
    lowered = normalize_text(raw_text)

    range_patterns = [
        r"\b\d+(?:[.,]\d+)?\s*(?:-|to|den)\s*\d+(?:[.,]\d+)?\s*(?:trieu|tr|million|m|usd|\$)(?:\s*vnd)?(?:/\w+)?\b",
        r"\b(?:up to|upto)\s*\d+(?:[.,]\d+)?\s*(?:trieu|tr|million|m|usd|\$)(?:\s*vnd)?(?:/\w+)?\b",
    ]
    for pattern in range_patterns:
        match = re.search(pattern, compact_text, re.IGNORECASE)
        if match:
            return match.group(0).strip()

    label_patterns = [
        r"(muc luong|luong|salary|compensation)\s*[:\-]?\s*([^\n,;]+)",
    ]
    for pattern in label_patterns:
        match = re.search(pattern, compact_text, re.IGNORECASE)
        if match:
            value = match.group(2).strip()
            if value:
                return value

    if any(token in lowered for token in ("thoa thuan", "thuong luong", "negotiable", "competitive")):
        return "Thoa thuan"
    return None


def detect_work_mode(raw_text: str) -> str:
    lowered = normalize_text(raw_text)
    remote_terms = (
        "remote",
        "online",
        "work from home",
        "wfh",
        "lam online",
        "lam tu xa",
    )
    if any(term in lowered for term in remote_terms):
        return "remote"
    if "hybrid" in lowered:
        return "hybrid"
    return "onsite"


def detect_skills(raw_text: str) -> list[str]:
    lowered = normalize_text(raw_text)
    found: list[str] = []
    for skill in COMMON_SKILLS:
        canonical = normalize_skill(skill)
        aliases = SKILL_SYNONYMS.get(canonical, {canonical})
        if any(alias in lowered for alias in aliases):
            if skill not in found:
                found.append(skill)
    return found


def build_candidate_profile(document: Document, raw_text: str) -> CandidateProfile:
    lowered = normalize_text(raw_text)
    return CandidateProfile(
        candidate_name=detect_candidate_name(raw_text, document.filename),
        current_job_title=detect_job_title(raw_text),
        desired_job_title=detect_job_title(raw_text),
        experience_years=detect_years_experience(raw_text),
        location=detect_location(raw_text),
        work_mode=detect_work_mode(raw_text),
        skills=detect_skills(raw_text),
        last_updated_date=document.created_at.date().isoformat() if document.created_at else None,
        willing_to_relocate="relocate" in lowered,
        open_to_remote=("remote" in lowered) or ("work from home" in lowered),
    )


def job_title_match_score(job_analysis: JdAnalysisPayload, profile: CandidateProfile) -> float:
    jd_title = normalize_title(job_analysis.job_title)
    alternative = {normalize_title(title) for title in job_analysis.alternative_job_titles}
    candidate_titles = {
        normalize_title(profile.current_job_title),
        normalize_title(profile.desired_job_title),
    } - {""}
    if not candidate_titles:
        return 20.0
    if jd_title in candidate_titles:
        return 100.0
    if candidate_titles & alternative:
        return 90.0
    if any(
        jd_title in candidate_title or candidate_title in jd_title
        for candidate_title in candidate_titles
    ):
        return 80.0
    if jd_title == "backend developer" and "full-stack developer" in candidate_titles:
        return 60.0
    return 10.0


def skill_match(job_analysis: JdAnalysisPayload, profile: CandidateProfile) -> tuple[float, list[str], list[str]]:
    required = [normalize_skill(skill) for skill in job_analysis.required_skills]
    preferred = [normalize_skill(skill) for skill in job_analysis.preferred_skills]
    candidate = {normalize_skill(skill): skill for skill in profile.skills}

    matched_required = [skill for skill in job_analysis.required_skills if normalize_skill(skill) in candidate]
    missing_required = [skill for skill in job_analysis.required_skills if normalize_skill(skill) not in candidate]
    matched_preferred = [skill for skill in job_analysis.preferred_skills if normalize_skill(skill) in candidate]

    if not required and not preferred:
        return 50.0, [], []

    required_ratio = len(matched_required) / max(1, len(required))
    preferred_ratio = len(matched_preferred) / max(1, len(preferred)) if preferred else 0.0
    score = required_ratio * 80 + preferred_ratio * 20
    return round(score, 2), matched_required, missing_required


def experience_match(job_analysis: JdAnalysisPayload, profile: CandidateProfile) -> float:
    required = job_analysis.required_experience_years
    candidate = profile.experience_years
    if required is None or candidate is None:
        return 50.0
    if candidate >= required:
        return 100.0
    if candidate >= max(0.0, required - 1):
        return 70.0
    if candidate >= max(0.0, required - 2):
        return 35.0
    return 5.0


def location_match(job_analysis: JdAnalysisPayload, profile: CandidateProfile) -> float:
    jd_location = normalize_location(job_analysis.work_location)
    candidate_location = normalize_location(profile.location)
    if not jd_location or not candidate_location:
        return 0.0
    if jd_location != candidate_location:
        return 10.0

    jd_area = extract_location_area(job_analysis.work_location)
    candidate_area = extract_location_area(profile.location)
    if not jd_area and not candidate_area:
        return 100.0
    if jd_area and candidate_area and jd_area == candidate_area:
        return 100.0
    return 70.0


def recency_score(last_updated_date: str | None) -> float:
    if not last_updated_date:
        return 40.0
    try:
        updated = datetime.fromisoformat(last_updated_date)
    except ValueError:
        return 40.0
    age_days = max(0, (datetime.now() - updated).days)
    if age_days <= 7:
        return 100.0
    if age_days <= 30:
        return 80.0
    if age_days <= 90:
        return 55.0
    return 20.0


def compute_minmax_recency_scores(documents: list[Document]) -> dict[int, float]:
    timestamps_by_id: dict[int, float | None] = {}
    valid_timestamps: list[float] = []

    for document in documents:
        if document.created_at is None:
            timestamps_by_id[document.id] = None
            continue
        timestamp = document.created_at.timestamp()
        timestamps_by_id[document.id] = timestamp
        valid_timestamps.append(timestamp)

    if not valid_timestamps:
        return {document.id: 40.0 for document in documents}

    min_time = min(valid_timestamps)
    max_time = max(valid_timestamps)
    if max_time == min_time:
        return {
            document.id: (0.0 if timestamps_by_id[document.id] is None else 100.0)
            for document in documents
        }

    scores: dict[int, float] = {}
    for document in documents:
        timestamp = timestamps_by_id[document.id]
        if timestamp is None:
            scores[document.id] = 0.0
            continue
        normalized = (timestamp - min_time) / (max_time - min_time)
        scores[document.id] = round(normalized * 100, 2)
    return scores


def should_filter_out(
    job_analysis: JdAnalysisPayload,
    profile: CandidateProfile,
    title_score: float,
    skill_score: float,
    experience_score: float,
) -> bool:
    if job_analysis.work_mode == "onsite" and profile.work_mode == "remote":
        return True
    if title_score <= 10.0:
        return True
    if title_score <= 10.0 and skill_score < 20.0:
        return True
    if experience_score <= 5.0 and skill_score < 40.0:
        return True
    return False


def build_recommendation_reason(
    profile: CandidateProfile,
    matched_required: list[str],
    missing_required: list[str],
    job_analysis: JdAnalysisPayload,
) -> str:
    parts: list[str] = []
    if profile.experience_years is not None:
        parts.append(f"ứng viên có {profile.experience_years:g} năm kinh nghiệm")
    if profile.current_job_title:
        parts.append(f"đang làm vị trí {profile.current_job_title}")
    if matched_required:
        parts.append(f"sở hữu {', '.join(matched_required[:4])}")
    if job_analysis.work_mode != "remote" and profile.location:
        parts.append(f"đang ở {profile.location}")
    if missing_required:
        parts.append(f"còn thiếu {', '.join(missing_required[:2])}")
    if profile.last_updated_date:
        parts.append(f"CV cập nhật ngày {profile.last_updated_date}")
    return "CV phù hợp vì " + ", ".join(parts) + "."


async def analyze_jd_text_with_ai(jd_text: str) -> JdAnalysisPayload:
    url = f"{settings.ai_service_url.rstrip('/')}/api/v1/jd-search/analyze-text"
    try:
        async with httpx.AsyncClient(timeout=settings.ai_service_timeout_seconds) as client:
            response = await client.post(url, data={"jd_text": jd_text})
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"AI service unreachable: {exc}") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"AI service error: {response.text}")

    payload = response.json()
    data = payload.get("data", payload)
    return JdAnalysisPayload(**data)


def heuristic_jd_analysis(jd_text: str) -> JdAnalysisPayload:
    lowered = normalize_text(jd_text)
    title = "Software Engineer"
    for canonical, aliases in TITLE_SYNONYMS.items():
        if any(alias in lowered for alias in aliases):
            title = canonical.title().replace("Qa", "QA").replace("Ai", "AI")
            break
    required_skills = [skill for skill in COMMON_SKILLS if normalize_skill(skill) in lowered][:8]
    work_mode = "remote" if "remote" in lowered else "hybrid" if "hybrid" in lowered else "onsite" if "onsite" in lowered else "unknown"
    seniority = "senior" if "senior" in lowered else "middle" if "middle" in lowered else "junior" if "junior" in lowered else "unknown"
    location = next((canonical.title() for canonical, aliases in LOCATION_SYNONYMS.items() if any(alias in lowered for alias in aliases)), None)
    years = None
    match = re.search(r"(\d+(?:\.\d+)?)\+?\s+(?:years|year|nam)", lowered)
    if match:
        years = float(match.group(1))
    return JdAnalysisPayload(
        job_title=title,
        job_category="Software Development",
        required_skills=required_skills,
        preferred_skills=[],
        required_experience_years=years,
        salary_text=detect_salary_text(jd_text),
        work_location=location,
        work_mode=work_mode,
        seniority_level=seniority,
        alternative_job_titles=[],
        confidence=0.45,
    )


async def get_jd_analysis(jd_text: str) -> JdAnalysisPayload:
    try:
        analysis = await analyze_jd_text_with_ai(jd_text)
        if analysis.salary_text:
            return analysis
        return analysis.model_copy(update={"salary_text": detect_salary_text(jd_text)})
    except HTTPException:
        return heuristic_jd_analysis(jd_text)


async def search_ranked_cvs_from_jd(
    db: Session,
    jd_text: str,
    top_k: int,
    min_score: float,
    auto_index_missing: bool,
    model_id: str | None,
) -> dict:
    jd_analysis = await get_jd_analysis(jd_text)
    jd_embedding_data = await create_text_embedding(jd_text, model_id)
    resolved_model_id = jd_embedding_data["model_id"]
    jd_vector = [float(value) for value in jd_embedding_data["embedding"]]

    documents = (
        db.query(Document)
        .filter(Document.category == "CV")
        .order_by(Document.created_at.desc(), Document.id.desc())
        .all()
    )
    recency_scores = compute_minmax_recency_scores(documents)

    ranked: list[tuple[CvSearchCandidate, int, datetime]] = []
    skipped: list[dict] = []
    filtered_out = 0
    indexed_missing = 0

    for document in documents:
        embedding = get_document_embedding(db, document.id, resolved_model_id)
        if not embedding and auto_index_missing:
            try:
                await index_cv_document(db, document, resolved_model_id)
                indexed_missing += 1
                embedding = get_document_embedding(db, document.id, resolved_model_id)
            except Exception as exc:
                skipped.append({"id": document.id, "filename": document.filename, "reason": str(exc)})
                continue
        if not embedding:
            skipped.append({"id": document.id, "filename": document.filename, "reason": f"not indexed for model {resolved_model_id}"})
            continue

        cv_vector = parse_embedding(embedding)
        semantic_score = cosine_similarity(jd_vector, cv_vector)
        if semantic_score < min_score:
            continue

        raw_text = (document.raw_text or "").strip()
        if not raw_text:
            path = await ensure_document_file(document)
            raw_text = extract_pdf_text(path)

        profile = build_candidate_profile(document, raw_text)
        title_score = job_title_match_score(jd_analysis, profile)
        skill_score, matched_required, missing_required = skill_match(jd_analysis, profile)
        exp_score = experience_match(jd_analysis, profile)
        loc_score = location_match(jd_analysis, profile)
        freshness = recency_scores.get(document.id, recency_score(profile.last_updated_date))

        if should_filter_out(jd_analysis, profile, title_score, skill_score, exp_score):
            filtered_out += 1
            continue

        total = round(
            title_score * 0.30
            + skill_score * 0.30
            + exp_score * 0.20
            + loc_score * 0.10
            + freshness * 0.10,
            2,
        )
        breakdown = CandidateScoreBreakdown(
            job_title_match_score=round(title_score, 2),
            skill_match_score=round(skill_score, 2),
            experience_match_score=round(exp_score, 2),
            location_match_score=round(loc_score, 2),
            cv_recency_score=round(freshness, 2),
        )
        candidate = CvSearchCandidate(
            id=str(document.id),
            candidate_id=str(document.id),
            candidate_name=profile.candidate_name,
            current_job_title=profile.current_job_title,
            desired_job_title=profile.desired_job_title,
            experience_years=profile.experience_years,
            location=profile.location,
            skills=profile.skills,
            matched_required_skills=matched_required,
            missing_required_skills=missing_required,
            last_updated_date=profile.last_updated_date,
            total_score=total,
            score_breakdown=breakdown,
            recommendation_reason=build_recommendation_reason(profile, matched_required, missing_required, jd_analysis),
            preview_url=document_preview_url(document),
            cloudinary_url=document.cloudinary_url,
            filename=document.filename,
            search_score=round(semantic_score, 6),
            created_at=document.created_at.isoformat() if document.created_at else None,
        )
        ranked.append((candidate, len(matched_required), document.created_at or datetime.min))

    ranked.sort(
        key=lambda item: (
            item[0].total_score,
            item[2],
            item[1],
        ),
        reverse=True,
    )

    results = [item[0].model_dump() for item in ranked[:top_k]]
    summary = {
        "total_cvs": len(documents),
        "indexed_cvs": len(documents) - len(skipped),
        "indexed_missing": indexed_missing,
        "filtered_out": filtered_out,
        "returned": len(results),
        "top_k": top_k,
        "min_score": min_score,
        "auto_index_missing": auto_index_missing,
        "search_mode": "jd_rule_ranking",
        "embedding_model_id": resolved_model_id,
        "sbert_id": jd_embedding_data.get("sbert_id"),
        "embedding_dimension": jd_embedding_data.get("dimension", len(jd_vector)),
        "skipped_cvs": skipped,
        "ranking_weights": {
            "job_title_match_score": 0.30,
            "skill_match_score": 0.30,
            "experience_match_score": 0.20,
            "location_match_score": 0.10,
            "cv_recency_score": 0.10,
        },
    }
    return {
        "success": True,
        "jd_analysis": jd_analysis.model_dump(),
        "total_candidates": len(results),
        "summary": summary,
        **summary,
        "candidates": results,
        "results": results,
        "rerank": None,
    }
