-- ============================================================================
-- AeroPulse: Airline/Flight Delay Analytics — Database Schema (Star Schema / 3NF)
-- Designed for Microsoft SQL Server / Azure SQL / SQLite compatibility
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Dimension Tables
-- ----------------------------------------------------------------------------

-- Dimension: Airlines
CREATE TABLE IF NOT EXISTS Airlines (
    airline_id INTEGER PRIMARY KEY AUTOINCREMENT,
    airline_code VARCHAR(10) UNIQUE NOT NULL,
    airline_name VARCHAR(100) NOT NULL
);

-- Dimension: Airports
CREATE TABLE IF NOT EXISTS Airports (
    airport_id INTEGER PRIMARY KEY AUTOINCREMENT,
    airport_code VARCHAR(10) UNIQUE NOT NULL,
    airport_name VARCHAR(150) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(50) NOT NULL,
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL
);

-- Dimension: Dates
CREATE TABLE IF NOT EXISTS Dates (
    date_id INT PRIMARY KEY, -- Format: YYYYMMDD
    full_date DATE NOT NULL,
    day_of_week VARCHAR(15) NOT NULL,
    day_num_of_week INT NOT NULL, -- 1=Monday, 7=Sunday
    month INT NOT NULL,
    month_name VARCHAR(15) NOT NULL,
    quarter INT NOT NULL,
    year INT NOT NULL,
    is_weekend SMALLINT NOT NULL DEFAULT 0 -- 0=Weekday, 1=Weekend
);

-- ----------------------------------------------------------------------------
-- 2. Fact Table: Flights
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Flights (
    flight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_id INT NOT NULL,
    airline_id INT NOT NULL,
    origin_airport_id INT NOT NULL,
    dest_airport_id INT NOT NULL,
    flight_number VARCHAR(10) NOT NULL,
    tail_number VARCHAR(10),
    scheduled_dep_time SMALLINT NOT NULL, -- HHMM format (e.g. 0830)
    actual_dep_time SMALLINT,             -- HHMM format (e.g. 0845)
    scheduled_arr_time SMALLINT NOT NULL, -- HHMM format (e.g. 1115)
    actual_arr_time SMALLINT,             -- HHMM format (e.g. 1140)
    dep_delay_min INT NOT NULL DEFAULT 0, -- Departure delay in minutes
    arr_delay_min INT NOT NULL DEFAULT 0, -- Arrival delay in minutes
    cancelled SMALLINT NOT NULL DEFAULT 0, -- 1 = cancelled
    cancellation_reason VARCHAR(10),       -- A=Carrier, B=Weather, C=NAS, D=Security
    diverted SMALLINT NOT NULL DEFAULT 0,  -- 1 = diverted
    air_time_min INT,                      -- Airborne time in minutes
    distance_miles INT,                    -- Flight distance
    carrier_delay INT NOT NULL DEFAULT 0,  -- Delay attributable to carrier (minutes)
    weather_delay INT NOT NULL DEFAULT 0,  -- Delay attributable to weather (minutes)
    nas_delay INT NOT NULL DEFAULT 0,      -- Delay attributable to National Aviation System
    security_delay INT NOT NULL DEFAULT 0, -- Delay attributable to security
    late_aircraft_delay INT NOT NULL DEFAULT 0, -- Delay attributable to late arrival of previous aircraft
    FOREIGN KEY (date_id) REFERENCES Dates(date_id),
    FOREIGN KEY (airline_id) REFERENCES Airlines(airline_id),
    FOREIGN KEY (origin_airport_id) REFERENCES Airports(airport_id),
    FOREIGN KEY (dest_airport_id) REFERENCES Airports(airport_id)
);

-- ----------------------------------------------------------------------------
-- 3. Audit & Governance Tables (Data Pipeline Integrity)
-- ----------------------------------------------------------------------------

-- Audit: ETL Execution Log
CREATE TABLE IF NOT EXISTS ETL_Log (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rows_inserted INT NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'SUCCESS',
    execution_time_sec DECIMAL(8,2)
);

-- Audit: Data Quality & Anomaly Tracking
CREATE TABLE IF NOT EXISTS DQ_Issues (
    issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INT,
    issue_type VARCHAR(100) NOT NULL,
    record_ref VARCHAR(255),
    detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    FOREIGN KEY (run_id) REFERENCES ETL_Log(run_id)
);

-- ----------------------------------------------------------------------------
-- 4. Performance Indexes for Analytics Query Optimization
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_flights_date ON Flights(date_id);
CREATE INDEX IF NOT EXISTS idx_flights_airline ON Flights(airline_id);
CREATE INDEX IF NOT EXISTS idx_flights_origin ON Flights(origin_airport_id);
CREATE INDEX IF NOT EXISTS idx_flights_dest ON Flights(dest_airport_id);
CREATE INDEX IF NOT EXISTS idx_flights_route ON Flights(origin_airport_id, dest_airport_id);
CREATE INDEX IF NOT EXISTS idx_flights_tail ON Flights(tail_number, date_id, scheduled_dep_time);
CREATE INDEX IF NOT EXISTS idx_flights_delays ON Flights(dep_delay_min, arr_delay_min);
