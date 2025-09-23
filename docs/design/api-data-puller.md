## API Data Puller Design

### Overview
The API data puller is a reusable ingestion framework to fetch, normalize, and persist data from third‑party APIs (e.g., Google Ads, Facebook, Northbeam, Slack, Gmail) for reporting and analysis. It follows the existing `growthkit` connector pattern and uses small, composable entrypoints in `scripts/` for scheduled jobs.

- **Key repos paths**:
  - Connectors: `src/growthkit/connectors/*`
  - Reports/consumers: `src/growthkit/reports/*`
  - CLI/entrypoints: `scripts/*`
  - Config/secrets templates: `config/*`
  - Data outputs: `data/*`

### Goals
- **Unified ingestion**: A consistent interface across APIs (list, get, iterate, paginate, normalize).
- **Idempotent & incremental**: Safe re-runs; resume from state without duplicating data.
- **Observable**: Structured logs, metrics, and simple alerts for failures/slowness.
- **Composable outputs**: Persist raw and modeled data for downstream reports.

### Non‑Goals
- Replace full-featured ETL platforms.
- Build a full data warehouse; outputs remain on local filesystem unless configured otherwise.

### Supported Sources (initial)
- Google Ads (Search, PMax, YouTube) — via `scripts/google_ads_export.py` and `config/google_ads/`.
- Facebook Marketing API — `src/growthkit/connectors/facebook/`.
- Northbeam — `src/growthkit/connectors/northbeam/` and `scripts/northbeam_*`.
- Slack — `src/growthkit/connectors/slack/` and `scripts/slack_export.py`.
- Gmail — `src/growthkit/connectors/mail/` and `scripts/email_export.py`.

Add new sources by creating a connector under `src/growthkit/connectors/<source>/` and a thin script in `scripts/` that wires config + state + runner.

### Architecture
- **Connector interface** (per source):
  - `Client`: Auth + low-level API calls.
  - `Engine`: High-level iterators (handles pagination, windows, backoff, retries).
  - `Schema`: Pydantic/typed models for normalized rows.
  - Optional: `Comment`, `Message`, etc. domain helpers.
- **Runner**:
  - Reads config from `config/<source>/...` and secrets from env/credential files.
  - Loads/updates incremental state (`.json` or `.sqlite`) in `data/ads/cache/` or source-specific cache dir.
  - Streams records to sinks (filesystem as CSV/NDJSON/Parquet).
- **Sinks**:
  - Default: `data/<domain>/...` (CSV/NDJSON). Future: S3/GCS if configured.

Sequence (per job run):
1) Load config and last sync state. 2) Build query window. 3) Pull pages with backoff. 4) Normalize to schema. 5) Write batch files atomically. 6) Update state. 7) Emit metrics/logs.

### Data Model & Schemas
- Use explicit models under each connector's `schema.py` (e.g., `src/growthkit/connectors/facebook/schema.py`).
- Prefer typed fields; store timestamps in ISO8601 UTC.
- Include stable IDs (e.g., `ad_id`, `campaign_id`, `message_id`) and `source` metadata.
- Keep raw payload (optional) under `raw_payload` for troubleshooting.

Example fields (Google Ads report row):
- `date`, `customer_id`, `campaign_id`, `ad_group_id`, `impressions`, `clicks`, `cost_micros`, `conversions`, `revenue` (if modeled), `updated_at`.

File formats:
- CSV for wide/aggregated tables; NDJSON for nested/event streams. Partition by `date` or `ingest_date`.

### Sync Strategy
- **Incremental cursor**: Use `updated_at`/`last_modified_time` where available; fallback to `date` windows.
- **State storage**: JSON file per stream: `data/<source>/cache/<stream>_state.json` with `{last_synced_cursor, last_run_at, backfill_complete}`.
- **Windowing**: Rolling windows with overlap to handle late-arriving updates (e.g., re-pull last 3 days for Ads; last 24h for Slack).
- **Pagination**: Token-based or offset/limit; resume safely.
- **Idempotency**: Deterministic filenames (e.g., `<stream>=<date>=<run_id>.ndjson`) and upserts on re-runs using primary keys when materializing aggregated outputs.
- **Retries/Backoff**: Exponential backoff with jitter; honor rate-limit headers; circuit-breaker after N failures.
- **Backfill**: Configurable historical ranges with checkpointing; split into chunks to avoid timeouts.

### Error Handling & Data Quality
- Classify errors: transient (retry) vs permanent (skip + alert).
- Validate rows against schema; on validation fail, send to `data/<source>/errors/` with reason.
- Row-level and job-level counts; checksum per file (record count + optional hash).

### Observability
- Structured logs via `src/growthkit/utils/logs/` with per-record and per-batch context.
- Metrics: total rows, duration, API requests, rate-limit hits, error counts, success/fail.
- Alerts: simple Slack webhook or console summary for CI; optional email.
- Run IDs: include `run_id` in filenames and logs for traceability.

### Configuration & Secrets
- Config files under `config/<source>/` (templates already exist for many sources).
- Secrets via environment variables or credential files ignored by VCS (`.gitignore`).
- Per-job YAML/INI supports: date range, accounts, streams, fields, filters, concurrency, backfill start.

### Scheduling & Execution
- Local: invoke `python scripts/<source>_export.py --start 2025-09-01 --end 2025-09-13`.
- CI/cron: run daily/hourly with safe overlapping windows; ensure non-interactive auth flows.
- Long-running pulls: paginate with checkpoint files every N pages.

### Storage Layout
- Base dir: `data/<domain>/...` (e.g., `data/ads/`, `data/mail/`, `data/slack/`).
- Partitioning: `data/<domain>/<stream>/date=YYYY-MM-DD/<run_id>.ndjson`.
- Cache/state: `data/<domain>/cache/` per stream.
- Errors: `data/<domain>/errors/`.

### Security & Compliance
- Never log secrets or PII. Redact tokens and emails by default.
- Respect API TOS and rate limits. Store only necessary fields.
- Use principle of least privilege for API scopes.

### Local Dev & Testing
- Unit tests for engines: pagination, backoff, windowing, and schema validation.
- Fixture recordings for API responses where allowed.
- Dry-run mode: fetch N records per stream to validate config.

### Performance & Cost
- Batch writes (e.g., 1–10k records per chunk).
- Use concurrency within API limits (per-account request caps).
- Reuse HTTP sessions; gzip NDJSON files.

### Backfill Strategy
- Define `backfill_start` per stream; chunk by date; checkpoint after each file.
- Stop/resume: read last written partition and continue.

### Rollout Plan
- Phase 1: Align Google Ads and Northbeam exports to this interface and layout.
- Phase 2: Migrate Facebook and Slack jobs; unify state handling.
- Phase 3: Add optional cloud sink (S3/GCS) behind a config flag.

### Runbook
- Retry a failed job: rerun the same command; idempotency ensures safe reprocessing.
- Stuck due to rate limits: increase backoff, lower concurrency, or split accounts.
- Data drift: compare row counts and ROAS deltas vs prior day using weekly report scripts.

### Open Questions
- Do we need a lightweight SQLite state store for cross-process locking?
- Which sink formats are required by downstream tools (CSV vs Parquet)?
- Should we standardize a `RunSummary` artifact under `data/reports/`? 