-- ============================================================================
-- AeroPulse: Airline/Flight Delay Analytics — Advanced Analytical SQL Queries
-- Showcase: Window Functions, CTEs, LAG/LEAD, Rolling Averages, and Rankings
-- ============================================================================

-- ----------------------------------------------------------------------------
-- QUERY 1: Inbound-to-Outbound Delay Propagation (LAG / LEAD)
-- Interview Story: "Does an incoming aircraft's arrival delay propagate into 
-- the next flight's departure delay on the same aircraft tail number?"
-- ----------------------------------------------------------------------------
WITH AircraftTurnaround AS (
    SELECT 
        f.flight_id,
        f.tail_number,
        a.airline_code,
        orig.airport_code AS departure_airport,
        dest.airport_code AS arrival_airport,
        f.date_id,
        f.scheduled_dep_time,
        f.dep_delay_min,
        f.scheduled_arr_time,
        f.arr_delay_min,
        -- Fetch arrival delay of previous flight performed by same aircraft
        LAG(f.arr_delay_min) OVER (
            PARTITION BY f.tail_number, f.date_id 
            ORDER BY f.scheduled_dep_time
        ) AS prev_flight_arr_delay,
        LAG(dest.airport_code) OVER (
            PARTITION BY f.tail_number, f.date_id 
            ORDER BY f.scheduled_dep_time
        ) AS prev_flight_dest
    FROM Flights f
    JOIN Airlines a ON f.airline_id = a.airline_id
    JOIN Airports orig ON f.origin_airport_id = orig.airport_id
    JOIN Airports dest ON f.dest_airport_id = dest.airport_id
    WHERE CAST(f.cancelled AS INT) = 0 AND f.tail_number IS NOT NULL
)
SELECT 
    tail_number,
    airline_code,
    prev_flight_dest AS arrived_from,
    departure_airport AS departing_from,
    arrival_airport AS heading_to,
    date_id,
    scheduled_dep_time,
    prev_flight_arr_delay,
    dep_delay_min,
    CASE 
        WHEN prev_flight_arr_delay > 15 AND dep_delay_min > 15 
            THEN 'Propagated Delay'
        WHEN prev_flight_arr_delay > 15 AND dep_delay_min <= 15 
            THEN 'Recovered on Ground'
        WHEN prev_flight_arr_delay <= 15 AND dep_delay_min > 15 
            THEN 'New Local Delay'
        ELSE 'On-Time Turnaround'
    END AS turnaround_status
FROM AircraftTurnaround
WHERE prev_flight_arr_delay IS NOT NULL
ORDER BY date_id, tail_number, scheduled_dep_time;


-- ----------------------------------------------------------------------------
-- QUERY 2: Rolling 7-Day Average Departure Delay per Airport Hub
-- Business Value: Identifies operational degradation patterns and smoothing
-- daily volatility to spotlight chronic airport congestion.
-- ----------------------------------------------------------------------------
WITH DailyAirportDelay AS (
    SELECT 
        orig.airport_id,
        orig.airport_code,
        orig.airport_name,
        d.full_date,
        COUNT(f.flight_id) AS total_departures,
        AVG(CAST(f.dep_delay_min AS FLOAT)) AS daily_avg_dep_delay
    FROM Flights f
    JOIN Airports orig ON f.origin_airport_id = orig.airport_id
    JOIN Dates d ON f.date_id = d.date_id
    WHERE CAST(f.cancelled AS INT) = 0
    GROUP BY orig.airport_id, orig.airport_code, orig.airport_name, d.full_date
)
SELECT 
    airport_code,
    airport_name,
    full_date,
    total_departures,
    ROUND(daily_avg_dep_delay, 2) AS daily_avg_dep_delay,
    ROUND(AVG(daily_avg_dep_delay) OVER (
        PARTITION BY airport_id 
        ORDER BY full_date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 2) AS rolling_7day_avg_delay
FROM DailyAirportDelay
ORDER BY airport_code, full_date;


-- ----------------------------------------------------------------------------
-- QUERY 3: Airline Performance Ranking (RANK vs. DENSE_RANK)
-- Quantifies on-time reliability across carriers using industry 15-minute standard
-- ----------------------------------------------------------------------------
WITH AirlineMetrics AS (
    SELECT 
        a.airline_code,
        a.airline_name,
        COUNT(f.flight_id) AS total_flights,
        SUM(CASE WHEN f.dep_delay_min <= 15 AND CAST(f.cancelled AS INT) = 0 THEN 1 ELSE 0 END) AS on_time_departures,
        SUM(CASE WHEN f.arr_delay_min <= 15 AND CAST(f.cancelled AS INT) = 0 THEN 1 ELSE 0 END) AS on_time_arrivals,
        SUM(CAST(f.cancelled AS INT)) AS total_cancelled,
        AVG(CASE WHEN CAST(f.cancelled AS INT) = 0 THEN CAST(f.dep_delay_min AS FLOAT) END) AS avg_dep_delay_min,
        AVG(CASE WHEN CAST(f.cancelled AS INT) = 0 THEN CAST(f.arr_delay_min AS FLOAT) END) AS avg_arr_delay_min
    FROM Flights f
    JOIN Airlines a ON f.airline_id = a.airline_id
    GROUP BY a.airline_code, a.airline_name
)
SELECT 
    airline_code,
    airline_name,
    total_flights,
    ROUND(100.0 * on_time_departures / total_flights, 2) AS on_time_dep_pct,
    ROUND(100.0 * on_time_arrivals / total_flights, 2) AS on_time_arr_pct,
    ROUND(100.0 * total_cancelled / total_flights, 2) AS cancellation_rate_pct,
    ROUND(avg_dep_delay_min, 2) AS avg_dep_delay_min,
    ROUND(avg_arr_delay_min, 2) AS avg_arr_delay_min,
    RANK() OVER (ORDER BY (100.0 * on_time_arrivals / total_flights) DESC) AS rank_by_ontime,
    DENSE_RANK() OVER (ORDER BY avg_arr_delay_min ASC) AS dense_rank_by_least_delay
FROM AirlineMetrics
ORDER BY rank_by_ontime;


-- ----------------------------------------------------------------------------
-- QUERY 4: Delay-Cause Attribution Breakdown by Route Corridors
-- Analyzes primary drivers (Carrier, Weather, NAS, Security, Late Aircraft)
-- ----------------------------------------------------------------------------
WITH RouteDelayTotals AS (
    SELECT 
        orig.airport_code AS origin,
        dest.airport_code AS destination,
        COUNT(f.flight_id) AS flight_count,
        SUM(f.carrier_delay) AS total_carrier_delay,
        SUM(f.weather_delay) AS total_weather_delay,
        SUM(f.nas_delay) AS total_nas_delay,
        SUM(f.security_delay) AS total_security_delay,
        SUM(f.late_aircraft_delay) AS total_late_aircraft_delay,
        SUM(f.carrier_delay + f.weather_delay + f.nas_delay + f.security_delay + f.late_aircraft_delay) AS total_explained_delay
    FROM Flights f
    JOIN Airports orig ON f.origin_airport_id = orig.airport_id
    JOIN Airports dest ON f.dest_airport_id = dest.airport_id
    WHERE CAST(f.cancelled AS INT) = 0
    GROUP BY orig.airport_code, dest.airport_code
    HAVING SUM(f.carrier_delay + f.weather_delay + f.nas_delay + f.security_delay + f.late_aircraft_delay) > 0
)
SELECT 
    origin,
    destination,
    flight_count,
    total_explained_delay,
    ROUND(100.0 * total_carrier_delay / total_explained_delay, 1) AS carrier_pct,
    ROUND(100.0 * total_weather_delay / total_explained_delay, 1) AS weather_pct,
    ROUND(100.0 * total_nas_delay / total_explained_delay, 1) AS nas_pct,
    ROUND(100.0 * total_late_aircraft_delay / total_explained_delay, 1) AS late_aircraft_pct,
    ROUND(100.0 * total_security_delay / total_explained_delay, 1) AS security_pct
FROM RouteDelayTotals
ORDER BY total_explained_delay DESC;


-- ----------------------------------------------------------------------------
-- QUERY 5: Cascading Delay Ripple Chains (Turnaround Succession)
-- Tracks multi-hop flight sequences executed by the same aircraft tail number
-- showing how an early morning delay ripples through subsequent legs
-- ----------------------------------------------------------------------------
WITH FlightLegs AS (
    SELECT 
        f.flight_id,
        f.tail_number,
        f.date_id,
        orig.airport_code AS origin,
        dest.airport_code AS destination,
        f.scheduled_dep_time,
        f.dep_delay_min,
        f.arr_delay_min,
        ROW_NUMBER() OVER (
            PARTITION BY f.tail_number, f.date_id 
            ORDER BY f.scheduled_dep_time
        ) AS leg_number
    FROM Flights f
    JOIN Airports orig ON f.origin_airport_id = orig.airport_id
    JOIN Airports dest ON f.dest_airport_id = dest.airport_id
    WHERE CAST(f.cancelled AS INT) = 0 AND f.tail_number IS NOT NULL
)
SELECT 
    l1.date_id,
    l1.tail_number,
    l1.origin || ' -> ' || l1.destination AS leg1_route,
    l1.dep_delay_min AS leg1_dep_delay,
    l1.arr_delay_min AS leg1_arr_delay,
    l2.origin || ' -> ' || l2.destination AS leg2_route,
    l2.dep_delay_min AS leg2_dep_delay,
    l2.arr_delay_min AS leg2_arr_delay,
    (l2.dep_delay_min - l1.arr_delay_min) AS ground_buffer_recovery
FROM FlightLegs l1
JOIN FlightLegs l2 
    ON l1.tail_number = l2.tail_number 
    AND l1.date_id = l2.date_id 
    AND l2.leg_number = l1.leg_number + 1
WHERE l1.arr_delay_min > 30 -- First flight suffered substantial delay
ORDER BY l1.date_id, l1.arr_delay_min DESC;


-- ----------------------------------------------------------------------------
-- QUERY 6: Statistical Delay Anomaly Detection (> 2 Standard Deviations)
-- Isolates abnormal route disruptions (severe weather shocks, ground stops)
-- by calculating route rolling mean and standard deviation.
-- ----------------------------------------------------------------------------
WITH RouteStatistics AS (
    SELECT 
        f.flight_id,
        f.date_id,
        d.full_date,
        a.airline_code,
        orig.airport_code AS origin,
        dest.airport_code AS destination,
        f.flight_number,
        f.dep_delay_min,
        f.arr_delay_min,
        -- Route baseline stats
        AVG(CAST(f.arr_delay_min AS FLOAT)) OVER (
            PARTITION BY f.origin_airport_id, f.dest_airport_id
        ) AS route_mean_delay,
        -- Standard deviation calculation
        AVG(CAST(f.arr_delay_min AS FLOAT) * CAST(f.arr_delay_min AS FLOAT)) OVER (
            PARTITION BY f.origin_airport_id, f.dest_airport_id
        ) AS route_mean_sq
    FROM Flights f
    JOIN Dates d ON f.date_id = d.date_id
    JOIN Airlines a ON f.airline_id = a.airline_id
    JOIN Airports orig ON f.origin_airport_id = orig.airport_id
    JOIN Airports dest ON f.dest_airport_id = dest.airport_id
    WHERE CAST(f.cancelled AS INT) = 0
)
SELECT 
    flight_id,
    full_date,
    airline_code,
    origin,
    destination,
    flight_number,
    arr_delay_min,
    ROUND(route_mean_delay, 1) AS route_baseline_avg,
    ROUND(SQRT(CASE WHEN route_mean_sq - (route_mean_delay * route_mean_delay) > 0 
                    THEN route_mean_sq - (route_mean_delay * route_mean_delay) 
                    ELSE 1 END), 1) AS route_std_dev,
    ROUND((arr_delay_min - route_mean_delay) / 
          NULLIF(SQRT(CASE WHEN route_mean_sq - (route_mean_delay * route_mean_delay) > 0 
                           THEN route_mean_sq - (route_mean_delay * route_mean_delay) 
                           ELSE 1 END), 0), 2) AS z_score,
    'High Anomaly (>2σ)' AS anomaly_flag
FROM RouteStatistics
WHERE arr_delay_min > (route_mean_delay + 2.0 * SQRT(CASE WHEN route_mean_sq - (route_mean_delay * route_mean_delay) > 0 
                                                          THEN route_mean_sq - (route_mean_delay * route_mean_delay) 
                                                          ELSE 1 END))
  AND arr_delay_min > 45
ORDER BY z_score DESC;
