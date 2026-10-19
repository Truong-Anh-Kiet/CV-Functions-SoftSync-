from typing import Literal, Optional

from pydantic import BaseModel, Field


class JDAnalysis(BaseModel):
    job_title: str = Field(..., description="Primary inferred job title")
    job_category: str = Field(..., description="Broad job category such as Software Development or Data")
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    required_experience_years: Optional[float] = None
    salary_text: Optional[str] = Field(default=None, description="Salary or compensation mentioned in the JD")
    work_location: Optional[str] = None
    work_mode: Literal["onsite", "hybrid", "remote", "unknown"] = "unknown"
    seniority_level: Literal["intern", "fresher", "junior", "middle", "senior", "lead", "unknown"] = "unknown"
    alternative_job_titles: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class JDAnalysisResponse(BaseModel):
    status: str
    data: JDAnalysis
