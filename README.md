# GrowthKit – Report Toolkit

A Python toolkit that turns Northbeam, Google Ads, Meta Ads, and Google Analytics exports into polished **Markdown** growth reports.

— Built with Python 3.10+ & pandas.

---

## 1. Quick Start

- Clone the repo & enter it:

```bash
$ git clone <your repo>
$ cd <repo>
```

### Mac/Linux

```bash
# 2)  Create a virtual environment
$ python3.10 -m venv --prompt gk venv

# 3)  Upgrade pip, wheel, and setuptools (recommended)
# macOS/Linux:
$ ./venv/bin/python -m pip install --upgrade pip wheel setuptools

# 4)  Install the project (this installs all dependencies from pyproject.toml)
# macOS/Linux:
$ ./venv/bin/pip install -e .

# 5)  Run a report (see sections below)
```

### Windows

```powershell
# 2)  Create a virtual environment
$ py -3.10 -m venv --prompt hdose venv

# 3)  Upgrade pip, wheel, and setuptools (recommended)
$ .\venv\Scripts\python -m pip install --upgrade pip wheel setuptools

# 4)  Activate the virtual environment
$ .\venv\Scripts\activate

# 5)  Install the project (this installs all dependencies from pyproject.toml)
$ .\venv\Scripts\pip install -e .

# 6)  Run a report (see sections below)
```

> ⚠️ The repo **does not** ship any proprietary data.  You will need to copy the appropriate CSV exports into `data/ads` before running the scripts.

---

## 2. Repository Layout

```
├── scripts/                # One-line wrappers you can execute directly
│   ├── report_executive.py # → automated MTD performance summary
│   ├── report_weekly.py    # → growthkit.reports.weekly.main()
│   ├── report_h1.py        # → growthkit.reports.h1.main()
│   ├── slack_export.py     # → growthkit.connectors.slack.slack_fetcher
│   └── email_export.py     # → growthkit.connectors.mail.gmail_sync
│
├── src/growthkit/         # Installable Python package
│   ├── reports/           # Report generation (executive.py, weekly.py, h1.py, …)
│   ├── connectors/
│   │   ├── slack/         # Playwright-based Slack fetcher & helpers
│   │   ├── mail/          # Gmail export functionality
│   │   └── facebook/      # Facebook (Meta) API integrations
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

After running `pip install -e .`, use these commands:

```bash
$ gk-weekly     # Generate weekly growth report
$ gk-h1         # Generate H1 growth report  
$ gk-slack      # Export Slack conversations
$ gk-email      # Export Gmail archive
```

### Option B: Using Script Wrappers

```bash
$ python scripts/report_executive.py
$ python scripts/report_weekly.py
$ python scripts/report_h1.py
$ python scripts/slack_export.py
$ python scripts/email_export.py
```

### Option C: Direct Module Execution

```bash
$ python -m growthkit.reports.weekly
$ python -m growthkit.reports.h1
$ python -m growthkit.connectors.slack.slack_fetcher
$ python -m growthkit.connectors.mail.gmail_sync
```

---

## 4. MTD Performance Summary

1. Place the relevant GA4, Shopify, and Northbeam CSV exports in `data/ads/` (the script will auto-detect files based on template needs).
2. Run the executive wrapper:
   ```bash
   $ python scripts/report_executive.py             # Month-to-date (default)
   $ python scripts/report_executive.py --month 2025-07   # Full month
   $ python scripts/report_executive.py --start 2025-07-01 --end 2025-07-28   # Custom range
   ```
3. The report is written to:
   ```
   data/reports/executive/automated-performance-report-YYYY-MM-DD.md
   ```

---

## 5. Weekly Growth Report

1. Download the **7-day** Northbeam "ad + platform – date breakdown" export (CSV).
2. Save it in `data/ads/`  → the filename can be anything.
3. Execute any of the following:

```bash
$ gk-weekly                          # CLI command (recommended)
$ python scripts/report_weekly.py    # Script wrapper
$ python -m higherdose.analysis.weekly_products --help  # Direct module
```

The script will prompt for the CSV if multiple files are present, analyse the data, then write a Markdown file to:

```
data/reports/weekly/weekly-growth-report-with-products-YYYY-MM-DD.md
```

---

## 6. H1 (Jan → Jun) Growth Report

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
$ gk-h1                           # CLI command (recommended)
$ python scripts/report_h1.py     # Script wrapper  
```

Output → `data/reports/h1/h1-growth-report-with-products-2025.md`

---

## 7. Exporting Slack Conversations

The Slack extractor uses **Playwright** and manages credentials automatically.

```bash
$ gk-slack                           # CLI command (recommended)
$ python scripts/slack_export.py    # Script wrapper
```

* Creates a `venv` if missing, installs Playwright & downloads the Chromium browser.
* Manages credentials automatically in `config/slack/`.
* Markdown files are written to `data/slack/exports/`.

Refer to `src/growthkit/connectors/slack/README.md` for detailed credential setup.

---

## 8. Exporting Gmail Archive

Export Gmail messages for analysis and record-keeping.

```bash
$ gk-email                           # CLI command (recommended)
$ python scripts/email_export.py    # Script wrapper
```

* Exports are written to `data/mail/exports/`.
* Requires Gmail API credentials setup.

---

## 9. Updating Product-Alias Mappings

Product & category tables rely on the alias dictionaries in `src/growthkit/reports/product_data.py`.
Unattributed rows with spend are automatically exported to
`data/products/unattributed/`—review these files periodically and
add new aliases to improve mapping accuracy.

---
## 10. Directory Guidelines

Each major folder now ships its own `README.md` explaining purpose, allowed contents, and banned items:

* `scripts/README.md`
* `src/growthkit/README.md`
* `config/README.md`
* `data/README.md`
* `src/growthkit/utils/README.md`  <!-- vendored, read-only -->

Make sure to read the relevant file before committing new code or data.

---

### License
Private project – not for public distribution.
