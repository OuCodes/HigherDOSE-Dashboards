# HigherDOSE Dashboards

Public Streamlit dashboards for HigherDOSE performance tracking.

## Available Dashboards

### 🎄 December Comparison Dashboard
- **File:** `december_comparison_app.py`
- **Description:** December 2024 vs 2025 performance comparison
- **Metrics:** Revenue, Orders, MER, GA4 Sessions, Ad Spend

### 📊 BFCM Dashboard  
- **File:** `streamlit_app.py`
- **Description:** Black Friday Cyber Monday performance tracking
- **Metrics:** Revenue, MER, Email Campaigns, Daily Performance

### 📈 November Insights Dashboard
- **File:** `november_insights_app.py`
- **Description:** November 2024 vs 2025 detailed analysis
- **Metrics:** Shopify, GA4, Meta, Google, SMS

## Running Locally

```bash
pip install -r requirements.txt
streamlit run december_comparison_app.py
```

## Data Structure

The dashboards expect data files in the following structure:
```
data/
├── ads/
│   ├── exec-sum/
│   └── weekly-report-2024-ads/
└── mail/
```

**Note:** This is a public repository for dashboard deployment. Actual data files are not included and must be uploaded separately or linked from a private source.

