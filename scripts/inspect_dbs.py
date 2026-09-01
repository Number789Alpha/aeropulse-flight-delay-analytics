import sqlite3
import pandas as pd
from sqlalchemy import create_engine, text
import urllib.parse

# 1. Check SQLite
print("=== SQLITE INSPECTION ===")
conn = sqlite3.connect("data/flights.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cur.fetchall()]
print("SQLite Tables:", tables)
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"  {t}: {cur.fetchone()[0]:,} rows")
conn.close()

# 2. Check SQL Server
print("\n=== SQL SERVER INSPECTION ===")
try:
    params = urllib.parse.quote_plus(
        "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=FlightDelaysDB;Trusted_Connection=yes;"
    )
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")
    with engine.connect() as s_conn:
        dq_rows = pd.read_sql(text("SELECT COUNT(*) AS c FROM DQ_Issues"), s_conn).iloc[0]['c']
        etl_rows = pd.read_sql(text("SELECT COUNT(*) AS c FROM ETL_Log"), s_conn).iloc[0]['c']
        flight_rows = pd.read_sql(text("SELECT COUNT(*) AS c FROM Flights"), s_conn).iloc[0]['c']
        print(f"  Flights: {flight_rows:,} rows")
        print(f"  DQ_Issues: {dq_rows:,} rows")
        print(f"  ETL_Log: {etl_rows:,} rows")
        
        print("\nRecent ETL_Log entries:")
        etl_df = pd.read_sql(text("SELECT TOP 5 run_id, run_timestamp, rows_inserted, status, execution_time_sec, source_file FROM ETL_Log ORDER BY run_id DESC"), s_conn)
        print(etl_df)

        print("\nRecent DQ_Issues entries:")
        dq_df = pd.read_sql(text("SELECT TOP 5 issue_id, issue_type, record_ref, details, detected_at FROM DQ_Issues ORDER BY issue_id DESC"), s_conn)
        print(dq_df)
except Exception as e:
    print("SQL Server inspection error:", e)
