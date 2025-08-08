# Performance Report Data Collection Guide

**For Weekly/Monthly GrowthKit Performance Reports**

---

## 📋 **Required Data Exports Checklist**

### 1. **Shopify Sales Data** ⭐ *CRITICAL*
**Files Needed:**
- `Total sales over time - [START_DATE] - [END_DATE].csv`
- `New vs returning customer sales - [START_DATE] - [END_DATE].csv` 
- `Total sales by product - [START_DATE] - [END_DATE].csv`

**Required Columns:**
```
Total sales over time:
- Day, Orders, Total sales, Gross sales, Net sales

New vs returning customer sales:
- New or returning customer, Month, Customers, Orders, Total sales

Total sales by product:
- Product title, Day, Total sales, New customers, Returning customers
```

**Export Instructions:**
1. Go to Shopify Admin → Analytics → Reports
2. Select "Sales" reports
3. Set date range (ensure it covers your reporting period completely)
4. Export as CSV with daily breakdown
5. **Important:** Make sure the date range includes the FULL period (don't miss last day)

---

### 2. **Google Ads Data** ⭐ *CRITICAL*
**File Needed:**
- `google-ads-account-level-[PERIOD]-report.csv`

**Required Columns:**
```
- Date (daily breakdown)
- Campaign, Ad group (optional for detail)
- Cost, Conversions, Conv. value
- Impressions, Clicks, CTR (optional)
```

**Export Instructions:**
1. Google Ads → Reports → Predefined reports → Basic → "Campaigns"
2. Date range: Set to your reporting period
3. Columns: Add Cost, Conversions, Conv. value
4. Segment by: Day
5. Download as CSV

**Example naming:** `google-mtd-export-jul-1-to-jul-31-2025-account-level-daily-report.csv`

---

### 3. **Meta Ads Data** ⭐ *CRITICAL*
**File Needed:**
- `meta-daily-export-[START_DATE]-to-[END_DATE].csv`

**Required Columns:**
```
- Date (daily breakdown)
- Campaign name, Ad set name (optional)
- Amount spent, Purchases, Purchase ROAS
- Results, Reach (optional)
```

**Export Instructions:**
1. Meta Ads Manager → Reports → Create Custom Report
2. Time frame: Set your reporting period
3. Breakdown: By Day
4. Metrics: Amount spent, Purchases, Purchase ROAS
5. Export as CSV

**Example naming:** `meta-mtd-export-jul-1-2025-to-jul-31-2025.csv`

---

### 4. **Google Analytics 4 Data** ⭐ *CRITICAL*
**File Needed:**
- `daily-traffic_acquisition_Session_default_channel_group-[DATES].csv`

**Required Columns:**
```
- Day, Session default channel group
- Sessions, Total revenue, Transactions
- Users (optional)
```

**Export Instructions:**
1. GA4 → Reports → Acquisition → Traffic acquisition
2. Date range: Your reporting period
3. Dimension: Session default channel group
4. Secondary dimension: Day
5. Metrics: Sessions, Total revenue, Transactions
6. Export as CSV
7. **Important:** Skip header rows when processing (usually first 9 rows)

---

### 5. **Other Ad Platforms** (If Running)

#### **TikTok Ads:**
- Date, Campaign, Spend, Purchase, Purchase value

#### **AppLovin:**
- Date, Campaign, Spend, Conversions, Revenue

#### **Pinterest Ads:**
- Date, Campaign, Spend, Total conversions, Total conversion value

#### **Microsoft Ads:**
- Date, Campaign, Cost, Conversions, Conv. value

---

### 6. **Affiliate/Partner Data**

#### **Awin (Commission Junction):**
- Date, Publisher, Clicks, Sales, Commission value

#### **ShopMyShelf:**
- Date, Influencer, Spend, Orders, Revenue

---

## 🛠️ **Step-by-Step Report Generation Process**

### **Step 1: Organize Your Data Files**
Create a folder structure:
```
data/
├── ads/
│   ├── weekly-report-[DATE]/
│   │   ├── total-sales-over-time-[DATES].csv
│   │   ├── new-vs-returning-[DATES].csv
│   │   ├── total-sales-by-product-[DATES].csv
│   │   ├── google-ads-[DATES].csv
│   │   ├── meta-ads-[DATES].csv
│   │   └── ga4-traffic-[DATES].csv
```

### **Step 2: Copy Template and Update Dates**
1. Copy your MTD summary template
2. Update **Time Period** line (e.g., "August 5-11" or "August 1-31")
3. Update **Date** line to current date

### **Step 3: Calculate Key Metrics**

#### **From Shopify Sales Data:**
```python
# Use Total sales over time CSV
total_revenue = sum(total_sales_column)
total_orders = sum(orders_column)
average_order_value = total_revenue / total_orders

# Use New vs returning customer CSV
new_customer_revenue = new_customer_total_sales
returning_customer_revenue = returning_customer_total_sales
new_customer_percentage = (new_customer_revenue / total_revenue) * 100
```

#### **From Ad Platform Data:**
```python
# Calculate for each platform
google_spend = sum(google_ads_cost)
google_revenue = sum(google_ads_conv_value)
google_roas = google_revenue / google_spend

meta_spend = sum(meta_ads_amount_spent)
meta_revenue = sum(meta_ads_purchase_value)
meta_roas = meta_revenue / meta_spend

# Total paid media
total_spend = google_spend + meta_spend + other_platforms
total_paid_revenue = google_revenue + meta_revenue + other_platforms
blended_roas = total_paid_revenue / total_spend
```

#### **Customer Acquisition Cost:**
```python
# From New vs returning customer data
new_customers = sum(new_customer_count)
cac = total_spend / new_customers
```

### **Step 4: Update Template Sections**

#### **Executive Summary:**
- Total Paid Media Spend: `$[total_spend]`
- Total Paid Media Revenue: `$[total_paid_revenue]`
- Blended ROAS: `[blended_roas]`
- Customer Acquisition Cost: `$[cac]`
- New to Brand Contribution: `[new_customer_percentage]%`

#### **Customer Mix Table:**
Use data from New vs returning customer CSV

#### **Channel Performance Table:**
Match GA4 revenue data with ad platform spend data by channel

#### **Product Performance:**
Use Total sales by product CSV, filter by date range, group by product

---

## ⚠️ **Common Pitfalls & Solutions**

### **1. Date Range Mismatches**
❌ **Problem:** Different end dates across exports
✅ **Solution:** Always export with same exact date range. Double-check last day is included.

### **2. GA4 Header Rows**
❌ **Problem:** CSV includes 9 header/comment rows
✅ **Solution:** When reading GA4 CSVs, skip first 9 rows: `pd.read_csv(file, skiprows=9)`

### **3. Channel Name Mismatches**
❌ **Problem:** "Google Ads" in ad platform vs "Paid Search" in GA4
✅ **Solution:** Create mapping dictionary:
```python
channel_mapping = {
    'Paid Search': 'Google Ads',
    'Paid Social': 'Meta Ads',
    # etc.
}
```

### **4. Currency/Number Formatting**
❌ **Problem:** Numbers stored as text with $ signs or commas
✅ **Solution:** Clean before calculating:
```python
df['spend'] = df['spend'].str.replace('$', '').str.replace(',', '').astype(float)
```

### **5. Attribution Discrepancies**
❌ **Problem:** Platform revenue ≠ GA4 revenue for same channel
✅ **Solution:** Note discrepancies in report. Use GA4 for consistency, mention platform data as reference.

---

## 📊 **Validation Checklist**

Before publishing your report:

- [ ] **Total revenue** matches Shopify dashboard for the period
- [ ] **Date ranges** are identical across all data sources
- [ ] **Spend totals** add up correctly across all channels
- [ ] **ROAS calculations** use correct revenue/spend pairing
- [ ] **Percentages** add up to 100% where applicable
- [ ] **YoY comparisons** use same date ranges from previous year
- [ ] **Product performance** reflects complete period (not partial)

---

## 🔧 **Quick Python Script Template**

```python
import pandas as pd

# Load data files
sales_data = pd.read_csv('total-sales-over-time.csv')
customer_data = pd.read_csv('new-vs-returning-customer-sales.csv')
google_data = pd.read_csv('google-ads-report.csv')
meta_data = pd.read_csv('meta-ads-report.csv')
ga4_data = pd.read_csv('ga4-traffic-report.csv', skiprows=9)

# Calculate key metrics
total_revenue = sales_data['Total sales'].sum()
total_orders = sales_data['Orders'].sum()
aov = total_revenue / total_orders

# Print results for easy copy-paste
print(f"Total Revenue: ${total_revenue:,.0f}")
print(f"Total Orders: {total_orders:,.0f}")
print(f"AOV: ${aov:.0f}")
# etc.
```

---

## 📞 **When You Need Help**

If data doesn't match or calculations seem off:
1. **Check date ranges first** - 80% of issues are date mismatches
2. **Verify file formats** - ensure CSVs have expected columns
3. **Compare totals** - cross-reference with platform dashboards
4. **Document discrepancies** - note any attribution differences in report

**Remember:** Perfect attribution is impossible. Consistency and clear notes about methodology are more important than perfect precision. 