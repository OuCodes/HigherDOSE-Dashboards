import argparse
from pathlib import Path

import duckdb
import pandas as pd

DEFAULT_DB = Path("brain/insights.duckdb")


def run_query(db_path: Path, sql: str, limit: int | None = None):
    con = duckdb.connect(str(db_path))
    if limit is not None:
        sql = f"{sql.strip().rstrip(';')} LIMIT {limit};"
    df = con.execute(sql).fetch_df()
    con.close()
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SQL against insights.duckdb and show results.")
    parser.add_argument("sql", help="SQL query to execute. Use quotes.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to DuckDB database (default: brain/insights.duckdb)")
    parser.add_argument("--limit", type=int, default=20, help="Limit rows displayed (None for all)")

    args = parser.parse_args()

    df = run_query(args.db, args.sql, args.limit)
    if df.empty:
        print("No rows returned.")
    else:
        with pd.option_context("display.max_rows", None, "display.max_columns", None):
            print(df) 