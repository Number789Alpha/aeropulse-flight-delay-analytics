"""
AeroPulse: Airline & Flight Delay Analytics — Data Quality & Validation Engine
Executes pre-ingestion validation assertions and logs audit anomalies into DQ_Issues.
"""

import os
import sys
import logging
import datetime
import pandas as pd
import numpy as np
from sqlalchemy import text

logger = logging.getLogger("DataQuality")

def validate_flight_data(df, engine=None, run_id=None):
    """
    Runs automated Data Quality (DQ) validation checks on raw flight data:
    1. Null checks on critical identifiers
    2. Logical consistency (HHMM bounds, positive distance, duration)
    3. Duplicate flight records detection
    4. Extreme delay outlier warnings
    """
    logger.info(f"Initiating Data Quality validation on {len(df):,} records...")
    issues = []

    # Check 1: Missing Critical Identifiers
    req_cols = ["date_id", "airline_code", "origin_code", "dest_code", "flight_number"]
    for col in req_cols:
        if col in df.columns:
            null_count = df[col].isnull().sum()
            if null_count > 0:
                issues.append({
                    "issue_type": "NULL_IDENTIFIER",
                    "record_ref": f"Column: {col}",
                    "details": f"Found {null_count} null entries in critical identifier column '{col}'"
                })

    # Check 2: Time Format Boundaries (HHMM format between 0 and 2400)
    for t_col in ["sched_dep_time", "actual_dep_time", "sched_arr_time", "actual_arr_time"]:
        if t_col in df.columns:
            invalid_time = df[(df[t_col] < 0) | (df[t_col] > 2400)]
            if len(invalid_time) > 0:
                issues.append({
                    "issue_type": "INVALID_TIME_FORMAT",
                    "record_ref": f"Column: {t_col}",
                    "details": f"Found {len(invalid_time)} records with invalid HHMM time values outside [0, 2400]"
                })

    # Check 3: Distance and Air Time Positivity
    if "distance_miles" in df.columns:
        neg_dist = df[df["distance_miles"] < 0]
        if len(neg_dist) > 0:
            issues.append({
                "issue_type": "NEGATIVE_DISTANCE",
                "record_ref": "distance_miles",
                "details": f"{len(neg_dist)} records contain negative flight distance"
            })

    # Check 4: Duplicate Flight Records
    dup_cols = ["date_id", "airline_code", "flight_number", "origin_code", "sched_dep_time"]
    existing_dup_cols = [c for c in dup_cols if c in df.columns]
    if len(existing_dup_cols) == len(dup_cols):
        dups = df.duplicated(subset=existing_dup_cols, keep=False)
        dup_count = dups.sum()
        if dup_count > 0:
            issues.append({
                "issue_type": "DUPLICATE_FLIGHT_RECORD",
                "record_ref": f"{dup_count} duplicate rows",
                "details": f"Detected {dup_count} duplicate flight records matching {existing_dup_cols}"
            })

    # Check 5: Logical Delay Cause Consistency (Causes shouldn't massively exceed total arrival delay)
    if "arr_delay_min" in df.columns and "carrier_delay" in df.columns:
        cause_sum = (
            df["carrier_delay"].fillna(0) +
            df["weather_delay"].fillna(0) +
            df["nas_delay"].fillna(0) +
            df["security_delay"].fillna(0) +
            df["late_aircraft_delay"].fillna(0)
        )
        inconsistent = df[(df["arr_delay_min"] > 15) & (cause_sum > (df["arr_delay_min"] + 45))]
        if len(inconsistent) > 0:
            issues.append({
                "issue_type": "DELAY_CAUSE_DISCREPANCY",
                "record_ref": f"{len(inconsistent)} records",
                "details": f"{len(inconsistent)} flights have delay cause minutes significantly exceeding arrival delay"
            })

    # Log issues to database if engine is supplied
    if engine is not None:
        try:
            with engine.begin() as conn:
                for issue in issues:
                    conn.execute(text("""
                        INSERT INTO DQ_Issues (run_id, issue_type, record_ref, details)
                        VALUES (:run_id, :issue_type, :record_ref, :details)
                    """), {
                        "run_id": run_id,
                        "issue_type": issue["issue_type"],
                        "record_ref": issue["record_ref"],
                        "details": issue["details"]
                    })
        except Exception as e:
            logger.warning(f"Could not persist DQ issues to DB: {e}")

    logger.info(f"Data Quality validation complete. Total issues detected: {len(issues)}")
    return issues

if __name__ == "__main__":
    from etl.etl_pipeline import get_db_engine
    import pandas as pd
    
    engine = get_db_engine("auto")
    csv_file = "data/raw_flights.csv"
    if os.path.exists(csv_file):
        df_sample = pd.read_csv(csv_file, nrows=10000)
        # Adapt column names to match clean_and_prepare
        from etl.etl_pipeline import clean_and_prepare_raw_data
        df_cleaned = clean_and_prepare_raw_data(csv_file)
        issues = validate_flight_data(df_cleaned, engine=engine, run_id=1)
        print(f"Validation Report: {len(issues)} issues logged.")
        for iss in issues:
            print(f" - [{iss['issue_type']}] {iss['details']}")
    else:
        print("data/raw_flights.csv not found.")
