Tutorial – Building a Practical Revenue- & Spend-Forecast for an e-commerce brand
===========================================================================
The two calls you captured (“Planning” 6-26 & “Forecasting” 7-02) outline a very pragmatic, spreadsheet-driven process Ingrid uses at HigherDOSE. Below is a step-by-step recipe you can reuse for any brand.
1. Define the frame of the forecast
• Time horizon: – full year split into Q1‐Q4, then months.
Outputs you’ll track:
Net DTC sales (Shopify).
Ad spend by channel.
Efficiency metrics: ROAS, CAC, % of revenue spent on media.
Scenarios: at minimum “Low/Conservative” and “High/Aggressive” spend.
2. Collect clean historical inputs
1. Pull last year’s MONTHLY sales & spend by channel.
Pull the most recent 3-month average (truer reflection of current momentum).
Export platform-reported revenue for non-ad channels:
CRM (Klaviyo + Attentive or Postscript).
Amazon 3P, Wholesale, etc.
Grab Shopify/GA4 “Direct” and “Organic” revenue – treat them as reference only (they’re not controllable levers).
Tip: store every extract on its own tab; never overwrite raw data.
3. Build the master “Actuals” sheet
Rows = months; Columns =
Total Sales (Actual)
Total Ad Spend (Actual)
Media % (Spend ÷ Sales)
ROAS (Sales ÷ Spend)
Color NOTHING here – it is 100 % factual.
4. Duplicate the sheet → create “Forecast” tabs
Create one tab for each future quarter (Q3, Q4, etc.) and one tab per future month inside those quarters.
Copy the structure of the Actuals sheet.
Highlight all forecast cells in a distinct color (Ingrid uses yellow) so you can see at a glance what’s a projection versus an actual.
5. Top-Down model (Calendar-driven)
1. On a spare tab, list every day of the target month.
Categorise each row:
Weekday (Mon-Thu)
Weekend (Fri-Sun)
“Sale Day” (planned promos/flash sales).
Input historical average revenue for each day-type (from GA or Shopify).
=COUNTIF() to total how many of each type occur.
Multiply counts by their average revenues and SUM – that gives you a “calendar forecast”.
6. Bottom-Up model (Channel-driven)
In each Monthly tab create a simple channel table:
Channel | Spend | Expected ROAS | Forecast Sales
--------|-------|---------------|----------------
Paid Social (Meta, etc.) | … | … | =Spend×ROAS
Paid Search (Google) | … | … | …
Demand Gen / Awareness (YouTube, CTV, Mountain…) | … | … | …
Affiliate / Influencer | … | … | …
CRM (Email/SMS) | (no spend) | n/a | Pull prior-year % of sales or Klaviyo projection
Amazon / 3P | (wholesale PO) | n/a | Input separately
Direct + Organic | n/a | n/a | carry prior‐year run-rate
Key rules (from the calls):
Maintain a ROAS floor (4.0 at HigherDOSE).
Let “Demand Gen” have looser 1:1 expectations – its job is top-of-funnel traffic.
Give channel owners (Jake for Meta, Rahul for Google, etc.) the spend envelope and let them fine-tune ad sets/campaigns beneath it.
7. Triangulate the two models
• Compare the Calendar total to the Channel total.
If they differ by > $100 k, examine assumptions:
Average order value?
Number of sale days?
ROAS goals too optimistic?
Iterate until the two models converge – that’s your “most plausible” plan.
8. Layer in scenarios
Create two extra columns: “Low-Spend” and “High-Spend”.
Adjust only the spend rows; leave efficiency unchanged to keep things realistic.
This quickly tells Finance the expected sales range if budgets tighten or loosen.
9. Roll up to Quarterly & Year-to-Date
In each Quarterly tab:
Metric | QTD Actual | QTD Forecast | % of Goal
-------|-----------|-------------|-----------
Sales | … | … | …
Spend | … | … | …
ROAS | … | … | …
This is Ingrid’s dashboard for leadership meetings; it shows whether you’re pacing to the FY revenue goal and how much “fuel” (spend) is still available.
10. Turn the plan into a living document
• Update every Monday: paste prior-week actual sales/spend, let formulas recalc variance.
If a channel under-delivers, re-allocate spend within the month (her rule: she only cares that Paid Social as a whole hits target; the mix of Reels vs PMax etc. is the channel owner’s problem).
Archive each month’s final version for post-mortems.
Power-user spreadsheet tricks
• =NETWORKDAYS.INTL() to count weekdays vs weekends.
=SUMPRODUCT(--(criteria_range=type),value_range) for flexible day-type multipliers.
Conditional formatting to auto-colour forecast vs actual cells.
Named ranges “Spend_PaidSocial”, “ROAS_PaidSocial” make scenario toggling easy.
Checklist before you present the forecast
☐ All assumptions (avg. revenue/day, ROAS targets) are foot-noted.
☐ Every projected cell is colour-coded.
☐ Low/High scenarios are filled in.
☐ Quarterly roll-up shows %‐to-goal.
☐ Channel owners have reviewed and signed off on their spend/ROAS targets.
Where this approach shines
• Combines calendar reality (holidays, product launches) with channel math (spend × ROAS).
Forces cross-team conversation (marketing, finance, agencies).
Simple enough to update without custom BI tools but rigorous enough for board decks.
Use this as a template, adapt the channel rows or efficiency floors to your brand, and you’ll have an Ingrid-approved forecasting engine. Good luck—and colour your projections!