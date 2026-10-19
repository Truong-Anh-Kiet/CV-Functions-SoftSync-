from fastapi import APIRouter

from app.api.v1.endpoints import embeddings, health, jd_search, matching

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(matching.router, prefix="/matching", tags=["matching"])
api_router.include_router(embeddings.router, prefix="/embeddings", tags=["embeddings"])
api_router.include_router(jd_search.router, prefix="/jd-search", tags=["jd-search"])
