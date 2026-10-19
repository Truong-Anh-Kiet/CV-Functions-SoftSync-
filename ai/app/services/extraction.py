import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.jd_search import JDAnalysis


CV_VIEWS = [
    "skills",
    "education",
    "year_experience",
    "experience",
    "responsibilities",
    "projects",
    "publications",
    "achievement",
    "certification",
    "employment_history",
]

JD_VIEWS = [
    "skills",
    "education",
    "year_experience_requirement",
    "experience_requirement",
    "responsibilities",
]


class CVStructured(BaseModel):
    skills: Optional[str] = Field(None, description="Technical and soft skills")
    education: Optional[str] = Field(None, description="Education background")
    year_experience: Optional[str] = Field(None, description="Total years of experience")
    experience: Optional[str] = Field(None, description="Work experience description")
    responsibilities: Optional[str] = Field(None, description="Job responsibilities held")
    projects: Optional[str] = Field(None, description="Projects")
    publications: Optional[str] = Field(None, description="Publications")
    achievement: Optional[str] = Field(None, description="Achievements")
    certification: Optional[str] = Field(None, description="Certifications")
    employment_history: Optional[str] = Field(None, description="Employment history")


class JDStructured(BaseModel):
    skills: Optional[str] = Field(None, description="Required skills")
    education: Optional[str] = Field(None, description="Required education")
    year_experience_requirement: Optional[str] = Field(None, description="Required years of experience")
    experience_requirement: Optional[str] = Field(None, description="Required experience type")
    responsibilities: Optional[str] = Field(None, description="Job responsibilities")


CV_SYSTEM_PROMPT = """
You are an expert resume parser.
Extract the CV into exactly the provided JSON schema.
Rules:
- Use "missing_section" when a field is not found.
- Do not invent information.
- Keep the source language. Do not translate.
- The input may come from visually complex PDFs: multi-column resumes, tables, sidebars, icons,
  text boxes, mixed Vietnamese/English headings, flattened lines, or imperfect PDF text extraction.
- Reconstruct the resume by using visual and semantic evidence together: nearby lines, date ranges,
  company names, job titles, bullet lists, section headings, and grouped text blocks.
- Read the entire CV before extracting. Do not focus only on the first page. Do not skip later pages,
  side columns, projects pages, certification blocks, or skills blocks shown in another column.
- Repair split tokens caused by PDF extraction when the meaning is obvious, for example:
  `Type\\nScript` -> `TypeScript`, `Postgre\\nSQL` -> `PostgreSQL`, `Pre\\nsent` -> `Present`.
- Map sections such as "Work Experience", "Professional Experience", "Employment History",
  "Research Experience", internships, "Kinh nghiem lam viec", "Qua trinh cong tac", and similar
  headings into `experience`.
- If the CV has a work-experience section, `experience` must contain the full work block,
  including company names, job titles, dates, and major work details. Do not return only a
  single job title when the section contains more information.
- Put role/company/date history under `employment_history` when present.
- Format `employment_history` as compact evidence-rich lines, one role per line when possible:
  `Company | Title | Date range | Location`.
- Put concrete task bullets, duties, ownership, and work performed under `responsibilities`
  when present. Prefer real bullet content from the CV over summaries.
- Never copy the `skills` block into `experience`, `responsibilities`, or `employment_history`
  unless the CV truly has no work-experience content.
- Put named project sections, project-based work, thesis work, and research projects under `projects`.
- Extract `certification` from sections such as "Certifications", "Certificates", "Licenses",
  "Courses", "Chung chi", "Khoa hoc", or named credentials/exams if they are listed.
- Pay close attention to sections such as "Skills", "Technical Skills", "Tech Stack", "Competencies",
  "Languages", "Frameworks", "Tools", "Databases", "Backend", "Frontend", "DevOps", "CI/CD",
  "Ky nang", and "Cong nghe".
- If the CV lists skill categories with bullets or comma-separated items, preserve them inside `skills`
  instead of marking the field as missing.
- If a "Skills" block exists anywhere in the CV, `skills` must contain that evidence.
- Prefer atomic, specific skills and technologies over generic categories. If the CV contains specific
  technologies such as `Python`, `Docker`, `ReactJS`, `PostgreSQL`, do not return only generic labels
  like `CNTT`, `Phan mem`, `Lap trinh`, or `Cong nghe thong tin`.
- If a work-experience section exists, do not leave both `responsibilities` and `employment_history`
  as "missing_section" unless the section truly contains no usable work details.
- If there is no explicit heading but you can see repeated patterns of company + title + dates + tasks,
  treat that as work experience and extract it.
- If dates, titles, and companies are spread across adjacent lines because of PDF layout, merge them
  into the correct field instead of dropping them.
- Do not confuse `projects` with official `work experience`. Do not copy project-only content into
  `responsibilities` or `employment_history` unless the CV clearly presents that project as real work.
- Return only valid JSON matching the schema.
""".strip()

CV_SKILLS_REPAIR_PROMPT = """
Re-extract this CV using the same schema, but focus on recovering `skills`.
Rules:
- Look carefully for blocks titled "Skills", "Technical Skills", "Tech Stack", "Competencies",
  "Languages", "Frameworks", "Tools", "Databases", "Backend", "Frontend", "DevOps", "CI/CD".
- Preserve category labels and bullet items in the `skills` field.
- Recover skills from all pages and all columns, not only the main column.
- Repair split tokens when obvious, such as `Type\\nScript` -> `TypeScript` and
  `Postgre\\nSQL` -> `PostgreSQL`.
- Prefer atomic, concrete technologies, tools, frameworks, databases, cloud services, and domain skills.
- If specific skills are present, do not return only generic categories like `CNTT`, `Phan mem`,
  `Lap trinh`, or `Cong nghe thong tin`.
- Use "missing_section" only if there is truly no skills-related content in the CV.
- Do not invent information.
- Keep the source language. Do not translate.
- Return only valid JSON matching the schema.
""".strip()

CV_EXPERIENCE_REPAIR_PROMPT = """
Re-extract this CV using the same schema, but focus on recovering work-history information.
Rules:
- Carefully read sections such as "Work Experience", "Professional Experience", "Employment History",
  "Research Experience", internships, project-based employment, "Kinh nghiem lam viec",
  and "Qua trinh cong tac".
- Read all pages and all columns before deciding a section is missing.
- `experience` must contain the actual work-experience content, not just a job title.
- `responsibilities` must contain task bullets, duties, or concrete work performed from each role.
- `employment_history` must contain company, title, date range, and location when present.
- `certification` must contain certificates, credentials, courses, exams, or licenses when listed.
- Recover information even when the PDF text is fragmented across columns, sidebars, or short lines.
- Repair split words and fragmented lines when the meaning is clear.
- If there is a clear company-title-date pattern, extract it as employment history even if the section
  heading is missing or damaged.
- Use important work keys aggressively: job titles, company names, date ranges, locations, reporting lines,
  project ownership, deployment/build/analysis verbs, and repeated task bullets.
- Never fill `experience`, `responsibilities`, or `employment_history` with content copied from `skills`
  if the CV contains work history.
- Use "missing_section" only when the requested evidence truly does not exist.
- Do not invent information.
- Keep the source language. Do not translate.
- Return only valid JSON matching the schema.
""".strip()

CV_COMPLETENESS_REPAIR_PROMPT = """
Re-extract this CV using the same schema, but focus on completeness for difficult PDF layouts.
Rules:
- The CV may be multi-column, partially flattened, or mixed between Vietnamese and English.
- Recover content from section headings, nearby text blocks, dates, company names, job titles,
  bullet points, and credential lines.
- Read all pages before returning any field as `missing_section`.
- Repair split technology names and split date words when the intended token is obvious.
- Prefer extracting partial but real evidence over returning "missing_section".
- `skills` should keep skill lists, categories, tools, technologies, and domains.
- Prefer specific skills over generic labels whenever both are present.
- `experience` should keep the full work-experience narrative when any work history is present.
- `responsibilities` should keep concrete tasks and duties.
- `employment_history` should keep company, title, date range, and location when present.
- `projects`, `achievement`, and `certification` should be filled whenever there is explicit evidence.
- Do not confuse project sections with official employment history.
- Do not invent information.
- Keep the source language. Do not translate.
- Return only valid JSON matching the schema.
""".strip()

CV_ANCILLARY_REPAIR_PROMPT = """
Re-extract this CV using the same schema, but focus only on recovering `projects`, `publications`,
`achievement`, and `certification`.
Rules:
- Read all pages and all columns before deciding these fields are missing.
- Look for sections such as "Projects", "Personal Projects", "Academic Projects", "Project Experience",
  "Publications", "Papers", "Conference", "Journal", "Achievements", "Awards", "Honors", "Scholarships",
  "Certifications", "Certificates", "Licenses", "Training", and their Vietnamese equivalents.
- Recover these fields even when the PDF text is fragmented, flattened, or split across short lines.
- Preserve explicit project names, publication titles, award names, and certification names exactly as shown.
- Do not confuse work experience bullets with projects unless the CV explicitly presents them as projects.
- Do not invent information.
- Keep the source language. Do not translate.
- Return only valid JSON matching the schema.
""".strip()

JD_SYSTEM_PROMPT = """
You are an expert job description parser.
Extract the JD into exactly the provided JSON schema.
Rules:
- Use "missing_section" when a field is not found.
- Do not invent information.
- Keep the source language. Do not translate.
- Return only valid JSON matching the schema.
""".strip()

JD_ANALYSIS_SYSTEM_PROMPT = """
You analyze a job description and infer a hiring search profile.
Rules:
- Use evidence from title, responsibilities, skills, experience and technology stack.
- Extract salary/compensation text when it is explicitly mentioned.
- Normalize equivalent titles and skills when appropriate.
- Return only valid JSON matching the schema.
- If uncertain, still choose the best primary title, provide 2-5 alternative_job_titles and set confidence accordingly.
- preferred_skills should exclude skills already listed in required_skills.
- work_mode must be one of: onsite, hybrid, remote, unknown.
- seniority_level must be one of: intern, fresher, junior, middle, senior, lead, unknown.
- confidence must be between 0 and 1.
- Do not invent facts not supported by the JD.
""".strip()


@lru_cache
def get_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


def upload_pdf(pdf_path: str) -> str:
    with open(pdf_path, "rb") as file_obj:
        uploaded = get_client().files.create(file=file_obj, purpose="user_data")
    return uploaded.id


_SKILLS_SECTION_PATTERNS = (
    r"skills?",
    r"technical skills?",
    r"tech(?:nology)? stack",
    r"core competencies",
    r"competencies",
    r"ky nang",
    r"ky nang chuyen mon",
    r"nang luc",
    r"cong nghe",
)

_SKILLS_SUBSECTION_PATTERNS = (
    r"backend(?: development| & apis?)?",
    r"frontend",
    r"languages?",
    r"programming languages?",
    r"frameworks?",
    r"libraries?",
    r"databases?",
    r"tools?",
    r"tooling",
    r"cloud",
    r"devops",
    r"ci/cd",
    r"system design",
    r"soft skills?",
    r"testing",
    r"mobile",
    r"ky nang mem",
    r"ngon ngu",
    r"cong cu",
)

_MAJOR_SECTION_PATTERNS = (
    r"summary",
    r"profile",
    r"objective",
    r"experience",
    r"work experience",
    r"professional experience",
    r"employment history",
    r"projects?",
    r"education",
    r"certifications?",
    r"awards?",
    r"publications?",
    r"activities",
    r"contact",
    r"references?",
    r"tom tat",
    r"gioi thieu",
    r"muc tieu nghe nghiep",
    r"ky nang",
    r"kinh nghiem",
    r"kinh nghiem lam viec",
    r"qua trinh cong tac",
    r"hoc van",
    r"trinh do hoc van",
    r"du an",
    r"chung chi",
    r"giai thuong",
)

_EDUCATION_SECTION_PATTERNS = (
    r"education",
    r"academic background",
    r"academic history",
    r"qualifications?",
    r"hoc van",
    r"trinh do hoc van",
    r"qua trinh hoc tap",
)

_EXPERIENCE_SECTION_PATTERNS = (
    r"experience",
    r"work experience",
    r"professional experience",
    r"employment history",
    r"work history",
    r"research experience",
    r"internships?",
    r"kinh nghiem",
    r"kinh nghiem lam viec",
    r"qua trinh cong tac",
    r"qua trinh lam viec",
    r"kinh nghiem nghien cuu",
    r"thuc tap",
)

_PROJECT_SECTION_PATTERNS = (
    r"projects?",
    r"personal projects?",
    r"academic projects?",
    r"side projects?",
    r"selected projects?",
    r"project experience",
    r"project activities",
    r"research projects?",
    r"du an",
    r"cac du an",
)

_PUBLICATION_SECTION_PATTERNS = (
    r"publications?",
    r"research publications?",
    r"conference papers?",
    r"journals?",
    r"conferences?",
    r"papers?",
    r"cong bo",
    r"bai bao",
)

_ACHIEVEMENT_SECTION_PATTERNS = (
    r"achievements?",
    r"awards?",
    r"honors?",
    r"scholarships?",
    r"accomplishments?",
    r"thanh tich",
    r"giai thuong",
)

_CERTIFICATION_SECTION_PATTERNS = (
    r"certifications?",
    r"certificates?",
    r"credentials?",
    r"licenses?",
    r"license & certifications?",
    r"training",
    r"chung chi",
    r"bang cap",
    r"khoa hoc",
    r"dao tao",
)

_RESPONSIBILITY_PREFIXES = (
    "developed",
    "deployment",
    "deploy",
    "configured",
    "configure",
    "configuration",
    "designed",
    "built",
    "implemented",
    "created",
    "led",
    "managed",
    "maintained",
    "optimized",
    "improved",
    "delivered",
    "deployed",
    "collaborated",
    "researched",
    "programmed",
    "presented",
    "authored",
    "analyzed",
    "trained",
    "supported",
    "operated",
    "operate",
    "initial",
    "installed",
    "owned",
    "architected",
)

_JOB_TITLE_KEYWORDS = (
    "engineer",
    "developer",
    "manager",
    "analyst",
    "specialist",
    "consultant",
    "intern",
    "researcher",
    "research",
    "architect",
    "lead",
    "tester",
    "qa",
    "qc",
    "devops",
    "administrator",
    "admin",
    "support",
    "executive",
    "officer",
    "teacher",
    "lecturer",
    "trainer",
    "designer",
    "accountant",
    "sales",
    "marketing",
    "customer service",
    "software engineer",
    "backend",
    "frontend",
    "full stack",
    "security engineer",
    "ai engineer",
    "data engineer",
    "data analyst",
    "chuyen vien",
    "ky su",
    "lap trinh vien",
    "nhan vien",
    "quan ly",
    "truong nhom",
    "thuc tap",
    "thuc tap sinh",
)

_COMPANY_KEYWORDS = (
    "company",
    "co.,",
    "co ",
    "corp",
    "corporation",
    "ltd",
    "llc",
    "inc",
    "jsc",
    "joint stock",
    "group",
    "bank",
    "university",
    "college",
    "institute",
    "school",
    "hospital",
    "center",
    "centre",
    "studio",
    "agency",
    "solutions",
    "technologies",
    "technology",
    "systems",
    "software",
    "cong ty",
    "tap doan",
    "ngan hang",
    "benh vien",
)

_LOCATION_KEYWORDS = (
    "ha noi",
    "hanoi",
    "ho chi minh",
    "hcm",
    "da nang",
    "can tho",
    "vietnam",
    "viet nam",
    "remote",
    "onsite",
    "hybrid",
)

_PROJECT_LINE_KEYWORDS = (
    "project",
    "system",
    "platform",
    "application",
    "app",
    "website",
    "portal",
    "dashboard",
    "crm",
    "erp",
    "du an",
)

_PUBLICATION_LINE_KEYWORDS = (
    "journal",
    "conference",
    "proceedings",
    "paper",
    "publication",
    "published",
    "doi",
    "isbn",
    "issn",
    "arxiv",
    "luan van",
    "bai bao",
)

_ACHIEVEMENT_LINE_KEYWORDS = (
    "award",
    "awarded",
    "honor",
    "honour",
    "scholarship",
    "winner",
    "runner-up",
    "finalist",
    "top ",
    "olympic",
    "giai",
    "hoc bong",
    "thanh tich",
)

_CERTIFICATION_LINE_KEYWORDS = (
    "certificate",
    "certification",
    "certified",
    "credential",
    "license",
    "licence",
    "toeic",
    "ielts",
    "toeffl",
    "aws",
    "azure",
    "gcp",
    "oracle",
    "coursera",
    "udemy",
    "training",
    "chung chi",
)

_ACHIEVEMENT_IMPACT_KEYWORDS = (
    "achiev",
    "delivered",
    "reduced",
    "improved",
    "increased",
    "optimized",
    "automated",
    "enabled",
    "deployed",
    "production-ready",
    "zero cloud dependency",
    "daily users",
    "applications per month",
    "processing time",
)


def _normalize_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t-â€¢*:")


def _normalize_text_block(value: str) -> str:
    lines = [_normalize_line(line) for line in value.splitlines()]
    cleaned = [line for line in lines if line]
    return "\n".join(cleaned).strip()


def _normalized_nonempty_lines(value: Optional[str]) -> list[str]:
    if value is None:
        return []
    return [line for line in (_normalize_line(part) for part in str(value).splitlines()) if line]


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _strip_leading_marker(value: str) -> str:
    return re.sub(r"^[\s•·▪‣\-\*\uFFFF\uFFFD]+", "", value).strip()


def _is_missing_section(value: Optional[str]) -> bool:
    if value is None:
        return True
    return str(value).strip().lower() in {"", "none", "missing_section"}


def _matches_heading(line: str, patterns: tuple[str, ...]) -> bool:
    normalized = _normalize_line(line).lower()
    if not normalized:
        return False
    normalized_ascii = _strip_accents(normalized)
    return any(
        re.fullmatch(pattern, candidate, flags=re.IGNORECASE)
        for pattern in patterns
        for candidate in (normalized, normalized_ascii)
    )


def _looks_like_major_heading(line: str) -> bool:
    normalized = _normalize_line(line)
    if not normalized:
        return False
    if _matches_heading(normalized, _SKILLS_SECTION_PATTERNS) or _matches_heading(normalized, _SKILLS_SUBSECTION_PATTERNS):
        return False
    if _matches_heading(normalized, _MAJOR_SECTION_PATTERNS):
        return True
    return normalized.isupper() and len(normalized.split()) <= 5


def _extract_skills_from_text(cv_text: str) -> Optional[str]:
    lines = [line.rstrip() for line in cv_text.splitlines()]
    for index, raw_line in enumerate(lines):
        if not _matches_heading(raw_line, _SKILLS_SECTION_PATTERNS):
            continue

        collected: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            current = lines[cursor].strip()
            if not current:
                cursor += 1
                continue
            if _looks_like_major_heading(current):
                break
            collected.append(_normalize_line(current))
            cursor += 1

        if collected:
            return "\n".join(collected)

    grouped_lines: list[str] = []
    for index, raw_line in enumerate(lines):
        if not _matches_heading(raw_line, _SKILLS_SUBSECTION_PATTERNS):
            continue
        block = [_normalize_line(raw_line)]
        cursor = index + 1
        while cursor < len(lines):
            current = lines[cursor].strip()
            if not current:
                break
            if _looks_like_major_heading(current):
                break
            block.append(_normalize_line(current))
            cursor += 1
        if len(block) > 1:
            grouped_lines.extend(block)

    if grouped_lines:
        return "\n".join(grouped_lines)
    return None


def _extract_section_from_text(cv_text: str, heading_patterns: tuple[str, ...]) -> Optional[str]:
    lines = [line.rstrip() for line in cv_text.splitlines()]
    blocks: list[str] = []

    for index, raw_line in enumerate(lines):
        if not _matches_heading(raw_line, heading_patterns):
            continue

        collected: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            current = lines[cursor].strip()
            if not current:
                cursor += 1
                continue
            if _looks_like_major_heading(current):
                break
            collected.append(_normalize_line(current))
            cursor += 1

        block = _normalize_text_block("\n".join(collected))
        if block and block not in blocks:
            blocks.append(block)

    if blocks:
        return "\n\n".join(blocks)
    return None


def _has_section_heading(cv_text: str, heading_patterns: tuple[str, ...]) -> bool:
    return any(_matches_heading(line, heading_patterns) for line in cv_text.splitlines())


def _extract_year_experience_from_text(cv_text: str) -> Optional[str]:
    patterns = (
        r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience",
        r"(\d+(?:\.\d+)?)\+?\s*(?:nam|n[aă]m)\s+kinh\s+nghi[eẹ]m",
        r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?|nam|n[aă]m)",
    )
    for pattern in patterns:
        match = re.search(pattern, cv_text, flags=re.IGNORECASE)
        if match:
            return _normalize_line(match.group(0))
    return None


def _looks_like_year_experience_line(line: str) -> bool:
    normalized = _strip_accents(_normalize_line(line).lower())
    return bool(
        re.search(
            r"\b\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|nam)\b(?:\s+(?:of\s+)?experience|\s+kinh\s+nghiem)?",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def _looks_like_education_line(line: str) -> bool:
    normalized = _strip_accents(_normalize_line(line).lower())
    return bool(
        re.search(
            r"\b(dai hoc|cao dang|cu nhan|thac si|tien si|bachelor|master|phd|university|college|hoc vien)\b",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def _looks_like_person_name(line: str) -> bool:
    normalized = _normalize_line(line)
    normalized_ascii = _strip_accents(normalized)
    if len(normalized_ascii.split()) < 2 or len(normalized_ascii.split()) > 5:
        return False
    if _looks_like_job_title(normalized) or _looks_like_company(normalized) or _looks_like_location(normalized):
        return False
    if _looks_like_education_line(normalized) or _looks_like_year_experience_line(normalized):
        return False
    return bool(re.fullmatch(r"[A-Za-zÀ-ỹ ]+", normalized)) and normalized_ascii.replace(" ", "").isalpha()


def _contains_keyword(line: str, keywords: tuple[str, ...]) -> bool:
    lowered = _strip_accents(_normalize_line(line).lower())
    return any(keyword in lowered for keyword in keywords)


def _looks_like_date_range(line: str) -> bool:
    normalized = _strip_accents(_normalize_line(line).lower())
    patterns = (
        r"\b(?:19|20)\d{2}\b",
        r"\b\d{1,2}[/-]\d{4}\b",
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\b",
        r"\b(?:present|current|now)\b",
        r"\b(?:tu|from)\b.*\b(?:den|to|-|present|current)\b",
    )
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)


def _looks_like_location(line: str) -> bool:
    normalized = _strip_accents(_normalize_line(line).lower())
    if _contains_keyword(normalized, _LOCATION_KEYWORDS):
        return True
    return bool(re.fullmatch(r"[A-Za-zÀ-ỹ0-9 .,/()-]{2,40}", line) and "," in line)


def _looks_like_job_title(line: str) -> bool:
    normalized = _strip_accents(_normalize_line(line).lower())
    if len(normalized.split()) > 8:
        return False
    return _contains_keyword(normalized, _JOB_TITLE_KEYWORDS)


def _looks_like_company(line: str) -> bool:
    normalized = _strip_accents(_normalize_line(line).lower())
    if _contains_keyword(normalized, _COMPANY_KEYWORDS):
        return True
    titleish = bool(re.search(r"\b(?:company|group|bank|university|institute|solutions|technology|software)\b", normalized))
    return titleish and len(normalized.split()) >= 2


def _looks_like_responsibility_line(line: str) -> bool:
    stripped = line.lstrip()
    normalized = _normalize_line(stripped)
    if not normalized:
        return False
    if stripped.startswith(("-", "*", "â€¢", "Â·", "â–ª", "â€£")):
        return True
    lowered = _strip_accents(normalized.lower())
    if lowered.startswith(_RESPONSIBILITY_PREFIXES):
        return True
    return bool(
        re.match(
            r"^(research(?:ed)?|deployment|deploy(?:ed)?|configuration|configure(?:d)?|initial|operate(?:d)?|installed?|build(?:ing)?|support(?:ed)?|maintain(?:ed)?|implement(?:ed)?)\b",
            lowered,
            flags=re.IGNORECASE,
        )
    )


def _work_signal_score(block_text: Optional[str]) -> int:
    if not block_text:
        return -1
    lines = _normalized_nonempty_lines(block_text)
    if not lines:
        return -1

    score = len(lines)
    score += sum(3 for line in lines if _looks_like_responsibility_line(line))
    score += sum(2 for line in lines if _looks_like_date_range(line))
    score += sum(2 for line in lines if _looks_like_job_title(line))
    score += sum(2 for line in lines if _looks_like_company(line))
    score += sum(1 for line in lines if _looks_like_location(line))
    score -= sum(2 for line in lines if _looks_like_education_line(line))
    score -= sum(2 for line in lines if _looks_like_year_experience_line(line))
    score -= sum(1 for line in lines if _looks_like_person_name(line))
    return score


def _looks_like_profile_header_block(block_text: Optional[str]) -> bool:
    if not block_text:
        return False
    lines = _normalized_nonempty_lines(block_text)
    if not lines:
        return False

    title_count = sum(1 for line in lines if _looks_like_job_title(line))
    company_count = sum(1 for line in lines if _looks_like_company(line))
    date_count = sum(1 for line in lines if _looks_like_date_range(line))
    responsibility_count = sum(1 for line in lines if _looks_like_responsibility_line(line))
    education_count = sum(1 for line in lines if _looks_like_education_line(line))
    year_count = sum(1 for line in lines if _looks_like_year_experience_line(line))
    name_count = sum(1 for line in lines if _looks_like_person_name(line))

    return (
        title_count >= 1
        and company_count == 0
        and date_count == 0
        and responsibility_count == 0
        and (education_count >= 1 or year_count >= 1 or name_count >= 1)
    )


def _extract_work_keyword_block(cv_text: str) -> Optional[str]:
    lines = [line for line in _normalized_nonempty_lines(cv_text) if not _matches_heading(line, _SKILLS_SECTION_PATTERNS)]
    if not lines:
        return None

    blocks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if _looks_like_major_heading(line):
            index += 1
            continue

        window = lines[index:index + 6]
        has_title = any(_looks_like_job_title(item) for item in window[:3])
        has_company = any(_looks_like_company(item) for item in window[:3])
        has_date = any(_looks_like_date_range(item) for item in window[:4])
        responsibility_hits = sum(1 for item in window[1:] if _looks_like_responsibility_line(item))

        if not ((has_title and (has_company or has_date or responsibility_hits)) or (has_company and (has_title or has_date or responsibility_hits >= 1))):
            index += 1
            continue

        start = index
        if start > 0 and not _looks_like_major_heading(lines[start - 1]):
            previous = lines[start - 1]
            if (
                _looks_like_company(previous)
                or _looks_like_job_title(previous)
                or _looks_like_date_range(previous)
                or _looks_like_location(previous)
            ):
                start -= 1

        end = start
        while end < len(lines):
            current = lines[end]
            if end > start and _looks_like_major_heading(current):
                break

            next_window = lines[end:end + 5]
            next_has_title = any(_looks_like_job_title(item) for item in next_window[:2])
            next_has_company = any(_looks_like_company(item) for item in next_window[:2])
            next_has_date = any(_looks_like_date_range(item) for item in next_window[:3])
            if end > start + 2 and next_has_title and next_has_company and next_has_date:
                break
            end += 1

        block = _normalize_text_block("\n".join(lines[start:end]))
        if block and _work_signal_score(block) >= 8 and block not in blocks:
            blocks.append(block)
        index = max(end, index + 1)

    if not blocks:
        return None
    return "\n\n".join(blocks)


def _extract_responsibilities_from_text(block_text: str) -> Optional[str]:
    lines = [line.strip() for line in block_text.splitlines() if line.strip()]
    if not lines:
        return None

    action_pattern = re.compile(
        r"^(research(?:ed)?|deployment|deploy(?:ed)?|configuration|configure(?:d)?|initial|operate(?:d)?|installed?)\b",
        flags=re.IGNORECASE,
    )

    bullet_lines: list[str] = []
    heuristic_lines: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        normalized = _normalize_line(stripped)
        if not normalized:
            continue

        if stripped.startswith(("-", "*", "•", "·", "▪", "‣")):
            bullet_lines.append(normalized)
            continue

        lowered = normalized.lower()
        if lowered.startswith(_RESPONSIBILITY_PREFIXES) or action_pattern.match(lowered):
            heuristic_lines.append(normalized)

    selected = bullet_lines or heuristic_lines
    if selected:
        return "\n".join(selected)
    return None


def _extract_employment_history_from_text(block_text: str) -> Optional[str]:
    lines = [line.strip() for line in block_text.splitlines() if line.strip()]
    if not lines:
        return None

    history_lines: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        normalized = _normalize_line(stripped)
        if not normalized:
            continue
        if stripped.startswith(("-", "*", "•", "·", "▪", "‣")):
            continue

        lowered = normalized.lower()
        if lowered.startswith(_RESPONSIBILITY_PREFIXES):
            continue

        words = normalized.split()
        if len(words) <= 14 or re.search(r"(19|20)\d{2}|present|current|intern|engineer|developer|research|manager|analyst", lowered):
            history_lines.append(normalized)

    if history_lines:
        return "\n".join(history_lines[:12])
    return None


def _looks_like_project_heading_line(line: str) -> bool:
    normalized = _normalize_line(line)
    ascii_line = _strip_accents(normalized.lower())
    if not normalized or _looks_like_major_heading(normalized):
        return False
    if _looks_like_date_range(normalized) or _looks_like_company(normalized) or _looks_like_job_title(normalized):
        return False
    if _looks_like_responsibility_line(normalized):
        return False
    if len(normalized.split()) < 2 or len(normalized.split()) > 12:
        return False
    if normalized.endswith(".") or "," in normalized:
        return False
    if "project" in ascii_line or "chatbot" in ascii_line or "system" in ascii_line or "platform" in ascii_line:
        return True
    return "—" in normalized or " – " in normalized


def _extract_projects_from_experience_block(block_text: Optional[str]) -> Optional[str]:
    if not block_text:
        return None

    lines = _normalized_nonempty_lines(block_text)
    projects: list[str] = []
    for index, line in enumerate(lines):
        if not _looks_like_project_heading_line(line):
            continue

        next_lines = lines[index + 1:index + 4]
        if any(_looks_like_responsibility_line(candidate) for candidate in next_lines):
            projects.append(line.lstrip("￿•*- ").strip())

    deduped = _dedupe_preserving_order(projects)
    if deduped:
        return "\n".join(deduped[:12])
    return None


def _extract_achievement_from_text(cv_text: str, experience_block: Optional[str]) -> Optional[str]:
    candidate_lines = _normalized_nonempty_lines(cv_text)
    if experience_block:
        candidate_lines = _normalized_nonempty_lines(experience_block) + candidate_lines

    achievements: list[str] = []
    for line in candidate_lines:
        normalized = _normalize_line(line)
        lowered = _strip_accents(normalized.lower())
        if _looks_like_major_heading(normalized):
            continue
        if _looks_like_project_heading_line(normalized):
            continue
        if not any(keyword in lowered for keyword in _ACHIEVEMENT_IMPACT_KEYWORDS):
            continue
        if not re.search(r"\d|production|users|applications|time|accuracy|latency|zero", lowered, flags=re.IGNORECASE):
            continue
        achievements.append(normalized)

    deduped = _remove_substring_duplicates(achievements)
    if deduped:
        return "\n".join(deduped[:10])
    return None


def _has_leading_marker(line: str) -> bool:
    return _strip_leading_marker(line) != line.lstrip()


def _looks_like_responsibility_line_v2(line: str) -> bool:
    normalized = _normalize_line(line)
    if not normalized:
        return False
    if _has_leading_marker(line):
        return True
    lowered = _strip_accents(normalized.lower())
    if lowered.startswith(_RESPONSIBILITY_PREFIXES):
        return True
    return bool(
        re.match(
            r"^(research(?:ed)?|deployment|deploy(?:ed)?|configuration|configure(?:d)?|initial|operate(?:d)?|installed?|build(?:ing)?|support(?:ed)?|maintain(?:ed)?|implement(?:ed)?)\b",
            lowered,
            flags=re.IGNORECASE,
        )
    )


def _extract_responsibilities_from_text_v2(block_text: Optional[str]) -> Optional[str]:
    if not block_text:
        return None
    lines = [line.strip() for line in block_text.splitlines() if line.strip()]
    bullet_lines: list[str] = []
    heuristic_lines: list[str] = []

    for line in lines:
        normalized = _normalize_line(line)
        if not normalized:
            continue
        if _has_leading_marker(line):
            bullet_lines.append(_strip_leading_marker(normalized))
            continue
        if _looks_like_responsibility_line_v2(normalized):
            heuristic_lines.append(normalized)

    selected = bullet_lines or heuristic_lines
    if selected:
        return "\n".join(_dedupe_preserving_order(selected))
    return None


def _extract_employment_history_from_text_v2(block_text: Optional[str]) -> Optional[str]:
    if not block_text:
        return None
    lines = [line.strip() for line in block_text.splitlines() if line.strip()]
    history_lines: list[str] = []

    for line in lines:
        normalized = _normalize_line(line)
        if not normalized:
            continue
        if _has_leading_marker(line):
            continue
        lowered = _strip_accents(normalized.lower())
        if lowered.startswith(_RESPONSIBILITY_PREFIXES):
            continue
        words = normalized.split()
        if len(words) <= 14 or re.search(r"(19|20)\d{2}|present|current|intern|engineer|developer|research|manager|analyst", lowered):
            history_lines.append(normalized)

    deduped = _dedupe_preserving_order(history_lines)
    if deduped:
        return "\n".join(deduped[:12])
    return None


def _extract_projects_from_experience_block_v2(block_text: Optional[str]) -> Optional[str]:
    if not block_text:
        return None
    lines = _normalized_nonempty_lines(block_text)
    projects: list[str] = []

    for index, line in enumerate(lines):
        if not _looks_like_project_heading_line(line):
            continue
        next_lines = lines[index + 1:index + 4]
        if any(_has_leading_marker(candidate) or _looks_like_responsibility_line_v2(candidate) for candidate in next_lines):
            projects.append(_strip_leading_marker(line))

    deduped = _remove_substring_duplicates(projects)
    if deduped:
        return "\n".join(deduped[:12])
    return None


def _extract_lines_by_keywords(
    cv_text: str,
    keywords: tuple[str, ...],
    *,
    max_lines: int = 12,
    exclude_patterns: tuple[str, ...] = (),
) -> Optional[str]:
    lines = _normalized_nonempty_lines(cv_text)
    collected: list[str] = []

    for line in lines:
        if _looks_like_major_heading(line):
            continue
        if exclude_patterns and any(_matches_heading(line, (pattern,)) for pattern in exclude_patterns):
            continue
        normalized = _strip_accents(_normalize_line(line).lower())
        if any(keyword in normalized for keyword in keywords):
            collected.append(_normalize_line(line))

    deduped = _dedupe_preserving_order(collected)
    if deduped:
        return "\n".join(deduped[:max_lines])
    return None


def _field_overlaps_with_skills(value: Optional[str], skills: Optional[str]) -> bool:
    if _is_missing_section(value) or _is_missing_section(skills):
        return False

    value_lines = _normalized_nonempty_lines(value)
    skills_lines = set(_normalized_nonempty_lines(skills))
    if not value_lines or not skills_lines:
        return False

    overlap_count = sum(1 for line in value_lines if line in skills_lines)
    return overlap_count == len(value_lines) or (overlap_count / len(value_lines)) >= 0.6


def _looks_like_short_stub(value: Optional[str], *, max_lines: int = 2, max_words: int = 12) -> bool:
    if _is_missing_section(value):
        return True
    lines = _normalized_nonempty_lines(value)
    if not lines:
        return True
    word_count = sum(len(line.split()) for line in lines)
    return len(lines) <= max_lines and word_count <= max_words


def _should_replace_experience(current: Optional[str], replacement: Optional[str], skills: Optional[str]) -> bool:
    if not replacement:
        return False
    return (
        _is_missing_section(current)
        or _field_overlaps_with_skills(current, skills)
        or _looks_like_profile_header_block(current)
        or _looks_like_short_stub(current, max_lines=2, max_words=16)
    )


def _should_replace_responsibilities(current: Optional[str], replacement: Optional[str], skills: Optional[str]) -> bool:
    if not replacement:
        return False
    return (
        _is_missing_section(current)
        or _field_overlaps_with_skills(current, skills)
        or _looks_like_profile_header_block(current)
        or _looks_like_short_stub(current, max_lines=3, max_words=24)
    )


def _should_replace_employment_history(current: Optional[str], replacement: Optional[str], skills: Optional[str]) -> bool:
    if not replacement:
        return False
    return (
        _is_missing_section(current)
        or _field_overlaps_with_skills(current, skills)
        or _looks_like_profile_header_block(current)
        or _looks_like_short_stub(current, max_lines=2, max_words=18)
    )


def _should_replace_certification(current: Optional[str], replacement: Optional[str], skills: Optional[str]) -> bool:
    if not replacement:
        return False
    return _is_missing_section(current) or _field_overlaps_with_skills(current, skills)


def _recover_cv_sections_from_text(parsed: dict, cv_text: str) -> dict:
    recovered = dict(parsed)

    if _is_missing_section(recovered.get("skills")):
        skills = _extract_skills_from_text(cv_text)
        if skills:
            recovered["skills"] = skills

    if _is_missing_section(recovered.get("education")):
        education = _extract_section_from_text(cv_text, _EDUCATION_SECTION_PATTERNS)
        if education:
            recovered["education"] = education

    if _is_missing_section(recovered.get("year_experience")):
        year_experience = _extract_year_experience_from_text(cv_text)
        if year_experience:
            recovered["year_experience"] = year_experience

    heading_experience_block = _extract_section_from_text(cv_text, _EXPERIENCE_SECTION_PATTERNS)
    keyword_experience_block = _extract_work_keyword_block(cv_text)
    experience_block = heading_experience_block
    if _work_signal_score(keyword_experience_block) > _work_signal_score(heading_experience_block):
        experience_block = keyword_experience_block

    if _should_replace_experience(recovered.get("experience"), experience_block, recovered.get("skills")):
        recovered["experience"] = experience_block

    responsibilities = _extract_responsibilities_from_text_v2(experience_block) if experience_block else None
    if _should_replace_responsibilities(recovered.get("responsibilities"), responsibilities, recovered.get("skills")):
        recovered["responsibilities"] = responsibilities
    elif experience_block and _is_missing_section(recovered.get("responsibilities")):
        recovered["responsibilities"] = experience_block

    employment_history = _extract_employment_history_from_text_v2(experience_block) if experience_block else None
    if _should_replace_employment_history(
        recovered.get("employment_history"),
        employment_history,
        recovered.get("skills"),
    ):
        recovered["employment_history"] = employment_history
    elif experience_block and _is_missing_section(recovered.get("employment_history")):
        recovered["employment_history"] = experience_block

    if _is_missing_section(recovered.get("projects")):
        projects = _extract_section_from_text(cv_text, _PROJECT_SECTION_PATTERNS)
        if not projects:
            projects = _extract_projects_from_experience_block_v2(experience_block)
        if not projects:
            projects = _extract_lines_by_keywords(
                cv_text,
                _PROJECT_LINE_KEYWORDS,
                exclude_patterns=_EXPERIENCE_SECTION_PATTERNS,
            )
        if projects:
            recovered["projects"] = projects

    if _is_missing_section(recovered.get("publications")):
        publications = _extract_section_from_text(cv_text, _PUBLICATION_SECTION_PATTERNS)
        if not publications:
            publications = _extract_lines_by_keywords(cv_text, _PUBLICATION_LINE_KEYWORDS)
        if publications:
            recovered["publications"] = publications

    if _is_missing_section(recovered.get("achievement")):
        achievement = _extract_section_from_text(cv_text, _ACHIEVEMENT_SECTION_PATTERNS)
        if not achievement:
            achievement = _extract_lines_by_keywords(cv_text, _ACHIEVEMENT_LINE_KEYWORDS)
        if not achievement:
            achievement = _extract_achievement_from_text(cv_text, experience_block)
        if achievement:
            recovered["achievement"] = achievement

    certification = _extract_section_from_text(cv_text, _CERTIFICATION_SECTION_PATTERNS)
    if not certification:
        certification = _extract_lines_by_keywords(cv_text, _CERTIFICATION_LINE_KEYWORDS)
    if _should_replace_certification(recovered.get("certification"), certification, recovered.get("skills")):
        recovered["certification"] = certification

    return recovered


def _dedupe_preserving_order(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for raw_line in lines:
        normalized = _normalize_line(raw_line)
        if not normalized:
            continue
        fingerprint = normalized.lower()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(normalized)
    return deduped


def _remove_substring_duplicates(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in sorted(_dedupe_preserving_order(lines), key=len, reverse=True):
        lowered = line.lower()
        if any(lowered in existing.lower() for existing in cleaned):
            continue
        cleaned.append(line)
    return list(reversed(cleaned))


def _line_has_priority_signal(line: str) -> bool:
    normalized = _normalize_line(line)
    lowered = _strip_accents(normalized.lower())
    if not normalized:
        return False
    if _looks_like_major_heading(normalized):
        return True
    signal_keywords = (
        "project",
        "publication",
        "paper",
        "journal",
        "conference",
        "award",
        "honor",
        "scholarship",
        "certificate",
        "certification",
        "license",
        "toeic",
        "ielts",
        "thesis",
        "chatbot",
        "system",
        "platform",
        "word add-in",
        "ocr",
        "rag",
    )
    return any(keyword in lowered for keyword in signal_keywords)


def _group_words_into_lines(words: list[tuple], *, y_tolerance: float = 3.0) -> list[str]:
    if not words:
        return []

    sorted_words = sorted(words, key=lambda word: (round(float(word[1]), 1), round(float(word[0]), 1)))
    grouped_rows: list[dict[str, object]] = []

    for word in sorted_words:
        x0, y0, _x1, _y1, token = float(word[0]), float(word[1]), float(word[2]), float(word[3]), str(word[4])
        normalized_token = _normalize_line(token)
        if not normalized_token:
            continue

        matched_row: Optional[dict[str, object]] = None
        for row in grouped_rows:
            if abs(float(row["y"]) - y0) <= y_tolerance:
                matched_row = row
                break

        if matched_row is None:
            matched_row = {"y": y0, "items": []}
            grouped_rows.append(matched_row)

        items = matched_row["items"]
        assert isinstance(items, list)
        items.append((x0, normalized_token))

    lines: list[str] = []
    for row in sorted(grouped_rows, key=lambda item: float(item["y"])):
        items = row["items"]
        assert isinstance(items, list)
        line = " ".join(token for _x, token in sorted(items, key=lambda item: item[0]))
        normalized_line = _normalize_line(line)
        if normalized_line:
            lines.append(normalized_line)

    return _dedupe_preserving_order(lines)


def _extract_pdf_page_lines_from_words(page) -> list[str]:
    try:
        words = page.get_text("words")
    except Exception:
        words = []

    if not words:
        return []

    page_width = float(page.rect.width)
    mid_x = page_width / 2
    gutter = max(page_width * 0.08, 24.0)

    left_words = [word for word in words if float(word[0]) <= mid_x - gutter]
    right_words = [word for word in words if float(word[0]) >= mid_x + gutter]
    center_words = [word for word in words if mid_x - gutter < float(word[0]) < mid_x + gutter]

    all_lines = _group_words_into_lines(words)
    left_lines = _group_words_into_lines(left_words + center_words[:0])
    right_lines = _group_words_into_lines(right_words)

    if not left_lines and not right_lines:
        return all_lines

    return _dedupe_preserving_order(all_lines + left_lines + right_lines)


def _extract_pdf_page_lines(page) -> list[str]:
    collected: list[str] = []

    text_variant = page.get_text("text", sort=True) or ""
    if text_variant:
        collected.extend(text_variant.splitlines())

    try:
        blocks = page.get_text("blocks")
    except Exception:
        blocks = []

    if blocks:
        sorted_blocks = sorted(blocks, key=lambda block: (round(block[1], 1), round(block[0], 1)))
        for block in sorted_blocks:
            block_text = str(block[4]).replace("\x00", " ")
            collected.extend(block_text.splitlines())

    base_lines = _dedupe_preserving_order(collected)
    word_lines = _extract_pdf_page_lines_from_words(page)
    if not word_lines:
        return base_lines

    if len(base_lines) < 35:
        return _dedupe_preserving_order(base_lines + word_lines)

    base_fingerprints = {line.lower() for line in base_lines}
    supplemental = [
        line
        for line in word_lines
        if line.lower() not in base_fingerprints and _line_has_priority_signal(line)
    ]
    return _dedupe_preserving_order(base_lines + supplemental)


def _extract_pdf_text(path: Path) -> Optional[str]:
    if path.suffix.lower() != ".pdf":
        return None
    try:
        import fitz
    except ImportError:
        return None

    text_parts: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            page_lines = _extract_pdf_page_lines(page)
            if page_lines:
                text_parts.append("\n".join(page_lines))
            else:
                raw_text = page.get_text("text").strip()
                if raw_text:
                    text_parts.append(raw_text)
    text = "\n".join(text_parts).replace("\x00", "").strip()
    return text or None


def _postprocess_cv_structured(parsed: dict, cv_text: Optional[str] = None) -> dict:
    normalized = dict(parsed)
    for key, value in list(normalized.items()):
        if isinstance(value, str):
            normalized[key] = _normalize_text_block(value) or "missing_section"

    if cv_text:
        normalized = _recover_cv_sections_from_text(normalized, cv_text)

    return normalized


def _extract_cv_from_file_id(file_id: str, system_prompt: str, instruction: str) -> dict:
    response = get_client().beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "file", "file": {"file_id": file_id}},
                    {"type": "text", "text": instruction},
                ],
            },
        ],
        response_format=CVStructured,
        temperature=0,
    )
    parsed = response.choices[0].message.parsed
    return parsed.model_dump()


def _extract_cv_from_text_with_prompt(cv_text: str, system_prompt: str, instruction: str) -> dict:
    response = get_client().beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{instruction}\n\n{cv_text}"},
        ],
        response_format=CVStructured,
        temperature=0,
    )
    parsed = response.choices[0].message.parsed
    return parsed.model_dump()


def _needs_experience_repair(parsed: dict, cv_text: Optional[str]) -> bool:
    if not cv_text:
        return any(
            _is_missing_section(parsed.get(key))
            for key in ("experience", "responsibilities", "employment_history", "certification")
        )

    has_experience_section = _has_section_heading(cv_text, _EXPERIENCE_SECTION_PATTERNS)
    has_certification_section = _has_section_heading(cv_text, _CERTIFICATION_SECTION_PATTERNS)
    skills = parsed.get("skills")

    if has_experience_section and (
        _is_missing_section(parsed.get("experience"))
        or _is_missing_section(parsed.get("responsibilities"))
        or _is_missing_section(parsed.get("employment_history"))
        or _field_overlaps_with_skills(parsed.get("experience"), skills)
        or _field_overlaps_with_skills(parsed.get("responsibilities"), skills)
        or _field_overlaps_with_skills(parsed.get("employment_history"), skills)
        or _looks_like_short_stub(parsed.get("experience"), max_lines=2, max_words=16)
        or _looks_like_short_stub(parsed.get("employment_history"), max_lines=2, max_words=18)
    ):
        return True

    if has_certification_section and _is_missing_section(parsed.get("certification")):
        return True

    return False


def _needs_completeness_repair(parsed: dict) -> bool:
    sparse_keys = (
        "experience",
        "responsibilities",
        "projects",
        "publications",
        "achievement",
        "certification",
        "employment_history",
    )
    missing_count = sum(1 for key in sparse_keys if _is_missing_section(parsed.get(key)))
    return missing_count >= 5


def _needs_ancillary_repair(parsed: dict, cv_text: Optional[str]) -> bool:
    if not cv_text:
        return any(_is_missing_section(parsed.get(key)) for key in ("projects", "publications", "achievement", "certification"))

    if _is_missing_section(parsed.get("projects")) and (
        _has_section_heading(cv_text, _PROJECT_SECTION_PATTERNS)
        or _extract_lines_by_keywords(cv_text, _PROJECT_LINE_KEYWORDS) is not None
    ):
        return True

    if _is_missing_section(parsed.get("publications")) and (
        _has_section_heading(cv_text, _PUBLICATION_SECTION_PATTERNS)
        or _extract_lines_by_keywords(cv_text, _PUBLICATION_LINE_KEYWORDS) is not None
    ):
        return True

    if _is_missing_section(parsed.get("achievement")) and (
        _has_section_heading(cv_text, _ACHIEVEMENT_SECTION_PATTERNS)
        or _extract_lines_by_keywords(cv_text, _ACHIEVEMENT_LINE_KEYWORDS) is not None
    ):
        return True

    if _is_missing_section(parsed.get("certification")) and (
        _has_section_heading(cv_text, _CERTIFICATION_SECTION_PATTERNS)
        or _extract_lines_by_keywords(cv_text, _CERTIFICATION_LINE_KEYWORDS) is not None
    ):
        return True

    return False


def _merge_cv_repair(parsed: dict, repaired: dict, cv_text: Optional[str]) -> dict:
    merged = dict(parsed)
    skills = merged.get("skills")

    if _should_replace_experience(merged.get("experience"), repaired.get("experience"), skills):
        merged["experience"] = repaired.get("experience")

    if _should_replace_responsibilities(merged.get("responsibilities"), repaired.get("responsibilities"), skills):
        merged["responsibilities"] = repaired.get("responsibilities")

    if _should_replace_employment_history(
        merged.get("employment_history"),
        repaired.get("employment_history"),
        skills,
    ):
        merged["employment_history"] = repaired.get("employment_history")

    if _should_replace_certification(merged.get("certification"), repaired.get("certification"), skills):
        merged["certification"] = repaired.get("certification")

    return _postprocess_cv_structured(merged, cv_text)


def _merge_missing_cv_sections(parsed: dict, repaired: dict, cv_text: Optional[str]) -> dict:
    merged = dict(parsed)
    for key in CV_VIEWS:
        if _is_missing_section(merged.get(key)) and not _is_missing_section(repaired.get(key)):
            merged[key] = repaired.get(key)
    return _postprocess_cv_structured(merged, cv_text)


def _merge_ancillary_sections(parsed: dict, repaired: dict, cv_text: Optional[str]) -> dict:
    merged = dict(parsed)
    for key in ("projects", "publications", "achievement", "certification"):
        if _is_missing_section(merged.get(key)) and not _is_missing_section(repaired.get(key)):
            merged[key] = repaired.get(key)
    return _postprocess_cv_structured(merged, cv_text)


def extract_cv(file_id: str) -> dict:
    file_ref = file_id
    cv_text: Optional[str] = None
    local_path = Path(file_id)
    if local_path.exists():
        cv_text = _extract_pdf_text(local_path)
        file_ref = upload_pdf(str(local_path))

    parsed = _extract_cv_from_file_id(
        file_ref,
        CV_SYSTEM_PROMPT,
        "Extract this CV using the defined schema.",
    )
    parsed = _postprocess_cv_structured(parsed, cv_text)

    if _is_missing_section(parsed.get("skills")):
        repaired = _extract_cv_from_file_id(
            file_ref,
            CV_SKILLS_REPAIR_PROMPT,
            "Re-extract this CV and prioritize recovering the skills section.",
        )
        parsed = {**repaired, **parsed, "skills": repaired.get("skills") or parsed.get("skills")}
        parsed = _postprocess_cv_structured(parsed, cv_text)

    if _needs_experience_repair(parsed, cv_text):
        if cv_text:
            repaired = _extract_cv_from_text_with_prompt(
                cv_text,
                CV_EXPERIENCE_REPAIR_PROMPT,
                "Re-extract this CV and prioritize recovering work history, responsibilities, employment history, and certifications.",
            )
        else:
            repaired = _extract_cv_from_file_id(
                file_ref,
                CV_EXPERIENCE_REPAIR_PROMPT,
                "Re-extract this CV and prioritize recovering work history, responsibilities, employment history, and certifications.",
            )
        parsed = _merge_cv_repair(parsed, repaired, cv_text)

    if cv_text and _needs_completeness_repair(parsed):
        repaired = _extract_cv_from_text_with_prompt(
            cv_text,
            CV_COMPLETENESS_REPAIR_PROMPT,
            "Re-extract this CV and prioritize recovering all missing sections from a difficult PDF layout.",
        )
        parsed = _merge_missing_cv_sections(parsed, repaired, cv_text)

    if cv_text and _needs_ancillary_repair(parsed, cv_text):
        repaired = _extract_cv_from_text_with_prompt(
            cv_text,
            CV_ANCILLARY_REPAIR_PROMPT,
            "Re-extract this CV and prioritize recovering projects, publications, achievements, and certifications.",
        )
        parsed = _merge_ancillary_sections(parsed, repaired, cv_text)

    return parsed


def extract_jd_from_pdf(file_id: str) -> dict:
    response = get_client().beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": JD_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "file", "file": {"file_id": file_id}},
                    {"type": "text", "text": "Extract this JD using the defined schema."},
                ],
            },
        ],
        response_format=JDStructured,
        temperature=0,
    )
    parsed = response.choices[0].message.parsed
    return parsed.model_dump()


def extract_cv_from_text(cv_text: str) -> dict:
    parsed = _extract_cv_from_text_with_prompt(
        cv_text,
        CV_SYSTEM_PROMPT,
        "Extract this CV using the defined schema.",
    )
    parsed = _postprocess_cv_structured(parsed, cv_text)

    if _is_missing_section(parsed.get("skills")):
        repaired = _extract_cv_from_text_with_prompt(
            cv_text,
            CV_SKILLS_REPAIR_PROMPT,
            "Re-extract this CV and prioritize recovering the skills section.",
        )
        parsed = {**repaired, **parsed, "skills": repaired.get("skills") or parsed.get("skills")}
        parsed = _postprocess_cv_structured(parsed, cv_text)

    if _needs_experience_repair(parsed, cv_text):
        repaired = _extract_cv_from_text_with_prompt(
            cv_text,
            CV_EXPERIENCE_REPAIR_PROMPT,
            "Re-extract this CV and prioritize recovering work history, responsibilities, employment history, and certifications.",
        )
        parsed = _merge_cv_repair(parsed, repaired, cv_text)

    if _needs_completeness_repair(parsed):
        repaired = _extract_cv_from_text_with_prompt(
            cv_text,
            CV_COMPLETENESS_REPAIR_PROMPT,
            "Re-extract this CV and prioritize recovering all missing sections from a difficult PDF layout.",
        )
        parsed = _merge_missing_cv_sections(parsed, repaired, cv_text)

    if _needs_ancillary_repair(parsed, cv_text):
        repaired = _extract_cv_from_text_with_prompt(
            cv_text,
            CV_ANCILLARY_REPAIR_PROMPT,
            "Re-extract this CV and prioritize recovering projects, publications, achievements, and certifications.",
        )
        parsed = _merge_ancillary_sections(parsed, repaired, cv_text)

    return parsed


def extract_jd_from_text(jd_text: str) -> dict:
    response = get_client().beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": JD_SYSTEM_PROMPT},
            {"role": "user", "content": jd_text},
        ],
        response_format=JDStructured,
        temperature=0,
    )
    parsed = response.choices[0].message.parsed
    return parsed.model_dump()


def analyze_jd_text(jd_text: str) -> JDAnalysis:
    response = get_client().beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": JD_ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": jd_text},
        ],
        response_format=JDAnalysis,
        temperature=0,
    )
    return response.choices[0].message.parsed


def analyze_jd_file(pdf_path: str) -> JDAnalysis:
    file_id = upload_pdf(pdf_path)
    response = get_client().beta.chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": JD_ANALYSIS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "file", "file": {"file_id": file_id}},
                    {"type": "text", "text": "Analyze this JD into a hiring search profile."},
                ],
            },
        ],
        response_format=JDAnalysis,
        temperature=0,
    )
    return response.choices[0].message.parsed
