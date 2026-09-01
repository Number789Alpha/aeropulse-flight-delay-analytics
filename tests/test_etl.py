"""
Tests for AeroPulse ETL Pipeline & Dimension Mapping
"""
import pytest
import pandas as pd
import numpy as np
from etl.etl_pipeline import clean_and_prepare_raw_data, get_db_engine

def test_clean_and_prepare():
    # Test cleaning on sample dataframe
    sample_data = pd.DataFrame([{
        "FL_DATE": "2023-01-15",
        "OP_CARRIER": "DL",
        "OP_CARRIER_FL_NUM": "105",
        "TAIL_NUM": "N123DL",
        "ORIGIN": "ATL",
        "DEST": "ORD",
        "CRS_DEP_TIME": 830,
        "DEP_TIME": 845,
        "DEP_DELAY": 15,
        "CRS_ARR_TIME": 1015,
        "ARR_TIME": 1030,
        "ARR_DELAY": 15,
        "CANCELLED": 0,
        "DIVERTED": 0,
        "CARRIER_DELAY": np.nan,
        "WEATHER_DELAY": np.nan,
        "NAS_DELAY": np.nan,
        "SECURITY_DELAY": np.nan,
        "LATE_AIRCRAFT_DELAY": np.nan
    }])
    sample_path = "data/test_temp.csv"
    sample_data.to_csv(sample_path, index=False)
    
    cleaned = clean_and_prepare_raw_data(sample_path)
    assert len(cleaned) == 1
    assert cleaned["date_id"].iloc[0] == 20230115
    assert cleaned["carrier_delay"].iloc[0] == 0 # Nulls imputed to 0 per DOT
    assert cleaned["dep_delay_min"].iloc[0] == 15
    
    import os
    if os.path.exists(sample_path):
        os.remove(sample_path)

def test_sqlite_engine_connection():
    engine = get_db_engine("sqlite")
    assert "sqlite" in engine.dialect.name.lower()
