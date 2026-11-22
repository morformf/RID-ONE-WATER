"""Shared validation, import and export for RID ONE WATER MVP.
All demo data is tagged 'demo'; imported files retain user_import source.
"""
from io import BytesIO
import pandas as pd
import numpy as np

STATION_COLUMNS = ["station_id","station_name","station_type","latitude","longitude","basin","province","source"]
OBS_COLUMNS = ["station_id","observed_at","parameter","value","unit","source"]
PARAMS = {"water_level":"ระดับน้ำ (ม.)", "discharge":"อัตราการไหล (ลบ.ม./วินาที)", "rainfall":"ฝน (มม.)", "salinity":"ความเค็ม (ppt)","ph":"pH", "do":"DO (mg/L)", "ec":"EC (µS/cm)","temperature":"อุณหภูมิ (°C)"}
ALLOWED_TYPES = {"telemetry", "reservoir", "gate", "water_quality"}


def load_table(upload):
    name = getattr(upload, 'name', '').lower()
    if not name.endswith(('.csv','.xlsx','.xls')): raise ValueError('รองรับเฉพาะ CSV และ Excel')
    if name.endswith('.csv'):
        raw = upload.getvalue()
        for enc in ('utf-8-sig','utf-8','cp874'):
            try: return pd.read_csv(BytesIO(raw), encoding=enc)
            except UnicodeDecodeError: pass
        raise ValueError('ไม่รองรับ encoding ของไฟล์ CSV')
    return pd.read_excel(BytesIO(upload.getvalue()))


def validate_stations(df):
    df=df.copy(); missing=set(STATION_COLUMNS)-set(df.columns)
    if missing: raise ValueError('คอลัมน์สถานีไม่ครบ: '+', '.join(sorted(missing)))
    df=df[STATION_COLUMNS].copy()
    for c in ('station_id','station_name','station_type','basin','province','source'):
        df[c]=df[c].fillna('').astype(str).str.strip()
    for c in ('latitude','longitude'): df[c]=pd.to_numeric(df[c],errors='coerce')
    valid=df.latitude.between(-90,90)&df.longitude.between(-180,180)&df.station_id.ne('')&df.station_type.isin(ALLOWED_TYPES)
    df=df.loc[valid].drop_duplicates('station_id',keep='last')
    if df.empty: raise ValueError('ไม่มีข้อมูลสถานีที่ผ่านการตรวจสอบ')
    return df.reset_index(drop=True)


def validate_observations(df):
    df=df.copy(); missing=set(OBS_COLUMNS)-set(df.columns)
    if missing: raise ValueError('คอลัมน์ข้อมูลตรวจวัดไม่ครบ: '+', '.join(sorted(missing)))
    df=df[OBS_COLUMNS].copy()
    df['station_id']=df.station_id.fillna('').astype(str).str.strip()
    df['parameter']=df.parameter.fillna('').astype(str).str.strip().str.lower()
    df['source']=df.source.fillna('user_import').astype(str)
    df['value']=pd.to_numeric(df.value,errors='coerce')
    df['observed_at']=pd.to_datetime(df.observed_at,errors='coerce',utc=True)
    df=df.loc[df.observed_at.notna()&df.value.notna()&df.station_id.ne('')&df.parameter.isin(PARAMS)].copy()
    if df.empty: raise ValueError('ไม่มีข้อมูลตรวจวัดที่ผ่านการตรวจสอบ')
    return df.sort_values('observed_at').drop_duplicates(['station_id','observed_at','parameter'],keep='last').reset_index(drop=True)


def classify_status(obs, stations, threshold_hours=3):
    """Statuses use observation timestamp, NOT fake alerts or forecast thresholds."""
    latest=obs.sort_values('observed_at').groupby('station_id').tail(1)[['station_id','observed_at']]
    out=stations.merge(latest,on='station_id',how='left')
    now=pd.Timestamp.now(tz='UTC')
    age=(now-out.observed_at).dt.total_seconds()/3600
    out['status']=np.select([out.observed_at.isna(),age>threshold_hours,age < -1],['ไม่มีข้อมูล','ข้อมูลล่าช้า','เวลาไม่ถูกต้อง'],default='ปกติ')
    out['age_hours']=age
    return out


def make_alerts(status_df, obs, limits):
    alerts=[]
    for r in status_df.itertuples():
        if r.status!='ปกติ': alerts.append({'station_id':r.station_id,'station_name':r.station_name,'category':'คุณภาพข้อมูล','message':r.status,'level':'ตรวจสอบ'})
    latest=obs.sort_values('observed_at').groupby(['station_id','parameter'],as_index=False).tail(1)
    names=dict(zip(status_df.station_id,status_df.station_name))
    for r in latest.itertuples():
        maxv=limits.get(r.parameter)
        if maxv is not None and r.value > maxv:
            alerts.append({'station_id':r.station_id,'station_name':names.get(r.station_id,r.station_id),'category':'เกินเกณฑ์สาธิต','message':f'{PARAMS.get(r.parameter,r.parameter)} = {r.value:,.2f} > {maxv:,.2f}','level':'เฝ้าระวัง'})
    return pd.DataFrame(alerts,columns=['station_id','station_name','category','message','level'])


def excel_bytes(sheets):
    buf=BytesIO()
    with pd.ExcelWriter(buf,engine='openpyxl') as writer:
        for name,df in sheets.items():
            df.to_excel(writer,sheet_name=name[:31],index=False)
            ws=writer.sheets[name[:31]]
            ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
            for col in ws.columns:
                max_len=min(48,max(len(str(cell.value or '')) for cell in list(col)[:500])+2)
                ws.column_dimensions[col[0].column_letter].width=max(14,max_len)
    return buf.getvalue()
