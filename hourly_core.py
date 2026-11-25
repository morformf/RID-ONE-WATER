"""Hourly station data parsing for RID ONE WATER; public source config is opt-in."""
from __future__ import annotations
from datetime import datetime
from io import BytesIO
from urllib.parse import urlparse
import pandas as pd
import requests

REQUIRED = ('station_id','observed_at','water_level_m','discharge_cms')
NUMERIC = ('water_level_m','discharge_cms')


def validate_hourly(frame: pd.DataFrame) -> pd.DataFrame:
    d = frame.copy()
    d.columns = [str(c).strip().lstrip('\ufeff') for c in d.columns]
    missing = [c for c in REQUIRED if c not in d]
    if missing:
        raise ValueError('ไม่พบคอลัมน์: ' + ', '.join(missing))
    d['station_id'] = d['station_id'].astype('string').str.strip().str.upper()
    # Input times without timezone are treated as local Thailand time, not UTC.
    timestamp = pd.to_datetime(d['observed_at'], errors='coerce', format='mixed')
    if timestamp.dt.tz is None:
        timestamp = timestamp.dt.tz_localize('Asia/Bangkok', ambiguous='NaT', nonexistent='NaT')
    else:
        timestamp = timestamp.dt.tz_convert('Asia/Bangkok')
    d['observed_at'] = timestamp
    for c in NUMERIC:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d.dropna(subset=['station_id','observed_at'])
    d = d[d['station_id'].str.len() > 0]
    if d.empty:
        raise ValueError('ไม่มีข้อมูลเวลา/สถานีที่ถูกต้อง')
    d = d.sort_values('observed_at').drop_duplicates(['station_id','observed_at'],keep='last')
    d = d.reset_index(drop=True)
    if d[['water_level_m','discharge_cms']].isna().all().all():
        raise ValueError('ไม่มีค่าระดับน้ำหรืออัตราการไหลที่อ่านได้')
    return d


def load_hourly_upload(upload) -> pd.DataFrame:
    fname=upload.name.lower()
    if fname.endswith('.csv'):
        df=pd.read_csv(upload,encoding='utf-8-sig')
    elif fname.endswith(('.xlsx','.xlsm')):
        df=pd.read_excel(upload)
    else:
        raise ValueError('รองรับ CSV และ XLSX เท่านั้น')
    return validate_hourly(df)


def extract_records(payload):
    if isinstance(payload,list):
        return payload
    if isinstance(payload,dict):
        for key in ('data','results','records','items','hourly'):
            if key in payload:
                return extract_records(payload[key])
    raise ValueError('รูปแบบ JSON จาก API ไม่ตรงกับที่รองรับ ต้องปรับ mapping ให้ตรงเอกสาร API')


def fetch_hourly_api(url: str, api_token: str = '', timeout: int=15) -> pd.DataFrame:
    parsed=urlparse(url)
    host=(parsed.hostname or '').lower()
    if parsed.scheme!='https' or not (host=='rid.go.th' or host.endswith('.rid.go.th')):
        raise ValueError('เพื่อความปลอดภัยอนุญาตเฉพาะ HTTPS ภายใต้โดเมน rid.go.th')
    headers={'Accept':'application/json','User-Agent':'RID-ONE-WATER-Hourly/1.6'}
    if api_token:
        headers['Authorization']='Bearer '+api_token
    r=requests.get(url,headers=headers,timeout=timeout,allow_redirects=False)
    if 300 <= r.status_code < 400:
        raise ValueError('ต้นทางตอบกลับด้วยการเปลี่ยนเส้นทาง ไม่ได้ติดตาม URL อัตโนมัติ')
    r.raise_for_status()
    payload=r.json()
    return validate_hourly(pd.DataFrame(extract_records(payload)))


def as_excel(frame: pd.DataFrame) -> bytes:
    buf=BytesIO()
    d=frame.copy()
    d['observed_at']=d['observed_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
    with pd.ExcelWriter(buf,engine='openpyxl') as w:
        d.to_excel(w,sheet_name='Hourly',index=False)
    return buf.getvalue()


def as_csv(frame: pd.DataFrame) -> bytes:
    d=frame.copy()
    d['observed_at']=d['observed_at'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    return d.to_csv(index=False).encode('utf-8-sig')
