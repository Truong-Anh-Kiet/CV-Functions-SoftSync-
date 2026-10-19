from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==================== COMMON STRUCTURED VIEWS ====================

class PersonalInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    website: Optional[str] = None


class Education(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    field_of_study: Optional[str] = None
    graduation_year: Optional[str] = None
    gpa: Optional[str] = None
    achievements: Optional[list[str]] = None


class WorkExperience(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    description: Optional[str] = None
    achievements: Optional[list[str]] = None


class Skill(BaseModel):
    category: Optional[str] = None
    items: Optional[list[str]] = None


class Project(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    role: Optional[str] = None
    technologies: Optional[list[str]] = None
    url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class Certification(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None
    expiry_date: Optional[str] = None
    credential_id: Optional[str] = None
    url: Optional[str] = None


class Language(BaseModel):
    language: Optional[str] = None
    proficiency: Optional[str] = None


class Achievement(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None


class Publication(BaseModel):
    title: Optional[str] = None
    publisher: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None


# ==================== CV STRUCTURED DATA ====================

class CVStructuredData(BaseModel):
    personal_info: Optional[PersonalInfo] = None
    summary: Optional[str] = None
    skills: Optional[list[Skill]] = None
    education: Optional[list[Education]] = None
    experience: Optional[list[WorkExperience]] = None
    projects: Optional[list[Project]] = None
    certifications: Optional[list[Certification]] = None
    languages: Optional[list[Language]] = None
    achievements: Optional[list[Achievement]] = None
    publications: Optional[list[Publication]] = None
    raw_text: Optional[str] = None


# ==================== JD STRUCTURED DATA ====================

class JDSkillRequirement(BaseModel):
    required: Optional[list[str]] = None
    preferred: Optional[list[str]] = None


class JDEducationRequirement(BaseModel):
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    institution_type: Optional[str] = None


class JDExperienceRequirement(BaseModel):
    years_min: Optional[int] = None
    years_max: Optional[int] = None
    level: Optional[str] = None
    description: Optional[str] = None


class JDResponsibility(BaseModel):
    main: Optional[list[str]] = None
    additional: Optional[list[str]] = None


class JDBenefit(BaseModel):
    salary: Optional[str] = None
    benefits: Optional[list[str]] = None
    culture: Optional[str] = None
    growth: Optional[str] = None


class JDStructuredData(BaseModel):
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    location: Optional[str] = None
    work_type: Optional[str] = None  # Remote, Onsite, Hybrid
    salary_range: Optional[str] = None
    skills: Optional[JDSkillRequirement] = None
    education: Optional[JDEducationRequirement] = None
    experience: Optional[JDExperienceRequirement] = None
    responsibilities: Optional[JDResponsibility] = None
    benefits: Optional[JDBenefit] = None
    application_deadline: Optional[str] = None
    raw_text: Optional[str] = None


# ==================== REQUEST/RESPONSE SCHEMAS ====================

class StructureCVRequest(BaseModel):
    extract_raw_text: bool = True


class StructureJDRequest(BaseModel):
    extract_raw_text: bool = True


class StructureResponse(BaseModel):
    status: str
    message: str
    structured_data: dict | None = None
    raw_text: str | None = None
    processing_time_ms: float | None = None
    model_used: str | None = None


class BatchStructureRequest(BaseModel):
    extract_raw_text: bool = True
    include_metadata: bool = True


class BatchStructureResponse(BaseModel):
    status: str
    total_files: int
    successful: int
    failed: int
    results: list[StructureResponse]


# ==================== SIMPLE VIEW FORMAT (For Matching) ====================

class SimpleStructuredViews(BaseModel):
    """Simple key-value format for CV-JD matching views"""
    # CV Views
    personal_info: Optional[str] = None
    summary: Optional[str] = None
    skills: Optional[str] = None
    education: Optional[str] = None
    experience: Optional[str] = None
    responsibilities: Optional[str] = None
    projects: Optional[str] = None
    certifications: Optional[str] = None

    # JD Views
    job_title: Optional[str] = None
    company_info: Optional[str] = None
    required_skills: Optional[str] = None
    education_requirement: Optional[str] = None
    experience_requirement: Optional[str] = None
    responsibilities_text: Optional[str] = None
    benefits: Optional[str] = None


class ViewLabels(BaseModel):
    """Labels for structured views display"""
    cv_views: dict[str, str] = {
        "personal_info": "Personal Info",
        "summary": "Summary",
        "skills": "Skills",
        "education": "Education",
        "experience": "Experience",
        "responsibilities": "Responsibilities",
        "projects": "Projects",
        "certifications": "Certifications",
    }
    jd_views: dict[str, str] = {
        "job_title": "Job Title",
        "company_info": "Company Info",
        "required_skills": "Required Skills",
        "education_requirement": "Education Requirement",
        "experience_requirement": "Experience Requirement",
        "responsibilities_text": "Responsibilities",
        "benefits": "Benefits",
    }
