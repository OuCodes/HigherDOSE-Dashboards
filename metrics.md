# Northbeam Metrics 101

Use this guide to understand our metrics and how they may differ from the numbers you’re used to seeing. :contentReference[oaicite:0]{index=0}

---

## Finding Metrics in the Dashboard

1. Navigate to **Attribution** in the left-hand menu.  
2. Click **Customize ⚙️** to open the metric picker.  
3. Add or remove any metrics you’d like to see.

---

## Northbeam Conversion Metrics

Conversion metrics are the most commonly used KPIs in Northbeam.

> **Note:** In **Accrual Accounting** mode, every conversion metric is reported in an *Attribution Window* that appears in the metric name—for example, `Transactions (1d)` or `ROAS (7d)`. :contentReference[oaicite:1]{index=1}

| Metric Name | Definition | Calculation / Notes |
|-------------|------------|---------------------|
| Transactions | Number of transactions from **all** customers | — |
| Transactions (New) | Transactions from **new** customers | — |
| Transactions (Returning) | Transactions from **returning** customers | — |
| Attributed Rev | Revenue from all customers attributed within the window | Accrual mode only |
| Attributed Rev (New) | Attributed revenue from new customers | Accrual mode only |
| Attributed Rev (Returning) | Attributed revenue from returning customers | Accrual mode only |
| Rev | Cash-basis revenue from all customers | Cash mode only |
| Rev (New) | Cash revenue from new customers | Cash mode only |
| Rev (Returning) | Cash revenue from returning customers | Cash mode only |
| AOV | Average order value (all) | Cash: `Rev ÷ Transactions`<br>Accrual: `Attributed Rev ÷ Transactions` |
| AOV (New) | Average order value (new customers) | Cash: `Rev (New) ÷ Transactions (New)`<br>Accrual: `Attributed Rev (New) ÷ Transactions (New)` |
| AOV (Returning) | Average order value (returning customers) | Cash: `Rev (Returning) ÷ Transactions (Returning)`<br>Accrual: `Attributed Rev (Returning) ÷ Transactions (Returning)` |
| Refunds | Returns, refunds & cancellations (all) | — |
| Refunds (New) | Returns, refunds & cancellations (new) | — |
| Refunds (Returning) | Returns, refunds & cancellations (returning) | — |
| Shipping | Shipping costs (all) | — |
| Shipping (New) | Shipping costs (new) | — |
| Shipping (Returning) | Shipping costs (returning) | — |
| Tax | Taxes (all) | — |
| Tax (New) | Taxes (new) | — |
| Tax (Returning) | Taxes (returning) | — |
| Discounts | Discounts (all) | — |
| Discounts (New) | Discounts (new) | — |
| Discounts (Returning) | Discounts (returning) | — |
| CAC | Customer-acquisition cost (all) | `Spend ÷ Transactions` |
| CAC (New) | CAC for new customers | `Spend ÷ Transactions (New)` |
| CAC (Returning) | CAC for returning customers | `Spend ÷ Transactions (Returning)` |
| ROAS | Return on ad spend (all) | `Attributed Rev ÷ Spend` |
| ROAS (New) | ROAS for new customers | `Attributed Rev (New) ÷ Spend` |
| ROAS (Returning) | ROAS for returning customers | `Attributed Rev (Returning) ÷ Spend` |
| MER | Media efficiency ratio (all) | `Rev ÷ Spend` |
| MER (New) | MER for new customers | `Rev (New) ÷ Spend` |
| MER (Returning) | MER for returning customers | `Rev (Returning) ÷ Spend` |
| ECR | Ecommerce conversion rate (all) | `Transactions ÷ Visits` |
| ECR (New) | ECR for new customers | `Transactions (New) ÷ Visits` |
| ECR (Returning) | ECR for returning customers | `Transactions (Returning) ÷ Visits` |

---

## Northbeam Click Metrics

Northbeam uses **Visits** (not raw ad clicks) for all click-based calculations. :contentReference[oaicite:2]{index=2}

| Metric Name | Definition | Calculation / Notes |
|-------------|------------|---------------------|
| Visits | Website visits recorded by the Northbeam Pixel | Visits are usually lower than platform-reported clicks |
| New Visits | Visits from users who have never been seen before | Determined via Pixel + device graph |
| % New Visits | Share of first-time visitors | `(New Visits ÷ Visits) × 100` |
| CPM | Cost per 1 000 impressions | `(Spend ÷ Impressions) × 1 000` |
| CTR | Click-through rate | `Visits ÷ Impressions` |
| eCPC | Effective cost per visit | `Spend ÷ Visits` |
| eCPNV | Effective cost per new visit | `Spend ÷ New Visits` |

---

## In-Platform Metrics

These are metrics pulled directly from each advertising platform’s API or from custom spend uploads. :contentReference[oaicite:3]{index=3}

| Metric Name | Definition | Source / Notes |
|-------------|------------|----------------|
| Spend | Ad spend | API connection or CSV/Sheet upload |
| Impressions | Times ads were served | API channels only |
| Facebook | Platform-reported clicks, creatives & conversions | Facebook Ads API |
| TikTok | Platform-reported clicks, creatives & conversions | TikTok Ads API |
| Google | Platform-reported clicks, creatives & conversions | Google Ads API |
| Snapchat | Platform-reported clicks, creatives & conversions | Snapchat Ads API |
| Pinterest | Platform-reported clicks, creatives & conversions | Pinterest Ads API |

---



# Attribution Windows

We offer a variety of Attribution Windows to help inform your decision-making.

## What is an Attribution Window?

An **Attribution Window** refers to the length of time in which a touchpoint receives credit for a purchase.

> **Note:** Attribution Windows are only available using the **Accrual Accounting Mode**.

---

## Which Attribution Windows are available?

### Click-Based models (except *Clicks + Modeled Views*)

- 1-Day Click  
- 3-Day Click  
- 7-Day Click  
- 14-Day Click  
- 30-Day Click  
- 90-Day Click  
- **LTV** (infinite)

### Clicks + Modeled Views

- 1-Day Click / 1-Day View  
- 3-Day Click / 1-Day View  
- 7-Day Click / 1-Day View  
- 14-Day Click / 1-Day View  
- 30-Day Click / 1-Day View  
- 90-Day Click / 1-Day View

---

## Attribution Windows in Northbeam

Attribution Windows apply to every conversion-based metric (Revenue, Transactions, Email Sign-Ups, Subscription Orders, and any Custom Event) and to any formulaic metric that includes a conversion metric (e.g., **ROAS**, **CAC**).

**Dashboard label examples**

- `Attributed Rev (1d)`  
- `LTV Attributed Revenue`  
- `ROAS (7d)`  
- `LTV ROAS`  
- `CAC (3d)`  
- `LTV CAC`

### Attribution-Window Cheat Sheet

| Attribution Window | Window Length | Definition |
|--------------------|---------------|------------|
| **(1d)**  | 1-day window  | Conversions within **1 day** after the touchpoint |
| **(3d)**  | 3-day window  | Conversions within **3 days** after the touchpoint |
| **(7d)**  | 7-day window  | Conversions within **7 days** after the touchpoint |
| **(14d)** | 14-day window | Conversions within **14 days** after the touchpoint |
| **(30d)** | 30-day window | Conversions within **30 days** after the touchpoint |
| **(60d)** | 60-day window | Conversions within **60 days** after the touchpoint |
| **(90d)** | 90-day window | Conversions within **90 days** after the touchpoint |
| **LTV**   | Infinite      | Conversions **any time** after the touchpoint |

---

## Attribution Window Examples

### Scenario

1. **Jan 1** – Facebook ad click  
2. **Jan 3** – Google ad click  
3. **Jan 5** – Direct visit resulting in a purchase for **$90**

_Assume an equal-weight (Linear) model and **Accrual Accounting Mode**._

### Jan 1 Performance

| Platform | Attributed Rev (1d) | Attributed Rev (3d) | Attributed Rev (7d) | LTV Attributed Rev |
|----------|--------------------|---------------------|---------------------|--------------------|
| Facebook | $0 | $0 | $30 | $30 |
| Google   | $0 | $0 | $0  | $0  |
| Direct   | $0 | $0 | $0  | $0  |

### Jan 3 Performance

| Platform | Attributed Rev (1d) | Attributed Rev (3d) | Attributed Rev (7d) | LTV Attributed Rev |
|----------|--------------------|---------------------|---------------------|--------------------|
| Facebook | $0 | $0 | $0  | $0  |
| Google   | $0 | $30 | $30 | $30 |
| Direct   | $0 | $0  | $0  | $0  |

### Jan 5 Performance

| Platform | Attributed Rev (1d) | Attributed Rev (3d) | Attributed Rev (7d) | LTV Attributed Rev |
|----------|--------------------|---------------------|---------------------|--------------------|
| Facebook | $0 | $0 | $0 | $0 |
| Google   | $0 | $0 | $0 | $0 |
| Direct   | $30 | $30 | $30 | $30 |

### Journey Total (Jan 1 – Jan 5)

| Platform | Attributed Rev (1d) | Attributed Rev (3d) | Attributed Rev (7d) | LTV Attributed Rev |
|----------|--------------------|---------------------|---------------------|--------------------|
| Facebook | $0 | $0 | $30 | $30 |
| Google   | $0 | $30 | $30 | $30 |
| Direct   | $30 | $30 | $30 | $30 |

---

# Accounting Modes

Our Accounting Modes determine **when** conversion and revenue credit are given in Northbeam.

---

## What are Accounting Modes?

| Accounting Mode | Best for | How credit is attributed | Primary use-cases | Example scenarios |
|-----------------|----------|--------------------------|-------------------|-------------------|
| **Cash Snapshot** | Reporting purposes | Credit is applied to the **day of the transaction** | Measuring cash flow; blended **MER** | 1. Review weekly / monthly / quarterly channel impact.<br>2. Identify which channels drove yesterday’s revenue spike. |
| **Accrual Performance** | Daily optimizations | Credit is applied to the **day of the interaction / touchpoint** | Scaling paid media; **CAC / ROAS** | 1. See which campaigns or ads performed best in the last 7 days.<br>2. Diagnose which channel is lagging when performance drops. |

*These names mirror “cash-basis” vs. “accrual” accounting in corporate finance.*

---

## What is Cash Snapshot?

In **Cash Snapshot**, revenue and transactions are booked on the date the order is placed.

> **Cash Snapshot is useful for understanding day-to-day cash flow.**

---

## What is Accrual Performance?

In **Accrual Performance**, revenue and transactions are booked on the date of the **marketing touchpoint** that led to the visit.

Typical touchpoints include:

- Ad clicks (paid social, search, display, etc.)
- Email or SMS clicks  
- Influencer, affiliate, or organic social links  
- Organic search clicks  
- Direct visits

> **Accrual Performance helps you measure the true return on marketing spend by crediting every contributing touchpoint.**

---

## Example: Cash vs. Accrual Credit Allocation

Dan visited the **Widgets Co** site on three days and purchased \$90 on **Jan 3**.

1. **Jan 1** — Facebook Ad click  
2. **Jan 2** — Google Ad click  
3. **Jan 3** — Affiliate link click → purchase  

Assume a **Linear** attribution model (each channel gets ⅓ credit).

### Cash Snapshot – Credit Allocation

| Channel | Jan 1 | Jan 2 | Jan 3 |
|---------|-------|-------|-------|
| Facebook Ad | \$0 rev; 0 tx | \$0 rev; 0 tx | **\$30 rev; 0.33 tx** |
| Google Ad   | \$0 rev; 0 tx | \$0 rev; 0 tx | **\$30 rev; 0.33 tx** |
| Affiliate   | \$0 rev; 0 tx | \$0 rev; 0 tx | **\$30 rev; 0.33 tx** |

#### Daily Performance (Cash Snapshot)

**Jan 1**

| Channel | Spend | Revenue | MER |
|---------|-------|---------|-----|
| Facebook | \$10 | \$0 | 0.0 |
| Google   | \$10 | \$0 | 0.0 |
| Affiliate| \$0  | \$0 | 0.0 |

**Jan 2** — identical to Jan 1.

**Jan 3**

| Channel | Spend | Revenue | MER |
|---------|-------|---------|-----|
| Facebook | \$10 | \$30 | 3.0 |
| Google   | \$10 | \$30 | 3.0 |
| Affiliate| \$0  | \$30 | — |

> *All credit lands on Jan 3, which can mislead media-buying decisions—especially for long conversion cycles.*

---

### Accrual Performance – Credit Allocation

| Channel | Jan 1 | Jan 2 | Jan 3 |
|---------|-------|-------|-------|
| Facebook Ad | **\$30 rev; 0.33 tx** | \$0 rev; 0 tx | \$0 rev; 0 tx |
| Google Ad   | \$0 rev; 0 tx | **\$30 rev; 0.33 tx** | \$0 rev; 0 tx |
| Affiliate   | \$0 rev; 0 tx | \$0 rev; 0 tx | **\$30 rev; 0.33 tx** |

Accrual spreads credit across the journey, giving a clearer picture of channel performance.  
(Overview & Sales pages default to **Accrual** mode.)

---

## Cash Snapshot Use Cases

### Use Case 1 – Goal Setting with **Blended MER**

Many brands track a blended MER target (Total Revenue ÷ Total Spend) to gauge profitability.  
Because Cash Snapshot does **not** shift credit by touchpoint, MER is the preferred ratio here, while ROAS is more appropriate in Accrual mode.

| Blended MER | Facebook ROAS (1-day click) | Google ROAS (1-day click) | TikTok ROAS (1-day click) |
|-------------|-----------------------------|---------------------------|---------------------------|
| **3.5** | 1.2 | 2.5 | 0.8 |
| **3.0** | 1.0 | 2.2 | 0.6 |
| **2.5** | 0.8 | 1.9 | 0.4 |
| **2.0** | 0.6 | 1.8 | 0.2 |

Use these benchmarks to translate a top-level MER goal into channel-level ROAS / CAC targets (Northbeam’s **Benchmarking Tool** can help).

---


