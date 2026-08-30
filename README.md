# AI Image Understanding & Content Matching Engine

A production-style **backend AI decision system** built for the FlyRank Backend
Track capstone. It ingests a small image corpus, understands each image with a
vision model, embeds images and blog posts, and then **recommends the right
image for each post — and explicitly rejects wrong or uncertain matches.**

> Good match → recommend it.
> Uncertain match → reject it.
> Clearly wrong match → reject it with an explanation.

This is **not** a generic image search engine. It is a *trustworthy* matcher
with an explicit safety / mismatch layer.

---

## Project Overview

Recommending an image for a blog post is deceptively hard: a "gray wolf" is
semantically very close to a "red fox", so a naive cosine-similarity ranker
will happily recommend the wolf. This system refuses to do that. Every
candidate passes through a **mismatch guard** that combines:

* structured image tags (subject / category / attributes),
* semantic similarity,
* vision confidence, and
* configurable thresholds.

The guard can **override a high similarity score** when the structured subject
is wrong. When nothing is confident enough, the system says *"I don't have a
sufficiently good match"* instead of forcing a recommendation.

---

## Architecture

```
Images
   ↓  (background job)
Vision Model  ──►  Structured Metadata (Pydantic-validated)
   ↓                                  │
Embedding Service                     │
   ↓                                  ↓
Vector Store (Postgres JSON)    Image record (status, confidence)
                                            │
Posts                                      │
   ↓                                        │
Post Embedding                             │
   ↓                                        ↓
Similarity Ranking  ───────►  Candidate list
   ↓
Mismatch Guard  (subject/category/confidence/similarity)
   ↓
Recommendation / Rejection  (+ human Review)
```

### Layers (HTTP → Service → Repository → Database)

```
app/
├── api/routes/        # FastAPI routers (no business logic)
├── core/              # config, logging (secret redaction), security
├── db/                # database, models, migrations (alembic)
├── schemas/           # Pydantic request/response models
├── services/          # vision, embedding, matching, mismatch_guard,
│                      #   evaluation, cost_tracking
├── workers/           # image_processing, embedding_processing, job_runner
├── repositories/      # image, post, match, job, ai_usage
└── main.py
```

---

## Features

* Vision understanding → validated structured JSON metadata per image.
* Deterministic, free, reproducible **local model** (no API key required).
  Real **Gemini Flash** vision + embeddings are used automatically when
  `GEMINI_API_KEY` is set.
* Image and post embeddings with cosine similarity.
* Candidate ranking **plus an independent mismatch guard**.
* Explicit decisions: `ACCEPTED`, `REJECTED`, `FLAGGED_FOR_REVIEW`.
* `NO_CONFIDENT_MATCH` when nothing passes the guard.
* **Low-confidence classifications are flagged at ingestion** (the batch job
  marks them `FLAGGED` instead of accepting them) *and* at match time.
* Async background jobs with status / progress / retries / idempotency.
* Per-call AI cost tracking **with a budget guard** (cumulative spend is
  checked against `BUDGET_USD`; it alerts, and in strict mode refuses calls).
* Human review workflow (approve / reject suggestions).
* Evaluation dataset + **Top-1 Precision** measured from real data
  (`POST /evaluation/run`, or `python scripts/evaluate.py`).
* Secrets only from environment variables; never hardcoded; never logged.

---

## Tech Stack

* Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0
* PostgreSQL (+ Alembic), SQLite for tests
* Docker + Docker Compose
* Gemini Flash (optional) / deterministic local fallback
* pytest, httpx, Pillow

---

## Setup

### 1. Run with Docker (recommended)

```bash
docker compose up --build
```

This starts `db`, `api` (port 8000), and a `worker` container that processes
background jobs.

### 2. Seed the corpus

In a separate terminal (against the running stack, or locally):

```bash
python scripts/seed.py
```

The seed script:

1. generates ~45 placeholder images across animals + environments,
2. writes structured labels (simulated vision output),
3. creates the blog posts,
4. processes images (vision → metadata → embedding) and post embeddings,
5. writes the evaluation labels.

All seed data under `data/` (placeholder images, `labels.json`,
`eval_labels.json`) is **generated deterministically by the seed script**, so it
is not committed to the repository — a fresh clone only needs to run the seed to
recreate an identical corpus (the local model is deterministic, so results are
reproducible). Re-running `seed.py` is idempotent (records are never
duplicated). For a clean, fully reproducible reset first drop all tables:

```bash
python scripts/seed.py --reset   # drop tables, then re-seed from scratch
```

### 3. Try it

```bash
curl http://localhost:8000/health

# Match a post to images
curl -X POST http://localhost:8000/posts/{post_id}/match

# Run the evaluation (also: `python scripts/evaluate.py`)
curl -X POST http://localhost:8000/evaluation/run
curl http://localhost:8000/evaluation/latest

# AI cost / usage (includes budget guard status)
curl http://localhost:8000/usage
```

### Local development (without Docker)

```bash
pip install -r requirements.txt
export DATABASE_URL="sqlite:///./dev.db"   # or a local Postgres
python scripts/seed.py
uvicorn app.main:app --reload
pytest
```

---

## API Documentation

All endpoints return proper HTTP status codes; invalid input yields clean 4xx.

### Health
`GET /health`
```json
{ "status": "ok", "use_real_ai": false, "similarity_threshold": 0.75 }
```

### Images
`POST /images` → create an image record (returns `201`).
`GET /images` → list images.
`GET /images/{image_id}` → image detail.

### Posts
`POST /posts` → create a post (enqueues embedding job).
`GET /posts`, `GET /posts/{post_id}`.

### Processing (background)
`POST /jobs/images/process` → `202 { "id": "job_xxx", "status": "QUEUED" }`
`GET /jobs/{job_id}` → progress / status.

### Matching
`GET /posts/{post_id}/images` → ranked candidates with decisions (read-only:
computes the ranking without persisting suggestions or writing embeddings).
`POST /posts/{post_id}/match` → recommendation:
```json
{
  "post_id": "post_1",
  "decision": "RECOMMENDED",
  "recommended_image_id": "img_fox",
  "top_similarity": 1.0,
  "reason": "Recommended image img_fox with similarity 1.00. ...",
  "candidates": [
    { "image_id": "img_fox", "similarity": 1.0, "decision": "ACCEPTED",
      "confidence": 0.95, "reason": "Strong semantic similarity ..." },
    { "image_id": "img_wolf", "similarity": 0.96, "decision": "REJECTED",
      "reason": "Animal category/subject mismatch: expected fox, detected wolf." }
  ]
}
```

### Review
`GET /reviews`, `GET /suggestions`, `GET /suggestions/{id}`.
`POST /suggestions/{id}/approve`, `POST /suggestions/{id}/reject`.

### Evaluation
`POST /evaluation/run` → runs Top-1 Precision over the labeled set.
`GET /evaluation/latest` → last result.

> The destructive/evaluation endpoints (`POST /suggestions/{id}/approve`,
> `POST /suggestions/{id}/reject`, `POST /evaluation/run`) are guarded by an
> optional `ADMIN_API_KEY`. When that environment variable is set they require
> an `X-API-Key` header (else `401`); when it is unset they remain open, so the
> zero-config demo and CI keep working without credentials.

### Cost / Usage
`GET /usage` → total AI calls, estimated cost, per-operation breakdown.

---

## Evaluation

Top-1 Precision is computed from a **real labeled evaluation set** (13 posts,
each with a correct image; plus hard negatives such as wolf images for fox
posts, and a deliberately unmatched art post).

**Measured result (this repository): `Top-1 Precision = 1.00` (13 / 13).**

> The metric is never fabricated — it is produced by
> `POST /evaluation/run` from the seeded labels. Re-running the seed and
> evaluation on your machine will reproduce this number (the local model is
> deterministic).

---

## Safety & Reliability

* **Schema validation** — raw vision output is validated by Pydantic
  (`ImageMetadata`); invalid JSON / out-of-range confidence is never stored.
  Persistent failures are marked `FLAGGED`, never silently accepted.
* **Confidence thresholds** — low-confidence classifications are flagged at
  **ingestion** (the batch job marks the image `FLAGGED` so it is excluded from
  matching) and at match time (`FLAGGED_FOR_REVIEW`), never auto-accepted.
* **Budget guard** — every AI call is cost-tracked and cumulative spend is
  checked against `BUDGET_USD`; the guard alerts (and, with
  `BUDGET_GUARD_STRICT=true`, refuses further calls) when the budget is
  exceeded.
* **Mismatch guard** — a standalone, unit-tested module that rejects wrong
  subjects *even when similarity is high*.
* **No-confident-match** — the system prefers "no match" over a forced,
  probably-wrong recommendation.
* **Retries** — the image pipeline retries transient vision failures up to
  `MAX_RETRIES`; exhausted retries are flagged/failed.
* **Idempotency** — completed images are skipped; embeddings are upserted, so
  re-running a job never duplicates data.
* **Cost tracking** — every vision/embedding call creates an `ai_usage`
  record (estimated cost is tracked even at $0).

---

## Limitations

* The free/local model is a **domain concept model**, not a general-purpose
  embedding. It is excellent for the animal/environment corpus in this
  capstone, but would need a real embedding model for open-domain text.
* Placeholder images are generated locally; swap in real licensed photos
  (and a Gemini key) for true vision understanding.
* This is a small-corpus, single-node design — not a horizontally scaled
  search platform.

---

## Future Improvements

* Automatic alt-text generation.
* Near-duplicate image detection.
* Human-in-the-loop QA for `FLAGGED_FOR_REVIEW` candidates.
* Real pgvector similarity search for larger corpora.
* Multi-model voting for the mismatch guard.
