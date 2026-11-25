"""Streamlit hourly surface; all observed vs screenshot-snapshot vs uploaded labeled."""
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from hourly_core import load_hourly_upload,validate_hourly,fetch_hourly_api,as_excel,as_csv

BASE=Path(__file__).parent

@st.cache_data(ttl=3600,show_spinner=False)
def live_hourly(api_url, token):
    return fetch_hourly_api(api_url,token)

@st.cache_data(show_spinner=False)
def screenshot_snapshot():
    return validate_hourly(pd.read_csv(BASE/'data'/'hourly_ping_screenshot_2569-11-24.csv'))


def render_hourly_page():
    st.markdown('<div class="section-band">🕐 ข้อมูลน้ำท่ารายชั่วโมง (Hydro / RID)</div>', unsafe_allow_html=True)
    st.info('📌 หน้าใหม่นี้แยกข้อมูลตามแหล่งที่มา: ข้อมูลจากภาพที่ส่งมา / ไฟล์อัปโหลด / API ที่ได้รับอนุญาต และไม่ใช้ข้อมูลจำลองปลอมเป็นข้อมูลสด')
    st.caption('อ้างอิง: หน้า hyd-app-db.rid.go.th ที่แสดงตารางลุ่มน้ำปิง | การเชื่อม API สดต้องทราบ URL จริงและรูปแบบผลลัพธ์')

    choices=['ตัวอย่างจากภาพที่ผู้ใช้ส่งมา (24 พ.ย. 2569)','อัปโหลดข้อมูลรายชั่วโมง CSV / Excel','เชื่อมต่อ API ที่ได้รับอนุญาต']
    source=st.radio('แหล่งข้อมูล',choices,horizontal=True)
    df=None
    if source==choices[0]:
        df=screenshot_snapshot()
        st.warning('ข้อมูลตัวอย่างคัดค่าจากภาพหน้าจอ 24 พฤศจิกายน 2569 เฉพาะช่วง 01:00–12:00 น. ไม่ใช่ข้อมูลสด และไม่ได้ครอบคลุมทุกสถานี')
    elif source==choices[1]:
        st.caption('คอลัมน์มาตรฐาน: station_id, observed_at, water_level_m, discharge_cms (และ station_name ถ้ามี)')
        upload=st.file_uploader('อัปโหลด CSV หรือ Excel',type=['csv','xlsx','xlsm'],key='hourly_upload')
        if upload is not None:
            try: df=load_hourly_upload(upload)
            except Exception as e:st.error('อ่านไฟล์ไม่สำเร็จ: '+str(e))
        with open(BASE/'data'/'hourly_ping_screenshot_2569-11-24.csv','rb') as f:
            st.download_button('ดาวน์โหลดตัวอย่างรูปแบบ CSV',f.read(),'hourly_template.csv',mime='text/csv')
    else:
        st.caption('ยังไม่ทราบ endpoint ของเว็บไซต์ hyd-app-db.rid.go.th ที่เปิดให้เรียกโดยตรง จึงไม่สามารถยืนยันการเชื่อมต่ออัตโนมัติได้')
        st.markdown('[เอกสาร SWOC API](https://swoc-api-service.rid.go.th/api/docs/) · [เว็บไซต์ต้นทาง](https://hyd-app-db.rid.go.th/)')
        conf=st.secrets.get('RID_HOURLY_API',{})
        api_url=conf.get('url','') if isinstance(conf,dict) else ''
        api_token=conf.get('token','') if isinstance(conf,dict) else ''
        if not api_url:
            st.warning('ยังไม่ได้ตั้ง RID_HOURLY_API.url ใน Streamlit Secrets สำหรับ endpoint JSON ที่ได้รับอนุญาต')
            st.code('[RID_HOURLY_API]\nurl = "https://<host>.rid.go.th/<verified-hourly-api-path>"\ntoken = ""',language='toml')
        else:
            if st.button('ตรวจสอบข้อมูลใหม่จากต้นทาง',key='hourly_refresh'):
                live_hourly.clear()
            try:
                df=live_hourly(api_url,api_token)
                st.success('ดึงข้อมูล API ได้สำเร็จ (ข้อมูลเวลาตรวจวัดดูจากตาราง)')
            except Exception as e:
                st.error('ยังดึงข้อมูล API ไม่ได้: '+str(e))
                st.caption('ระบบจะไม่ทดแทนค่าที่โหลดไม่สำเร็จด้วยข้อมูลเก่าหรือข้อมูลสมมติ')
    if df is None or df.empty:
        st.info('เลือกแหล่งข้อมูลหรืออัปโหลดไฟล์เพื่อแสดงกราฟ')
        return

    col1,col2=st.columns([2,1])
    with col1:
        stations=sorted(df.station_id.dropna().unique().tolist())
        chosen=st.multiselect('เลือกสถานี',stations,default=stations[:min(4,len(stations))])
    with col2:
        field=st.selectbox('ประเภทข้อมูล',['ระดับน้ำ (เมตร — อ้างอิงตามต้นทาง)','อัตราการไหล (ลบ.ม./วินาที)'])
    sub=df[df.station_id.isin(chosen)].copy()
    if sub.empty:
        st.warning('กรุณาเลือกอย่างน้อยหนึ่งสถานี')
        return
    last=sub.observed_at.max()
    cols=st.columns(3)
    cols[0].metric('จำนวนสถานีที่เลือก',int(sub.station_id.nunique()))
    cols[1].metric('จำนวนค่ารายชั่วโมง',len(sub))
    cols[2].metric('เวลาตรวจวัดล่าสุด',last.strftime('%d/%m/%Y %H:%M'))
    value_col='water_level_m' if field.startswith('ระดับ') else 'discharge_cms'
    fig=go.Figure()
    for name,group in sub.groupby('station_id'):
        fig.add_trace(go.Scatter(x=group.observed_at,y=group[value_col],mode='lines+markers',name=name,connectgaps=False))
    fig.update_layout(height=400,margin=dict(l=8,r=8,t=15,b=8),xaxis_title='วันและเวลา (ประเทศไทย)',yaxis_title=field,legend=dict(orientation='h',y=-0.25))
    st.plotly_chart(fig,use_container_width=True)
    st.markdown('#### ตารางข้อมูลรายชั่วโมง')
    shown=sub.sort_values(['station_id','observed_at']).copy()
    shown['observed_at']=shown.observed_at.dt.strftime('%d/%m/%Y %H:%M')
    st.dataframe(shown,hide_index=True,use_container_width=True)
    a,b=st.columns(2)
    a.download_button('📥 ดาวน์โหลด CSV',as_csv(sub),'RID_ONE_WATER_hourly.csv',mime='text/csv',use_container_width=True)
    b.download_button('📗 ดาวน์โหลด Excel',as_excel(sub),'RID_ONE_WATER_hourly.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
    st.caption('หมายเหตุ: ระดับน้ำเป็นค่าที่ต้นทางให้มา ไม่สามารถเทียบระดับอ้างอิงต่างระบบได้จนกว่าจะยืนยัน datum/รสม./รทก. ของแต่ละสถานี')
