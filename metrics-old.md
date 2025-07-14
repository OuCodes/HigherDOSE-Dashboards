# Northbeam Metrics 101

Use this guide to understand the different Northbeam metrics and how they may differ from the numbers you’re used to seeing. :contentReference[oaicite:0]{index=0}

---

## Finding Metrics in the Dashboard

1. Navigate to the **Attribution** page.  
2. Click **Customize ⚙️** to open the metric picker. :contentReference[oaicite:1]{index=1}

---

## Northbeam Conversion Metrics

Conversion metrics are the most commonly used KPIs in Northbeam.  

> **Note:** In **Accrual Accounting** mode, every conversion metric is reported in an *Attribution Window*, which appears in the metric name (e.g., `Transactions (1d)`, `ROAS (7d)`). :contentReference[oaicite:2]{index=2}

**Examples**

- `Transactions (1d)` – transactions completed within a 1-day window  
- `Attributed Rev (1d)` – revenue attributed in a 1-day window  
- `ROAS (7d)` – return on ad spend using 7-day revenue :contentReference[oaicite:3]{index=3}

### Conversion-Metric Reference

| Metric Name | Definition | Calculation / Notes |
|-------------|------------|---------------------|
| Transactions | Transactions from **all** customers | — |
| Transactions (1st Time) | Transactions from **new** customers | — |
| Transactions (Returning) | Transactions from **returning** customers | — |
| Attributed Rev | Revenue attributed to touch-points (all customers) | Accrual mode only |
| Attributed Rev (1st Time) | Attributed revenue from new customers | Accrual mode only |
| Attributed Rev (Returning) | Attributed revenue from returning customers | Accrual mode only |
| Rev | Cash-basis revenue (all customers) | Cash mode only (no attribution window) |
| Rev (1st Time) | Cash revenue from new customers | Cash mode only |
| Rev (Returning) | Cash revenue from returning customers | Cash mode only |
| AOV | Avg. order value (all) | Cash: `Rev ÷ Transactions`<br>Accrual: `Attributed Rev ÷ Transactions` |
| AOV (1st Time) | Avg. order value (new customers) | Cash: `Rev (1st Time) ÷ Transactions (1st Time)`<br>Accrual: `Attributed Rev (1st Time) ÷ Transactions (1st Time)` |
| AOV (Returning) | Avg. order value (returning customers) | Cash: `Rev (Returning) ÷ Transactions (Returning)`<br>Accrual: `Attributed Rev (Returning) ÷ Transactions (Returning)` |
| Refunds | Returns / refunds / cancellations (all) | — |
| Refunds (1st Time) | Returns / refunds / cancellations (new customers) | — |
| Refunds (Returning) | Returns / refunds / cancellations (returning customers) | — |
| Shipping | Shipping costs (all) | — |
| Shipping (1st Time) | Shipping costs (new customers) | — |
| Shipping (Returning) | Shipping costs (returning customers) | — |
| Tax | Taxes (all) | — |
| Tax (1st Time) | Taxes (new customers) | — |
| Tax (Returning) | Taxes (returning customers) | — |
| Discounts | Discounts (all) | — |
| Discounts (1st Time) | Discounts (new customers) | — |
| Discounts (Returning) | Discounts (returning customers) | — |
| CAC | Customer-acquisition cost (all) | `Spend ÷ Transactions` |
| CAC (1st Time) | New-customer CAC | `Spend ÷ Transactions (1st Time)` |
| CAC (Returning) | Returning-customer CAC | `Spend ÷ Transactions (Returning)` |
| ROAS | Return on ad spend (all) | `Attributed Rev ÷ Spend` |
| ROAS (1st Time) | ROAS (new customers) | `Attributed Rev (1st Time) ÷ Spend` |
| ROAS (Returning) | ROAS (returning customers) | `Attributed Rev (Returning) ÷ Spend` |
| MER | Media-efficiency ratio (all) | `Rev ÷ Spend` |
| MER (1st Time) | MER (new customers) | `Rev (1st Time) ÷ Spend` |
| MER (Returning) | MER (returning customers) | `Rev (Returning) ÷ Spend` |
| ECR | E-commerce conversion rate (all) | `Transactions ÷ Visits` |
| ECR (1st Time) | ECR (new customers) | `Transactions (1st Time) ÷ Visits` |
| ECR (Returning) | ECR (returning customers) | `Transactions (Returning) ÷ Visits` | :contentReference[oaicite:4]{index=4}

---

## Northbeam Click Metrics

Below are click-based metrics. **Northbeam uses *Visits*, not raw ad clicks, in all formulas.** :contentReference[oaicite:5]{index=5}

| Metric Name | Definition | Calculation / Notes |
|-------------|------------|---------------------|
| Visits | Website visits (tracked via the Northbeam Pixel) | Clicks ≠ Visits; Visits are usually lower |
| New Visits | Visits from users who have never been seen before | Determined via Pixel + device graph |
| % New Visits | Share of first-time visitors | `(New Visits ÷ Visits) × 100` |
| CPM | Cost per 1 000 impressions | `(Spend ÷ Impressions) × 1 000` |
| CTR | Click-through rate | `Visits ÷ Impressions` (uses Visits) |
| eCPC | Effective cost per visit | `Spend ÷ Visits` |
| eCPNV | Effective cost per new visit | `Spend ÷ New Visits` | :contentReference[oaicite:6]{index=6}

---

## In-Platform Metrics

These metrics come directly from each advertising platform’s API or custom spend uploads. :contentReference[oaicite:7]{index=7}

| Metric Name | Definition | Source / Notes |
|-------------|------------|----------------|
| Spend | Ad spend | API connection or custom spreadsheet |
| Impressions | Times ads were served | API channels only |
| Facebook | Platform-reported clicks / creative / conversions | Facebook Ads API |
| TikTok | Platform-reported clicks / creative / conversions | TikTok Ads API |
| Google | Platform-reported clicks / creative / conversions | Google Ads API |
| Snapchat | Platform-reported clicks / creative / conversions | Snapchat Ads API |
| Pinterest | Platform-reported clicks / creative / conversions | Pinterest Ads API | :contentReference[oaicite:8]{index=8}

---


