from __future__ import annotations

import hashlib
import re
import threading
import time
import textwrap
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote, urljoin

import fitz
import requests

from app.core.config import settings


class AcademicSearchError(RuntimeError):
    pass


_SEMANTIC_SCHOLAR_LOCK = threading.Lock()
_SEMANTIC_SCHOLAR_LAST_REQUEST_AT = 0.0
_ACADEMIC_PROFILE_CACHE_LOCK = threading.Lock()
_ACADEMIC_PROFILE_CACHE_TTL_SECONDS = 900.0
_ACADEMIC_PROFILE_CACHE: dict[str, tuple[float, dict]] = {}


@dataclass(frozen=True)
class AcademicPaper:
    title: str
    year: int | None = None
    venue: str | None = None
    cited_by_count: int | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    topics: list[str] | None = None


@dataclass(frozen=True)
class AcademicSearchProfileRecord:
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
    source: str = "Google Scholar"
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


MOCK_PROFILES: list[AcademicSearchProfileRecord] = [
    AcademicSearchProfileRecord(
        id="scholar-A1001",
        title="Research profile: Machine learning engineer",
        candidate_name="Nguyen Minh Khoa",
        resume_id="A1001",
        education="Academic publications",
        level="Research candidate",
        experience="5 papers",
        location="FPT University",
        last_access="2026",
        source_url="https://openalex.org",
        profile_url="https://openalex.org/A1001",
        attachment_url="generated://academic/A1001.pdf",
        summary="Machine learning, NLP, recommendation systems.",
        tags=["Machine Learning", "NLP", "Recommendation Systems"],
        raw_text=(
            "Research profile: Machine learning engineer\n"
            "Nguyen Minh Khoa\n"
            "Affiliation: FPT University\n"
            "Papers\n"
            "- Neural ranking for recommendation systems (2025)\n"
            "- Vietnamese NLP for recruitment matching (2024)\n"
            "Research summary\n"
            "The author has publications related to machine learning, natural language processing, "
            "and ranking models for candidate matching."
        ),
    ),
    AcademicSearchProfileRecord(
        id="scholar-A1002",
        title="Research profile: Data science researcher",
        candidate_name="Tran Hoang Anh",
        resume_id="A1002",
        education="Academic publications",
        level="Research candidate",
        experience="3 papers",
        location="Ho Chi Minh City",
        last_access="2025",
        source_url="https://openalex.org",
        profile_url="https://openalex.org/A1002",
        attachment_url="generated://academic/A1002.pdf",
        summary="Data mining, analytics, software engineering.",
        tags=["Data Mining", "Analytics", "Software Engineering"],
        raw_text=(
            "Research profile: Data science researcher\n"
            "Tran Hoang Anh\n"
            "Papers\n"
            "- Data mining techniques for software repositories (2025)\n"
            "- Analytics dashboards for hiring workflows (2024)"
        ),
    ),
]


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
    "paper",
    "position",
    "research",
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
    "machine learning",
    "natural language processing",
    "computer vision",
    "deep learning",
    "data science",
    "data mining",
    "software engineering",
    "information retrieval",
    "recommendation system",
    "large language model",
    "artificial intelligence",
    "business analyst",
    "data engineer",
    "backend",
    "frontend",
    "fullstack",
    "java",
    "python",
    "react",
    "database",
    "devops",
]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _strip_html(value: object) -> str:
    text = str(value or "")
    return re.sub(r"<[^>]+>", "", text).strip()


def _as_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _compact_lines(*values: object) -> str:
    lines = [str(value).strip() for value in values if value is not None and str(value).strip()]
    return "\n".join(lines)


def _profile_id_from(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"scholar-{digest}"


def _openalex_suffix(openalex_id: str | None, fallback: str) -> str:
    if not openalex_id:
        return fallback
    return openalex_id.rstrip("/").split("/")[-1]


def _semantic_author_suffix(author_id: str | None, fallback: str) -> str:
    value = str(author_id or "").strip()
    if value:
        return value
    return _profile_id_from(fallback).replace("scholar-", "")


def _profile_cache_key(profile_id: str | None, profile_url: str | None = None) -> str:
    return f"{profile_id or ''}|{profile_url or ''}".strip().lower()


def _get_cached_profile(profile_id: str | None, profile_url: str | None = None) -> dict | None:
    keys = [_profile_cache_key(profile_id, profile_url), _profile_cache_key(profile_id, None), _profile_cache_key(None, profile_url)]
    now = time.monotonic()
    with _ACADEMIC_PROFILE_CACHE_LOCK:
        for key in keys:
            if not key or key == "|":
                continue
            cached = _ACADEMIC_PROFILE_CACHE.get(key)
            if not cached:
                continue
            cached_at, payload = cached
            if now - cached_at <= _ACADEMIC_PROFILE_CACHE_TTL_SECONDS:
                return dict(payload)
            _ACADEMIC_PROFILE_CACHE.pop(key, None)
    return None


def _cache_profile(profile: dict) -> None:
    profile_id = str(profile.get("id") or "").strip()
    profile_url = str(profile.get("profile_url") or "").strip()
    keys = [_profile_cache_key(profile_id, profile_url), _profile_cache_key(profile_id, None), _profile_cache_key(None, profile_url)]
    now = time.monotonic()
    with _ACADEMIC_PROFILE_CACHE_LOCK:
        for key in keys:
            if key and key != "|":
                _ACADEMIC_PROFILE_CACHE[key] = (now, dict(profile))


def _cached_profile_paper_count(profile: dict) -> int:
    raw_text = str(profile.get("raw_text") or profile.get("summary") or "")
    return len(re.findall(r"(?m)^(?:- |\d+\. )", raw_text))


def _should_refresh_academic_profile(profile: dict) -> bool:
    raw_text = str(profile.get("raw_text") or profile.get("summary") or "")
    if "Profile detail:" in raw_text:
        return False
    if _cached_profile_paper_count(profile) >= 5 and (
        "Academic metrics" in raw_text or "H-index:" in raw_text or "Cited by count:" in raw_text
    ):
        return False
    return True


def _reconstruct_abstract(index: object) -> str | None:
    if not isinstance(index, dict):
        return None
    positions: list[tuple[int, str]] = []
    for word, raw_positions in index.items():
        if not isinstance(raw_positions, list):
            continue
        for position in raw_positions:
            number = _as_int(position)
            if number is not None:
                positions.append((number, str(word)))
    if not positions:
        return None
    words = [word for _, word in sorted(positions, key=lambda item: item[0])]
    return " ".join(words)


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "academic-profile"


class AcademicSearchClient:
    def search_profiles(self, query: str | None, page: int, page_size: int) -> dict:
        raise NotImplementedError

    def search_profiles_by_jd(self, jd_text: str, page: int, page_size: int) -> dict:
        query = self._query_from_jd_text(jd_text)
        return self.search_profiles(query=query, page=page, page_size=page_size)

    def get_profile(self, profile_id: str, profile_url: str | None = None) -> dict:
        raise NotImplementedError

    def get_profile_file(self, profile_id: str, profile_url: str | None = None) -> dict:
        cached_profile = _get_cached_profile(profile_id, profile_url)
        profile = cached_profile
        if cached_profile is None or _should_refresh_academic_profile(cached_profile):
            try:
                profile = self.get_profile(profile_id, profile_url)
            except AcademicSearchError:
                if cached_profile is None:
                    raise
                profile = cached_profile
        raw_text = str(profile.get("raw_text") or profile.get("summary") or "")
        content = self._render_profile_pdf(raw_text, str(profile.get("title") or "Academic profile"))
        filename = f"{profile.get('resume_id') or profile_id}.pdf"
        return {
            "content": content,
            "content_type": "application/pdf",
            "filename": filename,
        }

    def _query_from_jd_text(self, jd_text: str) -> str:
        normalized = unicodedata.normalize("NFKD", jd_text)
        normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
        normalized = normalized.replace("c++", "cplusplus").replace("c#", "csharp").replace(".net", "dotnet")

        for term in JD_PRIORITY_TERMS:
            if term in normalized:
                return term

        tokens = re.findall(r"[a-z][a-z0-9]{1,}", normalized)
        terms = [token for token in tokens if token not in JD_STOPWORDS and len(token) >= 3]
        if terms:
            return " ".join(terms[:4])
        raise ValueError("JD content does not contain searchable academic keywords")

    @staticmethod
    def _render_profile_pdf(raw_text: str, title: str) -> bytes:
        doc = fitz.open()
        width, height = 595, 842
        margin = 42
        line_height = 14
        font_size = 10
        font_kwargs = AcademicSearchClient._pdf_font_kwargs()

        def new_page():
            page = doc.new_page(width=width, height=height)
            page.insert_text((margin, margin), title[:100], fontsize=14, **font_kwargs)
            return page, margin + 28

        page, y = new_page()
        for raw_line in raw_text.splitlines() or ["No academic profile detail returned."]:
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


class OpenAlexClient(AcademicSearchClient):
    def __init__(self) -> None:
        self.base_url = settings.openalex_base_url.rstrip("/")

    def search_profiles(self, query: str | None, page: int, page_size: int) -> dict:
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")

        clean_query = (query or settings.openalex_default_query).strip()
        if settings.openalex_mock_enabled:
            profiles = self._mock_search(clean_query)
            start = (page - 1) * page_size
            items = profiles[start : start + page_size]
            total = len(profiles)
        else:
            result = self._search_openalex(clean_query, page, page_size)
            items = result["items"]
            total = result["total"]

        return {
            "source": "Google Scholar",
            "query": query,
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": self._serialize_records(items),
        }

    def get_profile(self, profile_id: str, profile_url: str | None = None) -> dict:
        for profile in MOCK_PROFILES:
            if profile.id == profile_id:
                return profile.to_dict()

        if settings.openalex_mock_enabled:
            raise LookupError("Academic profile not found")

        author_id = self._author_id_from_reference(profile_id, profile_url)
        author = self._get_json(f"/authors/{quote(author_id)}")
        works = self._author_works(author_id, per_page=20)
        profile = self._record_from_author(author, works).to_dict()
        _cache_profile(profile)
        return profile

    @staticmethod
    def _serialize_records(records: list[AcademicSearchProfileRecord]) -> list[dict]:
        payloads = [record.to_dict() for record in records]
        for payload in payloads:
            _cache_profile(payload)
        return payloads

    def _search_openalex(self, query: str, page: int, page_size: int) -> dict:
        per_page = max(25, min(200, page_size * 4))
        payload = self._get_json(
            "/works",
            params={
                "search": query,
                "page": page,
                "per-page": per_page,
                "sort": "relevance_score:desc",
                "filter": "type:article",
            },
        )
        works = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(works, list):
            raise AcademicSearchError("OpenAlex search did not return works")
        records = self._records_from_works(works, page_size)
        meta = payload.get("meta") or {}
        total = _as_int(meta.get("count")) or len(records)
        return {"items": records, "total": total}

    def _records_from_works(self, works: list[dict], limit: int) -> list[AcademicSearchProfileRecord]:
        by_author: dict[str, dict] = {}
        max_authors = max(1, settings.openalex_max_authors_per_work)
        for work in works:
            paper = self._paper_from_work(work)
            for authorship in (work.get("authorships") or [])[:max_authors]:
                author = authorship.get("author") if isinstance(authorship, dict) else None
                if not isinstance(author, dict):
                    continue
                author_id = author.get("id")
                author_name = author.get("display_name")
                if not author_id or not author_name:
                    continue
                key = _openalex_suffix(str(author_id), str(author_name))
                item = by_author.setdefault(
                    key,
                    {
                        "id": str(author_id),
                        "name": str(author_name),
                        "institutions": [],
                        "papers": [],
                        "topics": [],
                    },
                )
                institution = self._institution_from_authorship(authorship)
                if institution:
                    item["institutions"].append(institution)
                item["papers"].append(paper)
                item["topics"].extend(paper.topics or [])
                if len(by_author) >= limit and all(len(value["papers"]) >= 1 for value in by_author.values()):
                    break
            if len(by_author) >= limit:
                break
        return [self._record_from_group(group) for group in list(by_author.values())[:limit]]

    def _record_from_author(self, author: dict, works: list[dict]) -> AcademicSearchProfileRecord:
        author_id = str(author.get("id") or "")
        group = {
            "id": author_id,
            "name": str(author.get("display_name") or "Academic author"),
            "institutions": [],
            "papers": [self._paper_from_work(work) for work in works],
            "topics": [],
            "works_count": author.get("works_count"),
            "cited_by_count": author.get("cited_by_count"),
            "is_detailed": True,
        }
        institution = author.get("last_known_institution") or {}
        if isinstance(institution, dict) and institution.get("display_name"):
            group["institutions"].append(str(institution["display_name"]))
        for paper in group["papers"]:
            group["topics"].extend(paper.topics or [])
        return self._record_from_group(group)

    def _record_from_group(self, group: dict) -> AcademicSearchProfileRecord:
        author_id = str(group.get("id") or "")
        resume_id = _openalex_suffix(author_id, _profile_id_from(str(group.get("name") or ""))).replace("scholar-", "")
        name = str(group.get("name") or "Academic author")
        papers: list[AcademicPaper] = group.get("papers") or []
        topics = list(dict.fromkeys(topic for topic in (group.get("topics") or []) if topic))[:12]
        institutions = list(dict.fromkeys(item for item in (group.get("institutions") or []) if item))
        cited_by = group.get("cited_by_count")
        works_count = group.get("works_count") or len(papers)
        last_year = max([paper.year for paper in papers if paper.year] or [None])
        raw_text = self._raw_text_from_group(
            name,
            institutions,
            papers,
            topics,
            works_count,
            cited_by,
            bool(group.get("is_detailed")),
        )
        summary = "\n".join(raw_text.splitlines()[:18])
        profile_focus = ", ".join(topics[:3]) if topics else "Academic publications"
        return AcademicSearchProfileRecord(
            id=f"scholar-{resume_id}",
            resume_id=resume_id,
            title=f"Research profile: {profile_focus}",
            candidate_name=name,
            education="Academic publications",
            level="Research candidate",
            experience=f"{works_count} papers" if works_count else None,
            location=", ".join(institutions[:2]) if institutions else None,
            last_access=str(last_year) if last_year else None,
            source_url="https://scholar.google.com",
            profile_url=self._author_profile_url(author_id, name),
            attachment_url=f"generated://academic/{resume_id}.pdf",
            summary=summary,
            tags=topics,
            raw_text=raw_text,
        )

    def _raw_text_from_group(
        self,
        name: str,
        institutions: list[str],
        papers: list[AcademicPaper],
        topics: list[str],
        works_count: object,
        cited_by: object,
        is_detailed: bool = False,
    ) -> str:
        paper_lines: list[str] = []
        for index, paper in enumerate(papers[:20], start=1):
            meta = " | ".join(
                value
                for value in [
                    str(paper.year) if paper.year else None,
                    paper.venue,
                    f"{paper.cited_by_count} citations" if paper.cited_by_count is not None else None,
                    paper.doi,
                ]
                if value
            )
            topic_text = ", ".join((paper.topics or [])[:5])
            paper_lines.append(f"{index}. {paper.title}{f' ({meta})' if meta else ''}")
            if topic_text:
                paper_lines.append(f"   Topics: {topic_text}")
            if paper.abstract:
                paper_lines.append(f"   Abstract: {paper.abstract[:1200]}")
            if paper.url:
                paper_lines.append(f"   URL: {paper.url}")

        metrics = _compact_lines(
            f"Works count: {works_count}" if works_count else None,
            f"Cited by count: {cited_by}" if cited_by else None,
            f"Publications included in this CV: {len(papers[:20])}" if papers else None,
        )

        return _compact_lines(
            f"Academic candidate: {name}",
            "Profile detail: OpenAlex author profile" if is_detailed else None,
            f"Affiliation: {', '.join(institutions)}" if institutions else None,
            "Academic metrics",
            metrics,
            f"Research topics: {', '.join(topics[:12])}" if topics else None,
            "Selected publications",
            "\n".join(paper_lines),
        )

    def _paper_from_work(self, work: dict) -> AcademicPaper:
        source = work.get("primary_location") or {}
        source_info = source.get("source") if isinstance(source, dict) else None
        topics = []
        for topic in work.get("topics") or []:
            if isinstance(topic, dict) and topic.get("display_name"):
                topics.append(str(topic["display_name"]))
        for concept in work.get("concepts") or []:
            if isinstance(concept, dict) and concept.get("display_name"):
                topics.append(str(concept["display_name"]))
        return AcademicPaper(
            title=_strip_html(work.get("display_name")) or "Untitled paper",
            year=_as_int(work.get("publication_year")),
            venue=str(source_info.get("display_name")) if isinstance(source_info, dict) and source_info.get("display_name") else None,
            cited_by_count=_as_int(work.get("cited_by_count")),
            doi=_clean(work.get("doi")),
            url=self._paper_url(work),
            abstract=_reconstruct_abstract(work.get("abstract_inverted_index")),
            topics=list(dict.fromkeys(topics))[:8],
        )

    @staticmethod
    def _paper_url(work: dict) -> str | None:
        primary = work.get("primary_location") or {}
        if isinstance(primary, dict):
            landing = primary.get("landing_page_url")
            pdf = primary.get("pdf_url")
            if pdf:
                return str(pdf)
            if landing:
                return str(landing)
        return _clean(work.get("doi") or work.get("id"))

    @staticmethod
    def _institution_from_authorship(authorship: dict) -> str | None:
        institutions = authorship.get("institutions")
        if not isinstance(institutions, list) or not institutions:
            raw = authorship.get("raw_affiliation_string")
            return str(raw).strip() if raw else None
        names = [
            str(institution.get("display_name")).strip()
            for institution in institutions
            if isinstance(institution, dict) and institution.get("display_name")
        ]
        return ", ".join(names) if names else None

    def _author_works(self, author_id: str, per_page: int) -> list[dict]:
        payload = self._get_json(
            "/works",
            params={
                "filter": f"authorships.author.id:{author_id}",
                "sort": "cited_by_count:desc",
                "per-page": per_page,
            },
        )
        works = payload.get("results") if isinstance(payload, dict) else None
        return works if isinstance(works, list) else []

    def _get_json(self, path: str, params: dict | None = None) -> dict:
        url = urljoin(f"{self.base_url}/", path.lstrip("/"))
        request_params = dict(params or {})
        if settings.openalex_mailto:
            request_params["mailto"] = settings.openalex_mailto
        try:
            response = requests.get(
                url,
                params=request_params,
                headers={"User-Agent": settings.openalex_user_agent},
                timeout=settings.openalex_request_timeout_seconds,
            )
        except requests.Timeout as exc:
            raise AcademicSearchError("OpenAlex request timed out. Please try again later.") from exc
        except requests.RequestException as exc:
            raise AcademicSearchError(f"OpenAlex request failed: {exc}") from exc
        if response.status_code >= 400:
            raise AcademicSearchError(self._error_message(response))
        return response.json()

    @staticmethod
    def _mock_search(query: str) -> list[AcademicSearchProfileRecord]:
        clean_query = _normalize_text(query)
        if not clean_query:
            return MOCK_PROFILES
        keywords = [word for word in clean_query.split(" ") if len(word) >= 2]
        return [
            profile
            for profile in MOCK_PROFILES
            if all(keyword in _normalize_text(profile.raw_text or profile.summary or "") for keyword in keywords)
        ]

    @staticmethod
    def _author_id_from_reference(profile_id: str, profile_url: str | None) -> str:
        if profile_id.startswith("scholar-"):
            candidate = profile_id.removeprefix("scholar-")
            if re.fullmatch(r"A\d+", candidate, flags=re.IGNORECASE):
                return candidate
        if profile_url:
            match = re.search(r"openalex\.org/(A\d+)", profile_url, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        raise ValueError("Valid OpenAlex author id or profile_url is required")

    @staticmethod
    def _author_profile_url(author_id: str, name: str) -> str:
        suffix = _openalex_suffix(author_id, "")
        if suffix:
            return f"https://openalex.org/{suffix}"
        return f"https://scholar.google.com/scholar?q={quote(name)}"

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"OpenAlex request failed with status {response.status_code}"
        message = payload.get("message") or payload.get("error")
        return str(message or f"OpenAlex request failed with status {response.status_code}")


class SemanticScholarClient(AcademicSearchClient):
    PAPER_FIELDS = ",".join(
        [
            "paperId",
            "title",
            "year",
            "venue",
            "citationCount",
            "abstract",
            "url",
            "externalIds",
            "fieldsOfStudy",
            "s2FieldsOfStudy",
            "tldr",
            "authors.authorId",
            "authors.name",
            "authors.url",
        ]
    )
    AUTHOR_FIELDS = ",".join(
        [
            "authorId",
            "name",
            "url",
            "affiliations",
            "paperCount",
            "citationCount",
            "hIndex",
            "papers.paperId",
            "papers.title",
            "papers.year",
            "papers.venue",
            "papers.citationCount",
            "papers.abstract",
            "papers.url",
            "papers.externalIds",
            "papers.fieldsOfStudy",
            "papers.s2FieldsOfStudy",
        ]
    )
    AUTHOR_PAPER_FIELDS = ",".join(
        [
            "paperId",
            "title",
            "year",
            "venue",
            "citationCount",
            "abstract",
            "url",
            "externalIds",
            "fieldsOfStudy",
            "s2FieldsOfStudy",
        ]
    )

    def __init__(self) -> None:
        self.base_url = settings.semantic_scholar_base_url.rstrip("/")

    def search_profiles(self, query: str | None, page: int, page_size: int) -> dict:
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")

        clean_query = (query or settings.openalex_default_query).strip()
        limit = max(10, min(100, page_size * 3))
        offset = max(0, (page - 1) * page_size)
        payload = self._get_json(
            "/paper/search",
            params={
                "query": clean_query,
                "limit": limit,
                "offset": offset,
                "fields": self.PAPER_FIELDS,
            },
        )
        papers = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(papers, list):
            raise AcademicSearchError("Semantic Scholar search did not return papers")
        records = self._records_from_papers(papers, page_size)
        total = _as_int(payload.get("total")) or len(records)
        return {
            "source": "Google Scholar",
            "query": query,
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": self._serialize_records(records),
        }

    def get_profile(self, profile_id: str, profile_url: str | None = None) -> dict:
        for profile in MOCK_PROFILES:
            if profile.id == profile_id:
                return profile.to_dict()

        author_id = self._author_id_from_reference(profile_id, profile_url)
        payload = self._get_json(
            f"/author/{quote(author_id)}",
            params={"fields": self.AUTHOR_FIELDS},
        )
        paper_limit = max(1, min(100, settings.semantic_scholar_author_paper_limit))
        try:
            papers_payload = self._get_json(
                f"/author/{quote(author_id)}/papers",
                params={
                    "fields": self.AUTHOR_PAPER_FIELDS,
                    "limit": paper_limit,
                },
            )
            papers = papers_payload.get("data") if isinstance(papers_payload, dict) else None
            if isinstance(papers, list) and papers:
                payload["papers"] = papers
        except AcademicSearchError:
            pass
        profile = self._record_from_author(payload).to_dict()
        _cache_profile(profile)
        return profile

    @staticmethod
    def _serialize_records(records: list[AcademicSearchProfileRecord]) -> list[dict]:
        payloads = [record.to_dict() for record in records]
        for payload in payloads:
            _cache_profile(payload)
        return payloads

    def _records_from_papers(self, papers: list[dict], limit: int) -> list[AcademicSearchProfileRecord]:
        by_author: dict[str, dict] = {}
        max_authors = max(1, settings.semantic_scholar_max_authors_per_paper)
        for paper_payload in papers:
            paper = self._paper_from_payload(paper_payload)
            for author in (paper_payload.get("authors") or [])[:max_authors]:
                if not isinstance(author, dict):
                    continue
                author_id = _clean(author.get("authorId"))
                author_name = _clean(author.get("name"))
                if not author_id or not author_name:
                    continue
                item = by_author.setdefault(
                    author_id,
                    {
                        "id": author_id,
                        "name": author_name,
                        "url": _clean(author.get("url")),
                        "institutions": [],
                        "papers": [],
                        "topics": [],
                    },
                )
                item["papers"].append(paper)
                item["topics"].extend(paper.topics or [])
                if len(by_author) >= limit and all(len(value["papers"]) >= 1 for value in by_author.values()):
                    break
            if len(by_author) >= limit:
                break
        return [self._record_from_group(group) for group in list(by_author.values())[:limit]]

    def _record_from_author(self, author: dict) -> AcademicSearchProfileRecord:
        papers = [self._paper_from_payload(paper) for paper in (author.get("papers") or [])]
        papers.sort(key=lambda paper: (paper.cited_by_count or 0, paper.year or 0), reverse=True)
        paper_limit = max(1, min(100, settings.semantic_scholar_author_paper_limit))
        group = {
            "id": str(author.get("authorId") or ""),
            "name": str(author.get("name") or "Academic author"),
            "url": _clean(author.get("url")),
            "institutions": [
                str(value).strip()
                for value in (author.get("affiliations") or [])
                if value is not None and str(value).strip()
            ],
            "papers": papers[:paper_limit],
            "topics": [],
            "works_count": author.get("paperCount"),
            "cited_by_count": author.get("citationCount"),
            "h_index": author.get("hIndex"),
            "is_detailed": True,
        }
        for paper in group["papers"]:
            group["topics"].extend(paper.topics or [])
        return self._record_from_group(group)

    def _record_from_group(self, group: dict) -> AcademicSearchProfileRecord:
        author_id = str(group.get("id") or "")
        name = str(group.get("name") or "Academic author")
        resume_id = f"s2-{_semantic_author_suffix(author_id, name)}"
        papers: list[AcademicPaper] = group.get("papers") or []
        topics = list(dict.fromkeys(topic for topic in (group.get("topics") or []) if topic))[:12]
        institutions = list(dict.fromkeys(item for item in (group.get("institutions") or []) if item))
        works_count = group.get("works_count") or len(papers)
        cited_by = group.get("cited_by_count")
        h_index = group.get("h_index")
        last_year = max([paper.year for paper in papers if paper.year] or [None])
        raw_text = self._raw_text_from_group(
            name,
            institutions,
            papers,
            topics,
            works_count,
            cited_by,
            h_index,
            bool(group.get("is_detailed")),
        )
        summary = "\n".join(raw_text.splitlines()[:18])
        profile_focus = ", ".join(topics[:3]) if topics else "Academic publications"
        return AcademicSearchProfileRecord(
            id=f"scholar-{resume_id}",
            resume_id=resume_id,
            title=f"Research profile: {profile_focus}",
            candidate_name=name,
            education="Academic publications",
            level="Research candidate",
            experience=f"{works_count} papers" if works_count else None,
            location=", ".join(institutions[:2]) if institutions else None,
            last_access=str(last_year) if last_year else None,
            source_url="https://www.semanticscholar.org",
            profile_url=group.get("url") or self._author_profile_url(author_id, name),
            attachment_url=f"generated://academic/{resume_id}.pdf",
            summary=summary,
            tags=topics,
            raw_text=raw_text,
        )

    def _raw_text_from_group(
        self,
        name: str,
        institutions: list[str],
        papers: list[AcademicPaper],
        topics: list[str],
        works_count: object,
        cited_by: object,
        h_index: object,
        is_detailed: bool = False,
    ) -> str:
        paper_lines: list[str] = []
        paper_limit = max(1, min(100, settings.semantic_scholar_author_paper_limit))
        for index, paper in enumerate(papers[:paper_limit], start=1):
            meta = " | ".join(
                value
                for value in [
                    str(paper.year) if paper.year else None,
                    paper.venue,
                    f"{paper.cited_by_count} citations" if paper.cited_by_count is not None else None,
                    paper.doi,
                ]
                if value
            )
            topic_text = ", ".join((paper.topics or [])[:5])
            paper_lines.append(f"{index}. {paper.title}{f' ({meta})' if meta else ''}")
            if topic_text:
                paper_lines.append(f"   Topics: {topic_text}")
            if paper.abstract:
                paper_lines.append(f"   Abstract: {paper.abstract[:1200]}")
            if paper.url:
                paper_lines.append(f"   URL: {paper.url}")

        metrics = _compact_lines(
            f"Works count: {works_count}" if works_count else None,
            f"Cited by count: {cited_by}" if cited_by else None,
            f"H-index: {h_index}" if h_index else None,
            f"Publications included in this CV: {len(papers[:paper_limit])}" if papers else None,
        )

        return _compact_lines(
            f"Academic candidate: {name}",
            "Profile detail: Semantic Scholar author profile" if is_detailed else None,
            f"Affiliation: {', '.join(institutions)}" if institutions else None,
            "Academic metrics",
            metrics,
            f"Research topics: {', '.join(topics[:12])}" if topics else None,
            "Selected publications",
            "\n".join(paper_lines),
        )

    def _paper_from_payload(self, paper: dict) -> AcademicPaper:
        external_ids = paper.get("externalIds") if isinstance(paper.get("externalIds"), dict) else {}
        topics: list[str] = []
        for topic in paper.get("fieldsOfStudy") or []:
            if topic:
                topics.append(str(topic))
        for topic in paper.get("s2FieldsOfStudy") or []:
            if isinstance(topic, dict) and topic.get("category"):
                topics.append(str(topic["category"]))
        tldr = paper.get("tldr")
        tldr_text = tldr.get("text") if isinstance(tldr, dict) else None
        return AcademicPaper(
            title=_strip_html(paper.get("title")) or "Untitled paper",
            year=_as_int(paper.get("year")),
            venue=_clean(paper.get("venue")),
            cited_by_count=_as_int(paper.get("citationCount")),
            doi=_clean(external_ids.get("DOI")),
            url=_clean(paper.get("url") or (f"https://doi.org/{external_ids.get('DOI')}" if external_ids.get("DOI") else None)),
            abstract=_clean(paper.get("abstract") or tldr_text),
            topics=list(dict.fromkeys(topics))[:8],
        )

    def _get_json(self, path: str, params: dict | None = None) -> dict:
        url = urljoin(f"{self.base_url}/", path.lstrip("/"))
        headers = {"User-Agent": settings.semantic_scholar_user_agent}
        if settings.semantic_scholar_api_key:
            headers["x-api-key"] = settings.semantic_scholar_api_key
        max_retries = max(0, settings.semantic_scholar_max_retries)
        response: requests.Response | None = None
        for attempt in range(max_retries + 1):
            self._wait_for_rate_limit()
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=settings.semantic_scholar_request_timeout_seconds,
                )
            except requests.Timeout as exc:
                if attempt >= max_retries:
                    raise AcademicSearchError("Semantic Scholar request timed out. Please try again later.") from exc
                time.sleep(1.0 + attempt)
                continue
            except requests.RequestException as exc:
                raise AcademicSearchError(f"Semantic Scholar request failed: {exc}") from exc

            if response.status_code != 429:
                break
            if attempt >= max_retries:
                raise AcademicSearchError(self._error_message(response))
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 1.5 + attempt
            except ValueError:
                delay = 1.5 + attempt
            time.sleep(max(delay, settings.semantic_scholar_min_request_interval_seconds))

        if response is None:
            raise AcademicSearchError("Semantic Scholar request failed")
        if response.status_code >= 400:
            raise AcademicSearchError(self._error_message(response))
        return response.json()

    @staticmethod
    def _wait_for_rate_limit() -> None:
        global _SEMANTIC_SCHOLAR_LAST_REQUEST_AT
        interval = max(0.0, settings.semantic_scholar_min_request_interval_seconds)
        if interval <= 0:
            return
        with _SEMANTIC_SCHOLAR_LOCK:
            now = time.monotonic()
            wait_for = interval - (now - _SEMANTIC_SCHOLAR_LAST_REQUEST_AT)
            if wait_for > 0:
                time.sleep(wait_for)
            _SEMANTIC_SCHOLAR_LAST_REQUEST_AT = time.monotonic()

    @staticmethod
    def _author_id_from_reference(profile_id: str, profile_url: str | None) -> str:
        if profile_id.startswith("scholar-s2-"):
            return profile_id.removeprefix("scholar-s2-")
        if profile_id.startswith("s2-"):
            return profile_id.removeprefix("s2-")
        if profile_url:
            match = re.search(r"semanticscholar\.org/author/(?:[^/]+/)?([A-Za-z0-9]+)", profile_url)
            if match:
                return match.group(1)
        raise ValueError("Valid Semantic Scholar author id or profile_url is required")

    @staticmethod
    def _author_profile_url(author_id: str, name: str) -> str:
        if author_id:
            return f"https://www.semanticscholar.org/author/{quote(author_id)}"
        return f"https://www.semanticscholar.org/search?q={quote(name)}&sort=relevance"

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"Semantic Scholar request failed with status {response.status_code}"
        message = payload.get("message") or payload.get("error")
        return str(message or f"Semantic Scholar request failed with status {response.status_code}")


class HybridAcademicSearchClient(OpenAlexClient):
    def __init__(self) -> None:
        super().__init__()
        self.semantic = SemanticScholarClient()

    def search_profiles(self, query: str | None, page: int, page_size: int) -> dict:
        openalex_data = None
        semantic_data = None
        openalex_error = None
        semantic_error = None

        try:
            semantic_data = self.semantic.search_profiles(query=query, page=page, page_size=page_size)
        except ValueError:
            raise
        except AcademicSearchError as exc:
            semantic_error = exc

        if semantic_data and len(semantic_data.get("items") or []) >= page_size:
            return semantic_data

        try:
            openalex_data = super().search_profiles(query=query, page=page, page_size=page_size)
        except (ValueError, AcademicSearchError) as exc:
            openalex_error = exc

        if semantic_data is None:
            if openalex_data is None and semantic_error and openalex_error:
                raise AcademicSearchError(f"Semantic Scholar failed: {semantic_error}; OpenAlex failed: {openalex_error}") from openalex_error
            if openalex_data is None and semantic_error:
                raise semantic_error
            if openalex_data is None and openalex_error:
                raise openalex_error
            return openalex_data
        if openalex_data is None:
            return semantic_data

        combined_items: list[dict] = []
        seen: set[str] = set()
        for source_data in [semantic_data, openalex_data]:
            for item in source_data.get("items") or []:
                key = _normalize_text(f"{item.get('candidate_name') or ''} {item.get('title') or ''}")
                if not key or key in seen:
                    continue
                combined_items.append(item)
                seen.add(key)
                if len(combined_items) >= page_size:
                    break
            if len(combined_items) >= page_size:
                break

        return {
            "source": "Google Scholar",
            "query": query,
            "page": page,
            "page_size": page_size,
            "total": max(_as_int(semantic_data.get("total")) or 0, _as_int(openalex_data.get("total")) or 0),
            "items": combined_items,
        }

    def get_profile(self, profile_id: str, profile_url: str | None = None) -> dict:
        if profile_id.startswith("scholar-s2-") or profile_id.startswith("s2-") or (
            profile_url and "semanticscholar.org" in profile_url
        ):
            return self.semantic.get_profile(profile_id, profile_url)
        return super().get_profile(profile_id, profile_url)


def get_academic_search_client() -> AcademicSearchClient:
    provider = settings.academic_search_provider.strip().lower()
    if provider in {"hybrid", "semantic_openalex", "openalex_semantic"}:
        return HybridAcademicSearchClient()
    if provider in {"semantic_scholar", "semanticscholar", "s2"}:
        return SemanticScholarClient()
    if provider not in {"openalex", "google_scholar", "scholar"}:
        raise AcademicSearchError(f"Unsupported academic search provider: {settings.academic_search_provider}")
    return OpenAlexClient()
