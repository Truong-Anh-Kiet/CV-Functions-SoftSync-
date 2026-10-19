from typing import Any
from pydantic import BaseModel, Field


class ViewMatch(BaseModel):
    cv_view: str
    jd_view: str
    cv_label: str
    jd_label: str
    similarity: float
    status: str
    color: str
    cv_evidence: Any
    jd_evidence: Any
    reason: str


class MatchResult(BaseModel):
    rank: int
    cv_file: str
    score: float
    confidence: float
    match: bool
    label: str
    cv_view_coverage: str
    jd_view_coverage: str
    view_matches: list[ViewMatch] = Field(default_factory=list)
    cv_structured: dict[str, Any] | None = None
    jd_structured: dict[str, Any] | None = None
    # Thêm các trường dữ liệu phục vụ vẽ Heatmap visualize
    alignment_matrix_raw: list[list[float]] | None = Field(
        None, description="Ma trận cosine similarity 10x5 trước khi masking"
    )
    alignment_matrix_masked: list[list[float]] | None = Field(
        None, description="Ma trận cosine similarity 10x5 sau khi masking"
    )
    heatmap_labels: dict[str, list[str]] | None = Field(
        None, description="Danh sách nhãn hiển thị cho trục CV và JD trên Heatmap"
    )


class MatchingData(BaseModel):
    jd_file: str
    results: list[MatchResult]
    elapsed_seconds: float
    # Breakdown so the slow part is visible (extraction = OpenAI, inference = model).
    extraction_seconds: float = 0.0
    inference_seconds: float = 0.0
    model_used: str | None = None


class MatchingResponse(BaseModel):
    status: str
    data: MatchingData