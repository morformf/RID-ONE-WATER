"""Additional pure functions for all-in-one RID ONE WATER demonstrator."""
from __future__ import annotations
import pandas as pd

SEASON_NAMES = {True: 'ฤดูฝน', False: 'ฤดูแล้ง'}

def season_for_month(month: int) -> str:
    return SEASON_NAMES[5 <= int(month) <= 10]

def rainfall_summary(obs: pd.DataFrame) -> pd.DataFrame:
    df = obs.loc[obs['parameter'].eq('rainfall')].copy()
    if df.empty:
        return pd.DataFrame(columns=['station_id','rainfall_mm','records'])
    df['value'] = pd.to_numeric(df['value'],errors='coerce')
    return df.groupby('station_id',as_index=False).agg(rainfall_mm=('value','sum'),records=('value','count'))

def validate_release_plan(df: pd.DataFrame) -> pd.DataFrame:
    required = ['date','inflow_cms','release_cms']
    if not set(required).issubset(df.columns):
        raise ValueError('แผนระบายต้องมี date, inflow_cms, release_cms')
    out=df[required].copy()
    out['date']=pd.to_datetime(out['date'],errors='coerce')
    if out['date'].isna().any() or out['date'].duplicated().any():
        raise ValueError('วันที่ไม่ถูกต้องหรือซ้ำกัน')
    for col in ('inflow_cms','release_cms'):
        out[col]=pd.to_numeric(out[col],errors='coerce')
        if out[col].isna().any() or (out[col]<0).any():
            raise ValueError(f'{col} ต้องเป็นตัวเลขไม่ติดลบ')
    return out.sort_values('date').reset_index(drop=True)

def simulate_release(df: pd.DataFrame, initial_mcm: float, capacity_mcm: float) -> pd.DataFrame:
    """Educational water balance: daily average cms -> MCM/day (0.0864).
    Does NOT represent forecast, real operation, or explicit evaporation / unmodelled outlets.
    """
    if capacity_mcm <= 0 or not (0 <= initial_mcm <= capacity_mcm):
        raise ValueError('ค่าความจุและปริมาณน้ำเริ่มต้นไม่ถูกต้อง')
    out = validate_release_plan(df)
    balance=float(initial_mcm)
    rows=[]
    for row in out.itertuples():
        new = balance + (row.inflow_cms-row.release_cms)*0.0864
        overflow=max(new-capacity_mcm, 0)
        shortage=max(-new, 0)
        balance=max(0, min(capacity_mcm,new))
        rows.append((balance, overflow, shortage, balance/capacity_mcm*100,season_for_month(row.date.month)))
    out[['storage_mcm','overflow_mcm','unmet_mcm','storage_pct','season']]=pd.DataFrame(rows,index=out.index)
    return out

def safe_comments_table(df: pd.DataFrame) -> pd.DataFrame:
    """Public view must not reveal contacts or precise report coordinates."""
    cols=[x for x in ['ticket','kind','province','created_at','status','description'] if x in df]
    return df[cols].copy()
