"""
Unified inference pipeline shared by all 4 model variants.

The 4 classifiers all accept the same input shape (Tensor[B, 50]) — the
masked cross-view cosine similarity vector. This module owns the
SBERT-encode → cosine → mask → flatten preprocessing, plus the XAI
view-match builder used by the response payload.
"""

import numpy as np
import torch
import torch.nn.functional as F

from app.models.registry import ModelEntry
from app.models.runtime import device
from app.services.extraction import CV_VIEWS, JD_VIEWS


XAI_VIEW_PAIRS = [
    ("skills", "skills"),
    ("education", "education"),
    ("year_experience", "year_experience_requirement"),
    ("experience", "experience_requirement"),
    ("responsibilities", "responsibilities"),
    ("projects", "responsibilities"),
]

VIEW_LABELS = {
    "skills": "Skills",
    "education": "Education",
    "year_experience": "Year Experience",
    "experience": "Experience",
    "responsibilities": "Responsibilities",
    "projects": "Projects",
    "year_experience_requirement": "Year Experience Requirement",
    "experience_requirement": "Experience Requirement",
}


def process_view(view_data):
    if view_data is None:
        return "[EMPTY_SECTION]", 0
    if isinstance(view_data, list):
        clean = [str(item) for item in view_data if str(item).lower() != "missing_section"]
        if not clean:
            return "[EMPTY_SECTION]", 0
        return ". ".join(clean), 1

    val = str(view_data).lower()
    if val in ("missing_section", "", "none"):
        return "[EMPTY_SECTION]", 0
    return str(view_data), 1


def _classify_view_match(similarity: float, cv_exists: int, jd_exists: int) -> tuple[str, str]:
    if not cv_exists or not jd_exists:
        return "missing", "red"
    if similarity >= 0.68:
        return "strong_match", "green"
    if similarity >= 0.45:
        return "partial_match", "orange"
    return "mismatch", "red"


def _clean_evidence_text(raw) -> str:
    """Human-readable text for a structured view value (joins lists instead of
    showing Python list repr like ['Python', 'SQL'])."""
    if isinstance(raw, list):
        parts = [str(item) for item in raw if str(item).strip().lower() != "missing_section"]
        return ", ".join(parts)
    return str(raw) if raw is not None else ""


def _get_heatmap_label(view: str, structured: dict, max_len: int = 40) -> str:
    text = _clean_evidence_text(structured.get(view))
    if text.strip().lower() in ("missing_section", "", "none"):
        return f"[{view[:4].upper()}] (Empty)"
    return f"[{view[:4].upper()}] {text[:max_len]}.."


def _build_xai_matches(
    cv_structured: dict,
    jd_structured: dict,
    cv_exists: tuple[int, ...],
    jd_exists: tuple[int, ...],
    similarity_matrix,
) -> list[dict]:
    matches = []
    for cv_view, jd_view in XAI_VIEW_PAIRS:
        cv_idx = CV_VIEWS.index(cv_view)
        jd_idx = JD_VIEWS.index(jd_view)
        similarity = float(similarity_matrix[cv_idx][jd_idx])
        status, color = _classify_view_match(similarity, cv_exists[cv_idx], jd_exists[jd_idx])
        cv_evidence = cv_structured.get(cv_view) or "missing_section"
        jd_evidence = jd_structured.get(jd_view) or "missing_section"

        if status == "strong_match":
            reason = "Hai phần này có độ tương đồng ngữ nghĩa cao và đóng góp tích cực cho matching."
        elif status == "partial_match":
            reason = "Hai phần này có liên quan nhưng chưa khớp hoàn toàn."
        elif status == "missing":
            reason = "Thiếu thông tin ở CV hoặc JD nên model không có đủ bằng chứng cho view này."
        else:
            reason = "Hai phần này có độ tương đồng thấp, là tín hiệu không phù hợp."

        matches.append(
            {
                "cv_view": cv_view,
                "jd_view": jd_view,
                "cv_label": VIEW_LABELS.get(cv_view, cv_view),
                "jd_label": VIEW_LABELS.get(jd_view, jd_view),
                "similarity": round(similarity, 4),
                "status": status,
                "color": color,
                "cv_evidence": cv_evidence,
                "jd_evidence": jd_evidence,
                "reason": reason,
            }
        )
    return matches


def predict(
    cv_structured: dict,
    jd_structured: dict,
    model,
    sbert_model,
    entry: ModelEntry,
) -> dict:
    cv_data = [process_view(cv_structured.get(view)) for view in CV_VIEWS]
    jd_data = [process_view(jd_structured.get(view)) for view in JD_VIEWS]
    cv_texts, cv_exists = zip(*cv_data)
    jd_texts, jd_exists = zip(*jd_data)

    with torch.no_grad():
        cv_emb = (
            sbert_model.encode(list(cv_texts), convert_to_tensor=True, device=device)
            .clone()
            .unsqueeze(0)
        )
        jd_emb = (
            sbert_model.encode(list(jd_texts), convert_to_tensor=True, device=device)
            .clone()
            .unsqueeze(0)
        )

        cv_n = F.normalize(cv_emb, p=2, dim=-1)
        jd_n = F.normalize(jd_emb, p=2, dim=-1)
        sim = torch.bmm(cv_n, jd_n.transpose(1, 2))  # [1, num_cv, num_jd]
        similarity_matrix = sim.squeeze(0).detach().cpu().numpy()

        # Tính ma trận mask (binary 10x5)
        m_ij_mask = np.outer(cv_exists, jd_exists)
        
        # Tạo tensor mask phẳng để đưa vào model tính score tổng
        m_ij_flat = torch.tensor(
            m_ij_mask.flatten(),
            dtype=torch.float32,
            device=device,
        ).unsqueeze(0)

        # Pipeline tính toán matching: sim * mask
        x = sim.reshape(sim.size(0), -1) * m_ij_flat  # [1, 50]
        raw = model(x).item()

        # Dữ liệu phục vụ vẽ Heatmap (convert sang list để JSON serializable)
        alignment_raw = similarity_matrix.tolist()
        alignment_masked = (similarity_matrix * m_ij_mask).tolist()

    return {
        "score": round(raw * 10, 2),
        "confidence": round(max(0.0, raw), 4),
        "match": raw >= 0.5,
        "label": "MATCHED" if raw >= 0.5 else "MISMATCH",
        "cv_view_coverage": f"{sum(cv_exists)}/{len(cv_exists)}",
        "jd_view_coverage": f"{sum(jd_exists)}/{len(jd_exists)}",
        # Hai ma trận dữ liệu phục vụ vẽ Heatmap
        "alignment_matrix_raw": alignment_raw,
        "alignment_matrix_masked": alignment_masked,
        # Nhãn cho các trục của Heatmap - lấy từ structured data (cùng nguồn với XAI)
        "heatmap_labels": {
            "cv": [_get_heatmap_label(v, cv_structured, 45) for v in CV_VIEWS],
            "jd": [_get_heatmap_label(v, jd_structured, 40) for v in JD_VIEWS],
        },
        "view_matches": _build_xai_matches(
            cv_structured,
            jd_structured,
            cv_exists,
            jd_exists,
            similarity_matrix,
        ),
    }