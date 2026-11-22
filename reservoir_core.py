"""Reservoir operations calculations for a demonstrator (not an official release plan)."""
from __future__ import annotations
import pandas as pd

CMS_DAY_TO_MCM = 0.0864


def validate_plan(df: pd.DataFrame) -> pd.DataFrame:
    required = ['date', 'inflow_cms', 'release_cms']
    if any(c not in df.columns for c in required):
        raise ValueError('ต้องมีคอลัมน์ date, inflow_cms, release_cms')
    out = df.copy()
    out['date'] = pd.to_datetime(out['date'], errors='coerce')
    if out['date'].isna().any():
        raise ValueError('วันที่ไม่ถูกต้อง')
    for col in ['inflow_cms', 'release_cms']:
        out[col] = pd.to_numeric(out[col], errors='coerce')
        if out[col].isna().any() or (out[col] < 0).any():
            raise ValueError(f'{col} ต้องเป็นตัวเลขที่ไม่ติดลบ')
    if out['date'].duplicated().any():
        raise ValueError('วันที่ในแผนซ้ำกัน')
    return out.sort_values('date').reset_index(drop=True)


def simulate_storage(plan: pd.DataFrame, initial_mcm: float, capacity_mcm: float) -> pd.DataFrame:
    """Simple daily mass balance; unmodelled losses and spillway flows omitted.

    storage[t+1] = storage[t] + (inflow_cms - release_cms)*0.0864.
    Each plan row represents a daily mean discharge in cms.
    """
    if capacity_mcm <= 0 or not 0 <= initial_mcm <= capacity_mcm:
        raise ValueError('ปริมาณน้ำเริ่มต้นต้องอยู่ระหว่าง 0 และความจุอ่าง')
    out = validate_plan(plan)
    storage = float(initial_mcm)
    values = []
    for _, row in out.iterrows():
        delta = (row['inflow_cms'] - row['release_cms']) * CMS_DAY_TO_MCM
        raw = storage + delta
        spill = max(0.0, raw - capacity_mcm)
        storage = max(0.0, min(capacity_mcm, raw))
        values.append((delta, storage, spill, raw < 0))
    out[['net_change_mcm', 'storage_mcm', 'spill_mcm', 'shortage_flag']] = pd.DataFrame(values, index=out.index)
    out['storage_pct'] = out['storage_mcm'] / capacity_mcm * 100
    out['season'] = out['date'].dt.month.map(lambda m: 'ฤดูฝน' if 5 <= m <= 10 else 'ฤดูแล้ง')
    return out


def convert_rule_curve(df: pd.DataFrame) -> pd.DataFrame:
    expected = ['month', 'upper_mcm', 'lower_mcm']
    if any(c not in df.columns for c in expected):
        raise ValueError('Rule Curve ต้องมี month, upper_mcm, lower_mcm')
    out = df[expected].copy()
    for c in expected:
        out[c] = pd.to_numeric(out[c], errors='coerce')
    if out.isna().any().any() or len(out) != 12 or set(out['month']) != set(range(1, 13)):
        raise ValueError('Rule Curve ต้องมีเดือน 1–12 ครบและค่าตัวเลขถูกต้อง')
    if (out['lower_mcm'] > out['upper_mcm']).any():
        raise ValueError('Lower Rule Curve ต้องไม่สูงกว่า Upper Rule Curve')
    return out.sort_values('month').reset_index(drop=True)


def build_excel(sheets: dict[str, pd.DataFrame]) -> bytes:
    from io import BytesIO
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine='openpyxl') as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return bio.getvalue()
