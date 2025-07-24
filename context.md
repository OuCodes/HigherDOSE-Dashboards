# Context

## Reorganization

- I'm not sure that `data` > `processed` is the right place for transcripts. Maybe needs a better home.

- Need to check if `data` > `processed` is the right place for unattributed_lines because it is used in `src/higherdose/analysis/weekly_products.py`

- Probably can rename `weekly_products.py` to `products.py`

- Can probably rename `docs` > `brain` or fit into another category

- Seems like `product-list.md` should not be a markdown file

- Think `docs` > `slack_curl_example.txt` can be removed, outdated

- `reports` > `h1` and `reports` > `weekly` seem to be well organized and placed in the right place, no notes

- Really need to understand how the data flows through `src/higherdose/slack` 
   - Genuinely confused how `scripts/hd_slack_to_markdown.py` and `hd_slack_to_markdown.py` are used

- Maybe we create a top level `config` dir for secrets like `src/higherdose/mail/client_secret_874046668648-4untdu1pg2uklfvudvfaoa2e5o27aql2.apps.googleusercontent.com.json` and `data/raw/slack/slack_cookies/TA97020CV.env`

- Seems like every single script in `scripts` is having import issues and I would like to understand why

- Let's sort of combine weekly.py and weekly_products.py into a single script and rename it to weekly. Instead of importing weekly as a base to weeklyproducts.py lets just bring the code into weekly_products.py. Then let's rename _products to just weekly.py and get rid of the old weekly.py