from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = Field(default="AIP491 Backend", validation_alias="APP_NAME_BE")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    backend_public_url: str = Field(default="http://localhost:8000", validation_alias="BACKEND_PUBLIC_URL")
    
    # Database
    database_url: str = Field(
        default="sqlite:///./app.db",
        validation_alias="DATABASE_URL",
    )

    # Cloudinary
    cloudinary_cloud_name: str = Field(default="", validation_alias="CLOUDINARY_CLOUD_NAME")
    cloudinary_api_key: str = Field(default="", validation_alias="CLOUDINARY_API_KEY")
    cloudinary_api_secret: str = Field(default="", validation_alias="CLOUDINARY_API_SECRET")

    # Auth
    jwt_secret_key: str = Field(
        default="change-this-secret-key-before-production",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=15,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        validation_alias="REFRESH_TOKEN_EXPIRE_DAYS",
    )
    email_otp_expire_minutes: int = Field(
        default=10,
        validation_alias="EMAIL_OTP_EXPIRE_MINUTES",
    )
    password_reset_otp_expire_minutes: int = Field(
        default=10,
        validation_alias="PASSWORD_RESET_OTP_EXPIRE_MINUTES",
    )
    auth_return_otp_in_response: bool = Field(
        default=False,
        validation_alias="AUTH_RETURN_OTP_IN_RESPONSE",
    )
    smtp_host: str = Field(default="smtp.gmail.com", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_username: str = Field(default="", validation_alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", validation_alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="", validation_alias="SMTP_FROM_EMAIL")
    smtp_from_name: str = Field(default="AIP491", validation_alias="SMTP_FROM_NAME")
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")
    smtp_timeout_seconds: float = Field(default=20.0, validation_alias="SMTP_TIMEOUT_SECONDS")
    google_client_id: str = Field(default="", validation_alias="GOOGLE_CLIENT_ID")
    # AI service
    ai_service_url: str = Field(default="http://127.0.0.1:8001", validation_alias="AI_SERVICE_URL")
    ai_service_timeout_seconds: float = Field(default=600.0, validation_alias="AI_SERVICE_TIMEOUT_SECONDS")

    # File storage
    upload_dir: str = Field(default="static_uploads", validation_alias="UPLOAD_DIR")

    # CareerViet HR search
    careerviet_base_url: str = Field(default="https://careerviet.vn", validation_alias="CAREERVIET_BASE_URL")
    careerviet_api_base_url: str = Field(
        default="https://internal-api.careerviet.vn",
        validation_alias="CAREERVIET_API_BASE_URL",
    )
    careerviet_search_path: str = Field(
        default="/vi/tim-ung-vien/nganh-nghe/cntt-phan-mem",
        validation_alias="CAREERVIET_SEARCH_PATH",
    )
    careerviet_default_industry_ids: str = Field(default="1", validation_alias="CAREERVIET_DEFAULT_INDUSTRY_IDS")
    careerviet_keyword_match_type: int = Field(default=1, validation_alias="CAREERVIET_KEYWORD_MATCH_TYPE")
    careerviet_hr_email: str = Field(default="", validation_alias="CAREERVIET_HR_EMAIL")
    careerviet_hr_password: str = Field(default="", validation_alias="CAREERVIET_HR_PASSWORD")
    careerviet_access_token: str = Field(default="", validation_alias="CAREERVIET_ACCESS_TOKEN")
    careerviet_employer_tokens: str = Field(default="", validation_alias="CAREERVIET_EMPLOYER_TOKENS")
    careerviet_session_cookie: str = Field(default="", validation_alias="CAREERVIET_SESSION_COOKIE")
    careerviet_request_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="CAREERVIET_REQUEST_TIMEOUT_SECONDS",
    )
    careerviet_mock_enabled: bool = Field(default=True, validation_alias="CAREERVIET_MOCK_ENABLED")
    careerviet_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        validation_alias="CAREERVIET_USER_AGENT",
    )

    # VietnamWorks HR search
    vietnamworks_base_url: str = Field(default="https://employer.vietnamworks.com", validation_alias="VIETNAMWORKS_BASE_URL")
    vietnamworks_graphql_url: str = Field(
        default="https://ms.vietnamworks.com/resume-search-api/graphql",
        validation_alias="VIETNAMWORKS_GRAPHQL_URL",
    )
    vietnamworks_search_url: str = Field(
        default="https://employer.vietnamworks.com/v3/candidate/search",
        validation_alias="VIETNAMWORKS_SEARCH_URL",
    )
    vietnamworks_hr_email: str = Field(default="", validation_alias="VIETNAMWORKS_HR_EMAIL")
    vietnamworks_hr_password: str = Field(default="", validation_alias="VIETNAMWORKS_HR_PASSWORD")
    vietnamworks_onb_jwt: str = Field(default="", validation_alias="VIETNAMWORKS_ONB_JWT")
    vietnamworks_session_cookie: str = Field(default="", validation_alias="VIETNAMWORKS_SESSION_COOKIE")
    vietnamworks_request_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="VIETNAMWORKS_REQUEST_TIMEOUT_SECONDS",
    )
    vietnamworks_mock_enabled: bool = Field(default=True, validation_alias="VIETNAMWORKS_MOCK_ENABLED")
    vietnamworks_accept_language: int = Field(default=1, validation_alias="VIETNAMWORKS_ACCEPT_LANGUAGE")
    vietnamworks_locale: str = Field(default="vn", validation_alias="VIETNAMWORKS_LOCALE")
    vietnamworks_sort_by: str = Field(default="lastdateupdated", validation_alias="VIETNAMWORKS_SORT_BY")
    vietnamworks_search_by: int = Field(default=3, validation_alias="VIETNAMWORKS_SEARCH_BY")
    vietnamworks_default_filters: str = Field(default="", validation_alias="VIETNAMWORKS_DEFAULT_FILTERS")
    vietnamworks_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        validation_alias="VIETNAMWORKS_USER_AGENT",
    )

    # Academic / Google Scholar-style search
    academic_search_provider: str = Field(default="openalex", validation_alias="ACADEMIC_SEARCH_PROVIDER")
    openalex_base_url: str = Field(default="https://api.openalex.org", validation_alias="OPENALEX_BASE_URL")
    openalex_mailto: str = Field(default="", validation_alias="OPENALEX_MAILTO")
    openalex_default_query: str = Field(default="computer science", validation_alias="OPENALEX_DEFAULT_QUERY")
    openalex_request_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="OPENALEX_REQUEST_TIMEOUT_SECONDS",
    )
    openalex_mock_enabled: bool = Field(default=False, validation_alias="OPENALEX_MOCK_ENABLED")
    openalex_max_authors_per_work: int = Field(default=3, validation_alias="OPENALEX_MAX_AUTHORS_PER_WORK")
    openalex_user_agent: str = Field(
        default="AIP491 academic search (mailto:unknown@example.com)",
        validation_alias="OPENALEX_USER_AGENT",
    )
    semantic_scholar_base_url: str = Field(
        default="https://api.semanticscholar.org/graph/v1",
        validation_alias="SEMANTIC_SCHOLAR_BASE_URL",
    )
    semantic_scholar_api_key: str = Field(default="", validation_alias="SEMANTIC_SCHOLAR_API_KEY")
    semantic_scholar_request_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="SEMANTIC_SCHOLAR_REQUEST_TIMEOUT_SECONDS",
    )
    semantic_scholar_min_request_interval_seconds: float = Field(
        default=1.5,
        validation_alias="SEMANTIC_SCHOLAR_MIN_REQUEST_INTERVAL_SECONDS",
    )
    semantic_scholar_max_retries: int = Field(
        default=2,
        validation_alias="SEMANTIC_SCHOLAR_MAX_RETRIES",
    )
    semantic_scholar_max_authors_per_paper: int = Field(
        default=3,
        validation_alias="SEMANTIC_SCHOLAR_MAX_AUTHORS_PER_PAPER",
    )
    semantic_scholar_author_paper_limit: int = Field(
        default=20,
        validation_alias="SEMANTIC_SCHOLAR_AUTHOR_PAPER_LIMIT",
    )
    semantic_scholar_user_agent: str = Field(
        default="AIP491 academic search",
        validation_alias="SEMANTIC_SCHOLAR_USER_AGENT",
    )

    # Exchange rate
    usd_vnd_rate_api_url: str = Field(
        default="https://open.er-api.com/v6/latest/USD",
        validation_alias="USD_VND_RATE_API_URL",
    )
    usd_vnd_rate_timeout_seconds: float = Field(
        default=5.0,
        validation_alias="USD_VND_RATE_TIMEOUT_SECONDS",
    )
    default_usd_vnd_rate: float = Field(
        default=26236.346503,
        validation_alias="DEFAULT_USD_VND_RATE",
    )
    usd_vnd_rate_cache_file: str = Field(
        default=".cache/usd_vnd_rate.json",
        validation_alias="USD_VND_RATE_CACHE_FILE",
    )

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
