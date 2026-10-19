from typing import Literal, Optional

from pydantic import BaseModel, Field


class JdAnalysisPayload(BaseModel):
    job_title: str
    job_category: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    required_experience_years: Optional[float] = None
    salary_text: Optional[str] = None
    work_location: Optional[str] = None
    work_mode: Literal["onsite", "hybrid", "remote", "unknown"] = "unknown"
    seniority_level: Literal["intern", "fresher", "junior", "middle", "senior", "lead", "unknown"] = "unknown"
    alternative_job_titles: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class CandidateScoreBreakdown(BaseModel):
    job_title_match_score: float
    skill_match_score: float
    experience_match_score: float
    location_match_score: float
    cv_recency_score: float


class CvSearchCandidate(BaseModel):
    id: str
    candidate_id: str
    candidate_name: str
    current_job_title: Optional[str] = None
    desired_job_title: Optional[str] = None
    experience_years: Optional[float] = None
    location: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    matched_required_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    last_updated_date: Optional[str] = None
    total_score: float
    score_breakdown: CandidateScoreBreakdown
    recommendation_reason: str
    preview_url: Optional[str] = None
    cloudinary_url: Optional[str] = None
    filename: Optional[str] = None
    search_score: float
    category: Literal["CV"] = "CV"
    created_at: Optional[str] = None
