# AIP491 Frontend

React + TypeScript + Vite dashboard for the AIP491 CV–JD matching platform (dev server on port **5173**).

## Features

- **CV–JD Matching** — upload CV(s) + a JD (**PDF or pasted text**), pick an AI model, and view the match score, alignment heatmap, per-view XAI explanation, XAI-highlighted PDFs, and the processing time.
- **CV Ranking** — rank many CVs against one JD.
- **CV Comparison** — head-to-head compare 2 CVs for a JD.
- **CV Search** — semantic search over stored CVs (+ optional rerank).
- Auth (email + Google) and CV storage.

Talks to the backend at `VITE_API_BASE_URL` (default `http://localhost:8000`), which proxies ML requests to the AI service (:8001).

## Run locally

```powershell
npm install
copy .env.example .env      # set VITE_API_BASE_URL (and VITE_GOOGLE_CLIENT_ID)
npm run dev                 # http://localhost:5173
```

Build: `npm run build` · Lint: `npm run lint`

## Structure

```text
src/
  components/         Dashboard + sections (matching, ranking, comparison, search)
  components/dashboard/matching/    FullDocumentPanel, HeatmapSection, XaiExplanation
  hooks/              useMatching, useCvRanking, useCvComparison, useCvSearch, ...
  services/api/       HTTP clients (matching, ranking, webSearch, upload, client)
  types/              Shared TypeScript types
  context/            Auth context
```

## Tech

React 19 · TypeScript · Vite. Lint rules in `eslint.config.js`.
