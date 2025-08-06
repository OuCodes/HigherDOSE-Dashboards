# ADR-0001: Project Directory Structure & Folder Rules

* **Status:** Accepted  
* **Date:** 2025-08-06  
* **Deciders:** HigherDOSE Data Team  
* **Tech Story:** We need a clear convention so humans **and** AI assistants know where code, data, and secrets belong.

---

## 1. Context

The toolkit combines:

* Executable **wrapper scripts** for end-users.
* An installable **Python package** with reusable business logic.
* Large **CSV exports** and generated **Markdown/PDF** reports.
* **Credentials** for Slack, Gmail, Facebook, etc.
* A vendored **utils library** maintained in a separate repository.

Historically, contributors placed files in inconsistent locations, causing:

* Accidental commits of secrets to the public repo.
* Bloated package distributions containing multi-megabyte CSVs.
* Difficulty for AI coding agents to infer the right destination for new files.

---

## 2. Decision

We formalise the following top-level folder rules:

| Folder | Purpose | Key Rules |
|--------|---------|-----------|
| `scripts/` | Thin CLI wrappers (<30 LOC) | Import implementation from `higherdose.*`; **no** business logic. |
| `src/higherdose/` | Installable Python package | Pure, import-safe code; **no** data or env-specific config. |
| `src/higherdose/utils/` | Vendored helper library | **Read-only** in this repo; edits must occur upstream. |
| `data/` | Raw inputs & generated outputs | Only datasets (<50 MB) and reports; **no** Python code. |
| `config/` | Credential & runtime templates | Templates / sample files only; real secrets stay untracked. |
| `docs/` | Documentation, tutorials, ADRs | No source code beyond illustrative snippets. |

Enforcement mechanisms:

1. Folder-specific `README.md` files state allowed / forbidden content.
2. `CONTRIBUTING.md` summarises rules & adds a PR checklist.
3. Future: Pre-commit hook will block commits violating size & path rules.

---

## 3. Consequences

### Positive

* New contributors (human or AI) can quickly locate the correct folder.
* Reduced risk of leaking credentials or large proprietary datasets.
* Smaller, cleaner PyPI distribution.
* Easier code reviews thanks to predictable diff locations.

### Negative / Trade-offs

* Slight onboarding overhead—contributors must read multiple READMEs.
* Vendored `utils/` library requires a separate release process.
* Pre-commit hooks may block legitimate edge-cases (configurable).

---

## 4. Alternatives Considered

1. **Monolithic `src/`** – mix code, data, and configs. Rejected: messy, security risk.
2. **Multiple repos** – split data, configs, and code. Rejected: higher coordination cost for small team.
3. **Git submodules** for `utils/`. Rejected: adds Git complexity; vendoring is simpler.

---

## 5. Related Documents

* `README.md` – Section “10. Directory Guidelines”
* `CONTRIBUTING.md` – Folder rules table & checklist
* Folder README files under `scripts/`, `src/higherdose/`, `config/`, `data/`, `src/higherdose/utils/`

---

## 6. Follow-Up Actions

1. Add pre-commit hook to enforce file-size & path rules. *(Open)*
2. Draft ADR-0002 for secret-management strategy. *(Planned)*
