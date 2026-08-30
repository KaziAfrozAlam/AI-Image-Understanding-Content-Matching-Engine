# Build Log

Honest record of how this project was built, what went wrong, and what was
learned. The implementation was produced with AI coding assistance (a coding
agent), and several generated pieces were corrected through debugging rather
than accepted blindly.

---

## AI tools used

* A coding agent (Claude) produced the initial implementation of every module
  (config, DB models, schemas, repositories, services, workers, API, seed,
  tests, Docker, docs).
* The agent also ran the test suite and iterated on failures.
* No external "vibe" code was copied; all logic was written to the capstone
  spec.

---

## Where generated code was wrong (and what was changed)

1. **Logging filter corrupted log records.** The first `SecretFilter` mutated
   `record.msg` but left `record.args` intact, so the logging framework tried
   to re-format the already-formatted string and raised
   `TypeError: not all arguments converted`. Fixed by clearing `record.args`
   after formatting.

2. **SQLAlchemy `metadata` is reserved.** An `AiUsage` column was literally
   named `metadata`, which raises `InvalidRequestError`. Renamed to `meta`.

3. **`Base` import location.** `Base` lives in `app.db.models`, not
   `app.db.database`. Several repository / entrypoint imports were wrong after
   a package-init file was overwritten; corrected.

4. **`Optional` not imported in models.** Model files used `Mapped[Optional[...]]`
   without importing `Optional` from `typing`. Added the import.

5. **Similarity weighting was structurally wrong.** Initially every concept
   (including broad attributes like "wild") added category + group dimensions.
   Verbose posts diluted cosine similarity so a correct fox↔fox match fell
   below the 0.75 threshold. Reweighted so animal subjects dominate and
   environment/attribute concepts stay light.

6. **Environment context created false compatibility.** A wolf image whose
   caption/attributes mention "forest" became "compatible" with a fox post
   that also mentions forests, so the guard *accepted* the wolf. Fixed by
   judging compatibility on the **primary animal subject** only.

7. **The word "canine" was ambiguous.** It was a synonym for `dog`, so both a
   fox post ("wild canine") and a wolf image ("canine") were tagged `dog`,
   creating a false match. The guard now requires the post's *primary* animal
   subject to be present in the candidate's animal subjects, which removes the
   ambiguity (and "canine" was dropped from the dog synonyms).

---

## Important implementation decisions

* **$0 / reproducible by default.** With no `GEMINI_API_KEY`, the system uses a
  deterministic local concept model (shared by embeddings *and* the mismatch
  guard). Real Gemini Flash is used automatically when a key is present. This
  keeps the whole stack runnable on a clean machine with no paid infra.
* **Two backends behind one interface.** `get_vision_service` /
  `get_embedding_service` return a Gemini or local implementation, so the rest
  of the code is provider-agnostic.
* **Single-process worker + standalone worker.** The API starts an in-process
  background worker (disabled in the Docker `api` service), and a dedicated
  `worker` container runs `python -m app.workers.job_runner` so jobs are
  processed asynchronously and never block HTTP requests.
* **Embeddings stored as JSON** in Postgres (cosine computed in Python) to
  avoid a hard pgvector dependency for a 45-image corpus; pgvector is noted as
  a future improvement.
* **`create_all` on startup** makes the demo zero-config; Alembic scaffolding
  is included for formal migrations.

---

## Debugging problems encountered

* Tests initially imported models before tables were created (import order) —
  fixed by importing the application before `create_all` in fixtures.
* In-memory SQLite was flaky across sessions; switched the test DB to a temp
  file with `StaticPool`-free direct file connection and per-test table
  teardown.
* The mismatch guard went through three iterations (subject overlap →
  animal-subject overlap → primary-animal-subject containment) before it
  correctly rejected wolves for fox posts while still accepting synonyms like
  *Vulpes vulpes*.

---

## Lessons learned

* A "semantic similarity first" ranker is dangerous for trustworthy matching;
  structured subject/category checks must be able to **override** a high
  similarity score. That override is the core value of this system.
* Determinism matters for capstone reproducibility — a local, explainable
  model made the evaluation number stable and the tests reliable.
* Validation, retries, idempotency, and cost tracking are not boilerplate;
  each one caught a real failure mode during development.
