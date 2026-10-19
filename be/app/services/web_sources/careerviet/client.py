from __future__ import annotations

import hashlib
import json
import re
import textwrap
import unicodedata
from base64 import urlsafe_b64decode
from binascii import Error as BinasciiError
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import fitz
import requests

from app.core.config import settings


class CareerVietError(RuntimeError):
    pass


class CareerVietAuthError(CareerVietError):
    pass


@dataclass(frozen=True)
class CareerVietProfileRecord:
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
    source: str = "CareerViet"
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


MOCK_PROFILES: list[CareerVietProfileRecord] = [
    CareerVietProfileRecord(
        id="careerviet-101",
        title="IT Specialist Server & Office Application",
        candidate_name="HUYNH DOAN LINH TRAM",
        education="Cao dang",
        level="Nhan vien",
        experience="5 nam",
        salary="Thoa thuan",
        location="Ho Chi Minh",
        last_access="Ngay hom nay",
        source_url="https://careerviet.vn/vi/tim-ung-vien/nganh-nghe/cntt-phan-mem",
        profile_url="https://careerviet.vn/vi/tim-ung-vien/nganh-nghe/cntt-phan-mem",
        summary="Server, office application, IT support, internal system operation.",
        tags=["IT", "Server", "Office Application"],
        raw_text="IT Specialist Server Office Application 5 nam Ho Chi Minh",
    ),
    CareerVietProfileRecord(
        id="careerviet-102",
        title="Supervisor Database",
        candidate_name="TRAN TAN PHAT",
        education="Dai hoc",
        level="Nhan vien",
        experience="Tren 10 nam",
        salary="Thoa thuan",
        location="Ho Chi Minh",
        last_access="Ngay hom nay",
        source_url="https://careerviet.vn/vi/tim-ung-vien/nganh-nghe/cntt-phan-mem",
        profile_url="https://careerviet.vn/vi/tim-ung-vien/nganh-nghe/cntt-phan-mem",
        summary="Database supervisor with long experience in data operations.",
        tags=["Database", "SQL", "Supervisor"],
        raw_text="Supervisor Database SQL tren 10 nam Ho Chi Minh",
    ),
    CareerVietProfileRecord(
        id="careerviet-103",
        title="Business Analyst",
        candidate_name="TRAN TRANG",
        education="Dai hoc",
        level="Nhan vien",
        experience="5 nam",
        salary="Thoa thuan",
        location="Ha Noi",
        last_access="Ngay hom nay",
        source_url="https://careerviet.vn/vi/tim-ung-vien/nganh-nghe/cntt-phan-mem",
        profile_url="https://careerviet.vn/vi/tim-ung-vien/nganh-nghe/cntt-phan-mem",
        summary="Business analyst for software requirement and product workflow.",
        tags=["Business Analyst", "Requirement", "Software"],
        raw_text="Business Analyst requirement software 5 nam Ha Noi",
    ),
    CareerVietProfileRecord(
        id="careerviet-104",
        title="Data Entry Staff (Hop dong 8 thang-Fulltime)",
        candidate_name="PHAM KIEU ANH",
        education="Cao dang",
        level="Nhan vien",
        experience="Chua co kinh nghiem",
        salary="Thoa thuan",
        location="Ho Chi Minh",
        last_access="Ngay hom nay",
        source_url="https://careerviet.vn/vi/tim-ung-vien/nganh-nghe/cntt-phan-mem",
        profile_url="https://careerviet.vn/vi/tim-ung-vien/nganh-nghe/cntt-phan-mem",
        summary="Data entry staff for full-time contract work.",
        tags=["Data Entry", "Office"],
        raw_text="Data Entry Staff fulltime Ho Chi Minh",
    ),
]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _strip_tags(html: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", html)
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", "\n", text)
    text = unescape(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _profile_id_from(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"careerviet-{digest}"


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


def _decode_jwt_payload(token: str) -> dict:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = urlsafe_b64decode(payload.encode("utf-8"))
        return json.loads(decoded)
    except (IndexError, ValueError, json.JSONDecodeError, BinasciiError) as exc:
        raise CareerVietAuthError("CareerViet token is invalid") from exc


def _format_unix_timestamp(timestamp: int | float | None) -> str | None:
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    except (OverflowError, OSError, ValueError):
        return None


def _clean_salary_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    compact = re.sub(r"\s+", " ", text)
    normalized = _normalize_text(compact)
    if any(token in normalized for token in ["thoa thuan", "thuong luong", "negotiable"]):
        return "Thoa thuan"
    has_amount = bool(re.search(r"\d", compact))
    has_unit = bool(re.search(r"\b(vnd|usd|tri[eệ]u|tr)\b", compact, flags=re.IGNORECASE))
    if has_amount and has_unit:
        return compact
    return None


def _prefer_salary(primary: str | None, fallback: str | None) -> str | None:
    clean_primary = _clean_salary_text(primary) or (str(primary).strip() if primary else None)
    clean_fallback = _clean_salary_text(fallback) or (str(fallback).strip() if fallback else None)
    if clean_fallback and (not clean_primary or clean_primary == "Thoa thuan"):
        return clean_fallback
    return clean_primary


def _replace_salary_in_text_block(text: str | None, preferred_salary: str | None) -> str | None:
    if not text or not preferred_salary:
        return text
    lines = str(text).splitlines()
    updated = False
    for index, line in enumerate(lines):
        normalized = _normalize_text(line)
        if normalized.startswith("salary:") or normalized == "thoa thuan" or normalized.startswith("muc luong"):
            prefix = "Salary: " if ":" in line else ""
            lines[index] = f"{prefix}{preferred_salary}"
            updated = True
            continue
        if _clean_salary_text(line) == "Thoa thuan":
            lines[index] = preferred_salary
            updated = True
    return "\n".join(lines) if updated else text


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "ung-vien"


def _as_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _compact_lines(*values: object) -> str:
    lines = [str(value).strip() for value in values if value is not None and str(value).strip()]
    return "\n".join(lines)


JD_STOPWORDS = {
    "a",
    "able",
    "about",
    "and",
    "are",
    "as",
    "at",
    "be",
    "benefit",
    "benefits",
    "candidate",
    "candidates",
    "can",
    "co",
    "cong",
    "company",
    "cv",
    "duoc",
    "for",
    "from",
    "have",
    "in",
    "is",
    "it",
    "job",
    "lam",
    "mo",
    "mot",
    "of",
    "on",
    "or",
    "our",
    "phuc",
    "position",
    "quyen",
    "role",
    "salary",
    "the",
    "to",
    "ung",
    "vien",
    "voi",
    "we",
    "with",
    "work",
    "yeu",
}

JD_PRIORITY_TERMS = [
    "spring boot",
    "business analyst",
    "data analyst",
    "data engineer",
    "machine learning",
    "spring",
    "java",
    "postgresql",
    "mysql",
    "sql server",
    "sql",
    "database",
    "backend",
    "frontend",
    "fullstack",
    "react",
    "angular",
    "vue",
    "nodejs",
    "node",
    "typescript",
    "javascript",
    "python",
    "django",
    "flask",
    "fastapi",
    "devops",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "linux",
    "tester",
    "qa",
    "ai",
]

JD_QUERY_PATTERNS = [
    ("java spring boot", ("java", "spring boot")),
    ("business analyst", ("business analyst",)),
    ("data analyst", ("data analyst",)),
    ("data engineer", ("data engineer",)),
    ("machine learning", ("machine learning",)),
    ("fullstack", ("fullstack",)),
    ("devops", ("devops",)),
    ("react frontend", ("react", "frontend")),
    ("nodejs backend", ("nodejs", "backend")),
    ("python backend", ("python", "backend")),
    ("java backend", ("java", "backend")),
]


class CareerVietClient:
    def __init__(self) -> None:
        self.base_url = settings.careerviet_base_url.rstrip("/")
        self.api_base_url = settings.careerviet_api_base_url.rstrip("/")
        self.search_url = urljoin(f"{self.base_url}/", settings.careerviet_search_path.lstrip("/"))
        self.resume_search_api_url = urljoin(f"{self.api_base_url}/", "api/v1/jss/emp/resumes/hr-centrals")
        self._refreshed_access_token: str | None = None

    def search_profiles(self, query: str | None, page: int, page_size: int) -> dict:
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")

        if settings.careerviet_mock_enabled:
            profiles = self._mock_search(query)
            start = (page - 1) * page_size
            items = profiles[start : start + page_size]
            total = len(profiles)
        else:
            live_result = self._search_live(query=query, page=page, page_size=page_size)
            items = live_result["items"]
            total = live_result["total"]

        return {
            "source": "CareerViet",
            "query": query,
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": [item.to_dict() for item in items],
        }

    def search_profiles_by_jd(self, jd_text: str, page: int, page_size: int) -> dict:
        query = self._query_from_jd_text(jd_text)
        return self.search_profiles(query=query, page=page, page_size=page_size)

    @staticmethod
    def _apply_salary_hint(profile: CareerVietProfileRecord, salary_hint: str | None) -> CareerVietProfileRecord:
        preferred_salary = _prefer_salary(profile.salary, salary_hint)
        if preferred_salary == profile.salary:
            return profile
        return replace(
            profile,
            salary=preferred_salary,
            summary=_replace_salary_in_text_block(profile.summary, preferred_salary),
            raw_text=_replace_salary_in_text_block(profile.raw_text, preferred_salary),
        )

    def get_profile(self, profile_id: str, profile_url: str | None = None, salary_hint: str | None = None) -> dict:
        for profile in MOCK_PROFILES:
            if profile.id == profile_id:
                return self._apply_salary_hint(profile, salary_hint).to_dict()

        if settings.careerviet_mock_enabled:
            raise LookupError("CareerViet profile not found")

        profile = self._fetch_live_profile(profile_id, profile_url)
        return self._apply_salary_hint(profile, salary_hint).to_dict()

    def get_profile_file(self, profile_id: str, profile_url: str | None = None, salary_hint: str | None = None) -> dict:
        if settings.careerviet_mock_enabled:
            raise LookupError("CareerViet profile file not found")

        session = self._session()
        profile = self._fetch_live_profile(profile_id, profile_url, session=session)
        profile = self._apply_salary_hint(profile, salary_hint)
        if not profile.attachment_url:
            return self._generated_profile_file(profile)

        try:
            response = self._get_authorized_file(session, profile.attachment_url)
        except CareerVietError:
            return self._generated_profile_file(profile)
        content_type = response.headers.get("content-type") or "application/pdf"
        filename = f"{profile.resume_id or profile.id}.pdf"
        return {
            "content": response.content,
            "content_type": content_type,
            "filename": filename,
        }

    def _generated_profile_file(self, profile: CareerVietProfileRecord) -> dict:
        raw_text = _compact_lines(
            f"CareerViet profile: {profile.title}",
            f"Candidate: {profile.candidate_name}",
            f"Education: {profile.education}" if profile.education else None,
            f"Level: {profile.level}" if profile.level else None,
            f"Experience: {profile.experience}" if profile.experience else None,
            f"Salary: {profile.salary}" if profile.salary else None,
            f"Location: {profile.location}" if profile.location else None,
            f"Last access: {profile.last_access}" if profile.last_access else None,
            f"Tags: {', '.join(profile.tags or [])}" if profile.tags else None,
            "",
            "Profile text",
            profile.raw_text or profile.summary,
            "",
            "Source",
            profile.profile_url,
        )
        return {
            "content": self._render_profile_pdf(raw_text, profile.title),
            "content_type": "application/pdf",
            "filename": f"{profile.resume_id or profile.id}.pdf",
        }

    @staticmethod
    def _render_profile_pdf(raw_text: str, title: str) -> bytes:
        doc = fitz.open()
        width, height = 595, 842
        margin = 42
        line_height = 14
        font_size = 10
        font_kwargs = CareerVietClient._pdf_font_kwargs()

        def new_page():
            page = doc.new_page(width=width, height=height)
            page.insert_text((margin, margin), title[:100], fontsize=14, **font_kwargs)
            return page, margin + 28

        page, y = new_page()
        for raw_line in raw_text.splitlines() or ["No CareerViet profile detail returned."]:
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

    def _mock_search(self, query: str | None) -> list[CareerVietProfileRecord]:
        clean_query = _normalize_text(query or "")
        if not clean_query:
            return MOCK_PROFILES
        keywords = [word for word in clean_query.split(" ") if len(word) >= 2]
        matched: list[CareerVietProfileRecord] = []
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

    def _query_from_jd_text(self, jd_text: str) -> str:
        normalized = unicodedata.normalize("NFKD", jd_text)
        normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
        normalized = normalized.replace("c++", "cplusplus").replace("c#", "csharp").replace(".net", "dotnet")

        for query, required_terms in JD_QUERY_PATTERNS:
            if all(term in normalized for term in required_terms):
                return query

        terms: list[str] = []
        for term in JD_PRIORITY_TERMS:
            if term in normalized:
                terms.append(term)

        tokens = re.findall(r"[a-z][a-z0-9]{1,}", normalized)
        for token in tokens:
            if token in JD_STOPWORDS or token.isdigit():
                continue
            if len(token) < 3:
                continue
            terms.append(token)

        unique_terms = list(dict.fromkeys(terms))
        if not unique_terms:
            raise ValueError("JD content does not contain searchable keywords")
        return unique_terms[0]

    def _session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": settings.careerviet_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
            }
        )
        if settings.careerviet_session_cookie:
            session.cookies.update(_parse_cookie_header(settings.careerviet_session_cookie))
        if settings.careerviet_employer_tokens:
            session.cookies.set("employer-tokens", settings.careerviet_employer_tokens.strip())
        if settings.careerviet_session_cookie:
            return session
        if self._has_token_credentials():
            return session
        if settings.careerviet_hr_email and settings.careerviet_hr_password:
            raise CareerVietAuthError(
                "CAREERVIET_ACCESS_TOKEN, CAREERVIET_EMPLOYER_TOKENS, or CAREERVIET_SESSION_COOKIE is required for live mode. "
                "Password login needs a browser/CSRF flow and is intentionally not automated here."
            )
        raise CareerVietAuthError(
            "CareerViet live mode requires CAREERVIET_ACCESS_TOKEN, "
            "CAREERVIET_EMPLOYER_TOKENS, or CAREERVIET_SESSION_COOKIE"
        )

    def _api_headers(self, *, authenticated: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": self.search_url,
            "x-lang": "vi",
        }
        if authenticated or self._has_token_credentials():
            headers["Authorization"] = f"Bearer {self._employer_access_token()}"
        return headers

    @staticmethod
    def _has_token_credentials() -> bool:
        return bool(settings.careerviet_access_token or settings.careerviet_employer_tokens)

    def _employer_access_token(self) -> str:
        if self._refreshed_access_token:
            return self._refreshed_access_token
        access_token = settings.careerviet_access_token.strip()
        if access_token:
            return access_token.removeprefix("Bearer ").strip()

        token_cookie = settings.careerviet_employer_tokens.strip()
        if not token_cookie and settings.careerviet_session_cookie:
            cookies = _parse_cookie_header(settings.careerviet_session_cookie)
            token_cookie = cookies.get("employer-tokens", "")
        if not token_cookie:
            raise CareerVietAuthError(
                "CareerViet detail view requires CAREERVIET_ACCESS_TOKEN, "
                "CAREERVIET_EMPLOYER_TOKENS, or employer-tokens in CAREERVIET_SESSION_COOKIE"
            )
        payload = _decode_jwt_payload(token_cookie)
        decoded_access_token = payload.get("accessToken")
        if not isinstance(decoded_access_token, str) or not decoded_access_token:
            raise CareerVietAuthError("CareerViet employer access token is missing")
        return decoded_access_token

    def _refresh_employer_access_token(self, session: requests.Session) -> str:
        if not settings.careerviet_session_cookie and not settings.careerviet_employer_tokens:
            raise CareerVietAuthError("CareerViet token is invalid or expired. Please update CAREERVIET_ACCESS_TOKEN or CAREERVIET_EMPLOYER_TOKENS")
        token_cookie = settings.careerviet_employer_tokens.strip()
        if token_cookie:
            session.cookies.set("employer-tokens", token_cookie)
        elif settings.careerviet_session_cookie:
            token_cookie = _parse_cookie_header(settings.careerviet_session_cookie).get("employer-tokens", "")

        refresh_payload: dict | None = None
        access_token_expiry: str | None = None
        if token_cookie:
            payload = _decode_jwt_payload(token_cookie)
            access_token = payload.get("accessToken")
            refresh_token = payload.get("refreshToken")
            if isinstance(access_token, str) and access_token:
                access_payload = _decode_jwt_payload(access_token)
                access_token_expiry = _format_unix_timestamp(access_payload.get("exp"))
            if isinstance(refresh_token, str) and refresh_token:
                refresh_payload = {"refreshToken": refresh_token}

        refresh_url = urljoin(f"{self.base_url}/", "api/auth/employers/refresh")
        refresh_headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": self.search_url,
            "x-lang": "vi",
        }
        response = session.post(
            refresh_url,
            headers=refresh_headers,
            timeout=settings.careerviet_request_timeout_seconds,
        )
        if response.status_code in {401, 403} and refresh_payload:
            response = session.post(
                refresh_url,
                json=refresh_payload,
                headers=refresh_headers,
                timeout=settings.careerviet_request_timeout_seconds,
            )
        if response.status_code in {401, 403}:
            detail = "CareerViet session is expired or missing browser cookies."
            if access_token_expiry:
                detail += f" employer accessToken expired at {access_token_expiry}."
            raise CareerVietAuthError(
                detail + " "
                "Please update CAREERVIET_SESSION_COOKIE with the full Cookie header from the logged-in HR browser."
            )
        if response.status_code >= 400:
            raise CareerVietError(self._error_message(response))
        payload = response.json()
        token = payload.get("token") if isinstance(payload, dict) else None
        if not isinstance(token, dict) and isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict):
                token = data.get("token") if isinstance(data.get("token"), dict) else data
        access_token = token.get("accessToken") if isinstance(token, dict) else None
        if not payload.get("success") or not isinstance(access_token, str) or not access_token:
            raise CareerVietAuthError("CareerViet token refresh failed")
        self._refreshed_access_token = access_token
        return access_token

    def _search_live(self, query: str | None, page: int, page_size: int) -> dict:
        session = self._session()
        payload = self._build_search_payload(query=query, page=page, page_size=page_size)
        response = session.post(
            self.resume_search_api_url,
            json=payload,
            headers=self._api_headers(),
            timeout=settings.careerviet_request_timeout_seconds,
        )
        if response.status_code in {401, 403}:
            raise CareerVietAuthError("CareerViet session is invalid or expired")
        if response.status_code >= 400:
            raise CareerVietError(self._error_message(response))
        payload = response.json()
        if not payload.get("success"):
            raise CareerVietError(str(payload.get("message") or "CareerViet search failed"))
        items = [self._record_from_search_item(item) for item in payload.get("data") or []]
        metadata = payload.get("metadata") or {}
        return {"items": items, "total": int(metadata.get("itemCount") or len(items))}

    def _fetch_live_profile(
        self,
        profile_id: str,
        profile_url: str | None,
        session: requests.Session | None = None,
    ) -> CareerVietProfileRecord:
        session = session or self._session()
        resume_id = self._resume_id_from_reference(profile_id, profile_url)
        response = session.get(
            urljoin(f"{self.api_base_url}/", f"api/v1/jss/emp/resumes/{resume_id}"),
            headers=self._api_headers(authenticated=True),
            timeout=settings.careerviet_request_timeout_seconds,
        )
        if response.status_code in {401, 403}:
            self._refresh_employer_access_token(session)
            response = session.get(
                urljoin(f"{self.api_base_url}/", f"api/v1/jss/emp/resumes/{resume_id}"),
                headers=self._api_headers(authenticated=True),
                timeout=settings.careerviet_request_timeout_seconds,
            )
        if response.status_code in {401, 403}:
            raise CareerVietAuthError("CareerViet session is invalid, expired, or missing employer access token")
        if response.status_code >= 400:
            raise CareerVietError(self._error_message(response))
        payload = response.json()
        if not payload.get("success"):
            raise CareerVietError(str(payload.get("message") or "CareerViet profile detail failed"))
        return self._record_from_detail(payload.get("data") or {})

    def _get_authorized_file(self, session: requests.Session, attachment_url: str) -> requests.Response:
        resolved_url = urljoin(f"{self.api_base_url}/", attachment_url)
        headers = self._api_headers(authenticated=True)
        headers["Accept"] = "application/pdf,application/octet-stream,*/*"
        response = session.get(
            resolved_url,
            headers=headers,
            timeout=settings.careerviet_request_timeout_seconds,
        )
        if response.status_code in {401, 403}:
            self._refresh_employer_access_token(session)
            headers = self._api_headers(authenticated=True)
            headers["Accept"] = "application/pdf,application/octet-stream,*/*"
            response = session.get(
                resolved_url,
                headers=headers,
                timeout=settings.careerviet_request_timeout_seconds,
            )
        if response.status_code in {401, 403}:
            raise CareerVietAuthError("CareerViet session is invalid, expired, or missing employer access token")
        if response.status_code >= 400:
            raise CareerVietError(self._error_message(response))
        return response

    def _build_search_payload(self, query: str | None, page: int, page_size: int) -> dict:
        payload: dict[str, object] = {
            "page": page,
            "limit": page_size,
            "order": "DESC",
            "sort_by": "date",
        }
        industry_ids = self._default_industry_ids()
        if industry_ids:
            payload["industry_ids"] = industry_ids
        clean_query = (query or "").strip()
        if clean_query:
            payload["keyword"] = {
                "value": clean_query,
                "type": settings.careerviet_keyword_match_type,
            }
        return payload

    @staticmethod
    def _default_industry_ids() -> list[int]:
        industry_ids: list[int] = []
        for item in settings.careerviet_default_industry_ids.split(","):
            value = _as_int(item.strip())
            if value is not None:
                industry_ids.append(value)
        return industry_ids

    def _record_from_search_item(self, item: dict) -> CareerVietProfileRecord:
        resume_id = str(item.get("resume_id") or "").strip()
        title = str(item.get("resume_headline") or item.get("resume_headline_vn") or "CareerViet profile").strip()
        candidate_name = str(item.get("jobseeker_fullname") or "Ung vien").strip()
        education = item.get("degree_name") or item.get("resume_degree_name_vn") or item.get("resume_degree_name_en")
        level = item.get("level_name") or item.get("resume_level_name_vn") or item.get("resume_level_name_en")
        experience = self._format_experience(item.get("resume_year_of_experience"))
        salary = self._format_salary(item)
        location = item.get("resume_location_vn") or item.get("resume_location_en")
        last_access = item.get("jobseeker_last_active_date")
        profile_url = self._profile_url(resume_id, title)
        tags = self._tags_from(item.get("tags"))
        summary = _compact_lines(title, candidate_name, education, level, experience, salary, location, last_access)
        return CareerVietProfileRecord(
            id=self._public_profile_id(resume_id or profile_url),
            resume_id=resume_id or None,
            title=title,
            candidate_name=candidate_name,
            education=str(education).strip() if education else None,
            level=str(level).strip() if level else None,
            experience=experience,
            salary=salary,
            location=str(location).strip() if location else None,
            last_access=str(last_access).strip() if last_access else None,
            source_url=self.search_url,
            profile_url=profile_url,
            summary=summary,
            tags=tags,
            raw_text=summary,
        )

    def _record_from_detail(self, detail: dict) -> CareerVietProfileRecord:
        resume_id = str(detail.get("resume_id") or "").strip()
        title = str(
            detail.get("resume_headline_vn")
            or detail.get("resume_headline_en")
            or detail.get("resume_headline")
            or "CareerViet profile"
        ).strip()
        candidate_name = str(detail.get("jobseeker_fullname") or "Ung vien").strip()
        education = detail.get("resume_degree_name_vn") or detail.get("resume_degree_name_en")
        level = (
            detail.get("resume_present_level_name_vn")
            or detail.get("resume_level_name_vn")
            or detail.get("resume_present_level_name_en")
            or detail.get("resume_level_name_en")
        )
        experience = self._format_experience(detail.get("resume_year_of_experience"))
        salary = self._format_salary(detail)
        location = detail.get("jobseeker_location_name_vn") or detail.get("jobseeker_location_name_en")
        last_access = detail.get("jobseeker_last_active_date")
        attachment_url = detail.get("resume_attachment_url")
        profile_url = self._profile_url(resume_id, title)
        tags = self._detail_tags(detail)
        raw_text = self._detail_raw_text(detail)
        return CareerVietProfileRecord(
            id=self._public_profile_id(resume_id or profile_url),
            resume_id=resume_id or None,
            title=title,
            candidate_name=candidate_name,
            education=str(education).strip() if education else None,
            level=str(level).strip() if level else None,
            experience=experience,
            salary=salary,
            location=str(location).strip() if location else None,
            last_access=str(last_access).strip() if last_access else None,
            source_url=self.search_url,
            profile_url=profile_url,
            attachment_url=str(attachment_url).strip() if attachment_url else None,
            summary="\n".join(raw_text.splitlines()[:20]),
            tags=tags,
            raw_text=raw_text,
        )

    def _profile_url(self, resume_id: str, title: str) -> str:
        if not resume_id:
            return self.search_url
        slug = _slugify(title)
        path = f"vi/employers/popup/resumeinfo/{resume_id}/{resume_id}/{slug}/{resume_id}.html"
        return urljoin(f"{self.base_url}/", path)

    @staticmethod
    def _public_profile_id(resume_id_or_url: str) -> str:
        value = resume_id_or_url.strip()
        if value and re.fullmatch(r"[A-Za-z0-9_-]+", value):
            return f"careerviet-{value}"
        return _profile_id_from(value or "careerviet-profile")

    @staticmethod
    def _resume_id_from_reference(profile_id: str, profile_url: str | None) -> str:
        if profile_id.startswith("careerviet-"):
            candidate = profile_id.removeprefix("careerviet-")
            if re.fullmatch(r"[A-Za-z0-9_-]+", candidate):
                return candidate
        if profile_url:
            resume_info_match = re.search(r"/resumeinfo/([^/?#]+)", profile_url)
            if resume_info_match:
                return resume_info_match.group(1)
            html_id_match = re.search(r"/([A-Za-z0-9_-]+)\.html(?:[?#].*)?$", profile_url)
            if html_id_match:
                return html_id_match.group(1)
        raise ValueError("Valid CareerViet resume id or profile_url is required")

    @staticmethod
    def _format_experience(value: object) -> str | None:
        years = _as_int(value)
        if years is None:
            return None
        if years <= 0:
            return "Chua co kinh nghiem"
        return f"{years} nam"

    @staticmethod
    def _format_salary(item: dict) -> str | None:
        for key in [
            "resume_salary",
            "resume_salary_text",
            "resume_salary_display",
            "resume_target_job_salary_text",
            "resume_target_job_salary_display",
            "resume_ref_salary_text",
            "resume_ref_salary_display",
            "salary",
            "salary_text",
            "expected_salary",
            "desired_salary",
            "salary_vn",
        ]:
            salary_text = _clean_salary_text(item.get(key))
            if salary_text:
                return salary_text

        unit = str(
            item.get("resume_salary_unit")
            or item.get("resume_target_job_salary_unit")
            or item.get("resume_ref_salary_unit")
            or ""
        ).upper()
        from_salary = _as_int(item.get("resume_target_job_salary") or item.get("resume_ref_salary"))
        to_salary = _as_int(item.get("resume_target_job_to_salary") or item.get("resume_ref_to_salary"))
        amounts = [amount for amount in [from_salary, to_salary] if amount and amount > 0]
        if amounts and unit and unit not in {"NEG", "THOA_THUAN"}:
            if len(amounts) == 1 or amounts[0] == amounts[-1]:
                return f"{amounts[0]:,} {unit}"
            return f"{amounts[0]:,} - {amounts[-1]:,} {unit}"

        for key, value in item.items():
            if isinstance(value, str) and ("salary" in key.lower() or "luong" in key.lower()):
                salary_text = _clean_salary_text(value)
                if salary_text:
                    return salary_text

        if not unit or unit in {"NEG", "THOA_THUAN"} or not amounts:
            return "Thoa thuan"
        return None

    @staticmethod
    def _tags_from(raw_tags: object) -> list[str]:
        if not isinstance(raw_tags, list):
            return []
        tags: list[str] = []
        for tag in raw_tags:
            if isinstance(tag, str) and tag.strip():
                tags.append(tag.strip())
            elif isinstance(tag, dict):
                value = tag.get("tag_name") or tag.get("name") or tag.get("value")
                if value:
                    tags.append(str(value).strip())
        return tags

    def _detail_tags(self, detail: dict) -> list[str]:
        tags = self._tags_from(detail.get("resume_tags"))
        for industry in detail.get("resume_industries") or []:
            if isinstance(industry, dict):
                name = industry.get("industry_name_vn") or industry.get("industry_name_en")
                if name:
                    tags.append(str(name).strip())
        return list(dict.fromkeys(tag for tag in tags if tag))

    def _detail_raw_text(self, detail: dict) -> str:
        industries = ", ".join(self._detail_tags(detail))
        objective = detail.get("resume_objective_vn") or detail.get("resume_objective_en")
        addition = detail.get("resume_addition_info_vn") or detail.get("resume_addition_info_en")
        return _compact_lines(
            detail.get("resume_headline_vn") or detail.get("resume_headline_en"),
            detail.get("jobseeker_fullname"),
            detail.get("resume_degree_name_vn") or detail.get("resume_degree_name_en"),
            self._format_experience(detail.get("resume_year_of_experience")),
            self._format_salary(detail),
            detail.get("jobseeker_location_name_vn") or detail.get("jobseeker_location_name_en"),
            detail.get("resume_last_company"),
            detail.get("resume_last_job"),
            industries,
            objective,
            addition,
            detail.get("resume_attachment_url"),
        )

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"CareerViet request failed with status {response.status_code}"
        message = payload.get("message") or payload.get("error")
        return str(message or f"CareerViet request failed with status {response.status_code}")

    def _parse_search_html(self, html: str, source_url: str) -> list[CareerVietProfileRecord]:
        rows = re.findall(r"(?is)<tr\b.*?</tr>", html)
        parsed: list[CareerVietProfileRecord] = []
        for row in rows:
            text = _strip_tags(row)
            lines = [line for line in text.splitlines() if line]
            if len(lines) < 2:
                continue
            joined = " ".join(lines)
            if "ung vien" in _normalize_text(joined) and "kinh nghiem" in _normalize_text(joined):
                continue

            href_match = re.search(r'(?is)<a[^>]+href=["\']([^"\']+)["\']', row)
            profile_url = urljoin(f"{self.base_url}/", href_match.group(1)) if href_match else source_url
            parsed.append(
                CareerVietProfileRecord(
                    id=_profile_id_from(profile_url or joined),
                    title=lines[0],
                    candidate_name=lines[1] if len(lines) > 1 else lines[0],
                    experience=self._find_after_label(lines, ["kinh nghiem"]) or self._guess_column(lines, 2),
                    salary=self._find_after_label(lines, ["luong"]) or self._guess_column(lines, 3),
                    location=self._find_after_label(lines, ["noi lam viec"]) or self._guess_column(lines, 4),
                    last_access=self._find_after_label(lines, ["ngay truy cap"]) or self._guess_column(lines, 5),
                    source_url=source_url,
                    profile_url=profile_url,
                    summary="\n".join(lines[:12]),
                    raw_text=text,
                )
            )
        return parsed

    @staticmethod
    def _guess_column(lines: list[str], index: int) -> str | None:
        return lines[index] if len(lines) > index else None

    @staticmethod
    def _find_after_label(lines: list[str], labels: list[str]) -> str | None:
        normalized_labels = [_normalize_text(label) for label in labels]
        for index, line in enumerate(lines):
            clean_line = _normalize_text(line)
            if any(label in clean_line for label in normalized_labels) and len(lines) > index + 1:
                return lines[index + 1]
        return None


def get_careerviet_client() -> CareerVietClient:
    return CareerVietClient()
