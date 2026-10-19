# AIP491 Backend

FastAPI backend (port **8000**): auth, document storage, and the gateway that proxies ML requests to the AI service (:8001).

> 📖 **Hướng dẫn chạy toàn bộ hệ thống (BE + AI + FE) + chia sẻ demo qua Dev Tunnels + push GitHub:** xem [`HUONG_DAN_CHAY.md`](HUONG_DAN_CHAY.md).

## Features

- **CV–JD matching** (`POST /api/v1/matching/cv-jd`) — proxies to the AI service; accepts CV PDFs + JD as **PDF or pasted text**; returns the match results plus **XAI-highlighted** CV/JD PDFs.
- **CV vector search & ranking** (`/api/v1/matching/search-cvs`, `/search-cvs/from-jd`) — embed + cosine search over stored CVs, with optional cross-encoder rerank via the AI service.
- **JD analysis** (`/api/v1/matching/jd-analysis`).
- **Auth** (email + Google), **upload**, **structuring**, and **web search** endpoints.

Requires the **AI service (:8001)** running for matching/search — set `AI_SERVICE_URL` in `.env`.

## Structure

```text
app/
  api/              API routers (matching, auth, upload, structuring, web-search)
  core/             App settings, security
  db/               SQLAlchemy base, engine, sessions
  models/           SQLAlchemy models (Document, User, embeddings)
  schemas/          Pydantic request/response schemas
  services/         ai_client, cv_vector_search, xai_highlight, document_storage
  utils/            Shared helpers
alembic/            Database migrations
tests/              Automated tests
```

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # set DATABASE_URL, JWT secrets, AI_SERVICE_URL, ...
uvicorn app.main:app --reload
```

Health check: `GET http://127.0.0.1:8000/api/v1/health`

## Tests

```powershell
pytest
```

## Gmail password-reset delivery

Set `AUTH_RETURN_OTP_IN_RESPONSE=false` and configure the `SMTP_*` variables in `.env`.
For Gmail, enable 2-Step Verification and create a Google **App Password**; use that 16-character
app password as `SMTP_PASSWORD`. Do not use the normal Gmail password. With
`AUTH_RETURN_OTP_IN_RESPONSE=true`, SMTP is skipped and the OTP is returned only for local testing.
