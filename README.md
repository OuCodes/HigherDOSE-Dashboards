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

# 3)  Install the project (this installs all dependencies from pyproject.toml)
$ pip install -e .

# 4)  Run a report (see sections below)
```

> ⚠️ The repo **does not** ship any proprietary data.  You will need to copy the appropriate CSV exports into `data/ads` before running the scripts.

---

## 2. Repository Layout

```
├── scripts/               # One-line wrappers you can execute directly
│   ├── report_weekly.py   # → higherdose.analysis.weekly_products.main()
│   ├── report_h1.py       # → higherdose.analysis.h1.main()
│   ├── slack_export.py    # → higherdose.slack.slack_fetcher_playwright
│   └── email_export.py    # → higherdose.mail.gmail_archive.main()
│
├── src/higherdose/        # Installable Python package
│   ├── analysis/          # Core analytics modules (weekly.py, h1.py, …)
│   ├── slack/             # Playwright-based Slack fetcher & helpers
│   ├── mail/              # Gmail export functionality
│   ├── facebook/          # Facebook API integrations
│   └── utils/             # Shared utilities and helpers
│
├── data/
│   ├── ads/               # **INPUTS** – CSV exports from ad platforms
│   │   └── h1-report/     #   • Northbeam, Google, Meta exports for H1 reports
│   ├── reports/           # **OUTPUTS** – Final Markdown/PDF reports
│   │   ├── weekly/        #   • Weekly growth reports
│   │   └── h1/            #   • H1 (half-year) reports
│   ├── slack/             # Slack conversation exports
│   │   └── exports/       #   • Markdown channel exports
│   ├── mail/              # Gmail message exports
│   │   └── exports/       #   • Email archive data
│   ├── products/          # Product analysis data
│   │   └── unattributed/  #   • Unattributed product lines for review
│   └── facebook/          # Facebook data exports
│
├── config/                # Configuration files for various integrations
│   ├── slack/             # Slack credentials and settings
│   ├── facebook/          # Facebook API tokens and settings
│   └── mail/              # Email configuration
│
├── pyproject.toml         # Project configuration and dependencies
└── README.md              # (this file)
```

---

## 3. Running Reports

### Option A: Using CLI Commands (After Installation)

After running `pip install -e .`, you can use these convenient commands:

```bash
$ hd-weekly     # Generate weekly growth report
$ hd-h1         # Generate H1 growth report  
$ hd-slack      # Export Slack conversations
$ hd-email      # Export Gmail archive
```

### Option B: Using Script Wrappers

```bash
$ python scripts/report_weekly.py
$ python scripts/report_h1.py
$ python scripts/slack_export.py
$ python scripts/email_export.py
```

### Option C: Direct Module Execution

```bash
$ python -m higherdose.analysis.weekly_products
$ python -m higherdose.analysis.h1
$ python -m higherdose.slack.slack_fetcher_playwright
$ python -m higherdose.mail.gmail_archive
```

---

## 4. Weekly Growth Report

1. Download the **7-day** Northbeam "ad + platform – date breakdown" export (CSV).
2. Save it in `data/ads/`  → the filename can be anything.
3. Execute any of the following:

```bash
$ hd-weekly                          # CLI command (recommended)
$ python scripts/report_weekly.py    # Script wrapper
$ python -m higherdose.analysis.weekly_products --help  # Direct module
```

The script will prompt for the CSV if multiple files are present, analyse the data, then write a Markdown file to:

```
data/reports/weekly/weekly-growth-report-with-products-YYYY-MM-DD.md
```

---

## 5. H1 (Jan → Jun) Growth Report

Required files (place in `data/ads/h1-report/` or pass `--*` flags):

* `northbeam-2025-ad+platform-date-breakdown-level-ytd-report.csv`
* `google-2025-account-level-ytd-report.csv`
* `google-2024-account-level-ytd-report.csv`
* `meta-2025-account-level-ytd-report.csv`
* `meta-2024-account-level-ytd-report.csv`
* `google-analytics-jan-june-2025-traffic_acquisition_Session_source_medium.csv`
* `google-analytics-jan-june-2024-traffic_acquisition_Session_source_medium.csv`

Then run:

```bash
$ hd-h1                           # CLI command (recommended)
$ python scripts/report_h1.py     # Script wrapper  
```

Output → `data/reports/h1/h1-growth-report-with-products-2025.md`

---

## 6. Exporting Slack Conversations

The Slack extractor uses **Playwright** and manages credentials automatically.

```bash
$ hd-slack                           # CLI command (recommended)
$ python scripts/slack_export.py    # Script wrapper
```

* Creates a `venv` if missing, installs Playwright & downloads the Chromium browser.
* Manages credentials automatically in `config/slack/`.
* Markdown files are written to `data/slack/exports/`.

Refer to `src/higherdose/slack/README.md` for detailed credential setup.

---

## 7. Exporting Gmail Archive

Export Gmail messages for analysis and record-keeping.

```bash
$ hd-email                           # CLI command (recommended)
$ python scripts/email_export.py    # Script wrapper
```

* Exports are written to `data/mail/exports/`.
* Requires Gmail API credentials setup.

---

## 8. Updating Product-Alias Mappings

Product & category tables rely on the alias dictionaries in `src/higherdose/product_data.py`.
Unattributed rows with spend are automatically exported to
`data/products/unattributed/`—review these files periodically and
add new aliases to improve mapping accuracy.

---

## 9. Development & Contribution

* **Dependencies**: Managed via `pyproject.toml` - use `pip install -e .` for development.
* **Formatting**:  Run `black` and `ruff` before committing.
* **Testing**:    Reports are idempotent; simply rerun the scripts & compare output.
* **Commits**:    Follow Conventional Commits (feat|fix|chore|refactor).

---

## 10. Troubleshooting: Git Tracking Issues with Mail Exports

Git is still watching the contents of `data/mail/exports/`, so every time you clear the folder and try to download fresh messages it thinks the files were “deleted” and blocks you.  
Follow the exact sequence below (taken verbatim from `docs/tutorials/git-untrack-tutorial.md`, adapted to your path) and the problem will disappear.

1. Verify what’s still tracked  
   ```bash
   git ls-files data/mail/exports | head
   ```
   • If nothing prints, the directory is already un-tracked and you can skip to step 4.  
   • If you see file names, continue.

2. Tell Git to stop tracking the directory but keep the files on disk  
   ```bash
   git rm -r --cached data/mail/exports
   ```

3. Make sure the ignore rule exists in `.gitignore` (it’s already there, but double-check):  
   ```
   **/mail/exports/
   ```

4. Commit the changes  
   ```bash
   git add .gitignore
   git commit -m "Remove mail/exports from git tracking"
   ```

5. Confirm it worked  
   ```bash
   # should print nothing
   git ls-files data/mail/exports

   # should print the path (means Git is ignoring it)
   git check-ignore data/mail/exports/anyfile.md
   ```

Once the directory shows up in `git check-ignore` and NOT in `git ls-files`, Git will leave it alone. You can now wipe and re-download your email exports as often as you like without Git complaining.

---

### License
Internal HigherDOSE project – not for public distribution.
