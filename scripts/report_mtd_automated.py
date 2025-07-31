#!/usr/bin/env python3
"""
HigherDOSE Automated MTD Performance Report Generator

This script automates the creation of Month-to-Date performance summaries
by prompting for date ranges and data sources, then generating a comprehensive
markdown report similar to the weekly growth reports.

Usage:
    python scripts/report_mtd_automated.py

Requirements:
    - GA4 export files (session data by source/medium and default channel group)
    - Shopify exports (total sales, new vs returning customers, product sales)
    - Northbeam spend data (if available)
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import glob
from typing import Dict, List, Optional, Tuple

class MTDReportGenerator:
    def __init__(self):
        self.data_dir = Path("data/ads")
        self.reports_dir = Path("data/reports/weekly")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize data containers
        self.ga4_data = {}
        self.shopify_data = {}
        self.northbeam_data = {}
        self.date_range = {}
        
    def prompt_date_range(self) -> Tuple[str, str]:
        """Prompt user for start and end dates with preset options"""
        print("\n=== DATE RANGE SELECTION ===")
        print("Choose a date range preset or select Custom:")
        print("  1) Month-to-Date (from 1st of this month to yesterday)")
        print("  2) Last 30 Days (up to yesterday)")
        print("  3) Custom Range")
        
        while True:
            choice = input("Select option [1-3]: ").strip()
            today = datetime.today().date()
            if choice == "1":
                end_dt = today - timedelta(days=1)
                start_dt = end_dt.replace(day=1)
                start_date = start_dt.strftime("%Y-%m-%d")
                end_date = end_dt.strftime("%Y-%m-%d")
            elif choice == "2":
                days = 30
                end_dt = today - timedelta(days=1)
                start_dt = end_dt - timedelta(days=days - 1)
                start_date = start_dt.strftime("%Y-%m-%d")
                end_date = end_dt.strftime("%Y-%m-%d")
            elif choice == "3":
                # Custom range – ask user for dates
                print("Enter dates in YYYY-MM-DD format")
                try:
                    start_date = input("Start date: ").strip()
                    end_date = input("End date: ").strip()
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                    if start_dt > end_dt:
                        print("❌ Start date must be before end date. Try again.")
                        continue
                except ValueError:
                    print("❌ Invalid date format. Try again.")
                    continue
            else:
                print("❌ Invalid option. Please choose 1, 2, or 3.")
                continue
            # At this point we have start_date/end_date strings and start_dt/end_dt objects
            if choice in {"1", "2", "3"}:
                # We already assigned start_dt/end_dt above
                pass
            else:
                # ensure date objects for custom
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            
            self.date_range = {
                'start': start_date,
                'end': end_date,
                'start_dt': datetime.combine(start_dt, datetime.min.time()),
                'end_dt': datetime.combine(end_dt, datetime.min.time())
            }
            print(f"✅ Date range set: {start_date} to {end_date}")
            return start_date, end_date

    def _report_missing_data(self) -> None:
        """Check which key data sets are missing and alert the user"""
        missing_sources = []
        # Shopify customer mix
        if 'new_returning' not in self.shopify_data or self.shopify_data.get('new_returning') is None or self.shopify_data['new_returning'].empty:
            missing_sources.append("Shopify 'New vs Returning' customer data")
        # Shopify product performance
        if 'products' not in self.shopify_data or self.shopify_data['products'].empty:
            missing_sources.append("Shopify product sales data")
        # GA4 channel / source data
        if 'channel_group' not in self.ga4_data or self.ga4_data['channel_group'].empty:
            missing_sources.append("GA4 Channel Group data")
        if 'source_medium' not in self.ga4_data or self.ga4_data['source_medium'].empty:
            missing_sources.append("GA4 Source / Medium data")
        
        if missing_sources:
            print("\n⚠️  The following data sources were NOT found for the selected date range. Corresponding sections will be omitted:")
            for src in missing_sources:
                print(f"   • {src}")
        else:
            print("\n✅ All key data sources are available for this report.")
    
    def find_available_files(self) -> Dict[str, List[str]]:
        """Find available data files in the data directory"""
        file_patterns = {
            'ga4_source_medium': '*source_medium*.csv',
            'ga4_channel_group': '*default_channel_group*.csv',
            'shopify_total_sales': '*Total sales over time*.csv',
            'shopify_new_returning': '*New vs returning*.csv',
            'shopify_products': '*Total sales by product*.csv',
            'northbeam': '*northbeam*.csv'
        }
        
        available_files = {}
        
        print("\n=== SCANNING FOR DATA FILES ===")
        
        for file_type, pattern in file_patterns.items():
            files = glob.glob(str(self.data_dir / "**" / pattern), recursive=True)
            available_files[file_type] = files
            
            if files:
                print(f"✅ {file_type}: {len(files)} file(s) found")
                # Do not list every file to keep terminal output clean
            else:
                print(f"⚠️  {file_type}: No files found")
        
        return available_files
    
    def select_files(self, available_files: Dict[str, List[str]]) -> Dict[str, str]:
        """Let user select which files to use for the report"""
        selected_files = {}
        
        print("\n=== FILE SELECTION ===")
        
        for file_type, files in available_files.items():
            if not files:
                print(f"⚠️  Skipping {file_type} - no files available")
                continue
                
            if len(files) == 1:
                selected_files[file_type] = files[0]
                print(f"✅ Auto-selected for {file_type}: {os.path.basename(files[0])}")
            else:
                print(f"\n📁 Multiple {file_type} files found (showing up to 10 most recent):")
                # Sort by modification time (newest first) and take top 10
                files_sorted = sorted(files, key=os.path.getmtime, reverse=True)[:10]
                for i, file_path in enumerate(files_sorted):
                    print(f"   {i+1}. {os.path.basename(file_path)} (modified {datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M')})")
                
                # Use the sorted list for selection so indices line up
                files = files_sorted

                while True:
                    try:
                        choice = input(f"Select file for {file_type} (1-{len(files)}, or 's' to skip): ").strip()
                        
                        if choice.lower() == 's':
                            print(f"⏭️  Skipping {file_type}")
                            break
                            
                        choice_idx = int(choice) - 1
                        if 0 <= choice_idx < len(files):
                            selected_files[file_type] = files[choice_idx]
                            print(f"✅ Selected: {os.path.basename(files[choice_idx])}")
                            break
                        else:
                            print(f"❌ Please enter a number between 1 and {len(files)}")
                    except ValueError:
                        print("❌ Please enter a valid number or 's' to skip")
        
        return selected_files
    
    def load_data(self, selected_files: Dict[str, str]) -> None:
        """Load and process the selected data files"""
        print("\n=== LOADING DATA ===")
        
        start_date = self.date_range['start_dt']
        end_date = self.date_range['end_dt']
        
        # Load GA4 data
        if 'ga4_source_medium' in selected_files:
            print("📊 Loading GA4 source/medium data...")
            try:
                df = pd.read_csv(selected_files['ga4_source_medium'], skiprows=9)
                df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
                df_filtered = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
                df_filtered['Total revenue'] = pd.to_numeric(df_filtered['Total revenue'], errors='coerce').fillna(0)
                self.ga4_data['source_medium'] = df_filtered
                print(f"✅ Loaded {len(df_filtered)} rows of GA4 source/medium data")
            except Exception as e:
                print(f"❌ Error loading GA4 source/medium data: {e}")
        
        if 'ga4_channel_group' in selected_files:
            print("📊 Loading GA4 channel group data...")
            try:
                df = pd.read_csv(selected_files['ga4_channel_group'], skiprows=9)
                # Harmonize column names
                if 'Session default channel group' in df.columns and 'Default channel group' not in df.columns:
                    df.rename(columns={'Session default channel group': 'Default channel group'}, inplace=True)
                df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d', errors='coerce')
                df_filtered = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
                df_filtered['Total revenue'] = pd.to_numeric(df_filtered['Total revenue'], errors='coerce').fillna(0)
                self.ga4_data['channel_group'] = df_filtered
                print(f"✅ Loaded {len(df_filtered)} rows of GA4 channel group data")
            except Exception as e:
                print(f"❌ Error loading GA4 channel group data: {e}")
        
        # Load Shopify data
        if 'shopify_total_sales' in selected_files:
            print("🛒 Loading Shopify total sales data...")
            try:
                df = pd.read_csv(selected_files['shopify_total_sales'])
                self.shopify_data['total_sales'] = df
                print(f"✅ Loaded Shopify total sales data")
            except Exception as e:
                print(f"❌ Error loading Shopify total sales data: {e}")
        
        if 'shopify_new_returning' in selected_files:
            print("🛒 Loading Shopify new vs returning data...")
            try:
                df = pd.read_csv(selected_files['shopify_new_returning'])
                self.shopify_data['new_returning'] = df
                print(f"✅ Loaded Shopify new vs returning data")
            except Exception as e:
                print(f"❌ Error loading Shopify new vs returning data: {e}")
        
        if 'shopify_products' in selected_files:
            print("🛒 Loading Shopify product sales data...")
            try:
                df = pd.read_csv(selected_files['shopify_products'])
                if 'Day' in df.columns:
                    df['Day'] = pd.to_datetime(df['Day'])
                    df_filtered = df[(df['Day'] >= start_date) & (df['Day'] <= end_date)]
                    self.shopify_data['products'] = df_filtered
                    print(f"✅ Loaded {len(df_filtered)} rows of Shopify product data")
                else:
                    self.shopify_data['products'] = df
                    print(f"✅ Loaded Shopify product data (no date filtering)")
            except Exception as e:
                print(f"❌ Error loading Shopify product data: {e}")
    
    def calculate_ga4_metrics(self) -> Dict:
        """Calculate key metrics from GA4 data"""
        metrics = {}
        
        if 'source_medium' in self.ga4_data:
            df = self.ga4_data['source_medium']
            
            # Channel performance
            channel_performance = df.groupby('Session source / medium').agg({
                'Sessions': 'sum',
                'Total revenue': 'sum'
            }).sort_values('Total revenue', ascending=False)
            
            metrics['channel_performance'] = channel_performance
            metrics['total_sessions'] = df['Sessions'].sum()
            metrics['total_ga4_revenue'] = df['Total revenue'].sum()
        
        if 'channel_group' in self.ga4_data:
            df = self.ga4_data['channel_group']
            
            if 'Default channel group' not in df.columns:
                print("⚠️  GA4 Channel Group data missing 'Default channel group' column – skipping channel breakdown.")
            else:
                # Default channel group performance
                channel_group_performance = df.groupby('Default channel group').agg({
                    'Sessions': 'sum',
                    'Total revenue': 'sum'
                }).sort_values('Total revenue', ascending=False)
                
                metrics['channel_group_performance'] = channel_group_performance
        
        return metrics
    
    def calculate_shopify_metrics(self) -> Dict:
        """Calculate key metrics from Shopify data"""
        metrics = {}
        
        # Customer mix from new vs returning data
        if 'new_returning' in self.shopify_data:
            df = self.shopify_data['new_returning']
            
            # Find the most recent month's data (assuming monthly data)
            if 'Month' in df.columns:
                latest_month = df['Month'].max()
                current_data = df[df['Month'] == latest_month]
                
                if len(current_data) >= 2:  # Should have both New and Returning
                    new_data = current_data[current_data['New or returning customer'] == 'New'].iloc[0]
                    returning_data = current_data[current_data['New or returning customer'] == 'Returning'].iloc[0]
                    
                    metrics['customer_mix'] = {
                        'new_revenue': new_data['Total sales'],
                        'new_orders': new_data['Orders'],
                        'returning_revenue': returning_data['Total sales'],
                        'returning_orders': returning_data['Orders'],
                        'total_revenue': new_data['Total sales'] + returning_data['Total sales'],
                        'total_orders': new_data['Orders'] + returning_data['Orders']
                    }
        
        # Product performance
        if 'products' in self.shopify_data:
            df = self.shopify_data['products']
            
            if 'Product title' in df.columns and 'Total sales' in df.columns:
                product_performance = df.groupby('Product title').agg({
                    'Total sales': 'sum',
                    'Net items sold': 'sum'
                }).sort_values('Total sales', ascending=False)
                
                metrics['product_performance'] = product_performance.head(10)
        
        return metrics
    
    def generate_report(self, ga4_metrics: Dict, shopify_metrics: Dict) -> str:
        """Generate the markdown report"""
        start_date = self.date_range['start']
        end_date = self.date_range['end']
        report_date = datetime.now().strftime("%B %d, %Y")
        
        report = f"""# HigherDOSE MTD Performance Summary

**Time Period:** {start_date} - {end_date}  
**Generated:** {report_date}

---

## EXECUTIVE SUMMARY

"""
        
        # Build executive summary bullet list to match template
        exec_lines = []
        # Attempt to gather / calculate metrics
        total_paid_media_rev = ga4_metrics.get('total_ga4_revenue')  # approximation
        rev_to_net = None  # Not yet calculated
        blended_roas = None  # requires spend data
        cac = None  # requires orders + spend
        paid_contribution = None  # paid media rev / business revenue
        yoy = None  # needs prior-year data
        
        # Append bullets in desired order
        exec_lines.append(f"- **Total Paid Media Revenue:** ${total_paid_media_rev:,.0f}" if total_paid_media_rev is not None else "- **Total Paid Media Revenue:** N/A")
        exec_lines.append(f"- **Rev-to-Net:** ${rev_to_net:,.0f}" if rev_to_net else "- **Rev-to-Net:** N/A")
        exec_lines.append(f"- **Blended ROAS:** {blended_roas:.2f}" if blended_roas else "- **Blended ROAS:** N/A")
        exec_lines.append(f"- **Customer Acquisition Cost (CAC):** ${cac:,.0f}" if cac else "- **Customer Acquisition Cost (CAC):** N/A")
        if 'customer_mix' in shopify_metrics:
            cm = shopify_metrics['customer_mix']
            new_pct = (cm['new_revenue'] / cm['total_revenue'] * 100) if cm['total_revenue'] > 0 else 0
            returning_pct = (cm['returning_revenue'] / cm['total_revenue'] * 100) if cm['total_revenue'] > 0 else 0
            exec_lines.append(f"- **New to Brand Contribution:** {new_pct:.1f}%")
            exec_lines.append(f"- **Returning Customer Contribution:** {returning_pct:.1f}%")
        else:
            exec_lines.append("- **New to Brand Contribution:** N/A")
            exec_lines.append("- **Returning Customer Contribution:** N/A")
        exec_lines.append(f"- **Paid Media Contribution to Total Business Revenue:** {paid_contribution:.1f}%" if paid_contribution else "- **Paid Media Contribution to Total Business Revenue:** N/A")
        exec_lines.append(f"- **Total Business Revenue YoY:** {yoy}" if yoy else "- **Total Business Revenue YoY:** N/A")
        
        report += "\n".join(exec_lines) + "\n\n"
        
        report += """---

## Customer Mix (New vs. Returning)

"""
        
        if 'customer_mix' in shopify_metrics:
            cm = shopify_metrics['customer_mix']
            new_aov = cm['new_revenue'] / cm['new_orders'] if cm['new_orders'] > 0 else 0
            returning_aov = cm['returning_revenue'] / cm['returning_orders'] if cm['returning_orders'] > 0 else 0
            total_aov = cm['total_revenue'] / cm['total_orders'] if cm['total_orders'] > 0 else 0
            new_pct = (cm['new_revenue'] / cm['total_revenue'] * 100) if cm['total_revenue'] > 0 else 0
            returning_pct = (cm['returning_revenue'] / cm['total_revenue'] * 100) if cm['total_revenue'] > 0 else 0
            
            report += f"""| Segment               | Revenue | Orders | AOV | % of Total Revenue |
|-----------------------|---------|--------|-----|-------------------|
| New-to-Brand Users    | ${cm['new_revenue']:,.0f} | {cm['new_orders']:,} | ${new_aov:.0f} | {new_pct:.1f}% |
| Returning Customers   | ${cm['returning_revenue']:,.0f} | {cm['returning_orders']:,} | ${returning_aov:.0f} | {returning_pct:.1f}% |
| **Total**             | ${cm['total_revenue']:,.0f} | {cm['total_orders']:,} | ${total_aov:.0f} | **100%** |

**Insight:**  
> New customers generated {new_pct:.1f}% of total revenue with an AOV ${new_aov - returning_aov:+.0f} {'higher' if new_aov > returning_aov else 'lower'} than returning buyers (${new_aov:.0f} vs ${returning_aov:.0f}).

"""
        else:
            report += "⚠️ Customer mix data not available - please ensure Shopify 'New vs returning customer sales' data is loaded.\n\n"
        
        report += """---

## Channel Performance (GA4)

"""
        
        if 'channel_group_performance' in ga4_metrics:
            df = ga4_metrics['channel_group_performance']
            report += """| Channel | Sessions | Revenue | Revenue per Session |
|---------|----------|---------|-------------------|
"""
            for channel, row in df.head(10).iterrows():
                sessions = int(row['Sessions'])
                revenue = row['Total revenue']
                rps = revenue / sessions if sessions > 0 else 0
                report += f"| {channel} | {sessions:,} | ${revenue:,.0f} | ${rps:.2f} |\n"
        else:
            report += "⚠️ GA4 channel performance data not available.\n"
        
        report += """
---

## Top Products Performance

"""
        
        if 'product_performance' in shopify_metrics:
            df = shopify_metrics['product_performance']
            report += """| Product Name | Revenue | Items Sold |
|--------------|---------|------------|
"""
            for product, row in df.head(10).iterrows():
                revenue = row['Total sales']
                items = int(row['Net items sold']) if 'Net items sold' in row else 0
                report += f"| {product} | ${revenue:,.0f} | {items:,} |\n"
        else:
            report += "⚠️ Product performance data not available.\n"
        
        report += """
---

## Data Sources Used

"""
        
        # Document which data sources were used
        if self.ga4_data:
            report += "**GA4 Data:**\n"
            for key in self.ga4_data.keys():
                report += f"- {key.replace('_', ' ').title()}\n"
        
        if self.shopify_data:
            report += "\n**Shopify Data:**\n"
            for key in self.shopify_data.keys():
                report += f"- {key.replace('_', ' ').title()}\n"
        
        report += f"\n*Report generated on {report_date}*\n"
        
        return report
    
    def save_report(self, report_content: str) -> str:
        """Save the report to a file"""
        start_date = self.date_range['start']
        end_date = self.date_range['end']
        
        # Create filename
        filename = f"mtd-performance-report-{start_date}-to-{end_date}.md"
        filepath = self.reports_dir / filename
        
        # Save report
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"✅ Report saved to: {filepath}")
        return str(filepath)
    
    def run(self):
        """Main execution flow"""
        print("🚀 HigherDOSE MTD Performance Report Generator")
        print("=" * 50)
        
        # Step 1: Get date range
        self.prompt_date_range()
        
        # Step 2: Find available files
        available_files = self.find_available_files()
        
        # Step 3: Let user select files
        selected_files = self.select_files(available_files)
        
        if not selected_files:
            print("❌ No files selected. Exiting.")
            return
        
        # Step 4: Load data
        self.load_data(selected_files)
        
        # Step 5: Check for missing data
        self._report_missing_data()
        
        # Step 6: Calculate metrics
        print("\n=== CALCULATING METRICS ===")
        ga4_metrics = self.calculate_ga4_metrics()
        shopify_metrics = self.calculate_shopify_metrics()
        
        # Step 7: Generate report
        print("\n=== GENERATING REPORT ===")
        report_content = self.generate_report(ga4_metrics, shopify_metrics)
        
        # Step 8: Save report
        filepath = self.save_report(report_content)
        
        print(f"\n🎉 Report generation complete!")
        print(f"📄 Report available at: {filepath}")
        
        # Ask if user wants to open the report
        try:
            open_report = input("\n📖 Open the report now? (y/n): ").strip().lower()
            if open_report in ['y', 'yes']:
                os.system(f"open '{filepath}'")  # macOS
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")

def main():
    """Entry point for the script"""
    try:
        generator = MTDReportGenerator()
        generator.run()
    except KeyboardInterrupt:
        print("\n\n👋 Report generation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 