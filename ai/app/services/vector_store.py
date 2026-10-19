"""
File-based vector store for CV embeddings.
Stores CV embeddings in JSON files for persistence.
"""

import json
import shutil
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from app.core.config import settings


class CVVectorStore:
    """
    Simple file-based vector store for CV embeddings.
    Uses cosine similarity for search.
    """

    def __init__(self, store_dir: Path | None = None):
        self.store_dir = store_dir or (settings.tmp_dir / "cv_vectors")
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.store_dir / "index.json"
        self._load_index()

    def _load_index(self) -> None:
        """Load the index from disk."""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                self.index = json.load(f)
        else:
            self.index = {"documents": [], "metadata": {}}

    def _save_index(self) -> None:
        """Save the index to disk."""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def _get_sbert(self, sbert_id: str) -> SentenceTransformer:
        """Get or create SentenceTransformer instance."""
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return SentenceTransformer(sbert_id, device=device)

    def _embed_text(self, text: str, sbert: SentenceTransformer) -> np.ndarray:
        """Generate embedding for text."""
        with torch.no_grad():
            embedding = sbert.encode(
                text,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        return embedding

    def _embed_batch(self, texts: list[str], sbert: SentenceTransformer) -> np.ndarray:
        """Generate embeddings for multiple texts."""
        with torch.no_grad():
            embeddings = sbert.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        return embeddings

    def add_cv(
        self,
        cv_filename: str,
        cv_text: str,
        sbert_id: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Add a CV to the vector store.
        Returns the document ID.
        """
        sbert = self._get_sbert(sbert_id)
        embedding = self._embed_text(cv_text, sbert)

        doc_id = str(uuid.uuid4().hex)
        doc = {
            "id": doc_id,
            "filename": cv_filename,
            "text": cv_text,
            "embedding": embedding.tolist(),
            "sbert_id": sbert_id,
            "metadata": metadata or {},
        }

        self.index["documents"].append(doc)
        self.index["metadata"][doc_id] = {
            "filename": cv_filename,
            "sbert_id": sbert_id,
            **(metadata or {}),
        }
        self._save_index()
        return doc_id

    def add_cv_batch(
        self,
        cvs: list[dict],  # [{"filename": str, "text": str, "metadata": dict}]
        sbert_id: str,
    ) -> list[str]:
        """
        Add multiple CVs to the vector store in batch.
        Returns list of document IDs.
        """
        if not cvs:
            return []

        sbert = self._get_sbert(sbert_id)
        texts = [cv["text"] for cv in cvs]
        embeddings = self._embed_batch(texts, sbert)

        doc_ids = []
        for i, cv in enumerate(cvs):
            doc_id = str(uuid.uuid4().hex)
            doc = {
                "id": doc_id,
                "filename": cv["filename"],
                "text": cv["text"],
                "embedding": embeddings[i].tolist(),
                "sbert_id": sbert_id,
                "metadata": cv.get("metadata", {}),
            }
            self.index["documents"].append(doc)
            self.index["metadata"][doc_id] = {
                "filename": cv["filename"],
                "sbert_id": sbert_id,
                **cv.get("metadata", {}),
            }
            doc_ids.append(doc_id)

        self._save_index()
        return doc_ids

    def search(
        self,
        query_text: str,
        sbert_id: str,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[dict]:
        """
        Search for similar CVs using cosine similarity.
        Returns list of dicts with id, filename, score, text.
        """
        if not self.index["documents"]:
            return []

        # Filter documents by sbert_id
        matching_docs = [
            doc for doc in self.index["documents"]
            if doc.get("sbert_id") == sbert_id
        ]
        if not matching_docs:
            # Fallback: use any docs if no matching sbert_id
            matching_docs = self.index["documents"]

        sbert = self._get_sbert(sbert_id)
        query_embedding = self._embed_text(query_text, sbert)

        results = []
        for doc in matching_docs:
            doc_embedding = np.array(doc["embedding"])
            score = float(np.dot(query_embedding, doc_embedding))
            if score >= min_score:
                results.append({
                    "id": doc["id"],
                    "filename": doc["filename"],
                    "text": doc["text"],
                    "score": score,
                    "metadata": doc.get("metadata", {}),
                })

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get(self, doc_id: str) -> Optional[dict]:
        """Get a document by ID."""
        for doc in self.index["documents"]:
            if doc["id"] == doc_id:
                return doc
        return None

    def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        original_len = len(self.index["documents"])
        self.index["documents"] = [
            doc for doc in self.index["documents"] if doc["id"] != doc_id
        ]
        if doc_id in self.index["metadata"]:
            del self.index["metadata"][doc_id]

        if len(self.index["documents"]) < original_len:
            self._save_index()
            return True
        return False

    def clear(self) -> int:
        """Clear all documents. Returns count of deleted docs."""
        count = len(self.index["documents"])
        self.index = {"documents": [], "metadata": {}}
        self._save_index()
        return count

    def count(self) -> int:
        """Get total number of indexed CVs."""
        return len(self.index["documents"])

    def reindex_all(
        self,
        cvs: list[dict],  # [{"filename": str, "text": str, "metadata": dict}]
        sbert_id: str,
    ) -> dict:
        """
        Clear and reindex all CVs.
        Returns summary of indexing.
        """
        total = len(cvs)
        self.clear()

        if total == 0:
            return {"total_cvs": 0, "successful": 0, "failed": 0}

        successful = 0
        failed = 0

        # Process in batches
        batch_size = 50
        for i in range(0, total, batch_size):
            batch = cvs[i:i + batch_size]
            try:
                self.add_cv_batch(batch, sbert_id)
                successful += len(batch)
            except Exception as e:
                failed += len(batch)
                print(f"Batch indexing error: {e}")

        return {
            "total_cvs": total,
            "successful": successful,
            "failed": failed,
        }


# Global instance
_vector_store: Optional[CVVectorStore] = None


def get_vector_store() -> CVVectorStore:
    """Get or create the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = CVVectorStore()
    return _vector_store


def reset_vector_store() -> None:
    """Reset the global vector store (for testing)."""
    global _vector_store
    _vector_store = None
