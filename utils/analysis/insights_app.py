import duckdb
import pandas as pd
import streamlit as st
from pathlib import Path

DB_PATH = Path("brain/insights.duckdb")
TABLE = "events"

st.set_page_config(page_title="Timeline Explorer", layout="wide")

st.title("HigherDOSE Unified Timeline Explorer")

if not DB_PATH.exists():
    st.error(f"Database not found at {DB_PATH}. Run build_duckdb.py first.")
    st.stop()

# Sidebar filters
st.sidebar.header("Filters")

con = duckdb.connect(str(DB_PATH))
min_ts, max_ts = con.execute(f"SELECT MIN(timestamp), MAX(timestamp) FROM {TABLE}").fetchone()
con.close()

start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(pd.to_datetime(max_ts) - pd.Timedelta(days=7)).date(),
    min_value=pd.to_datetime(min_ts).date(),
    max_value=pd.to_datetime(max_ts).date(),
    format="YYYY-MM-DD",
    )

actor_filter = st.sidebar.text_input("Actor contains (comma-separated)")
keyword_filter = st.sidebar.text_input("Content keywords (space-separated)")
max_rows = st.sidebar.number_input("Max rows", 100, 10000, 1000, 100)

if st.sidebar.button("Run Query"):
    sql_parts = [f"SELECT * FROM {TABLE} WHERE DATE(timestamp) BETWEEN '{start_date}' AND '{end_date}'"]

    if actor_filter.strip():
        actor_conds = [f"actor ILIKE '%{a.strip()}%'" for a in actor_filter.split(",") if a.strip()]
        if actor_conds:
            sql_parts.append("AND (" + " OR ".join(actor_conds) + ")")

    if keyword_filter.strip():
        kw_conds = [f"content ILIKE '%{kw.strip()}%'" for kw in keyword_filter.split() if kw.strip()]
        if kw_conds:
            sql_parts.append("AND (" + " OR ".join(kw_conds) + ")")

    sql_parts.append(f"ORDER BY timestamp LIMIT {int(max_rows)}")
    sql = "\n".join(sql_parts)

    st.code(sql, language="sql")

    con = duckdb.connect(str(DB_PATH))
    df = con.execute(sql).fetch_df()
    con.close()

    st.write(f"Returned {len(df)} rows.")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, file_name="query_results.csv", mime="text/csv")

else:
    st.info("Set filters in the sidebar and press 'Run Query'.") 