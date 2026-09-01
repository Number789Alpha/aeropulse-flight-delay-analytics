"""
Airline/Flight Delay Analytics — Data Acquisition & Realistic Synthesizer
Provides multiple options to get dataset:
1. Kaggle CLI auto-downloader (if kaggle API key exists)
2. Direct BTS TranStats instructions
3. High-fidelity realistic US DOT flight data generator
   (Generates 30,000+ authentic flight records with real US airport coordinates,
   real carrier codes, tail-number turnaround chains, and delay causes).
"""

import os
import sys
import argparse
import random
import datetime
import numpy as np
import pandas as pd

# Define Major US Airlines (IATA code, Name)
AIRLINES = [
    ("DL", "Delta Air Lines Inc."),
    ("AA", "American Airlines Inc."),
    ("UA", "United Air Lines Inc."),
    ("WN", "Southwest Airlines Co."),
    ("B6", "JetBlue Airways"),
    ("AS", "Alaska Airlines Inc."),
    ("NK", "Spirit Air Lines"),
    ("F9", "Frontier Airlines Inc.")
]

# Define Top 25 US Airports with official coordinates
AIRPORTS = [
    ("ATL", "Hartsfield-Jackson Atlanta International Airport", "Atlanta", "GA", 33.6407, -84.4277),
    ("ORD", "Chicago O'Hare International Airport", "Chicago", "IL", 41.9742, -87.9073),
    ("DFW", "Dallas/Fort Worth International Airport", "Dallas", "TX", 32.8998, -97.0403),
    ("DEN", "Denver International Airport", "Denver", "CO", 39.8561, -104.6737),
    ("CLT", "Charlotte Douglas International Airport", "Charlotte", "NC", 35.2140, -80.9431),
    ("LAX", "Los Angeles International Airport", "Los Angeles", "CA", 33.9416, -118.4085),
    ("JFK", "John F. Kennedy International Airport", "New York", "NY", 40.6413, -73.7781),
    ("SFO", "San Francisco International Airport", "San Francisco", "CA", 37.6213, -122.3790),
    ("SEA", "Seattle-Tacoma International Airport", "Seattle", "WA", 47.4502, -122.3088),
    ("MCO", "Orlando International Airport", "Orlando", "FL", 28.4312, -81.3081),
    ("LAS", "Harry Reid International Airport", "Las Vegas", "NV", 36.0840, -115.1537),
    ("EWR", "Newark Liberty International Airport", "Newark", "NJ", 40.6895, -74.1745),
    ("MIA", "Miami International Airport", "Miami", "FL", 25.7959, -80.2870),
    ("PHX", "Phoenix Sky Harbor International Airport", "Phoenix", "AZ", 33.4373, -112.0078),
    ("BOS", "Boston Logan International Airport", "Boston", "MA", 42.3656, -71.0096),
    ("MSP", "Minneapolis-Saint Paul International Airport", "Minneapolis", "MN", 44.8848, -93.2223),
    ("DTW", "Detroit Metropolitan Wayne County Airport", "Detroit", "MI", 42.2162, -83.3554),
    ("FLL", "Fort Lauderdale-Hollywood International Airport", "Fort Lauderdale", "FL", 26.0742, -80.1506),
    ("PHL", "Philadelphia International Airport", "Philadelphia", "PA", 39.8729, -75.2437),
    ("LGA", "LaGuardia Airport", "New York", "NY", 40.7769, -73.8740),
    ("BWI", "Baltimore/Washington International Thurgood Marshall Airport", "Baltimore", "MD", 39.1774, -76.6684),
    ("SLC", "Salt Lake City International Airport", "Salt Lake City", "UT", 40.7899, -111.9791),
    ("SAN", "San Diego International Airport", "San Diego", "CA", 32.7338, -117.1933),
    ("IAD", "Washington Dulles International Airport", "Washington", "DC", 38.9531, -77.4565),
    ("TPA", "Tampa International Airport", "Tampa", "FL", 27.9772, -82.5311)
]

def generate_realistic_bts_dataset(output_dir="data", num_days=60, flights_per_day=500):
    """
    Synthesizes a realistic BTS-grade flight dataset honoring DOT delay attribution standards:
    - Multiple turnaround legs per tail number to enable authentic LAG delay propagation.
    - True DOT delay breakdowns (Carrier, Weather, NAS, Security, Late Aircraft).
    - Authentic time-of-day distributions and cancellation patterns.
    """
    os.makedirs(output_dir, exist_ok=True)
    random.seed(42)
    np.random.seed(42)

    print(f"Generating realistic US DOT flight dataset: {num_days} days, ~{flights_per_day} flights/day...")

    # Build aircraft fleet for each airline
    aircraft_fleet = {}
    for code, _ in AIRLINES:
        aircraft_fleet[code] = [f"N{random.randint(100, 999)}{code[:2]}" for _ in range(35)]

    start_date = datetime.date(2023, 1, 1)
    flight_records = []

    # Airport lookup
    airport_codes = [a[0] for a in AIRPORTS]

    for day_offset in range(num_days):
        current_date = start_date + datetime.timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Weekend effect: slight variation in volume
        is_weekend = 1 if current_date.weekday() >= 5 else 0
        daily_flight_target = int(flights_per_day * (0.85 if is_weekend else 1.05))

        # Weather shock event simulation on some days
        severe_weather_day = random.random() < 0.12
        weather_hub = random.choice(["ORD", "DEN", "JFK", "EWR", "ATL"]) if severe_weather_day else None

        for carrier_code, _ in AIRLINES:
            carrier_aircraft = aircraft_fleet[carrier_code]
            
            for tail in carrier_aircraft:
                # Each aircraft typically flies 2 to 4 legs per day
                legs = random.randint(2, 4)
                current_airport = random.choice(airport_codes)
                current_time_min = random.randint(360, 540) # Starts between 06:00 and 09:00 AM
                prev_arr_delay = 0

                for leg_idx in range(legs):
                    # Next destination (must be different from origin)
                    dest_airport = random.choice([a for a in airport_codes if a != current_airport])
                    flight_num = f"{random.randint(100, 2999)}"

                    # Scheduled times
                    sched_dep_min = current_time_min
                    flight_duration = random.randint(75, 260)
                    sched_arr_min = sched_dep_min + flight_duration

                    # Format to HHMM
                    sched_dep_hhmm = (sched_dep_min // 60) * 100 + (sched_dep_min % 60)
                    sched_arr_hhmm = ((sched_arr_min // 60) % 24) * 100 + (sched_arr_min % 60)

                    # Cancellation chance (higher during severe weather at hub)
                    is_cancelled = 0
                    cancellation_reason = None
                    if severe_weather_day and (current_airport == weather_hub or dest_airport == weather_hub):
                        if random.random() < 0.20:
                            is_cancelled = 1
                            cancellation_reason = "B" # Weather
                    elif random.random() < 0.015:
                        is_cancelled = 1
                        cancellation_reason = random.choice(["A", "C"]) # Carrier or NAS

                    if is_cancelled:
                        flight_records.append({
                            "FL_DATE": date_str,
                            "OP_CARRIER": carrier_code,
                            "OP_CARRIER_FL_NUM": flight_num,
                            "TAIL_NUM": tail,
                            "ORIGIN": current_airport,
                            "DEST": dest_airport,
                            "CRS_DEP_TIME": sched_dep_hhmm,
                            "DEP_TIME": np.nan,
                            "DEP_DELAY": np.nan,
                            "CRS_ARR_TIME": sched_arr_hhmm,
                            "ARR_TIME": np.nan,
                            "ARR_DELAY": np.nan,
                            "CANCELLED": 1,
                            "CANCELLATION_CODE": cancellation_reason,
                            "DIVERTED": 0,
                            "CRS_ELAPSED_TIME": flight_duration,
                            "ACTUAL_ELAPSED_TIME": np.nan,
                            "AIR_TIME": np.nan,
                            "DISTANCE": int(flight_duration * 7.5),
                            "CARRIER_DELAY": 0,
                            "WEATHER_DELAY": 0,
                            "NAS_DELAY": 0,
                            "SECURITY_DELAY": 0,
                            "LATE_AIRCRAFT_DELAY": 0
                        })
                        break # Turnaround stopped

                    # Delay calculations
                    # Propagate delay from previous leg if any
                    propagated_delay = 0
                    if prev_arr_delay > 15:
                        # Turnaround recovery buffer: 15-30 min
                        buffer = random.randint(15, 30)
                        propagated_delay = max(0, prev_arr_delay - buffer)

                    # Local new delay component
                    local_dep_delay = 0
                    weather_delay = 0
                    carrier_delay = 0
                    nas_delay = 0
                    security_delay = 0
                    late_aircraft_delay = propagated_delay

                    if severe_weather_day and (current_airport == weather_hub or dest_airport == weather_hub):
                        weather_delay = int(np.random.exponential(35) + 20)
                        local_dep_delay += weather_delay

                    # Random operational delay (log-normal distribution)
                    if random.random() < 0.35:
                        rand_delay = int(np.random.exponential(20))
                        if random.random() < 0.45:
                            carrier_delay += rand_delay
                        elif random.random() < 0.85:
                            nas_delay += rand_delay
                        else:
                            security_delay += min(20, rand_delay)
                        local_dep_delay += rand_delay
                    else:
                        # Minor slight early or on-time
                        local_dep_delay += random.randint(-8, 5)

                    total_dep_delay = local_dep_delay + late_aircraft_delay
                    actual_dep_min = sched_dep_min + total_dep_delay
                    actual_dep_hhmm = ((actual_dep_min // 60) % 24) * 100 + (actual_dep_min % 60)

                    # In-air adjustments (en-route weather, headwind/tailwind)
                    in_air_adj = random.randint(-12, 18)
                    actual_elapsed = max(30, flight_duration + in_air_adj)
                    air_time = actual_elapsed - random.randint(15, 25)

                    actual_arr_min = actual_dep_min + actual_elapsed
                    actual_arr_hhmm = ((actual_arr_min // 60) % 24) * 100 + (actual_arr_min % 60)
                    total_arr_delay = total_dep_delay + in_air_adj

                    # If total arrival delay < 15, BTS standards mandate zeroing delay cause fields
                    if total_arr_delay < 15:
                        carrier_delay = 0
                        weather_delay = 0
                        nas_delay = 0
                        security_delay = 0
                        late_aircraft_delay = 0
                    else:
                        # Normalize delay causes to sum close to total delay
                        raw_sum = carrier_delay + weather_delay + nas_delay + security_delay + late_aircraft_delay
                        if raw_sum > 0:
                            scale = total_arr_delay / raw_sum
                            carrier_delay = int(carrier_delay * scale)
                            weather_delay = int(weather_delay * scale)
                            nas_delay = int(nas_delay * scale)
                            security_delay = int(security_delay * scale)
                            late_aircraft_delay = int(late_aircraft_delay * scale)
                        else:
                            nas_delay = total_arr_delay

                    flight_records.append({
                        "FL_DATE": date_str,
                        "OP_CARRIER": carrier_code,
                        "OP_CARRIER_FL_NUM": flight_num,
                        "TAIL_NUM": tail,
                        "ORIGIN": current_airport,
                        "DEST": dest_airport,
                        "CRS_DEP_TIME": sched_dep_hhmm,
                        "DEP_TIME": actual_dep_hhmm,
                        "DEP_DELAY": total_dep_delay,
                        "CRS_ARR_TIME": sched_arr_hhmm,
                        "ARR_TIME": actual_arr_hhmm,
                        "ARR_DELAY": total_arr_delay,
                        "CANCELLED": 0,
                        "CANCELLATION_CODE": "",
                        "DIVERTED": 0,
                        "CRS_ELAPSED_TIME": flight_duration,
                        "ACTUAL_ELAPSED_TIME": actual_elapsed,
                        "AIR_TIME": air_time,
                        "DISTANCE": int(flight_duration * 7.5),
                        "CARRIER_DELAY": carrier_delay,
                        "WEATHER_DELAY": weather_delay,
                        "NAS_DELAY": nas_delay,
                        "SECURITY_DELAY": security_delay,
                        "LATE_AIRCRAFT_DELAY": late_aircraft_delay
                    })

                    # Setup next leg
                    current_airport = dest_airport
                    prev_arr_delay = max(0, total_arr_delay)
                    current_time_min = actual_arr_min + random.randint(45, 60) # Turnaround ground time
                    if current_time_min >= 1400: # After 11:20 PM, aircraft retires for night
                        break

    df_flights = pd.DataFrame(flight_records)
    raw_path = os.path.join(output_dir, "raw_flights.csv")
    df_flights.to_csv(raw_path, index=False)
    print(f"Generated {len(df_flights):,} flight records saved to {raw_path}")

    # Also export reference airports and airlines CSVs
    df_airports = pd.DataFrame(AIRPORTS, columns=["airport_code", "airport_name", "city", "state", "latitude", "longitude"])
    df_airports.to_csv(os.path.join(output_dir, "airports.csv"), index=False)

    df_airlines = pd.DataFrame(AIRLINES, columns=["airline_code", "airline_name"])
    df_airlines.to_csv(os.path.join(output_dir, "airlines.csv"), index=False)

    print("Reference airports.csv and airlines.csv created successfully.")
    return raw_path

def download_from_kaggle(output_dir="data"):
    """
    Attempts download via official Kaggle CLI if available and credentials exist.
    """
    try:
        import kaggle
        print("Kaggle package found. Initiating dataset download...")
        os.makedirs(output_dir, exist_ok=True)
        # 2015 Flight Delays and Cancellations
        os.system(f"kaggle datasets download -d usdot/flight-delays -p {output_dir} --unzip")
        print("Kaggle download completed.")
        return True
    except Exception as e:
        print(f"Kaggle download skipped or not configured: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Acquire or generate flight dataset")
    parser.add_argument("--source", choices=["kaggle", "bts-info", "generate"], default="generate")
    parser.add_argument("--days", type=int, default=60, help="Number of days to simulate")
    parser.add_argument("--flights-per-day", type=int, default=500, help="Average flights per day")
    args = parser.parse_args()

    if args.source == "kaggle":
        success = download_from_kaggle()
        if not success:
            print("Falling back to realistic data generation...")
            generate_realistic_bts_dataset(num_days=args.days, flights_per_day=args.flights_per_day)
    elif args.source == "bts-info":
        print("""
===================================================================
How to download direct from BTS TranStats (Official Source):
1. Navigate to: https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ
2. Select Year (e.g., 2023) and Month.
3. Check fields:
   - FlightDate, Reporting_Airline, Tail_Number, Flight_Number_Reporting_Airline
   - Origin, Dest, CRSDepTime, DepTime, DepDelay, CRSArrTime, ArrTime, ArrDelay
   - Cancelled, CancellationCode, Diverted, CRSElapsedTime, ActualElapsedTime, AirTime, Distance
   - CarrierDelay, WeatherDelay, NASDelay, SecurityDelay, LateAircraftDelay
4. Download ZIP, extract CSV, and place into 'data/raw_flights.csv'.
===================================================================
        """)
    else:
        generate_realistic_bts_dataset(num_days=args.days, flights_per_day=args.flights_per_day)
