#!/usr/bin/env python3
"""Run the Q4 2025 Sales Goals report."""
from growthkit.reports import sales_goals

if __name__ == "__main__":
	csv_path, md_path = sales_goals.main()
	print(str(csv_path))
	print(str(md_path)) 