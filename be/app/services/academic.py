from app.services.web_sources.academic import (
    AcademicSearchClient,
    AcademicSearchError,
    AcademicSearchProfileRecord,
    HybridAcademicSearchClient,
    OpenAlexClient,
    SemanticScholarClient,
    get_academic_search_client,
)

__all__ = [
    "AcademicSearchClient",
    "AcademicSearchError",
    "AcademicSearchProfileRecord",
    "HybridAcademicSearchClient",
    "OpenAlexClient",
    "SemanticScholarClient",
    "get_academic_search_client",
]
