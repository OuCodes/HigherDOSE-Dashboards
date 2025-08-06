# Weekly/Monthly Report Generation Checklist

**Print this page and keep it handy for report generation**

---

## 📥 **Data Export Checklist**

### **Before You Start:**
- [ ] Determine exact date range (e.g., Aug 5-11 or Aug 1-31)
- [ ] Create folder: `data/ads/weekly-report-[DATE]/`

### **Required Exports (Same Date Range!):**

#### **1. Shopify (3 files)** ⭐
- [ ] **Total sales over time** - Daily breakdown
- [ ] **New vs returning customer sales** - Monthly totals  
- [ ] **Total sales by product** - Daily breakdown with customer types

#### **2. Google Ads (1 file)** ⭐
- [ ] **Campaign report** - Daily breakdown with Cost, Conv. value
- [ ] Naming: `google-ads-[dates]-report.csv`

#### **3. Meta Ads (1 file)** ⭐  
- [ ] **Custom report** - Daily breakdown with Spend, Purchase value
- [ ] Naming: `meta-ads-[dates]-report.csv`

#### **4. Google Analytics 4 (1 file)** ⭐
- [ ] **Traffic acquisition** - By day + default channel group
- [ ] Include: Sessions, Total revenue, Transactions
- [ ] **Remember:** Skip first 9 rows when reading

#### **5. Other Platforms (as needed):**
- [ ] TikTok Ads - Daily spend/revenue
- [ ] AppLovin - Daily spend/revenue  
- [ ] Pinterest - Daily spend/revenue
- [ ] Microsoft Ads - Daily spend/revenue

---

## 🔢 **Key Calculations Quick Reference**

```python
# From Shopify data
total_revenue = sum(Total_sales)
total_orders = sum(Orders) 
aov = total_revenue / total_orders
new_customer_pct = (new_revenue / total_revenue) * 100

# From ad platforms  
total_spend = google_spend + meta_spend + other_spend
blended_roas = total_paid_revenue / total_spend
cac = total_spend / new_customers

# ROAS per channel
google_roas = google_revenue / google_spend
meta_roas = meta_revenue / meta_spend
```

---

## 📝 **Template Update Order**

1. **Copy template** → Rename with new date
2. **Update header dates** (Time Period & Date lines)
3. **Executive Summary** → All key metrics
4. **Customer Mix table** → New vs returning data
5. **Monthly Trends** → Add new period row
6. **YoY Comparison** → Previous year same period
7. **Product Performance** → Top 10 products from daily data
8. **Channel table** → Match spend to GA4 revenue
9. **Key Insights** → Update based on performance
10. **Strategic Recommendations** → Adjust based on results

---

## ⚠️ **Critical Checks Before Publishing**

- [ ] **Date ranges match** across all exports
- [ ] **Total revenue** matches Shopify dashboard  
- [ ] **Spend totals** add up correctly
- [ ] **ROAS calculations** are revenue ÷ spend
- [ ] **Percentages** add to 100% where applicable
- [ ] **GA4 data** processed correctly (skip header rows)
- [ ] **YoY comparison** uses exact same date range from previous year

---

## 🚨 **Common Issues Quick Fixes**

**"Numbers don't add up"**
→ Check date ranges first (90% of issues)

**"GA4 won't load"**  
→ Skip first 9 rows: `pd.read_csv(file, skiprows=9)`

**"Channel names don't match"**
→ Map GA4 names: Paid Search = Google Ads, Paid Social = Meta

**"Revenue way off"**
→ Ensure using Total sales (not Net sales) from Shopify

**"Product data missing"**
→ Use daily product CSV, not summary CSV

---

## 🎯 **Quality Benchmarks**

**Good Report Should Have:**
- Total revenue within 2% of Shopify dashboard
- Blended ROAS between 2.5-4.5 (typically)  
- New customer % between 60-80% (typically)
- Channel ROAS: Google 2-4x, Meta 0.5-2x (varies)
- Top 10 products = ~70-80% of revenue

**Red Flags:**
- ROAS over 10x (likely calculation error)
- 0% new customers (data missing)
- Negative revenue (wrong column)
- Spend > Revenue by huge margin (check attribution)

---

## 📞 **Emergency Contacts**

**Platform Issues:**
- Google Ads Support: Check conversion tracking
- Meta Support: Verify pixel firing  
- Shopify: Ensure reports include full date range

**Data Questions:**
- Always cross-reference with platform dashboards
- When in doubt, document the discrepancy
- Better to note uncertainty than guess 