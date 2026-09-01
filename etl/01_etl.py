"""
Airline/Flight Delay Analytics — Production ETL Pipeline
Transforms raw flight records into a 3NF / Star Schema database:
1. Data Cleaning (handling nulls, standardizing codes, parsing dates)
2. Dimension Table Extraction & Loading (Airlines, Airports, Dates)
3. Surrogate Key Mapping (resolving natural keys to surrogate IDs)
4. Fact Table Bulk Loading (Flights) using SQLAlchemy + fast_executemany
"""

import os
import sys
import argparse
import logging
import datetime
import urllib.parse
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

# Ensure current and parent directory are on sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
for p in [_current_dir, _parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ETL_Pipeline")

def get_db_engine(db_type="auto", server="localhost", database="FlightDelaysDB"):
    """
    Initializes SQLAlchemy database engine.
    Supports MS SQL Server with fast_executemany, with automatic SQLite fallback.
    """
    if db_type in ("sqlserver", "mssql"):
        params = urllib.parse.quote_plus(
            f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
        )
        conn_str = f"mssql+pyodbc:///?odbc_connect={params}"
        logger.info(f"Connecting to MS SQL Server: {server}/{database}")
        return create_engine(conn_str, fast_executemany=True)

    if db_type == "sqlite":
        os.makedirs("data", exist_ok=True)
        db_path = os.path.abspath("data/flights.db")
        logger.info(f"Connecting to SQLite database: {db_path}")
        return create_engine(f"sqlite:///{db_path}")

    # Auto mode: try SQL Server first, fallback to SQLite
    try:
        # Check master connection to ensure DB exists or create it
        master_params = urllib.parse.quote_plus(
            f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE=master;Trusted_Connection=yes;"
        )
        master_engine = create_engine(f"mssql+pyodbc:///?odbc_connect={master_params}", isolation_level="AUTOCOMMIT")
        with master_engine.connect() as conn:
            conn.execute(text(f"IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = '{database}') CREATE DATABASE {database};"))
        
        params = urllib.parse.quote_plus(
            f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
        )
        engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"Successfully connected to local MS SQL Server database '{database}'")
        return engine
    except Exception as e:
        logger.warning(f"Could not connect to MS SQL Server ({e}). Falling back to SQLite for zero-friction portability.")
        os.makedirs("data", exist_ok=True)
        db_path = os.path.abspath("data/flights.db")
        return create_engine(f"sqlite:///{db_path}")

def init_schema(engine):
    """
    Executes DDL schema creation.
    Handles dialect differences (SQL Server IDENTITY vs SQLite AUTOINCREMENT).
    """
    is_sqlite = "sqlite" in engine.dialect.name.lower()
    logger.info(f"Initializing database schema (Dialect: {engine.dialect.name})...")
    
    with engine.begin() as conn:
        if is_sqlite:
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Airlines (
                airline_id INTEGER PRIMARY KEY AUTOINCREMENT,
                airline_code VARCHAR(10) UNIQUE NOT NULL,
                airline_name VARCHAR(100) NOT NULL
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Airports (
                airport_id INTEGER PRIMARY KEY AUTOINCREMENT,
                airport_code VARCHAR(10) UNIQUE NOT NULL,
                airport_name VARCHAR(150) NOT NULL,
                city VARCHAR(100) NOT NULL,
                state VARCHAR(50) NOT NULL,
                latitude DECIMAL(9,6) NOT NULL,
                longitude DECIMAL(9,6) NOT NULL
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Dates (
                date_id INT PRIMARY KEY,
                full_date DATE NOT NULL,
                day_of_week VARCHAR(15) NOT NULL,
                day_num_of_week INT NOT NULL,
                month INT NOT NULL,
                month_name VARCHAR(15) NOT NULL,
                quarter INT NOT NULL,
                year INT NOT NULL,
                is_weekend SMALLINT NOT NULL DEFAULT 0
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Flights (
                flight_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_id INT NOT NULL,
                airline_id INT NOT NULL,
                origin_airport_id INT NOT NULL,
                dest_airport_id INT NOT NULL,
                flight_number VARCHAR(10) NOT NULL,
                tail_number VARCHAR(10),
                scheduled_dep_time SMALLINT NOT NULL,
                actual_dep_time SMALLINT,
                scheduled_arr_time SMALLINT NOT NULL,
                actual_arr_time SMALLINT,
                dep_delay_min INT NOT NULL DEFAULT 0,
                arr_delay_min INT NOT NULL DEFAULT 0,
                cancelled SMALLINT NOT NULL DEFAULT 0,
                cancellation_reason VARCHAR(10),
                diverted SMALLINT NOT NULL DEFAULT 0,
                air_time_min INT,
                distance_miles INT,
                carrier_delay INT NOT NULL DEFAULT 0,
                weather_delay INT NOT NULL DEFAULT 0,
                nas_delay INT NOT NULL DEFAULT 0,
                security_delay INT NOT NULL DEFAULT 0,
                late_aircraft_delay INT NOT NULL DEFAULT 0,
                FOREIGN KEY (date_id) REFERENCES Dates(date_id),
                FOREIGN KEY (airline_id) REFERENCES Airlines(airline_id),
                FOREIGN KEY (origin_airport_id) REFERENCES Airports(airport_id),
                FOREIGN KEY (dest_airport_id) REFERENCES Airports(airport_id)
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ETL_Log (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                rows_inserted INT NOT NULL,
                source_file VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'SUCCESS',
                execution_time_sec DECIMAL(8,2)
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS DQ_Issues (
                issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INT,
                issue_type VARCHAR(100) NOT NULL,
                record_ref VARCHAR(255),
                detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            );
            """))
        else: # SQL Server
            conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='ETL_Log' and xtype='U')
            CREATE TABLE ETL_Log (
                run_id INT PRIMARY KEY IDENTITY(1,1),
                run_timestamp DATETIME NOT NULL DEFAULT GETDATE(),
                rows_inserted INT NOT NULL,
                source_file VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'SUCCESS',
                execution_time_sec DECIMAL(8,2)
            );
            """))
            conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='DQ_Issues' and xtype='U')
            CREATE TABLE DQ_Issues (
                issue_id INT PRIMARY KEY IDENTITY(1,1),
                run_id INT,
                issue_type VARCHAR(100) NOT NULL,
                record_ref VARCHAR(255),
                detected_at DATETIME NOT NULL DEFAULT GETDATE(),
                details VARCHAR(MAX)
            );
            """))
            conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Airlines' and xtype='U')
            CREATE TABLE Airlines (
                airline_id INT PRIMARY KEY IDENTITY(1,1),
                airline_code VARCHAR(10) UNIQUE NOT NULL,
                airline_name VARCHAR(100) NOT NULL
            );
            """))
            conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Airports' and xtype='U')
            CREATE TABLE Airports (
                airport_id INT PRIMARY KEY IDENTITY(1,1),
                airport_code VARCHAR(10) UNIQUE NOT NULL,
                airport_name VARCHAR(150) NOT NULL,
                city VARCHAR(100) NOT NULL,
                state VARCHAR(50) NOT NULL,
                latitude DECIMAL(9,6) NOT NULL,
                longitude DECIMAL(9,6) NOT NULL
            );
            """))
            conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Dates' and xtype='U')
            CREATE TABLE Dates (
                date_id INT PRIMARY KEY,
                full_date DATE NOT NULL,
                day_of_week VARCHAR(15) NOT NULL,
                day_num_of_week INT NOT NULL,
                month INT NOT NULL,
                month_name VARCHAR(15) NOT NULL,
                quarter INT NOT NULL,
                year INT NOT NULL,
                is_weekend BIT NOT NULL DEFAULT 0
            );
            """))
            conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Flights' and xtype='U')
            CREATE TABLE Flights (
                flight_id BIGINT PRIMARY KEY IDENTITY(1,1),
                date_id INT NOT NULL FOREIGN KEY REFERENCES Dates(date_id),
                airline_id INT NOT NULL FOREIGN KEY REFERENCES Airlines(airline_id),
                origin_airport_id INT NOT NULL FOREIGN KEY REFERENCES Airports(airport_id),
                dest_airport_id INT NOT NULL FOREIGN KEY REFERENCES Airports(airport_id),
                flight_number VARCHAR(10) NOT NULL,
                tail_number VARCHAR(10),
                scheduled_dep_time SMALLINT NOT NULL,
                actual_dep_time SMALLINT,
                scheduled_arr_time SMALLINT NOT NULL,
                actual_arr_time SMALLINT,
                dep_delay_min INT NOT NULL DEFAULT 0,
                arr_delay_min INT NOT NULL DEFAULT 0,
                cancelled BIT NOT NULL DEFAULT 0,
                cancellation_reason VARCHAR(10),
                diverted BIT NOT NULL DEFAULT 0,
                air_time_min INT,
                distance_miles INT,
                carrier_delay INT NOT NULL DEFAULT 0,
                weather_delay INT NOT NULL DEFAULT 0,
                nas_delay INT NOT NULL DEFAULT 0,
                security_delay INT NOT NULL DEFAULT 0,
                late_aircraft_delay INT NOT NULL DEFAULT 0
            );
            """))

        # Create indexes
        indexes = [
            "CREATE INDEX idx_flights_date ON Flights(date_id);",
            "CREATE INDEX idx_flights_airline ON Flights(airline_id);",
            "CREATE INDEX idx_flights_origin ON Flights(origin_airport_id);",
            "CREATE INDEX idx_flights_dest ON Flights(dest_airport_id);",
            "CREATE INDEX idx_flights_route ON Flights(origin_airport_id, dest_airport_id);",
            "CREATE INDEX idx_flights_tail ON Flights(tail_number, date_id, scheduled_dep_time);",
        ]
        for idx in indexes:
            try:
                conn.execute(text(idx))
            except Exception:
                pass # Index may already exist

    logger.info("Database schema initialized successfully.")

def clean_and_prepare_raw_data(csv_path):
    """
    Cleans raw flight data:
    - Normalizes column names (supports both Kaggle 2015 and BTS TranStats schemas)
    - Fills missing delay cause numbers with 0
    - Formats dates and times
    """
    logger.info(f"Loading raw flight data from {csv_path}...")
    df = pd.read_csv(csv_path, low_memory=False)
    logger.info(f"Raw records loaded: {len(df):,}")

    # Standardize column mappings
    col_map = {
        # Kaggle 2015 column names
        "YEAR": "year", "MONTH": "month", "DAY": "day",
        "AIRLINE": "airline_code", "ORIGIN_AIRPORT": "origin_code", "DESTINATION_AIRPORT": "dest_code",
        "FLIGHT_NUMBER": "flight_number", "TAIL_NUMBER": "tail_number",
        "SCHEDULED_DEPARTURE": "sched_dep_time", "DEPARTURE_TIME": "actual_dep_time", "DEPARTURE_DELAY": "dep_delay",
        "SCHEDULED_ARRIVAL": "sched_arr_time", "ARRIVAL_TIME": "actual_arr_time", "ARRIVAL_DELAY": "arr_delay",
        "CANCELLED": "cancelled", "CANCELLATION_REASON": "cancellation_reason", "DIVERTED": "diverted",
        "AIR_TIME": "air_time", "DISTANCE": "distance",
        # BTS TranStats column names
        "FL_DATE": "fl_date", "OP_CARRIER": "airline_code", "OP_CARRIER_FL_NUM": "flight_number",
        "TAIL_NUM": "tail_number", "ORIGIN": "origin_code", "DEST": "dest_code",
        "CRS_DEP_TIME": "sched_dep_time", "DEP_TIME": "actual_dep_time", "DEP_DELAY": "dep_delay",
        "CRS_ARR_TIME": "sched_arr_time", "ARR_TIME": "actual_arr_time", "ARR_DELAY": "arr_delay",
        "CANCELLATION_CODE": "cancellation_reason", "CRS_ELAPSED_TIME": "elapsed_time"
    }

    # Normalize columns to uppercase for matching
    df.columns = [c.strip().upper() for c in df.columns]
    for orig, target in col_map.items():
        if orig in df.columns:
            df.rename(columns={orig: target}, inplace=True)

    # Convert fl_date or composite date columns
    if "fl_date" in df.columns:
        df["flight_date"] = pd.to_datetime(df["fl_date"])
    elif all(k in df.columns for k in ["year", "month", "day"]):
        df["flight_date"] = pd.to_datetime(df[["year", "month", "day"]])
    else:
        raise ValueError("Could not determine flight date columns.")

    # Create integer date_id YYYYMMDD
    df["date_id"] = df["flight_date"].dt.strftime("%Y%m%d").astype(int)

    # Handle delay causes: BTS standard fills 0 for unrecorded delays
    delay_cols = ["CARRIER_DELAY", "WEATHER_DELAY", "NAS_DELAY", "SECURITY_DELAY", "LATE_AIRCRAFT_DELAY"]
    for col in delay_cols:
        target_name = col.lower()
        if col in df.columns:
            df[target_name] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        else:
            df[target_name] = 0

    # Handle numeric columns
    df["dep_delay_min"] = pd.to_numeric(df["dep_delay"], errors="coerce").fillna(0).astype(int)
    df["arr_delay_min"] = pd.to_numeric(df["arr_delay"], errors="coerce").fillna(0).astype(int)
    if "cancellation_reason" in df.columns:
        df["cancellation_reason"] = df["cancellation_reason"].fillna("").astype(str)
    else:
        df["cancellation_reason"] = ""

    if "tail_number" in df.columns:
        df["tail_number"] = df["tail_number"].fillna("UNKNOWN").astype(str)
    else:
        df["tail_number"] = "UNKNOWN"

    if "flight_number" in df.columns:
        df["flight_number"] = df["flight_number"].fillna("0").astype(str)
    else:
        df["flight_number"] = "0"
    df["cancelled"] = pd.to_numeric(df["cancelled"], errors="coerce").fillna(0).astype(int) if "cancelled" in df.columns else 0
    df["diverted"] = pd.to_numeric(df["diverted"], errors="coerce").fillna(0).astype(int) if "diverted" in df.columns else 0
    df["sched_dep_time"] = pd.to_numeric(df["sched_dep_time"], errors="coerce").fillna(0).astype(int) if "sched_dep_time" in df.columns else 0
    df["actual_dep_time"] = pd.to_numeric(df["actual_dep_time"], errors="coerce").fillna(0).astype(int) if "actual_dep_time" in df.columns else 0
    df["sched_arr_time"] = pd.to_numeric(df["sched_arr_time"], errors="coerce").fillna(0).astype(int) if "sched_arr_time" in df.columns else 0
    df["actual_arr_time"] = pd.to_numeric(df["actual_arr_time"], errors="coerce").fillna(0).astype(int) if "actual_arr_time" in df.columns else 0
    df["air_time_min"] = pd.to_numeric(df["air_time"], errors="coerce").fillna(0).astype(int) if "air_time" in df.columns else 0
    df["distance_miles"] = pd.to_numeric(df["distance"], errors="coerce").fillna(0).astype(int) if "distance" in df.columns else 0

    logger.info("Raw data cleaned and standardized successfully.")
    return df

def populate_dimensions(df, engine):
    """
    Populates dimension tables (Airlines, Airports, Dates) and returns lookup maps.
    """
    logger.info("Extracting and loading dimension tables...")
    
    # 1. Dates Dimension
    unique_dates = df[["date_id", "flight_date"]].drop_duplicates().sort_values("date_id")
    date_records = []
    for _, row in unique_dates.iterrows():
        dt = row["flight_date"]
        date_records.append({
            "date_id": int(row["date_id"]),
            "full_date": dt.date(),
            "day_of_week": dt.strftime("%A"),
            "day_num_of_week": int(dt.weekday() + 1),
            "month": int(dt.month),
            "month_name": dt.strftime("%B"),
            "quarter": int((dt.month - 1) // 3 + 1),
            "year": int(dt.year),
            "is_weekend": 1 if dt.weekday() >= 5 else 0
        })
    df_dates = pd.DataFrame(date_records)

    # 2. Airlines Dimension
    unique_airline_codes = df["airline_code"].unique()
    # Check if airlines.csv exists for full names
    airline_name_map = {}
    if os.path.exists("data/airlines.csv"):
        ref_airlines = pd.read_csv("data/airlines.csv")
        airline_name_map = dict(zip(ref_airlines["airline_code"], ref_airlines["airline_name"]))
    
    airline_records = []
    for code in unique_airline_codes:
        code_str = str(code).strip()
        name = airline_name_map.get(code_str, f"Airline {code_str}")
        airline_records.append({"airline_code": code_str, "airline_name": name})
    df_airlines = pd.DataFrame(airline_records)

    # 3. Airports Dimension
    unique_airports = set(df["origin_code"].unique()).union(set(df["dest_code"].unique()))
    airport_ref_map = {}
    if os.path.exists("data/airports.csv"):
        ref_airports = pd.read_csv("data/airports.csv")
        for _, r in ref_airports.iterrows():
            airport_ref_map[r["airport_code"]] = r

    airport_records = []
    for code in unique_airports:
        code_str = str(code).strip()
        ref = airport_ref_map.get(code_str)
        if ref is not None:
            airport_records.append({
                "airport_code": code_str,
                "airport_name": ref["airport_name"],
                "city": ref["city"],
                "state": ref["state"],
                "latitude": float(ref["latitude"]),
                "longitude": float(ref["longitude"])
            })
        else:
            airport_records.append({
                "airport_code": code_str,
                "airport_name": f"{code_str} Airport",
                "city": "Unknown City",
                "state": "US",
                "latitude": 39.8283,
                "longitude": -98.5795
            })
    df_airports = pd.DataFrame(airport_records)

    # Write dimensions to DB using append
    logger.info(f"Loading {len(df_dates):,} dates, {len(df_airlines):,} airlines, {len(df_airports):,} airports...")
    
    with engine.begin() as conn:
        # Load Dates
        for _, row in df_dates.iterrows():
            try:
                conn.execute(text("""
                    INSERT INTO Dates (date_id, full_date, day_of_week, day_num_of_week, month, month_name, quarter, year, is_weekend)
                    VALUES (:date_id, :full_date, :day_of_week, :day_num_of_week, :month, :month_name, :quarter, :year, :is_weekend)
                """), row.to_dict())
            except Exception:
                pass # Already present

        # Load Airlines
        for _, row in df_airlines.iterrows():
            try:
                conn.execute(text("""
                    INSERT INTO Airlines (airline_code, airline_name)
                    VALUES (:airline_code, :airline_name)
                """), row.to_dict())
            except Exception:
                pass

        # Load Airports
        for _, row in df_airports.iterrows():
            try:
                conn.execute(text("""
                    INSERT INTO Airports (airport_code, airport_name, city, state, latitude, longitude)
                    VALUES (:airport_code, :airport_name, :city, :state, :latitude, :longitude)
                """), row.to_dict())
            except Exception:
                pass

    # Fetch surrogate keys back to create mapping dictionaries
    with engine.connect() as conn:
        airlines_db = pd.read_sql("SELECT airline_id, airline_code FROM Airlines", conn)
        airline_map = dict(zip(airlines_db["airline_code"], airlines_db["airline_id"]))

        airports_db = pd.read_sql("SELECT airport_id, airport_code FROM Airports", conn)
        airport_map = dict(zip(airports_db["airport_code"], airports_db["airport_id"]))

    logger.info("Dimension tables loaded and surrogate key lookups created.")
    return airline_map, airport_map

def load_fact_flights(df, engine, airline_map, airport_map, chunksize=5000):
    """
    Maps surrogate keys and bulk loads records into the Flights fact table.
    """
    logger.info("Mapping dimension surrogate keys to fact table...")
    df["airline_id"] = df["airline_code"].map(airline_map)
    df["origin_airport_id"] = df["origin_code"].map(airport_map)
    df["dest_airport_id"] = df["dest_code"].map(airport_map)

    # Drop any records where foreign key couldn't be resolved
    initial_len = len(df)
    df_clean = df.dropna(subset=["airline_id", "origin_airport_id", "dest_airport_id"]).copy()
    if len(df_clean) < initial_len:
        logger.warning(f"Filtered out {initial_len - len(df_clean)} records with unmapped dimension keys.")

    fact_cols = [
        "date_id", "airline_id", "origin_airport_id", "dest_airport_id",
        "flight_number", "tail_number",
        "sched_dep_time", "actual_dep_time", "sched_arr_time", "actual_arr_time",
        "dep_delay_min", "arr_delay_min", "cancelled", "cancellation_reason", "diverted",
        "air_time_min", "distance_miles",
        "carrier_delay", "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay"
    ]

    # Rename to exact DB column names
    rename_dict = {
        "sched_dep_time": "scheduled_dep_time",
        "actual_dep_time": "actual_dep_time",
        "sched_arr_time": "scheduled_arr_time",
        "actual_arr_time": "actual_arr_time"
    }
    df_fact = df_clean[fact_cols].rename(columns=rename_dict)

    # Cast integer columns properly
    int_cols = [
        "date_id", "airline_id", "origin_airport_id", "dest_airport_id",
        "scheduled_dep_time", "actual_dep_time", "scheduled_arr_time", "actual_arr_time",
        "dep_delay_min", "arr_delay_min", "cancelled", "diverted", "air_time_min", "distance_miles",
        "carrier_delay", "weather_delay", "nas_delay", "security_delay", "late_aircraft_delay"
    ]
    for c in int_cols:
        df_fact[c] = df_fact[c].fillna(0).astype(int)

    logger.info(f"Bulk-inserting {len(df_fact):,} fact records into 'Flights' table...")
    
    # Bulk insertion using pandas to_sql with chunking
    df_fact.to_sql("Flights", engine, if_exists="append", index=False, chunksize=chunksize)
    
    # Verify count
    with engine.connect() as conn:
        res = conn.execute(text("SELECT COUNT(*) FROM Flights")).scalar()
        logger.info(f"ETL completed successfully! Total rows in Flights fact table: {res:,}")

def run_pipeline(csv_path="data/raw_flights.csv", db_type="auto"):
    """
    Executes end-to-end ETL pipeline with automated Data Quality checks and ETL_Log auditing.
    """
    import time
    t_start = time.time()

    # Auto-generate sample data if raw_flights.csv doesn't exist yet
    if not os.path.exists(csv_path):
        logger.info(f"Raw data file {csv_path} not found. Synthesizing realistic BTS dataset first...")
        from download_data import generate_realistic_bts_dataset
        generate_realistic_bts_dataset(output_dir="data", num_days=60, flights_per_day=450)

    engine = get_db_engine(db_type=db_type)
    init_schema(engine)

    # 1. Initialize audit record in ETL_Log
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

    # 2. Clean and validate raw data
    df_cleaned = clean_and_prepare_raw_data(csv_path)
    
    try:
        from etl.validate import validate_flight_data
        issues = validate_flight_data(df_cleaned, engine=engine, run_id=run_id)
        logger.info(f"Data validation completed ({len(issues)} warnings logged).")
    except Exception as e:
        logger.warning(f"Validation step notice: {e}")

    # 3. Populate dimensions and fact table
    airline_map, airport_map = populate_dimensions(df_cleaned, engine)
    load_fact_flights(df_cleaned, engine, airline_map, airport_map)

    # 4. Finalize ETL_Log audit entry
    elapsed = round(time.time() - t_start, 2)
    with engine.begin() as conn:
        try:
            conn.execute(text("""
                UPDATE ETL_Log
                SET rows_inserted = :rows, status = 'SUCCESS', execution_time_sec = :elapsed, run_timestamp = CURRENT_TIMESTAMP
                WHERE run_id = :run_id
            """), {"rows": len(df_cleaned), "elapsed": elapsed, "run_id": run_id})
        except Exception as e:
            logger.warning(f"Could not finalize ETL_Log: {e}")

    logger.info(f"Pipeline executed successfully in {elapsed}s (Run ID: {run_id}).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Airline Delay Analytics ETL Pipeline")
    parser.add_argument("--csv", default="data/raw_flights.csv", help="Path to raw CSV dataset")
    parser.add_argument("--db", choices=["auto", "sqlserver", "sqlite"], default="auto", help="Database backend")
    args = parser.parse_args()

    run_pipeline(csv_path=args.csv, db_type=args.db)

