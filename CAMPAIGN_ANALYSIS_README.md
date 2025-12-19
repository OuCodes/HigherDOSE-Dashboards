# Q1 Campaign Analysis: 2024 vs 2025

## Overview

New **Campaign Analysis** tab added to the Q1 Growth Forecast Streamlit app showing Google & Meta campaign performance comparison between 2024 and 2025.

## Features

### 📊 Platform Spend Summary
- Total Q1 spend by platform (Google vs Meta)
- Platform distribution percentages
- Year-over-year January comparison

### 📈 Monthly Breakdown
- Visual comparison charts showing spend by month
- Side-by-side 2024 vs 2025 views
- Grouped by Google and Meta platforms

### 🎯 Top Campaigns
- Top 10 Google Ads campaigns by spend (2025)
- Top 10 Meta Ads campaigns by spend (2025)
- Sorted by total spend

### 🔍 Detailed Campaign View
- Filterable campaign list by year and platform
- Monthly spend breakdown per campaign
- Downloadable CSV export

## Key Findings

### 2024 Q1 Performance
- **Total Spend:** $1,619,003
- **Google:** $634,326 (39.2%)
- **Meta:** $984,677 (60.8%)

**Monthly Breakdown:**
- January: $623,482 (Google: $277,267, Meta: $346,215)
- February: $523,204 (Google: $200,552, Meta: $322,652)
- March: $472,317 (Google: $156,507, Meta: $315,810)

### 2025 Q1 Performance (January Only)
- **Total Spend:** $835,703
- **Google:** $344,468 (41.2%)
- **Meta:** $491,234 (58.8%)

**January YoY Change:** +34.0% ($212,221 increase)

### Top 2025 Google Campaigns
1. US_Search_Brand_Products - $81,070
2. US_NonBrand_Products+Concerns - $61,953
3. US_PMax_Non_Brand_AllProducts - $49,229
4. US_PMax_Brand_AllProducts - $43,640
5. US_Brand_Alone_Phrase - $41,182

### Top 2025 Meta Campaigns
1. PDM_ASC Wellness Tech Website + Shop - $118,333
2. US | ASC DYN | 010125 | CVN | Purchases | Volume | DABA - $90,084
3. US | ASC | 010125 | CVN | Purchases | Volume 20% ECBC | Red - $66,353
4. PDM_ STD MOF - $53,620
5. US | Retargeting | 010125 | CVN | Purchases - $40,700

## Data Sources

### 2024 Data
- **Google:** `data/ads/weekly-report-2024-ads/google-2024-account-level-daily report.csv`
- **Meta:** `data/ads/weekly-report-2024-ads/meta-daily-export-jan-1-2024-to-dec-31-2024.csv`
- Daily aggregated data (no individual campaign names for 2024)

### 2025 Data
- **Source:** `data/ads/northbeam-january-2025.csv`
- Campaign-level breakdown from Northbeam
- Platforms: Google Ads, Facebook Ads (normalized to Google/Meta)
- Accounting mode: Cash snapshot
- Currently: January 2025 only

## Files Generated

### Script
- `scripts/analyze_q1_campaigns.py` - Campaign data extraction and analysis

### Output Files
- `data/reports/campaign/q1_2024_campaigns.csv` - 2024 campaign data
- `data/reports/campaign/q1_2025_campaigns.csv` - 2025 campaign data

### Streamlit App
- `q1_growth_forecast_app.py` - Updated with Campaign Analysis tab (tab 4)

## Usage

### Run Campaign Analysis
```bash
python3 scripts/analyze_q1_campaigns.py
```

### Launch Streamlit App
```bash
streamlit run q1_growth_forecast_app.py
```

### Navigate to Campaign Analysis Tab
In the app, click on the **📢 Campaign Analysis** tab (4th tab)

## Tab Structure

The app now has 5 tabs:
1. **📊 Overview** - Executive summary and key metrics
2. **📈 Q1 YoY Analysis** - Year-over-year performance comparison
3. **🎯 2026 Growth Targets** - Revenue targets and scenarios
4. **📢 Campaign Analysis** - ✨ NEW: Campaign-level spend analysis
5. **📋 Data & Methodology** - Data sources and methodology

## Insights

### Spend Trends
- **January 2025 increased 34%** compared to January 2024
- Google spend increased 24% ($67K increase)
- Meta spend increased 42% ($145K increase)

### Platform Mix Shift
- 2024: 39% Google, 61% Meta
- 2025 (Jan): 41% Google, 59% Meta
- Slight shift toward Google in 2025

### Campaign Strategy
- **Google:** Focus on branded search and Performance Max campaigns
- **Meta:** Heavy investment in ASC (Advantage Shopping Campaigns) and dynamic ads

## Next Steps

To add February and March 2025 data:
1. Export February/March data from Northbeam
2. Update the analysis script to include new files
3. Re-run `python3 scripts/analyze_q1_campaigns.py`
4. Streamlit app will automatically reload with updated data

## Notes

- 2024 data is aggregated (no individual campaign names available)
- 2025 data includes full campaign-level detail from Northbeam
- For complete Q1 comparison, need Feb/Mar 2025 data
- Platform names normalized: "Google Ads" → "Google", "Facebook Ads" → "Meta"
