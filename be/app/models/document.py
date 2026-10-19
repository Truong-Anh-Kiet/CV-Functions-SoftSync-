from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.db.base import Base

def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    cloudinary_url = Column(String)
    category = Column(String)  # 'CV' hoặc 'JD'
    raw_text = Column(Text, nullable=True)  # extracted text stored for resilience
    created_at = Column(DateTime, default=utc_now_naive)
