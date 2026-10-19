# AIP491 AI Service

FastAPI service for CV–JD matching (extraction + inference + embeddings), served on port **8001**.

## Pipeline

```text
CV PDF/text + JD PDF/text
  -> OpenAI structured extraction (10 CV views, 5 JD views)
  -> mBERT cross-encoder scores all 10x5 = 50 view pairs
  -> fusion head -> match score (0-10) + alignment heatmap + per-view XAI
```

## Models

Four cross-encoder models **share a single `bert-base-multilingual-cased` (mBERT) backbone**; only the small fusion head differs. Checkpoints live in `checkpoints/<model_id>/*.pth` (saved as `{"model", "task_w"}`; `task_w` is training-only and ignored at inference).

| id (key)         | Fusion head    | Notes                     |
| ---------------- | -------------- | ------------------------- |
| `cross_weighted` | Weighted Sum   | **default**, best (~86% acc) |
| `cross_mlp`      | MLP            |                           |
| `cross_residual` | Residual MLP   |                           |
| `cross_attention`| Transformer    |                           |

List available models: `GET /api/v1/matching/models`.

## Inference optimizations

Output-preserving (matching score unchanged) unless stated:

- **Shared backbone** — mBERT loaded once, reused by all 4 heads.
- **Auto GPU/CPU** — `AI_DEVICE=auto|cpu|cuda` (a CUDA build of torch is required to use a GPU).
- **Warm-up on startup** — preloads backbone + heads and runs one forward, so the first request isn't cold.
- **Length-bucketed inference** — sorts view pairs by token length (~3x faster on CPU, identical output).
- **Skip empty view pairs** — backbone runs only on non-empty pairs (identical score).
- **Extraction** — `gpt-4o-mini` + content-hash cache: an identical CV/JD re-run is instant (no OpenAI calls).

## Structure

```text
app/
  api/          API routers (matching, embeddings, jd-search, health)
  core/         Settings (config.py)
  models/       Architectures, registry, runtime, device, inference
  schemas/      Pydantic response schemas
  services/     Extraction, pipeline, extract cache, vector store
checkpoints/    Model weights: <model_id>/*.pth
tmp/            Temporary uploads + caches
```

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # set OPENAI_API_KEY
uvicorn app.main:app --port 8001      # omit --reload for demos (single worker)
```

Health check: `GET http://127.0.0.1:8001/api/v1/health`

## Matching endpoint

```text
POST /api/v1/matching/predict   (multipart/form-data)
  cv_files: one or more PDF/TXT files
  jd_file:  one PDF,  OR  jd_text: plain JD text
  model_id: e.g. cross_weighted (optional)
  include_structured: false
->
  results[]: score, match, view_matches, alignment heatmap
  elapsed_seconds / extraction_seconds / inference_seconds
```

## Key environment variables

See `.env.example`. Notable:

| Var                    | Default          | Purpose                                   |
| ---------------------- | ---------------- | ----------------------------------------- |
| `OPENAI_API_KEY`       | —                | Structured extraction (required)          |
| `OPENAI_MODEL`         | `gpt-4o-mini`    | Extraction model                          |
| `DEFAULT_MODEL_ID`     | `cross_weighted` | Default matching model                    |
| `AI_DEVICE`            | `auto`           | `auto` / `cpu` / `cuda`                   |
| `TORCH_NUM_THREADS`    | `0` (auto ≤ 8)   | CPU threads (torch's default over-subscribes) |
| `INFERENCE_PAIR_CHUNK` | `6`              | Length-bucketing chunk size (0 = off)     |
| `EXTRACTION_CACHE`     | `true`           | Cache extraction by content hash          |
```
