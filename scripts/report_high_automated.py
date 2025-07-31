#!/usr/bin/env python3
"""
HigherDOSE Automated High-Level Report Generator (wrapper)

This script is an alias for `report_mtd_automated.py`.
Running this script will execute the same reporting workflow.
"""

from report_mtd_automated import MTDReportGenerator


def main() -> None:
    generator = MTDReportGenerator()
    generator.run()


if __name__ == "__main__":
    main() 