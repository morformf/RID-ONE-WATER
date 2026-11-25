import pandas as pd
import pytest
from hourly_core import validate_hourly,as_csv,as_excel,fetch_hourly_api

def test_valid_hourly_and_exports():
    d=validate_hourly(pd.DataFrame([{'station_id':'P.20','observed_at':'2026-11-24 01:00:00','water_level_m':0.07,'discharge_cms':7.89}]))
    assert d.observed_at.iloc[0].strftime('%z')=='+0700'
    assert len(as_excel(d))>2000
    assert b'P.20' in as_csv(d)

def test_invalid_schema():
    with pytest.raises(ValueError):validate_hourly(pd.DataFrame([{'station_id':'P.20'}]))

def test_url_validation():
    with pytest.raises(ValueError):fetch_hourly_api('https://example.com/private')
