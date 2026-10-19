import sys
import torch
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.registry import get_entry
from app.models.runtime import load_model as load_bi_model, _import_sentence_transformer

router = APIRouter()


class TextEmbeddingRequest(BaseModel):
    text: str = Field(..., min_length=1)
    model_id: str | None = None


@router.post("/text")
def embed_text(payload: TextEmbeddingRequest) -> dict:
    clean_text = payload.text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="text is required")

    try:
        entry = get_entry(payload.model_id)
        if entry.is_cross:
            # Cross-Encoder: load SBERT directly (no fusion model needed for embedding)
            SentenceTransformer = _import_sentence_transformer()
            sbert = SentenceTransformer(entry.sbert_id)
            sbert_id = entry.sbert_id
            with torch.no_grad():
                embedding = sbert.encode(
                    clean_text,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                )
        else:
            # Bi-Encoder: use standard load_model path
            _, sbert, entry = load_bi_model(payload.model_id)
            sbert_id = entry.sbert_id
            with torch.no_grad():
                embedding = sbert.encode(
                    clean_text,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    vector = embedding.astype(float).tolist()
    return {
        "status": "success",
        "data": {
            "model_id": entry.id,
            "sbert_id": sbert_id,
            "dimension": len(vector),
            "embedding": vector,
        },
    }
