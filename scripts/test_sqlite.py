from sqlalchemy import create_engine, text
import pandas as pd

eng = create_engine("sqlite:///data/flights.db")
with eng.connect() as conn:
    print("Testing SQLite connection...")
    df = pd.read_sql(text("SELECT COUNT(*) AS total FROM Flights"), conn)
    print("Total flights in SQLite:", df.iloc[0]['total'])

    # Test KPI query on SQLite
    kpi_sql = """
    SELECT 
        COUNT(f.flight_id) AS total_flights,
        SUM(CASE WHEN f.dep_delay_min <= 15 AND CAST(f.cancelled AS INT) = 0 THEN 1 ELSE 0 END) AS on_time_departures,
        SUM(CASE WHEN f.arr_delay_min <= 15 AND CAST(f.cancelled AS INT) = 0 THEN 1 ELSE 0 END) AS on_time_arrivals,
        SUM(CAST(f.cancelled AS INT)) AS total_cancelled,
        AVG(CASE WHEN CAST(f.cancelled AS INT) = 0 THEN CAST(f.arr_delay_min AS FLOAT) END) AS avg_arr_delay
    FROM Flights f
    JOIN Airlines a ON f.airline_id = a.airline_id
    JOIN Airports orig ON f.origin_airport_id = orig.airport_id
    JOIN Airports dest ON f.dest_airport_id = dest.airport_id
    JOIN Dates d ON f.date_id = d.date_id
    """
    df_kpi = pd.read_sql(text(kpi_sql), conn)
    print("KPI query on SQLite:", df_kpi.to_dict(orient='records'))
