from __future__ import annotations

import hashlib
import re
import textwrap
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin

import fitz
import requests

from app.core.config import settings


class VietnamWorksError(RuntimeError):
    pass


class VietnamWorksAuthError(VietnamWorksError):
    pass


@dataclass(frozen=True)
class VietnamWorksProfileRecord:
    id: str
    title: str
    candidate_name: str
    resume_id: str | None = None
    education: str | None = None
    level: str | None = None
    experience: str | None = None
    salary: str | None = None
    location: str | None = None
    last_access: str | None = None
    source: str = "VietnamWorks"
    source_url: str | None = None
    profile_url: str | None = None
    attachment_url: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    raw_text: str | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["tags"] = payload["tags"] or []
        return payload


MOCK_PROFILES: list[VietnamWorksProfileRecord] = [
    VietnamWorksProfileRecord(
        id="vietnamworks-1001",
        resume_id="1001",
        title="Backend Developer",
        candidate_name="Nguyen Van An",
        education="Dai hoc",
        level="Nhan vien",
        experience="3 nam",
        salary="$900",
        location="Ho Chi Minh",
        last_access="08/06/2026",
        source_url="https://employer.vietnamworks.com/v3/candidate/search",
        profile_url="https://employer.vietnamworks.com/resume-search/candidate-detail/resume-1001",
        attachment_url="generated://vietnamworks/1001.pdf",
        summary="Java, Spring Boot, PostgreSQL, REST API.",
        tags=["Java", "Spring Boot", "PostgreSQL"],
        raw_text="Backend Developer\nNguyen Van An\nJava, Spring Boot, PostgreSQL, REST API\n3 nam\nHo Chi Minh",
    ),
    VietnamWorksProfileRecord(
        id="vietnamworks-1002",
        resume_id="1002",
        title="Frontend Developer",
        candidate_name="Tran Thi Binh",
        education="Dai hoc",
        level="Nhan vien",
        experience="2 nam",
        salary="$800",
        location="Ha Noi",
        last_access="08/06/2026",
        source_url="https://employer.vietnamworks.com/v3/candidate/search",
        profile_url="https://employer.vietnamworks.com/resume-search/candidate-detail/resume-1002",
        attachment_url="generated://vietnamworks/1002.pdf",
        summary="React, TypeScript, UI integration.",
        tags=["React", "TypeScript", "Frontend"],
        raw_text="Frontend Developer\nTran Thi Binh\nReact, TypeScript, UI integration\n2 nam\nHa Noi",
    ),
]


SEARCH_QUERY = """
query search(
  $sortBy: String!
  $indexAlgolia: String!
  $algoliaFilter: AlgoliaFilter!
  $nestedFilter: NestedFilter
  $keyword: String!
  $locale: String!
  $filters: String
) {
  searchES(
    sortBy: $sortBy
    indexAlgolia: $indexAlgolia
    algoliaFilter: $algoliaFilter
    nestedFilter: $nestedFilter
    keyword: $keyword
    locale: $locale
    filters: $filters
  ) {
    hits {
      resume_id
      alias
      full_name
      mostrecent_company
      job_title
      expected_job_level_id
      expected_job_title
      year_of_exp
      salary
      updated_date
      job_level_id
      avatar
      is_attached
      district_id
      city_id
      city_ids
      city_names_vi
      city_names_en
      category_ids
      category_names_vi
      category_names_en
      expected_job_level_name_vi
      expected_job_level_name_en
      objectID
      birthday
      certifications
      highest_education
      current_job_level
      folder {
        id
        folderType
        name
      }
    }
    nbHits
    page
    nbPages
    hitsPerPage
    params {
      page
      query
      size
      sort_by
    }
    uri
  }
}
"""


DETAIL_QUERY = """
query resumeViewDetail($resumeId: Float!, $auto: Boolean!, $slug: String) {
  resumeDetail(resumeId: $resumeId, auto: $auto, slug: $slug) {
    jobseeker {
      firstName
      lastName
      avatar
      userId
      fullName
      birthday
      yearOfExperience
      expectedSalary
      address
      previousPosition
      latestCompany
      credit
      viewedRemaning
      isTrial
      remainingCredit
      detailUrl
    }
    resume {
      expectedSalary
      resumeId
      isReported
      detailUrl
      jobTitle
      expectedPosition
      updatedDate
      isUnknownProfile
      downloadNo
      viewsNo
      isBought
      isSearchable
      highestEducation
      maritalStatus
      expectedJobLevel
      currentJobLevel
      genderId
      gender
      languages
      downloadLink
      viewLink
      objective
      isAttach
      isDeleted
      jobLocations
      jobIndustryName
      jobFunctionName
      userCertification {
        id
        name
        organization
        fromDate
        linkCertification
        certificationOrder
      }
      folder {
        id
        name
      }
      references {
        name
        phoneNo
        company
        position
        email
      }
      workingExperiences {
        position
        company
        description
        toDate
        fromDate
        isCurrent
      }
      educations {
        major
        school
        highlight
        toDate
        fromDate
        degree
        description
      }
      skills {
        name
        rating
      }
      userActivities {
        id
        name
        title
        organization
        fromDate
        toDate
        description
        isCurrent
        activityOrder
      }
      userProject {
        entryid
        userId
        name
        role
        organization
        fromDate
        toDate
        link
        projectOrder
        description
        imageUrl
        updatedTS
        companyId
      }
      userRecommendation {
        entryid
        userId
        position
        company
        fullName
        linkedIn
        email
        phone
        coverLetter
        status
        isShown
        recommendationOrder
        recommendation
        token
        createdOn
        updatedOn
        updatedTS
      }
    }
    contactInfo {
      phoneNumber
      email
    }
    status
    code
    message
  }
}
"""


SEARCH_BY_ATTRIBUTES = {
    0: "",
    1: "mostRecentCompany^5,experienceCompanies^2",
    2: "mostRecentPosition^10,expectedJobTitle^5,experienceJobTitles^3",
    3: "skills.skillName^5",
    4: "fullName,content",
}


JD_STOPWORDS = {
    "and",
    "are",
    "candidate",
    "company",
    "cv",
    "for",
    "from",
    "have",
    "job",
    "role",
    "salary",
    "the",
    "to",
    "ung",
    "vien",
    "with",
    "work",
}


JD_PRIORITY_TERMS = [
    "spring boot",
    "business analyst",
    "data analyst",
    "data engineer",
    "machine learning",
    "java",
    "postgresql",
    "mysql",
    "sql",
    "database",
    "backend",
    "frontend",
    "fullstack",
    "react",
    "angular",
    "vue",
    "nodejs",
    "typescript",
    "javascript",
    "python",
    "devops",
    "docker",
    "kubernetes",
    "tester",
    "qa",
    "ai",
]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _compact_lines(*values: object) -> str:
    lines = [str(value).strip() for value in values if value is not None and str(value).strip()]
    return "\n".join(lines)


def _profile_id_from(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"vietnamworks-{digest}"


def _parse_cookie_header(cookie_header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for item in cookie_header.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        if key:
            cookies[key] = value.strip()
    return cookies


def _as_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _format_timestamp(value: object) -> str | None:
    timestamp = _as_int(value)
    if timestamp is None:
        return _clean(value)
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%d/%m/%Y")
    except (OverflowError, OSError, ValueError):
        return str(value)


def _format_experience(value: object) -> str | None:
    years = _as_int(value)
    if years is None:
        return _clean(value)
    if years <= 0:
        return "Chua co kinh nghiem"
    return f"{years} nam"


def _format_salary(value: object) -> str | None:
    amount = _as_int(value)
    if amount is None:
        return _clean(value) or "Thoa thuan"
    if amount <= 0:
        return "Thoa thuan"
    return f"${amount:,}"


def _join_names(value: object, *keys: str) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, list):
        return None
    names: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            names.append(item.strip())
        elif isinstance(item, dict):
            for key in keys:
                name = item.get(key)
                if name:
                    names.append(str(name).strip())
                    break
    return ", ".join(dict.fromkeys(name for name in names if name)) or None


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "resume"


class VietnamWorksClient:
    def __init__(self) -> None:
        self.base_url = settings.vietnamworks_base_url.rstrip("/")
        self.graphql_url = settings.vietnamworks_graphql_url
        self.search_url = settings.vietnamworks_search_url

    def search_profiles(self, query: str | None, page: int, page_size: int) -> dict:
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")

        if settings.vietnamworks_mock_enabled:
            profiles = self._mock_search(query)
            start = (page - 1) * page_size
            items = profiles[start : start + page_size]
            total = len(profiles)
        else:
            live_result = self._search_live(query=query, page=page, page_size=page_size)
            items = live_result["items"]
            total = live_result["total"]

        return {
            "source": "VietnamWorks",
            "query": query,
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": [item.to_dict() for item in items],
        }

    def search_profiles_by_jd(self, jd_text: str, page: int, page_size: int) -> dict:
        query = self._query_from_jd_text(jd_text)
        return self.search_profiles(query=query, page=page, page_size=page_size)

    def get_profile(self, profile_id: str, profile_url: str | None = None) -> dict:
        for profile in MOCK_PROFILES:
            if profile.id == profile_id:
                return profile.to_dict()

        if settings.vietnamworks_mock_enabled:
            raise LookupError("VietnamWorks profile not found")

        return self._fetch_live_profile(profile_id, profile_url).to_dict()

    def get_profile_file(self, profile_id: str, profile_url: str | None = None) -> dict:
        profile = self.get_profile(profile_id, profile_url)
        attachment_url = str(profile.get("attachment_url") or "").strip()
        if attachment_url and not attachment_url.startswith("generated://"):
            return self._download_profile_file(profile, attachment_url)

        raw_text = str(profile.get("raw_text") or profile.get("summary") or "")
        content = self._render_profile_pdf(raw_text, str(profile.get("title") or "VietnamWorks CV"))
        filename = f"{profile.get('resume_id') or profile_id}.pdf"
        return {
            "content": content,
            "content_type": "application/pdf",
            "filename": filename,
        }

    def _download_profile_file(self, profile: dict, attachment_url: str) -> dict:
        file_url = urljoin(f"{self.base_url}/", attachment_url)
        headers = self._auth_headers()
        headers.update(
            {
                "Accept": "application/pdf,text/html,application/octet-stream,*/*",
                "Referer": str(profile.get("profile_url") or self.search_url),
            }
        )
        if settings.vietnamworks_session_cookie:
            headers["Cookie"] = settings.vietnamworks_session_cookie

        response = requests.get(
            file_url,
            headers=headers,
            timeout=settings.vietnamworks_request_timeout_seconds,
            allow_redirects=True,
        )
        if response.status_code in {401, 403}:
            raise VietnamWorksAuthError("VietnamWorks session is invalid or cannot access this CV file")
        if response.status_code >= 400:
            raise VietnamWorksError(self._error_message(response))

        content_type = response.headers.get("content-type", "application/pdf").split(";", 1)[0].strip()
        content = response.content
        if not content:
            raise VietnamWorksError("VietnamWorks returned an empty CV file")

        if content.startswith(b"%PDF"):
            content_type = "application/pdf"
        elif "text/html" in content_type.lower() and b"login" in content[:2048].lower():
            raise VietnamWorksAuthError("VietnamWorks returned a login page instead of the CV file")

        filename = self._download_filename(response, profile, content_type)
        return {
            "content": content,
            "content_type": content_type or "application/octet-stream",
            "filename": filename,
        }

    @staticmethod
    def _download_filename(response: requests.Response, profile: dict, content_type: str) -> str:
        disposition = response.headers.get("content-disposition") or ""
        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', disposition, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().replace("/", "_").replace("\\", "_")

        extension = ".pdf" if "pdf" in content_type.lower() else ".html" if "html" in content_type.lower() else ".bin"
        base = str(profile.get("resume_id") or profile.get("id") or "vietnamworks-cv")
        return f"{base}{extension}"

    def _mock_search(self, query: str | None) -> list[VietnamWorksProfileRecord]:
        clean_query = _normalize_text(query or "")
        if not clean_query:
            return MOCK_PROFILES
        keywords = [word for word in clean_query.split(" ") if len(word) >= 2]
        matched: list[VietnamWorksProfileRecord] = []
        for profile in MOCK_PROFILES:
            haystack = _normalize_text(
                " ".join(
                    [
                        profile.title,
                        profile.candidate_name,
                        profile.education or "",
                        profile.level or "",
                        profile.experience or "",
                        profile.location or "",
                        profile.summary or "",
                        " ".join(profile.tags or []),
                        profile.raw_text or "",
                    ]
                )
            )
            if all(keyword in haystack for keyword in keywords):
                matched.append(profile)
        return matched

    def _search_live(self, query: str | None, page: int, page_size: int) -> dict:
        variables = self._build_search_variables(query=query, page=page, page_size=page_size)
        payload = self._graphql(SEARCH_QUERY, variables, operation_name="search")
        search_payload = (payload.get("data") or {}).get("searchES") if isinstance(payload, dict) else None
        if not isinstance(search_payload, dict):
            raise VietnamWorksError("VietnamWorks search did not return data")

        items = [self._record_from_search_hit(item) for item in search_payload.get("hits") or []]
        total = _as_int(search_payload.get("nbHits")) or len(items)
        return {"items": items, "total": total}

    def _fetch_live_profile(self, profile_id: str, profile_url: str | None) -> VietnamWorksProfileRecord:
        resume_id = self._resume_id_from_reference(profile_id, profile_url)
        payload = self._graphql(
            DETAIL_QUERY,
            {
                "resumeId": float(resume_id),
                "auto": False,
                "slug": self._profile_slug(profile_url, resume_id),
            },
            operation_name="resumeViewDetail",
        )
        detail = (payload.get("data") or {}).get("resumeDetail") if isinstance(payload, dict) else None
        if not isinstance(detail, dict):
            raise VietnamWorksError("VietnamWorks profile detail did not return data")

        code = _as_int(detail.get("code"))
        if code == 401:
            raise VietnamWorksAuthError("VietnamWorks session is expired. Please update VIETNAMWORKS_ONB_JWT")
        if code and code != 200:
            message = detail.get("message") or "VietnamWorks profile detail failed"
            raise VietnamWorksError(str(message))

        return self._record_from_detail(detail, profile_id=profile_id, profile_url=profile_url)

    def _graphql(self, query: str, variables: dict, operation_name: str) -> dict:
        response = requests.post(
            self.graphql_url,
            json={
                "operationName": operation_name,
                "query": query,
                "variables": variables,
            },
            headers=self._auth_headers(),
            timeout=settings.vietnamworks_request_timeout_seconds,
        )
        if response.status_code in {401, 403}:
            raise VietnamWorksAuthError("VietnamWorks session is invalid or expired")
        if response.status_code >= 400:
            raise VietnamWorksError(self._error_message(response))

        payload = response.json()
        errors = payload.get("errors") if isinstance(payload, dict) else None
        if errors:
            messages = "; ".join(str(error.get("message") or error) for error in errors if isinstance(error, dict))
            if "jwt" in messages.lower() or "auth" in messages.lower() or "token" in messages.lower():
                raise VietnamWorksAuthError(messages or "VietnamWorks session is invalid or expired")
            raise VietnamWorksError(messages or "VietnamWorks GraphQL request failed")
        return payload

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._onb_jwt()}",
            "accept-language": str(settings.vietnamworks_accept_language),
            "Origin": self.base_url,
            "Referer": self.search_url,
            "User-Agent": settings.vietnamworks_user_agent,
        }

    @staticmethod
    def _onb_jwt() -> str:
        if settings.vietnamworks_onb_jwt:
            return settings.vietnamworks_onb_jwt.strip()
        if settings.vietnamworks_session_cookie:
            cookies = _parse_cookie_header(settings.vietnamworks_session_cookie)
            token = cookies.get("ONB_JWT")
            if token:
                return token
        if settings.vietnamworks_hr_email and settings.vietnamworks_hr_password:
            raise VietnamWorksAuthError(
                "VIETNAMWORKS_ONB_JWT is required for live mode. "
                "Password login uses a browser flow and is not automated here."
            )
        raise VietnamWorksAuthError("VietnamWorks live mode requires VIETNAMWORKS_ONB_JWT or ONB_JWT in VIETNAMWORKS_SESSION_COOKIE")

    def _build_search_variables(self, query: str | None, page: int, page_size: int) -> dict:
        search_by = settings.vietnamworks_search_by
        restrict = SEARCH_BY_ATTRIBUTES.get(search_by, SEARCH_BY_ATTRIBUTES[3])
        clean_query = (query or "").strip()
        filters = settings.vietnamworks_default_filters.strip()
        return {
            "sortBy": settings.vietnamworks_sort_by,
            "indexAlgolia": settings.vietnamworks_sort_by,
            "algoliaFilter": {
                "page": page - 1,
                "hitsPerPage": page_size,
                "filters": filters,
                "restrictSearchableAttributes": restrict if clean_query else "",
            },
            "nestedFilter": None,
            "keyword": clean_query,
            "locale": settings.vietnamworks_locale,
            "filters": filters,
        }

    def _record_from_search_hit(self, item: dict) -> VietnamWorksProfileRecord:
        resume_id = str(item.get("resume_id") or "").strip()
        title = _clean(item.get("job_title") or item.get("expected_job_title")) or "VietnamWorks profile"
        candidate_name = _clean(item.get("full_name")) or "Ung vien"
        education = _clean(item.get("highest_education"))
        level = _clean(item.get("current_job_level") or item.get("expected_job_level_name_vi") or item.get("expected_job_level_name_en"))
        experience = _format_experience(item.get("year_of_exp"))
        salary = _format_salary(item.get("salary"))
        location = _join_names(item.get("city_names_vi")) or _join_names(item.get("city_names_en"))
        last_access = _format_timestamp(item.get("updated_date"))
        tags = self._tags_from_search_hit(item)
        raw_text = _compact_lines(
            title,
            candidate_name,
            education,
            level,
            experience,
            salary,
            location,
            item.get("mostrecent_company"),
            ", ".join(tags),
        )
        return VietnamWorksProfileRecord(
            id=self._public_profile_id(resume_id or raw_text),
            resume_id=resume_id or None,
            title=title,
            candidate_name=candidate_name,
            education=education,
            level=level,
            experience=experience,
            salary=salary,
            location=location,
            last_access=last_access,
            source_url=self.search_url,
            profile_url=self._profile_url(resume_id, title, item.get("alias")),
            attachment_url=f"generated://vietnamworks/{resume_id}.pdf" if resume_id else None,
            summary=raw_text,
            tags=tags,
            raw_text=raw_text,
        )

    def _record_from_detail(
        self,
        detail: dict,
        profile_id: str,
        profile_url: str | None,
    ) -> VietnamWorksProfileRecord:
        jobseeker = detail.get("jobseeker") or {}
        resume = detail.get("resume") or {}
        resume_id = str(resume.get("resumeId") or self._resume_id_from_reference(profile_id, profile_url)).strip()
        title = _clean(resume.get("jobTitle") or resume.get("expectedPosition") or jobseeker.get("previousPosition")) or "VietnamWorks profile"
        candidate_name = _clean(jobseeker.get("fullName")) or _compact_lines(jobseeker.get("firstName"), jobseeker.get("lastName")).replace("\n", " ") or "Ung vien"
        education = _clean(resume.get("highestEducation"))
        level = _clean(resume.get("currentJobLevel") or resume.get("expectedJobLevel"))
        experience = _format_experience(jobseeker.get("yearOfExperience"))
        salary = _format_salary(resume.get("expectedSalary") or jobseeker.get("expectedSalary"))
        location = _join_names(resume.get("jobLocations"), "name", "cityName", "label") or _clean(jobseeker.get("address"))
        last_access = _format_timestamp(resume.get("updatedDate"))
        tags = self._detail_tags(resume)
        raw_text = self._detail_raw_text(detail, title, candidate_name)
        attachment_url = resume.get("downloadLink") or resume.get("viewLink") or f"generated://vietnamworks/{resume_id}.pdf"
        return VietnamWorksProfileRecord(
            id=self._public_profile_id(resume_id or profile_id),
            resume_id=resume_id or None,
            title=title,
            candidate_name=candidate_name,
            education=education,
            level=level,
            experience=experience,
            salary=salary,
            location=location,
            last_access=last_access,
            source_url=self.search_url,
            profile_url=self._profile_url(resume_id, title, None, profile_url),
            attachment_url=str(attachment_url).strip() if attachment_url else None,
            summary="\n".join(raw_text.splitlines()[:20]),
            tags=tags,
            raw_text=raw_text,
        )

    def _detail_raw_text(self, detail: dict, title: str, candidate_name: str) -> str:
        jobseeker = detail.get("jobseeker") or {}
        resume = detail.get("resume") or {}
        contact = detail.get("contactInfo") or {}
        sections = [
            title,
            candidate_name,
            _compact_lines(
                f"Email: {contact.get('email')}" if contact.get("email") else None,
                f"Phone: {contact.get('phoneNumber')}" if contact.get("phoneNumber") else None,
                f"Experience: {_format_experience(jobseeker.get('yearOfExperience'))}",
                f"Expected salary: {_format_salary(resume.get('expectedSalary') or jobseeker.get('expectedSalary'))}",
                f"Location: {_join_names(resume.get('jobLocations'), 'name', 'cityName', 'label') or jobseeker.get('address')}",
                f"Industry: {resume.get('jobIndustryName')}",
                f"Function: {resume.get('jobFunctionName')}",
                f"Education: {resume.get('highestEducation')}",
                f"Current level: {resume.get('currentJobLevel')}",
                f"Expected level: {resume.get('expectedJobLevel')}",
            ),
            self._objective_text(resume),
            self._skills_text(resume.get("skills")),
            self._experiences_text(resume.get("workingExperiences")),
            self._education_text(resume.get("educations")),
            self._certifications_text(resume.get("userCertification")),
            self._projects_text(resume.get("userProject")),
            self._activities_text(resume.get("userActivities")),
            self._references_text(resume.get("references")),
        ]
        return "\n\n".join(section for section in sections if section)

    @staticmethod
    def _objective_text(resume: dict) -> str | None:
        objective = _clean(resume.get("objective"))
        return f"Objective\n{objective}" if objective else None

    @staticmethod
    def _skills_text(skills: object) -> str | None:
        if not isinstance(skills, list):
            return None
        lines = ["Skills"]
        for skill in skills:
            if not isinstance(skill, dict):
                continue
            name = _clean(skill.get("name"))
            rating = _clean(skill.get("rating"))
            if name:
                lines.append(f"- {name}{f' ({rating})' if rating else ''}")
        return "\n".join(lines) if len(lines) > 1 else None

    @staticmethod
    def _experiences_text(experiences: object) -> str | None:
        if not isinstance(experiences, list):
            return None
        lines = ["Working experiences"]
        for exp in experiences:
            if not isinstance(exp, dict):
                continue
            header = " - ".join(value for value in [_clean(exp.get("position")), _clean(exp.get("company"))] if value)
            dates = " to ".join(value for value in [_clean(exp.get("fromDate")), _clean(exp.get("toDate")) or ("Present" if exp.get("isCurrent") else None)] if value)
            description = _clean(exp.get("description"))
            if header:
                lines.append(f"- {header}")
            if dates:
                lines.append(f"  {dates}")
            if description:
                lines.append(f"  {description}")
        return "\n".join(lines) if len(lines) > 1 else None

    @staticmethod
    def _education_text(educations: object) -> str | None:
        if not isinstance(educations, list):
            return None
        lines = ["Education"]
        for education in educations:
            if not isinstance(education, dict):
                continue
            header = " - ".join(value for value in [_clean(education.get("degree")), _clean(education.get("school")), _clean(education.get("major"))] if value)
            description = _clean(education.get("description") or education.get("highlight"))
            if header:
                lines.append(f"- {header}")
            if description:
                lines.append(f"  {description}")
        return "\n".join(lines) if len(lines) > 1 else None

    @staticmethod
    def _certifications_text(certifications: object) -> str | None:
        if not isinstance(certifications, list):
            return None
        lines = ["Certifications"]
        for certification in certifications:
            if isinstance(certification, dict):
                name = _clean(certification.get("name"))
                organization = _clean(certification.get("organization"))
                if name:
                    lines.append(f"- {name}{f' - {organization}' if organization else ''}")
        return "\n".join(lines) if len(lines) > 1 else None

    @staticmethod
    def _projects_text(projects: object) -> str | None:
        if not isinstance(projects, list):
            return None
        lines = ["Projects"]
        for project in projects:
            if not isinstance(project, dict):
                continue
            name = _clean(project.get("name"))
            role = _clean(project.get("role"))
            description = _clean(project.get("description"))
            if name:
                lines.append(f"- {name}{f' - {role}' if role else ''}")
            if description:
                lines.append(f"  {description}")
        return "\n".join(lines) if len(lines) > 1 else None

    @staticmethod
    def _activities_text(activities: object) -> str | None:
        if not isinstance(activities, list):
            return None
        lines = ["Activities"]
        for activity in activities:
            if not isinstance(activity, dict):
                continue
            title = _clean(activity.get("title") or activity.get("name"))
            organization = _clean(activity.get("organization"))
            description = _clean(activity.get("description"))
            if title:
                lines.append(f"- {title}{f' - {organization}' if organization else ''}")
            if description:
                lines.append(f"  {description}")
        return "\n".join(lines) if len(lines) > 1 else None

    @staticmethod
    def _references_text(references: object) -> str | None:
        if not isinstance(references, list):
            return None
        lines = ["References"]
        for reference in references:
            if not isinstance(reference, dict):
                continue
            name = _clean(reference.get("name"))
            position = _clean(reference.get("position"))
            company = _clean(reference.get("company"))
            if name:
                lines.append(f"- {name}{f' - {position}' if position else ''}{f' at {company}' if company else ''}")
        return "\n".join(lines) if len(lines) > 1 else None

    @staticmethod
    def _tags_from_search_hit(item: dict) -> list[str]:
        tags: list[str] = []
        for value in [
            _join_names(item.get("category_names_vi")),
            _join_names(item.get("category_names_en")),
            _clean(item.get("expected_job_title")),
        ]:
            if value:
                tags.extend(part.strip() for part in value.split(",") if part.strip())
        return list(dict.fromkeys(tags))

    def _detail_tags(self, resume: dict) -> list[str]:
        tags: list[str] = []
        for value in [resume.get("jobIndustryName"), resume.get("jobFunctionName")]:
            clean = _clean(value)
            if clean:
                tags.append(clean)
        skills = resume.get("skills")
        if isinstance(skills, list):
            for skill in skills:
                if isinstance(skill, dict) and skill.get("name"):
                    tags.append(str(skill["name"]).strip())
        return list(dict.fromkeys(tag for tag in tags if tag))

    def _query_from_jd_text(self, jd_text: str) -> str:
        normalized = unicodedata.normalize("NFKD", jd_text)
        normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
        normalized = normalized.replace("c++", "cplusplus").replace("c#", "csharp").replace(".net", "dotnet")

        for term in JD_PRIORITY_TERMS:
            if term in normalized:
                return term

        tokens = re.findall(r"[a-z][a-z0-9]{1,}", normalized)
        for token in tokens:
            if token not in JD_STOPWORDS and len(token) >= 3:
                return token
        raise ValueError("JD content does not contain searchable keywords")

    def _profile_url(
        self,
        resume_id: str,
        title: str,
        alias: object = None,
        fallback_url: str | None = None,
    ) -> str:
        if fallback_url:
            return fallback_url
        if not resume_id:
            return self.search_url
        slug = str(alias or _slugify(title))
        path = f"/resume-search/candidate-detail/{quote(slug)}-{resume_id}"
        return urljoin(f"{self.base_url}/", path.lstrip("/"))

    @staticmethod
    def _public_profile_id(resume_id_or_url: str) -> str:
        value = resume_id_or_url.strip()
        if value and re.fullmatch(r"[A-Za-z0-9_-]+", value):
            return f"vietnamworks-{value}"
        return _profile_id_from(value or "vietnamworks-profile")

    @staticmethod
    def _resume_id_from_reference(profile_id: str, profile_url: str | None) -> str:
        if profile_id.startswith("vietnamworks-"):
            candidate = profile_id.removeprefix("vietnamworks-")
            if re.fullmatch(r"\d+", candidate):
                return candidate
        if profile_url:
            match = re.search(r"(?:resume-|resumeId=|resume_id=)(\d+)", profile_url)
            if match:
                return match.group(1)
            trailing = re.search(r"-(\d+)(?:[/?#].*)?$", profile_url)
            if trailing:
                return trailing.group(1)
        raise ValueError("Valid VietnamWorks resume id or profile_url is required")

    @staticmethod
    def _profile_slug(profile_url: str | None, resume_id: str) -> str:
        if profile_url:
            match = re.search(r"/candidate-detail/([^/?#]+)", profile_url)
            if match:
                return match.group(1)
        return f"resume-{resume_id}"

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"VietnamWorks request failed with status {response.status_code}"
        message = payload.get("message") or payload.get("error")
        return str(message or f"VietnamWorks request failed with status {response.status_code}")

    @staticmethod
    def _render_profile_pdf(raw_text: str, title: str) -> bytes:
        doc = fitz.open()
        width, height = 595, 842
        margin = 42
        line_height = 14
        font_size = 10
        font_kwargs = VietnamWorksClient._pdf_font_kwargs()

        def new_page():
            page = doc.new_page(width=width, height=height)
            page.insert_text((margin, margin), title[:100], fontsize=14, **font_kwargs)
            return page, margin + 28

        page, y = new_page()
        for raw_line in raw_text.splitlines() or ["No profile detail returned."]:
            wrapped = textwrap.wrap(raw_line, width=92, replace_whitespace=False) or [""]
            for line in wrapped:
                if y > height - margin:
                    page, y = new_page()
                try:
                    page.insert_text((margin, y), line, fontsize=font_size, **font_kwargs)
                except Exception:
                    safe_line = unicodedata.normalize("NFKD", line).encode("ascii", "ignore").decode("ascii")
                    page.insert_text((margin, y), safe_line, fontsize=font_size, fontname="helv")
                y += line_height
        content = doc.tobytes()
        doc.close()
        return content

    @staticmethod
    def _pdf_font_kwargs() -> dict:
        font_path = Path("C:/Windows/Fonts/arial.ttf")
        if font_path.exists():
            return {"fontname": "Arial", "fontfile": str(font_path)}
        return {"fontname": "helv"}


def get_vietnamworks_client() -> VietnamWorksClient:
    return VietnamWorksClient()
