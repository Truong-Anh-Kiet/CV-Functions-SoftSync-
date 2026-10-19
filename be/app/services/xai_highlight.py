import re
import uuid
from pathlib import Path
from typing import Any

from app.services.document_storage import UPLOAD_DIR, preview_url_for, safe_filename


HIGHLIGHT_COLORS = {
    "green": (0.20, 0.80, 0.35),
    "orange": (1.00, 0.62, 0.15),
    "red": (0.95, 0.25, 0.25),
}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)


# A snippet must be at least this long to be specific enough that an exact
# match in the PDF is very unlikely to be coincidental (avoids highlighting
# unrelated text). GPT-extracted evidence is often reworded, so we only search
# for longer sentence/clause fragments — precision over recall.
_MIN_SNIPPET = 30
_MAX_SNIPPET = 200


def _candidate_snippets(value: Any) -> list[str]:
    text = _stringify(value)
    if not text or text.strip().lower() in {"missing_section", "none"}:
        return []

    normalized = " ".join(text.replace("\x00", " ").split())
    if len(normalized) < _MIN_SNIPPET:
        return []

    # Only sentence / clause-level fragments — specific enough to be verbatim.
    # (Deliberately NO short word-chunks or a prefix fallback: those matched
    # unrelated text and produced wrong highlights.)
    candidates: list[str] = []
    for part in re.split(r"(?<=[.!?;:])\s+|\n+|[•·•]", normalized):
        clean = part.strip(" -–—•·\t")
        if _MIN_SNIPPET <= len(clean) <= _MAX_SNIPPET:
            candidates.append(clean)

    seen: set[str] = set()
    unique: list[str] = []
    for candidate in sorted(candidates, key=len, reverse=True):  # longest (most specific) first
        key = candidate.lower()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique[:6]


def create_highlighted_pdf(
    source_path: Path,
    view_matches: list[dict],
    side: str,
) -> str | None:
    if source_path.suffix.lower() != ".pdf" or not source_path.exists():
        return None

    try:
        import fitz
    except Exception:
        return None

    output_name = safe_filename(f"xai_{uuid.uuid4().hex}_{source_path.name}")
    output_path = UPLOAD_DIR / output_name
    evidence_key = f"{side}_evidence"

    try:
        max_hits_per_match = 8
        max_occurrences_per_snippet = 3  # a fragment found in many places is generic -> skip

        document = fitz.open(source_path)
        for match in view_matches:
            color = HIGHLIGHT_COLORS.get(match.get("color"), HIGHLIGHT_COLORS["orange"])
            snippets = _candidate_snippets(match.get(evidence_key))
            hits_for_match = 0

            for snippet in snippets:
                if hits_for_match >= max_hits_per_match:
                    break
                occurrences = [(page, rect) for page in document for rect in page.search_for(snippet)]
                # Skip fragments that don't match, or match in too many places
                # (ambiguous -> likely highlighting the wrong region).
                if not occurrences or len(occurrences) > max_occurrences_per_snippet:
                    continue
                for page, rect in occurrences:
                    if hits_for_match >= max_hits_per_match:
                        break
                    annot = page.add_highlight_annot(rect)
                    annot.set_colors(stroke=color)
                    annot.set_opacity(0.35)
                    annot.update()
                    hits_for_match += 1

        document.save(output_path, garbage=4, deflate=True)
        document.close()
        return preview_url_for(output_name)
    except Exception:
        return None
