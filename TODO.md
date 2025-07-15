# TODO List

## Organizing

- [x] Add the transcript to the repo
- [x] Ground the context file in the transcript
- [x] Add transcript to repository and set up system for future transcript processing
- [ ] As we accomplish certain goals, we should move them from the comprehensive context.md file to a specific timestamped markdown file in the @/notes folder.

- [x] Create a requirements.txt file for the project

## Scripting

- [x] Add utility scripts to the repo
- [x] Add logging to the slack converter script
- [x] Create a home for the slack script and the Slack JSON exports so the script can track which files have been converted, instead of leaving everything in the repo root
- [x] Update the weekly and monthly report scripts to prompt the user to select the correct CSV file from the `stats/` folder at runtime
- [x] Conduct preliminary research on the Gmail API/setup so we can convert emails to markdown and store them in this repo

- [ ] Format `email/tutorial.md` correctly. The headers for prompt and response are not formatted correctly.

## Improving `Mail`

- [ ] Explore what the script is pulling in for each email BEFORE it is converted to markdown.