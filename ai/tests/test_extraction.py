import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

fake_pydantic = ModuleType("pydantic")
fake_pydantic.BaseModel = object
fake_pydantic.Field = lambda default=None, **_: default

fake_config = ModuleType("app.core.config")
fake_config.settings = SimpleNamespace(openai_api_key="", openai_model="test-model")

fake_jd_search = ModuleType("app.schemas.jd_search")
fake_jd_search.JDAnalysis = object

with patch.dict(
    "sys.modules",
    {
        "openai": SimpleNamespace(OpenAI=object),
        "pydantic": fake_pydantic,
        "app.core.config": fake_config,
        "app.schemas.jd_search": fake_jd_search,
    },
):
    from app.services.extraction import _postprocess_cv_structured


class ExtractionHeuristicTests(unittest.TestCase):
    def test_recovers_experience_responsibilities_and_history_from_work_experience_section(self) -> None:
        cv_text = """
Dung Do
AI Engineer

SKILLS
Python
PyTorch
TensorFlow
Docker

WORK EXPERIENCE
SkyMap Global Pte Ltd
AI Engineer
Ha Noi
- Developed and trained ML models for satellite and aerial imagery analysis.
- Built data pipelines including normalization, morphology, and shapefile geometry processing.
- Implemented CNNs for segmentation and time-series classification.

IRD Institute de recherche pour le developpement
Research Intern
Hanoi
- Researched agent-based simulations and mathematical model relationships.
- Programmed simulations using GAMA and Python.
- Presented findings in English to an international research audience.

EDUCATION
Dai hoc
""".strip()

        parsed = {
            "skills": "missing_section",
            "education": "Dai hoc",
            "year_experience": "3 nam",
            "experience": "missing_section",
            "responsibilities": "missing_section",
            "projects": "missing_section",
            "publications": "missing_section",
            "achievement": "missing_section",
            "certification": "missing_section",
            "employment_history": "missing_section",
        }

        result = _postprocess_cv_structured(parsed, cv_text)

        self.assertIn("SkyMap Global Pte Ltd", result["experience"])
        self.assertIn("Developed and trained ML models", result["responsibilities"])
        self.assertIn("Research Intern", result["employment_history"])
        self.assertIn("Python", result["skills"])

    def test_recovers_projects_from_project_section(self) -> None:
        cv_text = """
PROJECTS
AI Resume Matching Platform
Built a resume-to-job matching platform with FastAPI, React, and PostgreSQL.

EDUCATION
Bachelor of Information Technology
""".strip()

        parsed = {
            "skills": "missing_section",
            "education": "Bachelor of Information Technology",
            "year_experience": "missing_section",
            "experience": "missing_section",
            "responsibilities": "missing_section",
            "projects": "missing_section",
            "publications": "missing_section",
            "achievement": "missing_section",
            "certification": "missing_section",
            "employment_history": "missing_section",
        }

        result = _postprocess_cv_structured(parsed, cv_text)

        self.assertIn("AI Resume Matching Platform", result["projects"])

    def test_replaces_weak_work_fields_and_recovers_certifications(self) -> None:
        cv_text = """
DO MINH THO

TECHNICAL SKILLS
Programing in Python, C++
Trellix
Proof of Concept

WORK EXPERIENCE
Viet Hoa Quang Electronic Solutions Joint Stock Company - Vietnamshine
Security Engineer (An Ninh He Thong)
Mar 2025 - Present
- Deployment and configuration FortiPAM/FortiEMS & Mitsubishi Electric.
- Initial and configure server FortiPAM/FortiEMS.
- Configure local admin policy via ZTNA, assign permissions, monitor, and report.

Digital Transformation Joint Stock Company - DTCJSC
Security Engineer
Mar 2024 - Jan 2025
- Research, deploy, and operate Trellix ePO SaaS solution.
- Research and operate NAC solution.

CERTIFICATES
Trellix Intrusion Prevention System (IPS) 10.1 Essentials | Technical Professional
TOEIC LISTENING & READING 550 - (2023)
""".strip()

        parsed = {
            "skills": "Programing in Python, C++\nTrellix\nProof of Concept",
            "education": "Dai hoc",
            "year_experience": "2 nam",
            "experience": "Security Engineer (An Ninh He Thong)",
            "responsibilities": "Programing in Python, C++\nTrellix\nProof of Concept",
            "projects": "missing_section",
            "publications": "missing_section",
            "achievement": "missing_section",
            "certification": "missing_section",
            "employment_history": "Programing in Python, C++\nTrellix\nProof of Concept",
        }

        result = _postprocess_cv_structured(parsed, cv_text)

        self.assertIn("Viet Hoa Quang Electronic Solutions Joint Stock Company", result["experience"])
        self.assertIn("Deployment and configuration FortiPAM/FortiEMS", result["responsibilities"])
        self.assertIn("Digital Transformation Joint Stock Company - DTCJSC", result["employment_history"])
        self.assertIn("Trellix Intrusion Prevention System", result["certification"])

    def test_recovers_sections_from_vietnamese_headings(self) -> None:
        cv_text = """
NGUYEN VAN A

KY NANG
Python
SQL
Cham soc khach hang

KINH NGHIEM LAM VIEC
Cong ty ABC
Chuyen vien ho tro khach hang
01/2023 - 05/2025
- Ho tro khach hang qua email va dien thoai.
- Phoi hop voi doi ky thuat de xu ly su co.

HOC VAN
Cao dang Cong nghe thong tin

CHUNG CHI
Google Data Analytics Certificate
""".strip()

        parsed = {
            "skills": "missing_section",
            "education": "missing_section",
            "year_experience": "2 nam",
            "experience": "missing_section",
            "responsibilities": "missing_section",
            "projects": "missing_section",
            "publications": "missing_section",
            "achievement": "missing_section",
            "certification": "missing_section",
            "employment_history": "missing_section",
        }

        result = _postprocess_cv_structured(parsed, cv_text)

        self.assertIn("Python", result["skills"])
        self.assertIn("Cong ty ABC", result["experience"])
        self.assertIn("Ho tro khach hang qua email", result["responsibilities"])
        self.assertIn("Chuyen vien ho tro khach hang", result["employment_history"])
        self.assertIn("Cao dang Cong nghe thong tin", result["education"])
        self.assertIn("Google Data Analytics Certificate", result["certification"])

    def test_recovers_work_history_from_keyword_signals_without_heading(self) -> None:
        cv_text = """
TRAN VAN B
Software Engineer
Ho Chi Minh

ABC Technology Solutions
Software Engineer
Ho Chi Minh
03/2023 - Present
Developed backend APIs for CRM platform.
Maintained PostgreSQL database and deployment pipeline.
Collaborated with frontend team to ship customer features.

XYZ Digital Company
Intern Developer
06/2022 - 02/2023
Built internal tools for customer service team.

HOC VAN
Dai hoc
""".strip()

        parsed = {
            "skills": "CNTT\nPhan mem",
            "education": "Dai hoc",
            "year_experience": "2 nam",
            "experience": "missing_section",
            "responsibilities": "missing_section",
            "projects": "missing_section",
            "publications": "missing_section",
            "achievement": "missing_section",
            "certification": "missing_section",
            "employment_history": "Software Engineer, Ho Chi Minh",
        }

        result = _postprocess_cv_structured(parsed, cv_text)

        self.assertIn("ABC Technology Solutions", result["experience"])
        self.assertIn("Developed backend APIs for CRM platform", result["responsibilities"])
        self.assertIn("Intern Developer", result["employment_history"])

    def test_replaces_profile_header_noise_with_real_work_history(self) -> None:
        cv_text = """
Dinh Truong Luan
Backend Engineer (Python/FastAPI)

SKILLS
Python
FastAPI

WORK EXPERIENCE
ABC Software Company
Backend Engineer (Python/FastAPI)
Ho Chi Minh
01/2022 - Present
- Built and maintained backend services using Python and FastAPI.
- Designed REST APIs and optimized database queries.

EDUCATION
Dai hoc
""".strip()

        parsed = {
            "skills": "Python, FastAPI",
            "education": "Dai hoc",
            "year_experience": "3 nam",
            "experience": "Backend Engineer (Python/FastAPI)\nDinh Truong Luan\nDai hoc\nNhan vien\n3 nam",
            "responsibilities": "Backend Engineer (Python/FastAPI)\nDinh Truong Luan\nDai hoc\nNhan vien\n3 nam",
            "projects": "missing_section",
            "publications": "missing_section",
            "achievement": "missing_section",
            "certification": "missing_section",
            "employment_history": "Backend Engineer (Python/FastAPI)\nDinh Truong Luan\nDai hoc\nNhan vien\n3 nam",
        }

        result = _postprocess_cv_structured(parsed, cv_text)

        self.assertIn("ABC Software Company", result["experience"])
        self.assertIn("Built and maintained backend services using Python and FastAPI", result["responsibilities"])
        self.assertIn("ABC Software Company", result["employment_history"])
        self.assertNotIn("Dinh Truong Luan", result["responsibilities"])


if __name__ == "__main__":
    unittest.main()
