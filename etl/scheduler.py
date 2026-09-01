"""
AeroPulse: Airline & Flight Delay Analytics — ETL Batch Scheduler
Simulates periodic (e.g. monthly or daily) BTS flight data ingestion refreshes.
Logs each execution run into ETL_Log.
"""

import os
import sys
import time
import argparse
import datetime
import schedule
import logging
from sqlalchemy import text

# Ensure current and parent directory are on sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
for p in [_current_dir, _parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Scheduler] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ETL_Scheduler")

def trigger_scheduled_refresh(csv_path="data/raw_flights.csv", db_type="auto"):
    """
    Executes a scheduled refresh cycle:
    1. Runs Data Quality checks
    2. Ingests records into Star Schema
    3. Records entry in ETL_Log
    """
    t_start = time.time()
    logger.info("Executing scheduled BTS data refresh...")

    from etl.etl_pipeline import get_db_engine, init_schema, clean_and_prepare_raw_data, populate_dimensions, load_fact_flights
    from etl.validate import validate_flight_data

    engine = get_db_engine(db_type=db_type)
    init_schema(engine)

    if not os.path.exists(csv_path):
        from etl.download_data import generate_realistic_bts_dataset
        generate_realistic_bts_dataset(output_dir="data", num_days=15, flights_per_day=300)

    # 1. Create run log entry
    run_id = None
    with engine.begin() as conn:
        try:
            if "sqlite" in engine.dialect.name.lower():
                res = conn.execute(text("""
                    INSERT INTO ETL_Log (source_file, rows_inserted, status)
                    VALUES (:source_file, 0, 'RUNNING')
                """), {"source_file": csv_path})
                run_id = res.lastrowid
            else:
                res = conn.execute(text("""
                    INSERT INTO ETL_Log (source_file, rows_inserted, status)
                    OUTPUT INSERTED.run_id
                    VALUES (:source_file, 0, 'RUNNING')
                """), {"source_file": csv_path})
                run_id = res.scalar()
        except Exception as e:
            logger.warning(f"Could not initialize ETL_Log: {e}")

    # 2. Clean & Validate
    df_cleaned = clean_and_prepare_raw_data(csv_path)
    issues = validate_flight_data(df_cleaned, engine=engine, run_id=run_id)

    # 3. Populate
    airline_map, airport_map = populate_dimensions(df_cleaned, engine)
    load_fact_flights(df_cleaned, engine, airline_map, airport_map)

    # 4. Finalize run log
    elapsed = round(time.time() - t_start, 2)
    with engine.begin() as conn:
        try:
            conn.execute(text("""
                UPDATE ETL_Log 
                SET rows_inserted = :rows, status = 'SUCCESS', execution_time_sec = :elapsed, run_timestamp = CURRENT_TIMESTAMP
                WHERE run_id = :run_id
            """), {"rows": len(df_cleaned), "elapsed": elapsed, "run_id": run_id})
        except Exception as e:
            logger.warning(f"Could not update ETL_Log: {e}")

    logger.info(f"Scheduled refresh completed successfully in {elapsed}s. {len(df_cleaned):,} rows loaded.")

def run_scheduler(interval_seconds=60, runs=1):
    """
    Runs the scheduler for specified iterations or continuously.
    """
    logger.info(f"Scheduler started. Running every {interval_seconds} seconds (Target iterations: {runs}).")
    completed = 0
    
    # Run once immediately
    trigger_scheduled_refresh()
    completed += 1

    if runs > 1:
        schedule.every(interval_seconds).seconds.do(trigger_scheduled_refresh)
        while completed < runs:
            schedule.run_pending()
            time.sleep(1)
            completed += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate periodic BTS ETL refreshes")
    parser.add_argument("--interval", type=int, default=30, help="Interval in seconds")
    parser.add_argument("--runs", type=int, default=1, help="Number of iterations to execute")
    args = parser.parse_args()

    run_scheduler(interval_seconds=args.interval, runs=args.runs)
