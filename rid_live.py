"""Read-only public RID feeds for RID ONE WATER prototype.
The hourly cache refresh interval is NOT a claim of hourly measurements.
"""
from datetime import datetime, timezone
import pandas as pd
import requests

RID_FEEDS = {
    'อ่างเก็บน้ำขนาดกลาง': 'https://app.rid.go.th/reservoir/api/reservoir/public',
    'เขื่อน / อ่างเก็บน้ำขนาดใหญ่': 'https://app.rid.go.th/reservoir/api/dam/public',
}


def _find_records(obj, depth=0):
    if depth > 9:
        return []
    if isinstance(obj, list):
        if obj and all(isinstance(v, dict) for v in obj):
            # Common API payloads: a list of dicts representing reservoirs.
            if any(any(not isinstance(x, (dict,list)) for x in d.values()) for d in obj):
                return obj
        for v in obj:
            result = _find_records(v, depth + 1)
            if result:
                return result
    elif isinstance(obj, dict):
        for key in ('data', 'result', 'results', 'reservoirs', 'dams', 'items', 'records'):
            if key in obj:
                found = _find_records(obj[key], depth + 1)
                if found:
                    return found
        for v in obj.values():
            if isinstance(v, (dict,list)):
                found = _find_records(v, depth+1)
                if found:
                    return found
    return []


def unpack_payload(payload):
    """Preserve actual upstream field names, never fabricate missing columns."""
    records = _find_records(payload)
    if records:
        frame = pd.json_normalize(records, sep='_')
    elif isinstance(payload, dict):
        frame = pd.json_normalize(payload, sep='_')
    elif isinstance(payload, list):
        frame = pd.DataFrame({'value':payload})
    else:
        raise ValueError('ไม่รู้จักรูปแบบข้อมูล API')
    if frame.empty:
        raise ValueError('API ส่งชุดข้อมูลว่าง')
    # Streamlit table rendering does not support nested dict/list directly.
    for field in frame.columns:
        if frame[field].map(lambda x:isinstance(x,(dict,list))).any():
            frame[field] = frame[field].astype(str)
    return frame


def fetch_public_rid(feed, timeout=20):
    if feed not in RID_FEEDS:
        raise ValueError('แหล่งข้อมูลไม่อยู่ในรายการที่อนุญาต')
    response = requests.get(RID_FEEDS[feed], timeout=timeout,
                            headers={'Accept':'application/json', 'User-Agent':'RID-ONE-WATER-Public-Demo/1.2'})
    response.raise_for_status()
    frame=unpack_payload(response.json())
    retrieved_at=datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
    return frame,retrieved_at
