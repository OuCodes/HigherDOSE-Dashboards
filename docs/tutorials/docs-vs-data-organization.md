# Directory Organization: `/docs` vs `/data`

This tutorial explains the organizational structure and purpose of the `/docs` and `/data` directories in the HigherDOSE project.

## Overview

The project uses a clear separation between documentation and data to maintain organization and clarity:

- **`/docs`** - Documentation, guides, reference materials, and human-readable content
- **`/data`** - Raw data, processed data, exports, and data artifacts

## `/docs` Directory

### Purpose
Contains all documentation, tutorials, guides, and reference materials that help understand, use, or develop the project.

### What GOES in `/docs`:

#### ✅ Documentation Files
- **Tutorials**: Step-by-step guides (e.g., `cli-entrypoints.md`, `git-untrack-tutorial.md`)
- **Reference materials**: Lists, specifications, configurations (e.g., `product-list.md`)
- **Development notes**: Historical context, design decisions (e.g., `metrics-old.md`)
- **Prompt collections**: Reusable prompts and templates (e.g., `winning-prompts.txt`)

#### ✅ Development Artifacts
- **Chat logs**: Development session transcripts from Cursor/AI assistance (`chats/`)
- **Meeting notes**: Planning sessions, requirement discussions
- **Design documents**: Architecture decisions, API specifications
- **Process documentation**: Workflows, procedures, best practices

#### ✅ Human-Readable Content
- Markdown files (`.md`)
- Text files with instructions or notes (`.txt`)
- Documentation that explains how things work
- Reference materials for developers

### What does NOT go in `/docs`:

#### ❌ Raw Data Files
- CSV exports from advertising platforms
- JSON data dumps
- Database exports
- API response files

#### ❌ Generated Content
- Automated reports
- Data analysis outputs
- Processed datasets
- Application logs

#### ❌ Binary Files
- Images (unless part of documentation)
- Compressed archives
- Application data files

## `/data` Directory

### Purpose
Contains all data files, both raw and processed, organized by source and type.

### What GOES in `/data`:

#### ✅ Raw Data Files
- **Advertising data**: Google Ads, Meta Ads exports (`.csv`)
- **Social media data**: Slack exports, Facebook comments (`.json`, `.md`)
- **Email data**: Gmail exports and archives
- **Analytics data**: Traffic, conversion, and performance metrics

#### ✅ Processed Data
- **Generated reports**: Weekly, monthly, H1 reports (`.md`, `.pdf`)
- **Analysis outputs**: Processed datasets, filtered data
- **Aggregated data**: Summary files, rollups, calculated metrics

#### ✅ Data Artifacts
- **Transcripts**: Audio/video transcription files (`.vtt`, `.md`)
- **Configuration data**: API tokens, credentials (in `config/` structure)
- **Tracking files**: Conversation trackers, state files (`.json`)

#### ✅ Structured Data
- Contact databases (`rolodex.json`)
- Product catalogs and inventories
- Customer data and profiles
- Transaction records

### What does NOT go in `/data`:

#### ❌ Documentation
- How-to guides
- API documentation
- Setup instructions
- Code comments or explanations

#### ❌ Source Code
- Python scripts
- Configuration templates
- Application code

#### ❌ Reference Materials
- Static lists or catalogs (unless they're data exports)
- Template files
- Example configurations

## Directory Structure Examples

### `/docs` Structure:
```
docs/
├── tutorials/           # Step-by-step guides
│   ├── cli-entrypoints.md
│   └── git-untrack-tutorial.md
├── chats/              # Development session logs
│   └── cursor_automate_slack_conversation_extr.md
├── product-list.md     # Product reference documentation
├── metrics-old.md      # Historical documentation
└── winning-prompts.txt # Reference materials
```

### `/data` Structure:
```
data/
├── ads/                # Advertising platform exports
│   ├── google-2024-account-level-daily report.csv
│   └── meta-daily-export-jan-1-2024-to-dec-31-2024.csv
├── reports/            # Generated analysis reports
│   ├── weekly/
│   └── h1/
├── slack/              # Slack conversation exports
│   └── exports/
├── transcripts/        # Audio/video transcriptions
│   └── jourdan-eskiin-facebook-setup-2025-07-22_-_22-33-29.vtt
├── facebook/           # Facebook/Meta data exports
├── mail/               # Email exports and archives
└── rolodex.json       # Contact database
```

## Decision Framework

When deciding where to place a file, ask these questions:

### Put in `/docs` if:
- **Is it documentation?** - Explains how something works
- **Is it a guide?** - Helps someone accomplish a task
- **Is it reference material?** - Static information for lookup
- **Is it human-authored?** - Written by a person for other people

### Put in `/data` if:
- **Is it raw data?** - Exported from a system or API
- **Is it generated?** - Created by a script or automated process
- **Is it structured data?** - JSON, CSV, database-like content
- **Is it an artifact?** - Output from some process or system

## Best Practices

### File Naming
- **`/docs`**: Use descriptive, human-readable names (`setup-guide.md`, `api-reference.md`)
- **`/data`**: Include timestamps and source identifiers (`meta-export-2025-07-24.csv`)

### Organization
- **`/docs`**: Organize by topic or audience (`tutorials/`, `reference/`, `development/`)
- **`/data`**: Organize by source system (`ads/`, `slack/`, `facebook/`)

### Versioning
- **`/docs`**: Version control with git, use meaningful commit messages
- **`/data`**: Include timestamps in filenames, maintain data lineage

## Migration Guidelines

When reorganizing existing files:

1. **Identify the file type** using the decision framework above
2. **Check for dependencies** - search codebase for references
3. **Move the file** to the appropriate directory
4. **Update all references** in code, configuration, and documentation
5. **Test** to ensure nothing breaks

## Common Mistakes

### ❌ Don't put data exports in `/docs`
Even if they're "documentation" of system state, raw data belongs in `/data`.

### ❌ Don't put tutorials in `/data`
Even if they're about data processing, guides belong in `/docs`.

### ❌ Don't mix human-authored and machine-generated content
Keep documentation (human) separate from data artifacts (machine).

### ❌ Don't put temporary files in either directory
Use `/tmp` or project-specific temp directories for temporary files.

---

Following this organization ensures that:
- **Developers** can easily find documentation and guides
- **Data analysts** can locate datasets and exports
- **Scripts** can reliably access data files
- **Version control** works appropriately for each content type 