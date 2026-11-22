"""Official public reservoir feeds; no credentials required per published docs.
Fails closed on unsupported response formats and never substitutes demo data as live.
"""
import requests
import pandas as pd
from functools import lru_cache

FEEDS = {
  'เขื่อนขนาดใหญ่': 'https://app.rid.go.th/reservoir/api/dam/public',
  'อ่างขนาดกลาง': 'https://app.rid.go.th/reservoir/api/reservoir/public'
}
FIELDS = ['date','id','name','region','capacity','storage','dead_storage','volume','percent_storage','inflow','outflow','owner']


def _records(payload):
    """Supports list, wrapped `data`, and province/region grouped objects."""
    found=[]
    def visit(obj,depth=0):
        if depth>7:return
        if isinstance(obj,list):
            for item in obj: visit(item,depth+1)
        elif isinstance(obj,dict):
            if ('name' in obj or 'id' in obj) and any(k in obj for k in ('volume','storage','inflow','outflow')):
                found.append(obj);return
            for val in obj.values():
                if isinstance(val,(list,dict)):visit(val,depth+1)
    visit(payload)
    return found


def normalize_reservoir(payload,kind):
    records=_records(payload)
    if not records: raise ValueError('ไม่พบระเบียนอ่างเก็บน้ำในรูปแบบ API ที่รองรับ กรุณาตรวจ JSON ต้นทาง')
    df=pd.json_normalize(records,sep='_')
    for c in FIELDS:
        if c not in df.columns:df[c]=None
    df=df[FIELDS].copy()
    for c in ['capacity','storage','dead_storage','volume','percent_storage','inflow','outflow']:
        df[c]=pd.to_numeric(df[c],errors='coerce')
    df['kind']=kind
    df['source']='RID Public Reservoir API'
    # Date can be on top-level envelope rather than each record
    if df['date'].isna().all() and isinstance(payload,dict): df['date']=payload.get('date')
    return df


def fetch_reservoir(kind):
    if kind not in FEEDS: raise ValueError('ประเภทข้อมูลไม่รองรับ')
    r=requests.get(FEEDS[kind], timeout=(5,15), headers={'Accept':'application/json','User-Agent':'RIDOneWaterDemo/1.0'})
    r.raise_for_status()
    return normalize_reservoir(r.json(),kind)
