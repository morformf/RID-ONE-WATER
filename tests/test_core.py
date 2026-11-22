import pandas as pd
import pytest
from data_utils import validate_stations, validate_observations, classify_status, make_alerts, excel_bytes
from connectors import normalize_reservoir

def test_station_validation():
    df=pd.DataFrame([{'station_id':'A','station_name':'A','station_type':'telemetry','latitude':15,'longitude':100,'basin':'B','province':'P','source':'demo'}])
    assert len(validate_stations(df))==1
    df.loc[0,'latitude']=999
    with pytest.raises(ValueError):validate_stations(df)

def test_obs_missing():
    df=pd.DataFrame([{'station_id':'A','observed_at':'2026-11-21T10:00:00+07:00','parameter':'water_level','value':1.2,'unit':'m','source':'demo'}])
    assert len(validate_observations(df))==1

def test_reservoir_nested():
    payload={'date':'2026-11-21','data':[{'region':'เหนือ','dam':[{'id':'A','name':'X','storage':100,'volume':89,'inflow':2,'outflow':1}]}]}
    d=normalize_reservoir(payload,'เขื่อนขนาดใหญ่')
    assert d.iloc[0]['name']=='X' and d.iloc[0]['date']=='2026-11-21'

def test_excel():
    b=excel_bytes({'Stations':pd.DataFrame({'a':[1]})})
    assert b[:2]==b'PK'
