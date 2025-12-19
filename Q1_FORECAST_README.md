# Q1 Growth & Forecast Dashboard

## 🎯 What This Dashboard Does

Provides comprehensive Q1 analysis comparing 2024 vs 2025, with 20% growth targets for 2026:

- **Overview Tab**: Executive summary with key Q1 metrics across all 3 years
- **Q1 YoY Analysis Tab**: Detailed 2024 vs 2025 comparison (revenue, spend, MER by month and day)
- **2026 Growth Targets Tab**: 20% growth scenarios with spend and MER requirements
- **Data & Methodology Tab**: Full documentation of data sources and calculations

## 📊 Data Files Created

### 1. 2025 Northbeam YTD Export
- **File**: `data/ads/ytd_sales_data-higher_dose_llc-2025_12_18-*.csv`
- **Created by**: `scripts/pull_northbeam_ytd_2025.py`
- **Contains**: Full year 2025 (Jan 1 - Dec 18) with all 428 Northbeam metrics
- **Size**: ~90 MB, 102,783 rows
- **Schema**: Daily data by platform with spend, revenue, transactions, MER, CAC, LTV metrics

### 2. 2024 Spend Aggregation
- **File**: `data/ads/northbeam_style_daily_2024-*.csv`
- **Created by**: `scripts/build_2024_spend_file.py`
- **Contains**: Daily spend for Meta + Google throughout 2024
- **Size**: ~40 KB, 732 rows
- **Schema**: date, platform, spend, accounting_mode, attribution_model, attribution_window

## 🚀 How to Run

### Prerequisites

```bash
# Install dependencies (if not already installed)
pip install streamlit pandas plotly
```

### Launch the Dashboard

```bash
# From the repo root
streamlit run q1_growth_forecast_app.py
```

The dashboard will open in your browser at http://localhost:8501

## 🔄 Updating Data

### To Pull Latest 2025 Data

```bash
# Pull fresh Northbeam data (updates through current date)
python3 scripts/pull_northbeam_ytd_2025.py
```

### To Rebuild 2024 Data

```bash
# Rebuild 2024 spend file from Meta/Google exports
python3 scripts/build_2024_spend_file.py
```

## 📈 Key Features

### Overview Tab
- Q1 totals for 2024, 2025, and 2026 goal (+20%)
- YoY comparison with delta percentages
- Pullback analysis (if 2025 < 2024)
- Scenario analysis for hitting 2026 targets
- Monthly breakdown table

### Q1 YoY Analysis Tab
- Monthly revenue and MER comparison charts
- Daily revenue trend lines (2024 vs 2025)
- Daily MER trend lines with 3.0x target reference

### 2026 Growth Targets Tab
- Monthly revenue targets table (2024/2025/2026)
- Grouped bar chart visualization
- Scenario 1: Hold MER constant → required spend increase
- Scenario 2: Hold spend constant → required MER improvement
- Daily pacing requirements

### Data & Methodology Tab
- Complete documentation of data sources
- Calculation methodologies
- Known limitations
- File paths for reference

## 📝 Key Metrics Explained

### MER (Marketing Efficiency Ratio)
- **Formula**: MER = Revenue / Spend
- **Revenue source**: Shopify total sales
- **Spend source**: 
  - 2024: Meta + Google only
  - 2025: All channels via Northbeam
- **Note**: 2024 vs 2025 MER comparison has limitations due to different channel coverage

### Q1 Definition
- January 1 → March 31 (90 days)

### 2026 Growth Target
- Goal: +20% revenue growth over Q1 2025
- Applied uniformly to each month
- Daily target = Total Q1 goal / 90 days

## ⚠️ Important Notes

### Data Comparison Limitations

**2024 vs 2025 Spend:**
- 2024 includes only Meta + Google (70% and 30% respectively)
- 2025 includes all channels via Northbeam (Meta, Google, Email, Affiliate, etc.)
- This makes direct spend comparisons not perfectly apples-to-apples
- MER comparisons between years should account for this difference

**Why This Matters:**
- 2024 MER may appear artificially high because denominator (spend) doesn't include all channels
- 2025 MER is more accurate as it captures full marketing spend
- For true YoY efficiency comparison, focus on revenue trends and within-year MER improvements

### Recommended Analysis Approach

1. **For 2024→2025 comparison**: Focus on revenue trends and understand that MER differences are partially due to spend coverage
2. **For 2026 planning**: Use 2025 as the baseline since it has complete spend data
3. **For spend planning**: Use 2025 Northbeam data as the foundation, not 2024

## 🗂️ File Structure

```
data/ads/
├── ytd_sales_data-higher_dose_llc-2025_12_18-*.csv  # 2025 Northbeam YTD
├── northbeam_style_daily_2024-*.csv                  # 2024 spend (Meta+Google)
└── exec-sum/
    ├── Total sales over time - 2024-01-01 - 2024-12-31-DAILY.csv  # 2024 sales
    └── Total sales over time - OU - 2025-01-01 - *.csv            # 2025 sales

scripts/
├── pull_northbeam_ytd_2025.py      # Pull fresh 2025 Northbeam data
└── build_2024_spend_file.py         # Build 2024 spend aggregation

q1_growth_forecast_app.py            # Main Streamlit dashboard
```

## 🔧 Troubleshooting

### "No 2025 sales file found"
- Check that you have a file matching: `data/ads/exec-sum/Total sales over time - OU - 2025-*.csv`

### "No 2024 spend file found"
- Run: `python3 scripts/build_2024_spend_file.py`

### "No 2025 Northbeam YTD file found"
- Run: `python3 scripts/pull_northbeam_ytd_2025.py`
- Make sure Northbeam credentials are set in `config/northbeam/.env`

### Streamlit not installed
```bash
pip install streamlit pandas plotly
```

## 💡 Tips for Use

1. **Start with Overview tab** to get the high-level Q1 story
2. **Use Q1 YoY Analysis** to understand where the differences are (monthly or daily patterns)
3. **Reference 2026 Growth Targets** for planning and resource allocation
4. **Export data** using the download buttons in each tab for further analysis
5. **Refresh data regularly** by re-running the pull scripts to keep forecasts current

## 📞 Questions?

Refer to the **Data & Methodology** tab in the dashboard for detailed documentation of all calculations and data sources.
