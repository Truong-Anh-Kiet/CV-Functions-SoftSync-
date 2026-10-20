import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # Thêm dòng này
from fastapi.staticfiles import StaticFiles
import os

from app.api.v1.api import api_router
from app.api.v1.endpoints.auth import router as auth_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401

logger = logging.getLogger("uvicorn.error")

def create_app() -> FastAPI:
    # Tự động tạo bảng Database
    Base.metadata.create_all(bind=engine)
    
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    # ================= CẤU HÌNH CORS (QUAN TRỌNG) =================
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # Cho phép tất cả các nguồn (hoặc điền cụ thể ["http://localhost:5173"])
        allow_credentials=True,
        allow_methods=["*"], # Cho phép tất cả các phương thức (GET, POST, PUT, DELETE...)
        allow_headers=["*"], # Cho phép tất cả các headers
    )
    # ============================================================

    # Thư mục lưu file upload
    upload_dir = settings.upload_dir

    # Vercel chỉ cho phép ghi tạm vào /tmp
    if os.getenv("VERCEL") and not os.path.isabs(upload_dir):
        upload_dir = os.path.join("/tmp", upload_dir)

    os.makedirs(upload_dir, exist_ok=True)

    # Phục vụ file tĩnh
    app.mount( "/static", StaticFiles(directory=upload_dir), name="static",)

    # Đăng ký router
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.on_event("startup")
    def log_swagger_url() -> None:
        logger.info("Swagger UI available at: http://127.0.0.1:8000/docs")
    
    return app


app = create_app()
