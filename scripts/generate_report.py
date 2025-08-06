#!/usr/bin/env python3
"""
Simple Report Generator

Quick command-line interface for generating reports.

Usage:
    python scripts/generate_report.py
    python scripts/generate_report.py --template mtd_performance
    python scripts/generate_report.py --start 2025-07-01 --end 2025-07-27
"""

import argparse
import sys
from pathlib import Path

# Add the scripts directory to the path so we can import other modules
sys.path.insert(0, str(Path(__file__).parent))

try:
    from scripts.report_executive import MTDReportGenerator  # new preferred name
except ImportError:
    from report_mtd_automated import MTDReportGenerator  # fallback for compatibility
from report_config import list_available_templates, get_report_template

def main():
    parser = argparse.ArgumentParser(description='Generate HigherDOSE performance reports')
    
    parser.add_argument('--template', 
                       choices=list_available_templates(),
                       help='Report template to use')
    
    parser.add_argument('--start', 
                       help='Start date (YYYY-MM-DD)')
    
    parser.add_argument('--end', 
                       help='End date (YYYY-MM-DD)')
    
    parser.add_argument('--auto', 
                       action='store_true',
                       help='Auto-select the most recent files for each data type')
    
    parser.add_argument('--list-templates', 
                       action='store_true',
                       help='List available report templates')
    
    args = parser.parse_args()
    
    if args.list_templates:
        print("Available Report Templates:")
        print("=" * 30)
        for template_name in list_available_templates():
            template = get_report_template(template_name)
            print(f"• {template_name}: {template.description}")
        return
    
    # Create and run the generator
    generator = MTDReportGenerator()
    
    # Override date range if provided
    if args.start and args.end:
        try:
            from datetime import datetime
            start_dt = datetime.strptime(args.start, "%Y-%m-%d")
            end_dt = datetime.strptime(args.end, "%Y-%m-%d")
            
            generator.date_range = {
                'start': args.start,
                'end': args.end,
                'start_dt': start_dt,
                'end_dt': end_dt
            }
            
            print(f"✅ Using provided date range: {args.start} to {args.end}")
        except ValueError:
            print("❌ Invalid date format. Please use YYYY-MM-DD")
            return
    
    # Run the generator
    if args.start and args.end:
        # Skip date prompting if dates were provided
        available_files = generator.find_available_files()
        
        if args.auto:
            # Auto-select files
            selected_files = {}
            for file_type, files in available_files.items():
                if files:
                    # Select the most recent file (assuming naming convention includes dates)
                    selected_files[file_type] = sorted(files)[-1]
                    print(f"✅ Auto-selected for {file_type}: {Path(files[-1]).name}")
        else:
            selected_files = generator.select_files(available_files)
        
        if selected_files:
            generator.load_data(selected_files)
            
            print("\n=== CALCULATING METRICS ===")
            ga4_metrics = generator.calculate_ga4_metrics()
            shopify_metrics = generator.calculate_shopify_metrics()
            
            print("\n=== GENERATING REPORT ===")
            report_content = generator.generate_report(ga4_metrics, shopify_metrics)
            
            filepath = generator.save_report(report_content)
            print(f"\n🎉 Report generation complete!")
            print(f"📄 Report available at: {filepath}")
        else:
            print("❌ No files selected. Exiting.")
    else:
        # Run interactive mode
        generator.run()

if __name__ == "__main__":
    main() 