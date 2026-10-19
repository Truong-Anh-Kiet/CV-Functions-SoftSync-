import json
import re
import time
from pathlib import Path
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.structuring import (
    BatchStructureResponse,
    BatchStructureRequest,
    SimpleStructuredViews,
    StructureResponse,
    ViewLabels,
)
from app.services.document_storage import (
    StoredUpload,
    save_upload_file,
    validate_pdf_file,
    validate_supported_file,
)

router = APIRouter()


# ==================== MOCK DATA FOR STRUCTURING (When AI service not available) ====================

MOCK_CV_STRUCTURED = {
    "personal_info": {
        "name": "Nguyễn Văn A",
        "email": "nguyenvana@email.com",
        "phone": "0912 345 678",
        "location": "TP. Hồ Chí Minh",
        "linkedin": "linkedin.com/in/nguyenvana",
        "website": "nguyenvana.dev"
    },
    "summary": "Kỹ sư phần mềm với 5 năm kinh nghiệm phát triển ứng dụng web và mobile. Chuyên môn về Python, JavaScript, và React. Đam mê áp dụng AI/ML vào sản phẩm thực tế.",
    "skills": [
        {"category": "Programming Languages", "items": ["Python", "JavaScript", "TypeScript", "Java", "SQL"]},
        {"category": "Frontend", "items": ["React", "Vue.js", "Next.js", "Tailwind CSS"]},
        {"category": "Backend", "items": ["FastAPI", "Django", "Node.js", "Express"]},
        {"category": "Database", "items": ["PostgreSQL", "MongoDB", "Redis", "Elasticsearch"]},
        {"category": "DevOps", "items": ["Docker", "Kubernetes", "AWS", "CI/CD"]},
        {"category": "AI/ML", "items": ["TensorFlow", "PyTorch", "OpenAI API", "LangChain"]}
    ],
    "education": [
        {
            "degree": "Kỹ sư Công nghệ Thông tin",
            "institution": "Đại học Bách Khoa TP.HCM",
            "field_of_study": "Công nghệ Thông tin",
            "graduation_year": "2019",
            "gpa": "3.5/4.0",
            "achievements": ["Giải nhất cuộc thi IT Marathon 2018", "Sinh viên xuất sắc năm 2019"]
        }
    ],
    "experience": [
        {
            "job_title": "Senior Software Engineer",
            "company": "TechV Corporation",
            "location": "TP. Hồ Chí Minh",
            "start_date": "2022-01",
            "end_date": None,
            "is_current": True,
            "description": "Phát triển và bảo trì hệ thống thương mại điện tử quy mô lớn với hơn 1 triệu người dùng.",
            "achievements": [
                "Cải thiện hiệu suất hệ thống 40% thông qua tối ưu database và caching",
                "Xây dựng microservices architecture giảm thời gian deploy từ 2 giờ xuống 15 phút",
                "Mentor 3 junior developers và review code hàng tuần"
            ]
        },
        {
            "job_title": "Software Engineer",
            "company": "StartupXYZ",
            "location": "TP. Hồ Chí Minh",
            "start_date": "2019-06",
            "end_date": "2021-12",
            "is_current": False,
            "description": "Phát triển ứng dụng mobile và web cho nền tảng EdTech.",
            "achievements": [
                "Phát triển ứng dụng học tiếng Anh với 100K+ người dùng",
                "Implement real-time chat feature sử dụng WebSocket"
            ]
        }
    ],
    "projects": [
        {
            "name": "AI CV-JD Matching System",
            "description": "Hệ thống so khớp CV và JD sử dụng Multi-view Cross-view Matching architecture với AI.",
            "role": "Tech Lead",
            "technologies": ["Python", "FastAPI", "React", "PostgreSQL", "QDrant"],
            "url": "github.com/nguyenvana/ai-matching"
        },
        {
            "name": "E-Commerce Platform",
            "description": "Nền tảng thương mại điện tử với tính năng AI recommendation và real-time inventory.",
            "role": "Full-stack Developer",
            "technologies": ["Next.js", "Node.js", "MongoDB", "Redis", "Stripe"],
            "url": "ecommerce-platform.demo"
        }
    ],
    "certifications": [
        {"name": "AWS Solutions Architect", "issuer": "Amazon Web Services", "date": "2023-05"},
        {"name": "Google Cloud Professional Data Engineer", "issuer": "Google", "date": "2022-11"},
        {"name": "Deep Learning Specialization", "issuer": "deeplearning.ai", "date": "2023-02"}
    ],
    "languages": [
        {"language": "Tiếng Việt", "proficiency": "Bản ngữ"},
        {"language": "English", "proficiency": "IELTS 7.5"}
    ]
}

MOCK_JD_STRUCTURED = {
    "job_title": "Senior Python Developer",
    "company_name": "Global Tech Solutions",
    "company_description": "Công ty công nghệ hàng đầu chuyên cung cấp giải pháp AI và Cloud cho doanh nghiệp toàn cầu.",
    "location": "TP. Hồ Chí Minh (Hybrid)",
    "work_type": "Hybrid",
    "salary_range": "$2,500 - $4,000",
    "skills": {
        "required": [
            "Python (5+ years)",
            "FastAPI hoặc Django",
            "PostgreSQL / MongoDB",
            "Docker / Kubernetes",
            "AWS hoặc GCP",
            "RESTful API Design",
            "Microservices Architecture"
        ],
        "preferred": [
            "React hoặc Vue.js",
            "CI/CD Pipelines",
            "Machine Learning basics",
            "Agile/Scrum methodology"
        ]
    },
    "education": {
        "degree": "Bachelor's",
        "field_of_study": "Computer Science, Software Engineering, or equivalent",
        "institution_type": "University"
    },
    "experience": {
        "years_min": 5,
        "years_max": 8,
        "level": "Senior",
        "description": "5+ năm kinh nghiệm phát triển phần mềm, ưu tiên ứng viên có kinh nghiệm với hệ thống phân tán và cloud services."
    },
    "responsibilities": {
        "main": [
            "Thiết kế và phát triển các microservices sử dụng Python",
            "Xây dựng và tối ưu hóa RESTful APIs",
            "Implement CI/CD pipelines và automated testing",
            "Collaborate với team để đảm bảo code quality và performance",
            "Mentor junior developers và tham gia code reviews"
        ],
        "additional": [
            "Tham gia technical design discussions",
            "Contribute vào open-source projects",
            "Research và recommend new technologies"
        ]
    },
    "benefits": {
        "salary": "$2,500 - $4,000 + Performance Bonus",
        "benefits": [
            "Annual salary review",
            "Health insurance (Premium package)",
            "15 days annual leave + 5 days sick leave",
            "Professional development budget ($1,000/year)",
            "Latest MacBook/laptop provided",
            "Free lunch and parking"
        ],
        "culture": "Open, collaborative, innovation-driven environment với nhiều team activities và learning opportunities.",
        "growth": "Clear career path với opportunities để grow thành Tech Lead hoặc Principal Engineer."
    },
    "application_deadline": "2024-03-31"
}

MOCK_SIMPLE_CV_VIEWS = {
    "personal_info": "Nguyễn Văn A | nguyenvana@email.com | 0912 345 678 | TP. HCM | linkedin.com/in/nguyenvana",
    "summary": "Kỹ sư phần mềm với 5 năm kinh nghiệm phát triển ứng dụng web và mobile. Chuyên môn về Python, JavaScript, và React. Đam mê áp dụng AI/ML vào sản phẩm thực tế.",
    "skills": "Python, JavaScript, TypeScript, Java, SQL | React, Vue.js, Next.js | FastAPI, Django, Node.js | PostgreSQL, MongoDB, Redis | Docker, Kubernetes, AWS | TensorFlow, PyTorch",
    "education": "Kỹ sư CNTT - Đại học Bách Khoa TP.HCM (2019) - GPA 3.5/4.0",
    "experience": "Senior Software Engineer @ TechV Corp (2022-Present) - Phát triển hệ thống E-commerce quy mô lớn. Software Engineer @ StartupXYZ (2019-2021) - Phát triển ứng dụng EdTech với 100K+ users.",
    "responsibilities": "Phát triển và bảo trì hệ thống | Tối ưu hóa performance | Xây dựng microservices | Mentor junior developers | Code review",
    "projects": "AI CV-JD Matching System (Tech Lead) - Python, FastAPI, React | E-Commerce Platform (Full-stack) - Next.js, Node.js",
    "certifications": "AWS Solutions Architect | Google Cloud Professional Data Engineer | Deep Learning Specialization"
}

MOCK_SIMPLE_JD_VIEWS = {
    "job_title": "Senior Python Developer",
    "company_info": "Global Tech Solutions - Công ty công nghệ hàng đầu chuyên cung cấp giải pháp AI và Cloud",
    "required_skills": "Python (5+ years), FastAPI/Django, PostgreSQL/MongoDB, Docker/Kubernetes, AWS/GCP, RESTful API, Microservices",
    "education_requirement": "Bachelor's in Computer Science or equivalent",
    "experience_requirement": "5+ năm kinh nghiệm phát triển phần mềm, ưu tiên hệ thống phân tán và cloud",
    "responsibilities_text": "Thiết kế microservices Python | Xây dựng RESTful APIs | Implement CI/CD | Code quality | Mentor junior devs",
    "benefits": "$2,500-$4,000 + Bonus | Health insurance | 15 days leave | MacBook provided | Free lunch"
}


# ==================== HELPER FUNCTIONS ====================

def _validate_structure_file(file: UploadFile, field_name: str) -> None:
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    validate_pdf_file(filename)


def _extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from PDF using PyPDF2 or pdfplumber"""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts) if text_parts else ""
    except ImportError:
        try:
            from PyPDF2 import PdfReader
            text_parts = []
            reader = PdfReader(file_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n".join(text_parts) if text_parts else ""
        except ImportError:
            return "Text extraction library not available. Please install pdfplumber or PyPDF2."
    except Exception as e:
        return f"Error extracting text: {str(e)}"


def _call_ai_structuring_service(file_bytes: bytes, file_type: str = "cv") -> dict:
    """Call AI service for structuring (when available)"""
    url = f"{settings.ai_service_url.rstrip('/')}/api/v1/structuring/{file_type}"

    try:
        with httpx.AsyncClient(timeout=settings.ai_service_timeout_seconds) as client:
            response = client.post(
                url,
                files={"file": ("document.pdf", file_bytes, "application/pdf")},
                data={"extract_raw_text": "true"},
            )

        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"AI service error: {response.text}")

        return response.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="AI Structuring Service is not available. Please ensure the AI service is running on port 8001."
        )


def _convert_to_simple_views(structured_data: dict, file_type: str) -> dict:
    """Convert full structured data to simple views for matching"""
    if file_type == "cv":
        parts = []

        if structured_data.get("personal_info"):
            pi = structured_data["personal_info"]
            pi_parts = [pi.get("name", ""), pi.get("email", ""), pi.get("phone", ""),
                       pi.get("location", ""), pi.get("linkedin", "")]
            parts.append(" | ".join(p for p in pi_parts if p))

        if structured_data.get("summary"):
            parts.append(structured_data["summary"])

        if structured_data.get("skills"):
            skill_items = []
            for skill_group in structured_data["skills"]:
                if skill_group.get("items"):
                    skill_items.extend(skill_group["items"])
            if skill_items:
                parts.append(", ".join(skill_items))

        if structured_data.get("education"):
            edu_items = []
            for edu in structured_data["education"]:
                edu_str = f"{edu.get('degree', '')} - {edu.get('institution', '')} ({edu.get('graduation_year', '')})"
                if edu.get("gpa"):
                    edu_str += f" - GPA {edu['gpa']}"
                edu_items.append(edu_str)
            parts.append(" | ".join(edu_items))

        if structured_data.get("experience"):
            exp_parts = []
            for exp in structured_data["experience"]:
                exp_str = f"{exp.get('job_title', '')} @ {exp.get('company', '')} ({exp.get('start_date', '')}-{exp.get('end_date', 'Present') if exp.get('is_current') else exp.get('end_date', '')})"
                if exp.get("description"):
                    exp_str += f" - {exp['description']}"
                exp_parts.append(exp_str)
            parts.append(" | ".join(exp_parts))

        if structured_data.get("projects"):
            proj_parts = []
            for proj in structured_data["projects"]:
                proj_str = f"{proj.get('name', '')} ({proj.get('role', '')}) - {proj.get('description', '')}"
                if proj.get("technologies"):
                    proj_str += f" - {', '.join(proj['technologies'])}"
                proj_parts.append(proj_str)
            parts.append(" | ".join(proj_parts))

        return SimpleStructuredViews(
            personal_info=parts[0] if len(parts) > 0 else None,
            summary=parts[1] if len(parts) > 1 else None,
            skills=parts[2] if len(parts) > 2 else None,
            education=parts[3] if len(parts) > 3 else None,
            experience=parts[4] if len(parts) > 4 else None,
            responsibilities=None,  # CV doesn't have this
            projects=parts[5] if len(parts) > 5 else None,
            certifications=None,  # Can add if needed
        ).model_dump(exclude_none=True)

    else:  # JD
        parts = []

        if structured_data.get("job_title"):
            parts.append(structured_data["job_title"])

        if structured_data.get("company_name"):
            company_info = structured_data["company_name"]
            if structured_data.get("company_description"):
                company_info += f" - {structured_data['company_description']}"
            parts.append(company_info)

        if structured_data.get("skills"):
            skill_parts = []
            if structured_data["skills"].get("required"):
                skill_parts.append("Required: " + ", ".join(structured_data["skills"]["required"]))
            if structured_data["skills"].get("preferred"):
                skill_parts.append("Preferred: " + ", ".join(structured_data["skills"]["preferred"]))
            if skill_parts:
                parts.append(" | ".join(skill_parts))

        if structured_data.get("education"):
            edu = structured_data["education"]
            edu_parts = [edu.get("degree", ""), edu.get("field_of_study", ""), edu.get("institution_type", "")]
            parts.append(" - ".join(p for p in edu_parts if p))

        if structured_data.get("experience"):
            exp = structured_data["experience"]
            exp_parts = []
            if exp.get("years_min"):
                exp_parts.append(f"{exp['years_min']}+ years")
            if exp.get("level"):
                exp_parts.append(exp["level"])
            if exp.get("description"):
                exp_parts.append(exp["description"])
            parts.append(" | ".join(exp_parts))

        if structured_data.get("responsibilities"):
            resp = structured_data["responsibilities"]
            resp_parts = []
            if resp.get("main"):
                resp_parts.extend(resp["main"])
            if resp.get("additional"):
                resp_parts.extend(resp["additional"])
            parts.append(" | ".join(resp_parts))

        if structured_data.get("benefits"):
            benefit_parts = []
            if structured_data["benefits"].get("salary"):
                benefit_parts.append(structured_data["benefits"]["salary"])
            if structured_data["benefits"].get("benefits"):
                benefit_parts.extend(structured_data["benefits"]["benefits"])
            parts.append(" | ".join(benefit_parts))

        return {
            "job_title": parts[0] if len(parts) > 0 else None,
            "company_info": parts[1] if len(parts) > 1 else None,
            "required_skills": parts[2] if len(parts) > 2 else None,
            "education_requirement": parts[3] if len(parts) > 3 else None,
            "experience_requirement": parts[4] if len(parts) > 4 else None,
            "responsibilities_text": parts[5] if len(parts) > 5 else None,
            "benefits": parts[6] if len(parts) > 6 else None,
        }


# ==================== API ENDPOINTS ====================

@router.post("/cv/structure", response_model=StructureResponse)
async def structure_cv(
    file: Annotated[UploadFile, File(description="CV file (PDF, DOC, DOCX)")],
    extract_raw_text: Annotated[bool, Form()] = True,
) -> StructureResponse:
    """
    Structure a CV file into structured JSON format.
    
    Extracts:
    - Personal information (name, email, phone, location)
    - Summary/Objective
    - Skills (categorized)
    - Education history
    - Work experience
    - Projects
    - Certifications
    - Languages
    - Achievements
    """
    _validate_structure_file(file, "file")

    try:
        # Save file temporarily
        stored = save_upload_file(file)
        start_time = time.time()

        # Try to call AI service first
        try:
            with open(stored.path, "rb") as f:
                file_bytes = f.read()

            ai_response = _call_ai_structuring_service(file_bytes, "cv")

            processing_time = (time.time() - start_time) * 1000

            return StructureResponse(
                status="success",
                message="CV structured successfully using AI service",
                structured_data=ai_response.get("structured_data", ai_response),
                raw_text=ai_response.get("raw_text"),
                processing_time_ms=processing_time,
                model_used=ai_response.get("model_used", "AI Service"),
            )
        except HTTPException:
            raise
        except Exception:
            # Fallback to mock data if AI service unavailable
            pass

        # Fallback: Extract text and return mock structured data
        processing_time = (time.time() - start_time) * 1000
        raw_text = _extract_text_from_pdf(stored.path) if extract_raw_text else None

        return StructureResponse(
            status="success",
            message="CV structured using demo data (AI service not available)",
            structured_data=MOCK_CV_STRUCTURED,
            raw_text=raw_text or MOCK_CV_STRUCTURED.get("summary", ""),
            processing_time_ms=processing_time,
            model_used="Demo/Mock",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error structuring CV: {str(e)}")


@router.post("/jd/structure", response_model=StructureResponse)
async def structure_jd(
    file: Annotated[UploadFile, File(description="JD file (PDF, DOC, DOCX)")],
    extract_raw_text: Annotated[bool, Form()] = True,
) -> StructureResponse:
    """
    Structure a Job Description file into structured JSON format.
    
    Extracts:
    - Job title
    - Company information
    - Location and work type
    - Salary range
    - Required/preferred skills
    - Education requirements
    - Experience requirements
    - Responsibilities
    - Benefits
    - Application deadline
    """
    _validate_structure_file(file, "file")

    try:
        # Save file temporarily
        stored = save_upload_file(file)
        start_time = time.time()

        # Try to call AI service first
        try:
            with open(stored.path, "rb") as f:
                file_bytes = f.read()

            ai_response = _call_ai_structuring_service(file_bytes, "jd")

            processing_time = (time.time() - start_time) * 1000

            return StructureResponse(
                status="success",
                message="JD structured successfully using AI service",
                structured_data=ai_response.get("structured_data", ai_response),
                raw_text=ai_response.get("raw_text"),
                processing_time_ms=processing_time,
                model_used=ai_response.get("model_used", "AI Service"),
            )
        except HTTPException:
            raise
        except Exception:
            # Fallback to mock data if AI service unavailable
            pass

        # Fallback: Extract text and return mock structured data
        processing_time = (time.time() - start_time) * 1000
        raw_text = _extract_text_from_pdf(stored.path) if extract_raw_text else None

        return StructureResponse(
            status="success",
            message="JD structured using demo data (AI service not available)",
            structured_data=MOCK_JD_STRUCTURED,
            raw_text=raw_text or MOCK_JD_STRUCTURED.get("job_title", ""),
            processing_time_ms=processing_time,
            model_used="Demo/Mock",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error structuring JD: {str(e)}")


@router.post("/jd/text-structure", response_model=StructureResponse)
async def structure_jd_text(
    jd_text: Annotated[str, Form(description="JD text content")],
    extract_raw_text: Annotated[bool, Form()] = True,
) -> StructureResponse:
    """
    Structure a Job Description from raw text.
    """
    try:
        start_time = time.time()

        # Try to call AI service first
        try:
            url = f"{settings.ai_service_url.rstrip('/')}/api/v1/structuring/jd/text"

            with httpx.AsyncClient(timeout=settings.ai_service_timeout_seconds) as client:
                response = client.post(
                    url,
                    data={"jd_text": jd_text, "extract_raw_text": str(extract_raw_text).lower()},
                )

            if response.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"AI service error: {response.text}")

            ai_response = response.json()
            processing_time = (time.time() - start_time) * 1000

            return StructureResponse(
                status="success",
                message="JD structured successfully using AI service",
                structured_data=ai_response.get("structured_data", ai_response),
                raw_text=jd_text if extract_raw_text else None,
                processing_time_ms=processing_time,
                model_used=ai_response.get("model_used", "AI Service"),
            )
        except httpx.ConnectError:
            pass  # Fallback to mock

        # Fallback
        processing_time = (time.time() - start_time) * 1000

        return StructureResponse(
            status="success",
            message="JD structured using demo data (AI service not available)",
            structured_data=MOCK_JD_STRUCTURED,
            raw_text=jd_text if extract_raw_text else None,
            processing_time_ms=processing_time,
            model_used="Demo/Mock",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error structuring JD text: {str(e)}")


@router.post("/batch", response_model=BatchStructureResponse)
async def batch_structure(
    cv_files: Annotated[list[UploadFile], File(description="CV files")],
    file_type: Annotated[str, Form(description="Type: 'cv' or 'jd'")] = "cv",
    extract_raw_text: Annotated[bool, Form()] = True,
) -> BatchStructureResponse:
    """
    Batch structure multiple CV or JD files.
    """
    if not cv_files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    if file_type not in ["cv", "jd"]:
        raise HTTPException(status_code=400, detail="file_type must be 'cv' or 'jd'")

    results = []
    successful = 0
    failed = 0

    for file in cv_files:
        try:
            _validate_structure_file(file, file.filename)

            # Process each file (using single file endpoint logic)
            stored = save_upload_file(file)
            start_time = time.time()

            try:
                with open(stored.path, "rb") as f:
                    file_bytes = f.read()
                ai_response = _call_ai_structuring_service(file_bytes, file_type)
                processing_time = (time.time() - start_time) * 1000

                results.append(StructureResponse(
                    status="success",
                    message=f"{file_type.upper()} structured successfully",
                    structured_data=ai_response.get("structured_data", ai_response),
                    raw_text=ai_response.get("raw_text"),
                    processing_time_ms=processing_time,
                    model_used=ai_response.get("model_used", "AI Service"),
                ))
                successful += 1
            except HTTPException:
                raise
            except Exception:
                # Fallback to mock
                mock_data = MOCK_CV_STRUCTURED if file_type == "cv" else MOCK_JD_STRUCTURED
                processing_time = (time.time() - start_time) * 1000
                raw_text = _extract_text_from_pdf(stored.path) if extract_raw_text else None

                results.append(StructureResponse(
                    status="success",
                    message=f"{file_type.upper()} structured using demo data",
                    structured_data=mock_data,
                    raw_text=raw_text,
                    processing_time_ms=processing_time,
                    model_used="Demo/Mock",
                ))
                successful += 1

        except HTTPException as e:
            failed += 1
            results.append(StructureResponse(
                status="error",
                message=f"Failed to structure {file.filename}: {e.detail}",
                structured_data=None,
                raw_text=None,
                processing_time_ms=None,
                model_used=None,
            ))
        except Exception as e:
            failed += 1
            results.append(StructureResponse(
                status="error",
                message=f"Failed to structure {file.filename}: {str(e)}",
                structured_data=None,
                raw_text=None,
                processing_time_ms=None,
                model_used=None,
            ))

    return BatchStructureResponse(
        status="completed",
        total_files=len(cv_files),
        successful=successful,
        failed=failed,
        results=results,
    )


@router.get("/views-labels", response_model=ViewLabels)
async def get_view_labels() -> ViewLabels:
    """
    Get the labels for structured views (for UI display).
    """
    return ViewLabels()
