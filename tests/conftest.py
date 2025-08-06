import pandas as pd
import pytest
from pathlib import Path

@pytest.fixture()
def sample_csvs(tmp_path: Path):
    """Create minimal CSVs with the required columns for GA4 & Shopify sources."""
    data_dir = tmp_path / "ads"
    data_dir.mkdir(parents=True)

    # GA4 channel group
    (data_dir / "daily-ga4-default_channel_group-2025.csv").write_text(
        "Date,Default channel group,Sessions,Total revenue\n"
        "2025-08-01,Paid Search,10,100\n"
    )

    # GA4 source medium
    (data_dir / "daily-ga4-source_medium-2025.csv").write_text(
        "Date,Session source / medium,Sessions,Total revenue\n"
        "2025-08-01,google / cpc,10,100\n"
    )

    # Shopify new vs returning
    (data_dir / "New vs returning customer sales - 2025-08.csv").write_text(
        "Month,New or returning customer,Total sales,Orders\n"
        "2025-08,New,100,2\n"
        "2025-08,Returning,50,1\n"
    )

    # Shopify products
    (data_dir / "Total sales by product - 2025-08.csv").write_text(
        "Day,Product title,Total sales,Net items sold\n"
        "2025-08-01,Test Product,150,3\n"
    )

    return data_dir
