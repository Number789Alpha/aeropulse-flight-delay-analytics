"""
Tests for Data Quality Validation and Machine Learning Inference
"""
import pytest
import pandas as pd
from etl.validate import validate_flight_data
from ml.predict_delay import predict_delay_risk

def test_dq_validation_assertions():
    # Construct invalid test records
    invalid_data = pd.DataFrame([
        {
            "date_id": 20230101,
            "airline_code": None, # Missing identifier
            "origin_code": "ATL",
            "dest_code": "JFK",
            "flight_number": "100",
            "sched_dep_time": 2800, # Invalid time > 2400
            "distance_miles": -150 # Negative distance
        }
    ])
    issues = validate_flight_data(invalid_data, engine=None)
    assert len(issues) >= 2
    issue_types = [i["issue_type"] for i in issues]
    assert "NULL_IDENTIFIER" in issue_types
    assert "INVALID_TIME_FORMAT" in issue_types

def test_ml_delay_prediction():
    res = predict_delay_risk(
        carrier="AA",
        origin="DFW",
        dest="ORD",
        dep_hour=17,
        day_of_week=4,
        month=6
    )
    assert "delay_probability" in res
    assert 0.0 <= res["delay_probability"] <= 1.0
    assert "risk_level" in res
    assert "recommendation" in res
