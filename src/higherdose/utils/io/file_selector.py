#!/usr/bin/env python3
"""
File Selection Utility
Interactive file selection from specified directories
"""

import os
import sys
import glob

# Add parent directory to path for utils imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from higherdose.utils.style import ansi



def select_csv_file(directory="data/raw/stats", file_pattern="*.csv", prompt_message=None, max_items: int | None = None):
    """
    Interactive CSV file selection from a directory.
    
    Args:
        directory: Directory to search for files (default: "stats")
        file_pattern: Glob pattern for file matching (default: "*.csv")
        prompt_message: Custom prompt message (optional)
    
    Returns:
        str: Selected file path, or None if no selection made
    """
    # Ensure directory exists
    if not os.path.exists(directory):
        print(f"{ansi.red}Error:{ansi.reset} Directory '{directory}' does not exist")
        return None
    
    # Find all matching files
    search_pattern = os.path.join(directory, file_pattern)
    files = glob.glob(search_pattern)
    
    if not files:
        print(f"{ansi.yellow}No files found{ansi.reset} matching pattern '{file_pattern}' in '{directory}'")
        return None
    
    # Sort files by modification time (newest first)
    files.sort(key=os.path.getmtime, reverse=True)

    # Limit to most recent N files if requested
    if max_items is not None:
        files = files[:max_items]
    
    # Display options
    print(f"\n{ansi.cyan}Available files in {directory}:{ansi.reset}")
    print("-" * 50)
    
    for i, file_path in enumerate(files, 1):
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        size_mb = file_size / (1024 * 1024)
        
        # Get basic file info
        mtime = os.path.getmtime(file_path)
        from datetime import datetime
        mod_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
        
        print(f"{ansi.green}{i:2}.{ansi.reset} {filename}")
        print(f"     {ansi.grey}Size: {size_mb:.1f} MB | Modified: {mod_date}{ansi.reset}")
    
    # Get user selection
    if prompt_message:
        prompt = prompt_message
    else:
        prompt = f"\n{ansi.yellow}Select a file{ansi.reset} (1-{len(files)}, or 'q' to quit): "
    
    while True:
        try:
            choice = input(prompt).strip().lower()
            
            if choice == 'q' or choice == 'quit':
                print(f"{ansi.yellow}Selection cancelled{ansi.reset}")
                return None
            
            file_index = int(choice) - 1
            
            if 0 <= file_index < len(files):
                selected_file = files[file_index]
                filename = os.path.basename(selected_file)
                print(f"\n{ansi.green}Selected:{ansi.reset} {filename}")
                return selected_file
            else:
                print(f"{ansi.red}Invalid selection.{ansi.reset} Please choose 1-{len(files)} or 'q' to quit.")
                
        except ValueError:
            print(f"{ansi.red}Invalid input.{ansi.reset} Please enter a number 1-{len(files)} or 'q' to quit.")
        except KeyboardInterrupt:
            print(f"\n{ansi.yellow}Selection cancelled{ansi.reset}")
            return None


def select_data_file_for_report(report_type="weekly"):
    """
    Specialized function for selecting data files for reports.
    
    Args:
        report_type: "weekly" or "monthly" to filter appropriate files
    
    Returns:
        str: Selected file path, or None if no selection made
    """
    if report_type.lower() == "weekly":
        pattern = "*7d*sales_data*.csv"
        message = f"\n{ansi.cyan}Select 7-day sales data file for weekly report:{ansi.reset} "
    elif report_type.lower() == "monthly":
        pattern = "*30D*sales_data*.csv"
        message = f"\n{ansi.cyan}Select 30-day sales data file for monthly report:{ansi.reset} "
    else:
        pattern = "*sales_data*.csv"
        message = f"\n{ansi.cyan}Select sales data file for {report_type} report:{ansi.reset} "
    
    return select_csv_file(
        directory="data/raw/stats",
        file_pattern=pattern,
        prompt_message=message
    )


if __name__ == "__main__":
    # Test the file selection
    print("Testing file selection utility...")
    selected = select_csv_file()
    if selected:
        print(f"You selected: {selected}")
    else:
        print("No file selected")