from pydantic import BaseModel, Field


class CareerVietProfile(BaseModel):
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
    tags: list[str] = Field(default_factory=list)
    raw_text: str | None = None


class CareerVietSearchData(BaseModel):
    source: str = "CareerViet"
    query: str | None = None
    page: int
    page_size: int
    total: int
    items: list[CareerVietProfile]


class CareerVietSearchResponse(BaseModel):
    status: str
    data: CareerVietSearchData


class CareerVietProfileResponse(BaseModel):
    status: str
    data: CareerVietProfile
