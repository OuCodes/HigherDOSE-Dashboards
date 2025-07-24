# TODO List

## Organizing

- [ ] As we accomplish certain goals, we should move them from the comprehensive context.md file to a specific timestamped markdown file in the @/notes folder.
- [x] Create a requirements.txt file for the project
- [ ] Convert `product-list.md` to a more appropriate (non-markdown) format.
- [ ] Document the data flow in `src/higherdose/slack` and clarify how `scripts/hd_slack_to_markdown.py` and `hd_slack_to_markdown.py` are used.
- [ ] Create a top-level `config` directory for secrets (e.g., Gmail client secrets, Slack cookies).
- [ ] Merge `weekly.py` and `weekly_products.py` into a single `weekly.py` script and remove the old file.
- [ ] Update the README.md to reflect the new structure and usage instructions.
- [ ] Merge requirements.txt into the pyproject.toml file.
- [ ] Change mail tutorial.md to README.md
- [ ] Data folders need a much better naming convention
- [ ] Maybe rethink data/raw/stats naming convention should it be timeframe? or csv?

## Scripting

- [ ] Add logging to all the src logic
- [ ] Format `email/tutorial.md` correctly. The headers for prompt and response are not formatted correctly.
- [ ] Rewrite the monthly report, very out of date at this point.
- [ ] Move io.file_selector.py logic into analysis script.

## Product Data

- [ ] Determine if this should just be a dataclass type thing

## Email

- [ ] Fix the trailing and leading whitespaces around links in certain emails.