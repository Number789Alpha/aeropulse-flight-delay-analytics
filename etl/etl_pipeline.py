"""
Airline/Flight Delay Analytics — ETL Pipeline Import Wrapper
Enables standard Python imports for etl module.
"""
import importlib.util
import os

_file_path = os.path.join(os.path.dirname(__file__), "01_etl.py")
_spec = importlib.util.spec_from_file_location("etl_01", _file_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

get_db_engine = _module.get_db_engine
init_schema = _module.init_schema
clean_and_prepare_raw_data = _module.clean_and_prepare_raw_data
populate_dimensions = _module.populate_dimensions
load_fact_flights = _module.load_fact_flights
run_pipeline = _module.run_pipeline
