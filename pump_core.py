"""Pumping station schema and validation. All input is user-provided or clearly labeled demo."""
import pandas as pd

PUMP_COLUMNS=['pump_id','pump_name','province','basin','latitude','longitude','purpose','total_pumps','rated_capacity_cms','source']
PUMP_OBS_COLUMNS=['pump_id','observed_at','running_pumps','flow_cms','upstream_m','downstream_m','status','source']


def validate_pump_stations(df):
    missing=set(PUMP_COLUMNS)-set(df.columns)
    if missing:raise ValueError('คอลัมน์ทะเบียนสถานีสูบน้ำไม่ครบ: '+', '.join(sorted(missing)))
    out=df[PUMP_COLUMNS].copy()
    for col in ['pump_id','pump_name','province','basin','purpose','source']:
        out[col]=out[col].fillna('').astype(str).str.strip()
    for col in ['latitude','longitude','total_pumps','rated_capacity_cms']:
        out[col]=pd.to_numeric(out[col],errors='coerce')
    good=(out.pump_id.ne('') & out.pump_name.ne('') & out.latitude.between(5,21) & out.longitude.between(97,106)
          & out.total_pumps.ge(1) & out.total_pumps.eq(out.total_pumps.round()) & out.rated_capacity_cms.ge(0))
    if not good.all():raise ValueError('ทะเบียนสถานีสูบน้ำมีค่าผิดปกติ: ตรวจสอบ ID, ชื่อ, พิกัดประเทศไทย, จำนวนเครื่อง และกำลังสูบ')
    out['total_pumps']=out.total_pumps.astype(int)
    if out.pump_id.duplicated().any():raise ValueError('รหัสสถานีสูบน้ำซ้ำ')
    return out.reset_index(drop=True)


def validate_pump_observations(df, stations):
    missing=set(PUMP_OBS_COLUMNS)-set(df.columns)
    if missing:raise ValueError('คอลัมน์ข้อมูลเดินเครื่องไม่ครบ: '+', '.join(sorted(missing)))
    out=df[PUMP_OBS_COLUMNS].copy()
    for col in ['pump_id','status','source']:
        out[col]=out[col].fillna('').astype(str).str.strip()
    out['observed_at']=pd.to_datetime(out.observed_at,errors='coerce',utc=True)
    for col in ['running_pumps','flow_cms','upstream_m','downstream_m']:
        out[col]=pd.to_numeric(out[col],errors='coerce')
    known=set(stations.pump_id)
    max_pumps=dict(zip(stations.pump_id,stations.total_pumps))
    valid=(out.pump_id.isin(known)&out.observed_at.notna()&out.running_pumps.notna()&out.running_pumps.ge(0)
           &out.running_pumps.eq(out.running_pumps.round())&out.flow_cms.ge(0)
           &out.upstream_m.notna()&out.downstream_m.notna())
    if not valid.all():raise ValueError('ข้อมูลเดินเครื่องไม่ถูกต้อง: รหัสสถานี/เวลา/ค่าการสูบ/ระดับน้ำไม่ครบหรือไม่สมเหตุสมผล')
    if any(row.running_pumps>max_pumps[row.pump_id] for row in out.itertuples()):
        raise ValueError('จำนวนเครื่องกำลังเดินเกินจำนวนเครื่องที่ติดตั้ง')
    if ((out.running_pumps==0)&(out.flow_cms>0)).any():
        raise ValueError('พบอัตราสูบมากกว่า 0 ในขณะที่จำนวนเครื่องกำลังเดินเป็น 0')
    out['running_pumps']=out.running_pumps.astype(int)
    return out.sort_values('observed_at').drop_duplicates(['pump_id','observed_at'],keep='last').reset_index(drop=True)


def pumping_volume_mcm(df):
    """Integrate piecewise-constant measured flow from each timestamp to next; no assumed sampling cadence."""
    d=df.sort_values('observed_at').copy()
    if len(d)<2:return 0.0
    intervals=(d.observed_at.shift(-1)-d.observed_at).dt.total_seconds().iloc[:-1]
    return float((d.flow_cms.iloc[:-1]*intervals).sum()/1e6)
