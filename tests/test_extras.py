import pandas as pd
import pytest
from extras import season_for_month,validate_release_plan,simulate_release,safe_comments_table

def test_seasons():
    assert season_for_month(5)=='ฤดูฝน'
    assert season_for_month(10)=='ฤดูฝน'
    assert season_for_month(11)=='ฤดูแล้ง'

def test_balance():
    d=pd.DataFrame({'date':['2026-11-23'],'inflow_cms':[200],'release_cms':[100]})
    x=simulate_release(d,500,1000)
    assert abs(x.storage_mcm.iloc[0]-508.64)<1e-5

def test_reject_invalid():
    with pytest.raises(ValueError):
        validate_release_plan(pd.DataFrame({'date':['nope'],'inflow_cms':[5],'release_cms':[-1]}))

def test_public_redaction():
    df=pd.DataFrame({'ticket':['A1'],'contact':['secret'],'province':['น่าน'],'latitude':[1.0]})
    assert 'contact' not in safe_comments_table(df).columns
    assert 'latitude' not in safe_comments_table(df).columns
