# Automated Report Generation Tutorial

This guide explains how to use the automated report generation system to create weekly and monthly performance reports.

## Overview

The automation system consists of three main components:

1. **`report_mtd_automated.py`** - Main report generator with interactive prompts
2. **`generate_report.py`** - Simple command-line interface for quick reports
3. **`report_config.py`** - Configuration templates for different report types

## Quick Start

### Option 1: Interactive Mode (Recommended for first-time users)

```bash
# Activate your virtual environment first
source venv/bin/activate

# Run the interactive report generator
python scripts/report_mtd_automated.py
```

This will prompt you for:
- Date range (start and end dates)
- Available data files in your `data/ads/` directory
- Which files to use for each data type

### Option 2: Command Line (Faster for regular use)

```bash
# Generate report for specific date range
python scripts/generate_report.py --start 2025-07-01 --end 2025-07-27

# Auto-select the most recent files
python scripts/generate_report.py --start 2025-07-01 --end 2025-07-27 --auto

# List available report templates
python scripts/generate_report.py --list-templates
```

## Data Requirements

The system looks for these file types in your `data/ads/` directory:

### Required Files:
- **GA4 Source/Medium Data**: `*source_medium*.csv`
  - Contains session and revenue data by traffic source
  - Used for channel performance analysis

- **Shopify New vs Returning**: `*New vs returning*.csv` 
  - Customer mix analysis
  - Revenue breakdown by customer type

### Optional Files:
- **GA4 Channel Groups**: `*default_channel_group*.csv`
  - Aggregated channel performance
  - Useful for high-level summaries

- **Shopify Product Data**: `*Total sales by product*.csv`
  - Product performance analysis
  - Top-selling items breakdown

- **Shopify Total Sales**: `*Total sales over time*.csv`
  - Overall sales trends
  - Year-over-year comparisons

## File Naming Conventions

The system works best when your export files follow these naming patterns:

```
GA4 Exports:
- daily-traffic_acquisition_Session_source_medium-2025-07-01-2025-07-27.csv
- daily-traffic_acquisition_Session_default_channel_group-2025-07-01-2025-07-27.csv

Shopify Exports:
- New vs returning customer sales - 2025-01-01 - 2025-07-30.csv
- Total sales by product- new vs returning by date - 2025-01-01 - 2025-07-30.csv
- Total sales over time - 2025-01-01 - 2025-07-30.csv
```

## Export Instructions

### GA4 Exports

1. **Source/Medium Data**:
   - Go to Reports → Acquisition → Traffic acquisition
   - Change dimension to "Session source / medium" 
   - Set date range (e.g., July 1-27, 2025)
   - Add "Date" as secondary dimension
   - Export as CSV

2. **Channel Group Data**:
   - Same report but use "Session default channel group" dimension
   - Add "Date" as secondary dimension
   - Export as CSV

### Shopify Exports

1. **New vs Returning Customers**:
   - Analytics → Reports → Customer reports
   - "New vs returning customer sales"
   - Set date range to cover your period
   - Export as CSV

2. **Product Sales**:
   - Analytics → Reports → Product reports  
   - "Total sales by product"
   - Filter by date range
   - Include new vs returning breakdown if available
   - Export as CSV

## Generated Report Structure

The automated reports include:

### Executive Summary
- Total business revenue
- Customer mix percentages  
- Key performance indicators
- Summary insights

### Customer Mix Analysis
- New vs returning customer breakdown
- Revenue, orders, and AOV by segment
- Performance insights

### Channel Performance  
- GA4 traffic and revenue by channel
- Revenue per session metrics
- Top-performing channels

### Product Performance
- Top 10 products by revenue
- Items sold and performance metrics

## Customization

### Adding New Report Templates

Edit `scripts/report_config.py` to add new report types:

```python
'my_custom_report': ReportTemplate(
    name="My Custom Report",
    description="Description of what this report does",
    sections=[
        ReportSection(
            name="Custom Section",
            required_data=['shopify_total_sales'],
            template="""## Custom Section
            
            Your custom markdown template here...
            """
        )
    ]
)
```

### Modifying Existing Templates

You can customize the markdown templates in `report_config.py` to change:
- Section layouts
- Metrics calculated
- Insights generated
- Formatting and styling

## Troubleshooting

### Common Issues:

1. **"No files found" error**:
   - Check that your CSV files are in the `data/ads/` directory
   - Verify file naming matches expected patterns
   - Ensure files aren't corrupted or empty

2. **Date parsing errors**:
   - GA4 exports should have dates in YYYYMMDD format
   - Shopify exports vary - check the date column format
   - Some files may need the `skip_rows` parameter adjusted

3. **Missing columns**:
   - Verify your exports include all required columns
   - Column names must match exactly (case-sensitive)
   - Some exports may have different column names than expected

### Debug Mode:

Add print statements to see what data is being loaded:

```python
# In report_mtd_automated.py, add after loading data:
print("Loaded data keys:", list(self.ga4_data.keys()))
print("Sample GA4 columns:", list(self.ga4_data.get('source_medium', {}).columns) if 'source_medium' in self.ga4_data else 'None')
```

## Output

Reports are saved to `data/reports/weekly/` with filenames like:
- `mtd-performance-report-2025-07-01-to-2025-07-27.md`

The script will automatically offer to open the generated report when complete.

## Weekly Workflow

For regular weekly reports, create a simple routine:

1. **Monday**: Export fresh data from GA4 and Shopify for the previous week
2. **Save exports** to `data/ads/` with clear date ranges in filenames  
3. **Run**: `python scripts/generate_report.py --start 2025-07-01 --end 2025-07-27 --auto`
4. **Review** generated report and add any manual insights
5. **Share** with team via Slack or email

This automation should save you significant time each week while ensuring consistency in your reporting format and calculations. 