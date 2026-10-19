from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from app.db.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"
    __table_args__ = (
        UniqueConstraint("document_id", "model_id", name="uq_document_embedding_model"),
    )

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    model_id = Column(String, index=True)
    sbert_id = Column(String)
    dimension = Column(Integer)
    text_hash = Column(String, index=True)
    source_text = Column(Text)
    embedding_json = Column(Text)
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
