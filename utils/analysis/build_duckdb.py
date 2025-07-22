import argparse
from pathlib import Path

import duckdb
import pandas as pd


def build_duckdb(csv_path: Path, db_path: Path, table: str = "events"):
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    print(f"Loading {csv_path} …")
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])

    # Ensure destination dir exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing DuckDB database → {db_path} …")
    con = duckdb.connect(str(db_path))

    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM df")
    con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_content ON {table}(content)")
    con.execute("PRAGMA optimize;")
    con.close()

    print("Done. You can now query with duckdb CLI or Python.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert timeline CSV to DuckDB database.")
    parser.add_argument("csv", type=Path, nargs="?", default=Path("brain/timeline.csv"), help="Path to timeline CSV (default: brain/timeline.csv)")
    parser.add_argument("--db", type=Path, default=Path("brain/insights.duckdb"), help="Output DuckDB database file (default: brain/insights.duckdb)")
    args = parser.parse_args()

    build_duckdb(args.csv, args.db) 