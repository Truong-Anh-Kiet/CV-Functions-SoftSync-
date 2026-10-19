from fastapi import APIRouter

from app.api.v1.endpoints import academic, careerviet, exchange_rate, health, matching, ranking, structuring, upload, vietnamworks

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(exchange_rate.router, prefix="/exchange-rate", tags=["exchange-rate"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(matching.router, prefix="/matching", tags=["matching"])
api_router.include_router(ranking.router, prefix="/ranking", tags=["ranking"])
api_router.include_router(structuring.router, prefix="/structuring", tags=["structuring"])
api_router.include_router(careerviet.router, prefix="/web-search/careerviet", tags=["web-search-careerviet"])
api_router.include_router(vietnamworks.router, prefix="/web-search/vietnamworks", tags=["web-search-vietnamworks"])
api_router.include_router(academic.router, prefix="/web-search/academic", tags=["web-search-academic"])
