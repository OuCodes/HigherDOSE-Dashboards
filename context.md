# Context

## Reorganization

- Seems like `product-list.md` should not be a markdown file

- Really need to understand how the data flows through `src/higherdose/slack` 
   - Genuinely confused how `scripts/hd_slack_to_markdown.py` and `hd_slack_to_markdown.py` are used

- ✅ Created a top level `config` dir for secrets like `config/mail/client_secret_*.json` and `config/slack/TA97020CV.env`

- Let's sort of combine weekly.py and weekly_products.py into a single script and rename it to weekly. Instead of importing weekly as a base to weeklyproducts.py lets just bring the code into weekly_products.py. Then let's rename _products to just weekly.py and get rid of the old weekly.py