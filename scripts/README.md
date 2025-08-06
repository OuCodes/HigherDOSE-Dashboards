# `scripts/` — Thin CLI Wrappers

This directory holds **executable, one-liner** Python wrappers that you can
invoke directly from the command-line (e.g. `python scripts/report_weekly.py`).
Each wrapper should do nothing more than:

1. Validate / bootstrap **local environment state** that _cannot_ live inside
   the library (e.g. ensure a config file has been generated).
2. Import the **real implementation** from the installable `higherdose` package.
3. Delegate execution to a single `main()` function.

The goal is to keep the package import-safe (side-effect-free) while still
shipping ergonomic entry-points for end-users.

---

## What **should** live here

| ✅  | Description |
|----|-------------|
| Tiny, self-contained wrappers | One-file scripts < ~30 LOC that only call `higherdose.*` code. |
| Shebang & docstring | Each file starts with `#!/usr/bin/env python3` and a concise docstring. |
| CLI convenience | Argument parsing **only** if it cannot be moved into the library without side-effects. |
| Transitional glue | Light helpers that prepare *runtime* artefacts (e.g. create a default config file) before delegating. |

---

## What **should _not_** live here

| ❌  | Reason |
|----|--------|
| Business logic, data processing, or analysis code | Put that in `src/higherdose/` so it can be unit-tested and imported elsewhere. |
| Secrets, API tokens, or environment-specific config | Use the `config/` hierarchy; scripts must read from there, not embed secrets. |
| Large helper libraries | If more than ~30 LOC and reusable, move it into `higherdose.utils` (or a more specific sub-module). |
| Long-running daemons / services | Create a dedicated module (or `cli/` entry-point) instead of hiding it here. |

---

## Existing Wrappers (2025-08-05)

| File | Delegates to | Purpose |
|------|--------------|---------|
| `report_executive.py` | `higherdose.analysis.executive.main()` | Generate **month-to-date** executive performance summary. |
| `report_weekly.py` | `higherdose.analysis.weekly_products.main()` | Generate **weekly** growth & product report. |
| `report_h1.py` | `higherdose.analysis.h1.main()` | Generate H1 (half-year) growth report. |
| `slack_export.py` | `higherdose.slack.slack_fetcher.run_main()` | Export Slack messages via Playwright. |
| `email_export.py` | `higherdose.mail.gmail_archive.main()` | Export a complete Gmail archive. |

Every new script should follow the same **import-then-delegate** pattern used
in these examples.