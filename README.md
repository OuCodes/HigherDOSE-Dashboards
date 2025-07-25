# HigherDOSE Growth-Report Toolkit

A data-analysis toolkit that transforms Northbeam, Google Ads, Meta Ads, and Google-Analytics exports into polished **Markdown** growth-reports for the HigherDOSE team.

— Built with Python 3.10+ & pandas.

---

## 1. Quick Start

```bash
# 1)  Clone the repo & enter it
$ git clone git@github.com:HigherDOSE/growth-reports.git
$ cd HigherDOSE

# 2)  Create + activate a virtual-env (recommended)
$ python3 -m venv venv
$ source venv/bin/activate   # Windows → venv\Scripts\activate.bat

# 3)  Install project requirements
$ pip install -r requirements.txt

# 4)  Run a report (see sections below)
```

> ⚠️ The repo **does not** ship any proprietary data.  You will need to copy the appropriate CSV exports into `data/raw` before running the scripts.

---

## 2. Repository Layout (post-reorg)

```
├── scripts/               # One-line wrappers you actually execute
│   ├── report_weekly.py   # → higherdose.analysis.weekly_products.main()
│   ├── report_h1.py       # → higherdose.analysis.h1.main()
│   └── slack_export.py    # → higherdose.slack.slack_fetcher_playwright
│
├── src/higherdose/        # Installable Python package
│   ├── analysis/          # Core analytics modules (weekly.py, h1.py, …)
│   ├── slack/             # Playwright-based Slack fetcher & helpers
│   └── mail/              # Archived Gmail messages (for reference only)
│
├── data/
│   ├── raw/               # **INPUTS** – drop CSV exports in here
│   │   └── stats/         #   • Northbeam, Google, Meta exports, etc.
│   └── processed/         # **OUTPUTS** & intermediate files
│       ├── transcripts/   #   • Meeting transcripts
│       └── slack/         #   • Markdown channel exports
│
├── reports/               # Final Markdown/PDF reports written by scripts
│   ├── weekly/
│   └── h1/
└── README.md              # (this file)
```

---

## 3. Running the **Weekly** Growth Report

1. Download the **7-day** Northbeam “ad + platform – date breakdown” export (CSV).
2. Save it in `data/raw/stats/`  → the filename can be anything.
3. Execute:

```bash
$ python scripts/report_weekly.py
```

The script will prompt for the CSV if multiple files are present, analyse the data, then write a Markdown file to:

```
reports/weekly/weekly-growth-report-with-products-YYYY-MM-DD.md
```

### Options
The wrapper is intentionally minimal.  For advanced usage call the module directly:

```bash
$ python -m higherdose.analysis.weekly_products --help
```

---

## 4. Running the **H1** (Jan → Jun) Growth Report

Required files (place in `data/raw/stats/h1-report/` or pass `--*` flags):

* `northbeam-2025-ad+platform-date-breakdown-level-ytd-report.csv`
* `google-2025-account-level-ytd-report.csv`
* `google-2024-account-level-ytd-report.csv`
* `meta-2025-account-level-ytd-report.csv`
* `meta-2024-account-level-ytd-report.csv`
* `google-analytics-jan-june-2025-traffic_acquisition_Session_source_medium.csv`
* `google-analytics-jan-june-2024-traffic_acquisition_Session_source_medium.csv`

Then run:

```bash
$ python scripts/report_h1.py  # accepts --northbeam_csv etc. if paths differ
```

Output → `reports/h1/h1-growth-report-with-products-2025.md`

---

## 5. Exporting Slack Conversations

The Slack extractor uses **Playwright**.

```bash
$ python scripts/slack_export.py
```

* Creates a `venv` if missing, installs Playwright & downloads the Chromium browser.
* Launches `higherdose.slack.slack_fetcher_playwright` which manages credentials automatically in `config/slack/`.
* Markdown files are written to `data/processed/slack/markdown_exports/`.

Refer to `slack/README.md` for detailed credential setup.

---

## 6. Updating Product-Alias Mappings

Product & category tables rely on the alias dictionaries in `src/higherdose/product_data.py`.
Unattributed rows with spend are automatically exported to
`data/processed/unattributed_products/`—review these files periodically and
add new aliases to improve mapping accuracy.

---

## 7. Development & Contribution

* **Formatting**:  Run `black` and `ruff` before committing.
* **Testing**:    Reports are idempotent; simply rerun the scripts & compare output.
* **Commits**:    Follow Conventional Commits (feat|fix|chore|refactor).

---

## 8. Release History (last 12 commits)

```
# git log -12 --pretty=format:"%h  %s"
51bfdb5  chore: after the reorg
139921d  chore: remove piplist.md and update TODO …
219e2af  refactor: streamline report generation …
64ee6ae  refactor: enhance organization and output handling …
a91ea25  feat: add pyproject.toml for project configuration
c311ca0  refactor: moving and deleting
bc733ff  refactor: small add-on to last attempt
9b793ab  refactor: reorganize hierarchy of codebase
…
```

(Use `git log` for full details.)

---

### License
Internal HigherDOSE project – not for public distribution.

Git is still watching the contents of `src/higherdose/mail/archive/`, so every time you clear the folder and try to download fresh messages it thinks the files were “deleted” and blocks you.  
Follow the exact sequence below (taken verbatim from `docs/tutorials/git-untrack-tutorial.md`, adapted to your path) and the problem will disappear.

1. Verify what’s still tracked  
   ```bash
   git ls-files src/higherdose/mail/archive | head
   ```
   • If nothing prints, the directory is already un-tracked and you can skip to step 4.  
   • If you see file names, continue.

2. Tell Git to stop tracking the directory but keep the files on disk  
   ```bash
   git rm -r --cached src/higherdose/mail/archive
   ```

3. Make sure the ignore rule exists in `.gitignore` (it’s already there, but double-check):  
   ```
   **/mail/archive/
   ```

4. Commit the changes  
   ```bash
   git add .gitignore
   git commit -m "Remove mail/archive from git tracking"
   ```

5. Confirm it worked  
   ```bash
   # should print nothing
   git ls-files src/higherdose/mail/archive

   # should print the path (means Git is ignoring it)
   git check-ignore src/higherdose/mail/archive/anyfile.md
   ```

Once the directory shows up in `git check-ignore` and NOT in `git ls-files`, Git will leave it alone. You can now wipe and re-download your email archive as often as you like without Git complaining.
