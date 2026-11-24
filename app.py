"""RID ONE WATER MVP 1.0 | Streamlit dashboard.
Run: streamlit run app.py. User uploads are session-scoped, not written to disk.
"""
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
from data_utils import (STATION_COLUMNS,OBS_COLUMNS,PARAMS,load_table,validate_stations,
                        validate_observations,classify_status,make_alerts,excel_bytes)
from connectors import FEEDS,fetch_reservoir
from rid_live import RID_FEEDS,fetch_public_rid
from pump_core import PUMP_COLUMNS,PUMP_OBS_COLUMNS,validate_pump_stations,validate_pump_observations,pumping_volume_mcm
from extras import rainfall_summary, validate_release_plan, simulate_release, season_for_month, safe_comments_table
import uuid
from datetime import datetime, timezone

BASE=Path(__file__).parent
st.set_page_config(page_title='RID ONE WATER | แพลตฟอร์มข้อมูลน้ำ',page_icon='🌊',layout='wide',initial_sidebar_state='collapsed')
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"],div[data-testid="stApp"],button,input {font-family:'Noto Sans Thai',sans-serif;}
.stApp{background:#f2f8ff;color:#17395d;}
.block-container{padding-top:.4rem;max-width:1650px;padding-bottom:3rem;}
[data-testid="stHeader"]{background:transparent;height:2rem;}
[data-testid="stSidebar"]{background:#e7f2fe;}
.stMetric{background:#fff;border:1px solid #dae8f8;border-radius:14px;padding:15px;box-shadow:0 3px 13px rgba(28,88,145,.06);}
[data-testid="stMetricLabel"]{font-size:14px;color:#2d5d88;}
[data-testid="stMetricValue"]{color:#073b75;font-weight:800;}
h1,h2,h3{color:#063c73;letter-spacing:0;}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:16px;}
[data-testid="stDataFrame"]{background:#fff;border-radius:13px;overflow:hidden;}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{background:#0877dd;border-radius:12px;border:0;}
.stTabs [data-baseweb="tab"]{background:#eaf3ff;border-radius:9px;margin-right:5px;padding:8px 15px;}
.stTabs [aria-selected="true"]{background:#0874d2;color:white;}
div[data-testid="stHorizontalBlock"]{align-items:stretch;}
.hero{background:linear-gradient(105deg,#07386e 0%,#0875c4 62%,#37a4d7 100%);border-radius:16px;color:white;padding:22px 25px 18px;margin:5px 0 12px;position:relative;overflow:hidden;}
.hero:after{content:'≋  ≋  ≋';position:absolute;right:22px;bottom:-21px;font-size:90px;opacity:.13;letter-spacing:8px;}
.hero-title{font-size:36px;font-weight:800;line-height:1.1;color:white;}
.hero-sub{font-size:14px;opacity:.94;margin-top:7px;}
.hero-mark{color:#96eaff;margin-right:11px;}
.section-band{font-size:21px;font-weight:800;color:#123d6b;background:linear-gradient(90deg,#e4f2ff,rgba(228,242,255,0));border-left:5px solid #0786dc;border-radius:9px;padding:9px 13px;margin:14px 0 10px;}
.kpi-box{background:#fff;border:1px solid #dceafd;border-radius:15px;padding:15px 17px;box-shadow:0 2px 11px rgba(20,80,130,.06);min-height:112px;}
.kpi-label{font-size:13px;font-weight:600;color:#35658d;}
.kpi-value{font-size:27px;font-weight:800;color:#063f79;margin-top:4px;}
.kpi-note{font-size:11px;color:#6686a7;}
.citizen-box{background:linear-gradient(140deg,#edf7ff,#f8fcff);border:1px solid #cce4fb;border-radius:17px;padding:19px;margin:0 0 13px;}
.citizen-title{font-size:21px;font-weight:800;color:#084b89;}
.demo-note{color:#865e11;background:#fff5d8;border:1px solid #ffe1a0;border-radius:10px;padding:8px 12px;font-size:12px;margin:8px 0;}
.footnote{padding:12px 0;color:#6985a6;font-size:12px;}
@media(max-width:800px){.hero-title{font-size:26px}.block-container{padding-left:12px;padding-right:12px;}.kpi-value{font-size:22px}.section-band{font-size:18px}}
</style>""",unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def demo_data():
    s=validate_stations(pd.read_csv(BASE/'data'/'stations_demo.csv'))
    o=validate_observations(pd.read_csv(BASE/'data'/'observations_demo.csv'))
    return s,o

@st.cache_data(ttl=3600,show_spinner=False)
def cached_public_rid(feed):
    return fetch_public_rid(feed)

@st.cache_data(ttl=900,show_spinner=False)
def live_reservoir(kind):
    return fetch_reservoir(kind)

def fmt_time(ts):
    try:return pd.to_datetime(ts,utc=True).tz_convert('Asia/Bangkok').strftime('%d/%m/%Y %H:%M')
    except:return 'ไม่ระบุ'

def show_fig(df,parameter,title):
    d=df[df.parameter==parameter].copy()
    if d.empty: st.info('ไม่มีข้อมูล '+title);return
    d['เวลาไทย']=d.observed_at.dt.tz_convert('Asia/Bangkok')
    labels=dict(zip(stations.station_id,stations.station_name))
    d['สถานี']=d.station_id.map(labels).fillna(d.station_id)
    fig=px.line(d,x='เวลาไทย',y='value',color='สถานี',markers=True,
                labels={'value':PARAMS.get(parameter,parameter),'เวลาไทย':'เวลา (ประเทศไทย)'})
    fig.update_layout(height=330,margin=dict(l=10,r=10,t=25,b=10),legend=dict(orientation='h',y=-0.28))
    st.plotly_chart(fig,use_container_width=True)

stations_demo,obs_demo=demo_data()
if 'stations' not in st.session_state:st.session_state.stations=stations_demo
if 'obs' not in st.session_state:st.session_state.obs=obs_demo
if 'gates' not in st.session_state:st.session_state.gates=pd.read_csv(BASE/'data'/'gates_demo.csv')
if 'quality' not in st.session_state:st.session_state.quality=pd.read_csv(BASE/'data'/'quality_demo.csv')
if 'rule_curve' not in st.session_state:st.session_state.rule_curve=pd.read_csv(BASE/'data'/'rule_curve_demo.csv')
if 'release_plan' not in st.session_state:st.session_state.release_plan=pd.read_csv(BASE/'data'/'release_plan_demo.csv')
if 'pumps' not in st.session_state:st.session_state.pumps=validate_pump_stations(pd.read_csv(BASE/'data'/'pumping_stations_demo.csv'))
if 'pump_obs' not in st.session_state:st.session_state.pump_obs=validate_pump_observations(pd.read_csv(BASE/'data'/'pumping_operations_demo.csv'),st.session_state.pumps)
if 'tickets' not in st.session_state:st.session_state.tickets=[]
stations=st.session_state.stations; obs=st.session_state.obs

PAGES=['🏠 ภาพรวมและ GIS','📡 สถานีและกราฟ','🌧️ ข้อมูลฝน','💧 เขื่อน / อ่างเก็บน้ำ','🚪 ประตูระบายน้ำ','🚰 สถานีสูบน้ำ','🧪 คุณภาพน้ำ','🗺️ ผังน้ำและทิศทางการไหล','🔔 แจ้งเตือน','📣 ประชาชนแจ้งเหตุ / ข้อเสนอแนะ','🛰️ ข้อมูลจริงจาก RID','🗂️ จัดการเรื่องแจ้ง (สาธิต)','📥 นำเข้าข้อมูล','📤 ส่งออกรายงาน','☎️ ติดต่อกรมชลประทาน']
PRIMARY=PAGES[:9]
SECONDARY=PAGES[9:]
if 'selected_page' not in st.session_state:st.session_state.selected_page=PAGES[0]

def choose_page(p):
    st.session_state.selected_page=p

st.markdown("""<div class="hero"><div class="hero-title"><span class="hero-mark">◉</span>RID ONE WATER</div>
<div class="hero-sub">กรมชลประทาน | แพลตฟอร์มบูรณาการข้อมูลน้ำเพื่อประชาชน · Integrated Water Intelligence Platform</div></div>""",unsafe_allow_html=True)
with st.container():
    # Native navigation remains usable on mobile; overflow options are available in the More menu.
    c_nav,c_more=st.columns([5.3,1.2],gap='small')
    with c_nav:
        current=st.session_state.selected_page
        display=current if current in PRIMARY else None
        selected=st.radio('เมนูเว็บไซต์',PRIMARY,index=PRIMARY.index(display) if display else None,horizontal=True,label_visibility='collapsed',key='top_primary',on_change=lambda: choose_page(st.session_state.top_primary) if st.session_state.top_primary else None)
    with c_more:
        extra=st.selectbox('เมนูเพิ่มเติม',['เพิ่มเติม / นำเข้าข้อมูล']+SECONDARY,index=0,key='top_secondary',label_visibility='collapsed',on_change=lambda: choose_page(st.session_state.top_secondary) if st.session_state.top_secondary in SECONDARY else None)
with st.sidebar:
    st.markdown('### ⚙️ ตั้งค่า / เมนูทั้งหมด')
    page_side=st.selectbox('ไปยังหน้า',PAGES,index=PAGES.index(st.session_state.selected_page),key='sidebar_nav')
    if st.button('เปิดหน้าที่เลือก',use_container_width=True):
        choose_page(page_side);st.rerun()
    st.divider()
    st.caption('ข้อมูลจำลองสำหรับสาธิต · ข้อมูลจาก API มีสถานะและแหล่งที่มาแยกต่างหาก')
    threshold_hours=st.number_input('ข้อมูลล่าช้าหากเกิน (ชั่วโมง)',min_value=1,max_value=168,value=3)
    if st.button('คืนค่าชุดข้อมูลสาธิต',use_container_width=True):
        for key in ['stations','obs','gates','quality','rule_curve','release_plan','tickets','pumps','pump_obs']:
            if key in st.session_state:del st.session_state[key]
        st.rerun()
page=st.session_state.selected_page.split(' ',1)[1]

statuses=classify_status(obs,stations,threshold_hours)
st.caption('🔵 RID ONE WATER · ระบบแสดงข้อมูลน้ำ')

if page=='ภาพรวมและ GIS':
    st.markdown('<div class="section-band">ภาพรวมสถานการณ์น้ำทั่วประเทศ <span style="font-size:12px;color:#768da7">(ข้อมูลตัวอย่างสำหรับสาธิต)</span></div>',unsafe_allow_html=True)
    total=len(stations)
    timely=int((statuses.status=='ปกติ').sum())
    delayed=int((statuses.status=='ข้อมูลล่าช้า').sum())
    missing=int((statuses.status=='ไม่มีข้อมูล').sum())
    last_rain=obs[obs.parameter.eq('rainfall')]
    rain_max=float(last_rain.value.max()) if not last_rain.empty else 0
    for col,(icon,label,value,comment) in zip(st.columns(5,gap='small'),[
        ('🌧️','ปริมาณฝนสูงสุด',f'{rain_max:,.1f} มม.','จากข้อมูลตัวอย่าง'),
        ('🌊','สถานีโทรมาตร',f'{timely:,} / {total:,}','ประเมินจากเวลารายงาน'),
        ('🏞️','อ่างเก็บน้ำ','ดูเมนูอ่าง','สถานะและ Rule Curve'),
        ('⚠️','ข้อมูลล่าช้า',f'{delayed:,} จุด','ต้องตรวจสอบ'),
        ('📡','ไม่มีข้อมูล',f'{missing:,} จุด','ไม่มีข้อมูลตรวจวัด')]):
        with col:
            st.markdown(f'<div class="kpi-box"><div class="kpi-label">{icon} {label}</div><div class="kpi-value">{value}</div><div class="kpi-note">{comment}</div></div>',unsafe_allow_html=True)
    st.write('')
    map_col,chart_col,cit_col=st.columns([1.25,1.65,1.1],gap='medium')
    with map_col:
        st.markdown('#### 🗺️ แผนที่สถานีตรวจวัด')
        selected_province=st.selectbox('จังหวัด',['ทั้งหมด']+sorted(stations.province.dropna().unique().tolist()),key='home_province')
        filtered=statuses.copy()
        if selected_province!='ทั้งหมด':filtered=filtered[filtered.province.eq(selected_province)]
        if not filtered.empty:
            colors={'ปกติ':[12,167,104,210],'ข้อมูลล่าช้า':[250,173,36,210],'ไม่มีข้อมูล':[130,145,155,190],'เวลาไม่ถูกต้อง':[221,50,63,210]}
            filtered['color']=filtered.status.apply(lambda v:colors.get(v,[100,100,100,190]))
            st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',initial_view_state=pdk.ViewState(latitude=float(filtered.latitude.mean()),longitude=float(filtered.longitude.mean()),zoom=5.7 if selected_province=='ทั้งหมด' else 8.7),layers=[pdk.Layer('ScatterplotLayer',filtered,get_position='[longitude,latitude]',get_fill_color='color',get_radius=5000,pickable=True,radius_min_pixels=6,radius_max_pixels=15)],tooltip={'html':'<b>{station_name}</b><br/>{station_id} · {status}'}),use_container_width=True,height=400)
        st.caption('🟢 ทันเวลา  🟠 ล่าช้า  ⚪ ไม่มีข้อมูล · สีไม่ใช่เกณฑ์น้ำท่วม')
    with chart_col:
        st.markdown('#### 📈 สถานการณ์น้ำจากสถานีตัวอย่าง')
        params={'ระดับน้ำ':'water_level','ปริมาณน้ำ (Q)':'discharge','ฝน':'rainfall'}
        chosen_metric=st.radio('ค่าที่แสดง',list(params),horizontal=True,label_visibility='collapsed',key='home_metric')
        d=obs.loc[obs.parameter.eq(params[chosen_metric or 'ระดับน้ำ'])].copy()
        if len(d):
            top_ids=list(d.station_id.dropna().unique())[:3]
            d=d[d.station_id.isin(top_ids)]
            d['เวลาไทย']=d.observed_at.dt.tz_convert('Asia/Bangkok')
            d['สถานี']=d.station_id.map(dict(zip(stations.station_id,stations.station_name))).fillna(d.station_id)
            fig=px.line(d,x='เวลาไทย',y='value',color='สถานี',markers=True,labels={'value':chosen_metric,'เวลาไทย':'เวลาประเทศไทย'})
            fig.update_layout(height=400,margin=dict(l=10,r=8,t=20,b=10),legend=dict(orientation='h',y=-.3),plot_bgcolor='#ffffff',paper_bgcolor='#ffffff',font=dict(color='#14436c'))
            fig.update_traces(line=dict(width=3))
            st.plotly_chart(fig,use_container_width=True)
        else:st.info('ยังไม่มีข้อมูลสำหรับกราฟนี้')
        st.caption('เลือกข้อมูลรายชั่วโมงจริงได้เมื่อเชื่อม API TeleHydro ที่ได้รับอนุญาต')
    with cit_col:
        st.markdown("""<div class="citizen-box"><div class="citizen-title">📣 มีเรื่องแจ้งหรือเสนอแนะ?</div>
        <div style="font-size:13px;color:#51718f">ร่วมเป็นส่วนหนึ่งในการดูแลทรัพยากรน้ำ</div></div>""",unsafe_allow_html=True)
        if st.button('📸 แจ้งเหตุ / ปัญหา',use_container_width=True,type='primary',key='home_report'):
            choose_page('📣 ประชาชนแจ้งเหตุ / ข้อเสนอแนะ');st.rerun()
        if st.button('💬 แสดงความคิดเห็น',use_container_width=True,key='home_feedback'):
            choose_page('📣 ประชาชนแจ้งเหตุ / ข้อเสนอแนะ');st.rerun()
        st.markdown('#### 🔔 สถานะข้อมูลล่าสุด')
        st.info(f'สถานีที่มีข้อมูลทันเวลา: **{timely}** จุด')
        if delayed:st.warning(f'ข้อมูลล่าช้า: **{delayed}** จุด')
        if missing:st.error(f'สถานีไม่มีข้อมูล: **{missing}** จุด')
        st.info('📞 **แจ้งปัญหาด้านชลประทาน: สายด่วน 1460**')
        if st.button('☎️ ที่อยู่และช่องทางติดต่อกรม',use_container_width=True,key='home_contact'):
            choose_page('☎️ ติดต่อกรมชลประทาน');st.rerun()
    st.markdown('<div class="section-band">ข้อมูลและบริการสำหรับประชาชน</div>',unsafe_allow_html=True)
    cards=st.columns(5,gap='small')
    for col,(label,target,caption) in zip(cards,[('🏞️ อ่างเก็บน้ำ','💧 เขื่อน / อ่างเก็บน้ำ','Rule Curve · แผนระบาย · ฤดูฝน/แล้ง'),('🚪 ประตูระบายน้ำ','🚪 ประตูระบายน้ำ','ระดับเหนือน้ำ–ท้ายน้ำ'),('🚰 สถานีสูบน้ำ','🚰 สถานีสูบน้ำ','ข้อมูลกำลังสูบ · เวลาเดินเครื่อง'),('🧪 คุณภาพน้ำ','🧪 คุณภาพน้ำ','pH · DO · EC · ความเค็ม'),('🗺️ ผังน้ำ','🗺️ ผังน้ำและทิศทางการไหล','ดูทิศทางน้ำต้นน้ำ–ปลายน้ำ')]):
        with col:
            with st.container(border=True):
                st.markdown('**'+label+'**')
                st.caption(caption)
                if st.button('ดูรายละเอียด →',key='go_'+target,use_container_width=True):
                    choose_page(target);st.rerun()
    with st.expander('📍 รายชื่อและสถานะสถานีตัวอย่าง'):
        st.dataframe(statuses[['station_id','station_name','province','basin','status','source']],hide_index=True,use_container_width=True)
    st.markdown('<div class="demo-note">ข้อมูลสถานี/ตัวเลขในหน้า Dashboard เป็นข้อมูลสาธิต ไม่ใช่สถานการณ์น้ำจริงหรือประกาศเตือนภัยอย่างเป็นทางการ</div>',unsafe_allow_html=True)

elif page=='สถานีและกราฟ':
    st.subheader('ตรวจวัดระดับน้ำ ปริมาณน้ำ และฝน')
    names=dict(zip(stations.station_id,stations.station_name))
    chosen=st.multiselect('เลือกสถานี',options=list(names),default=list(names)[:3],format_func=lambda k:f'{k} — {names[k]}')
    filtered=obs[obs.station_id.isin(chosen)]
    tab1,tab2,tab3,tab4=st.tabs(['ระดับน้ำ','อัตราการไหล','ฝน','ตารางข้อมูล'])
    with tab1:show_fig(filtered,'water_level','ระดับน้ำ')
    with tab2:show_fig(filtered,'discharge','อัตราการไหล')
    with tab3:show_fig(filtered,'rainfall','ฝน')
    with tab4:st.dataframe(filtered.sort_values('observed_at',ascending=False),hide_index=True,use_container_width=True)
    st.caption('กราฟเฉพาะข้อมูลที่นำเข้าหรือสาธิต ยังไม่ได้เชื่อมค่าระดับน้ำรายสถานีแบบสดจาก RID')

elif page=='ข้อมูลฝน':
    st.subheader('🌧️ ปริมาณฝนและแผนที่สถานีฝน')
    st.info('ค่าฝนจากข้อมูลสาธิต/ข้อมูลที่นำเข้ามา ไม่ใช่ปริมาณฝนจริงจากทุกจังหวัด; ผลรวมขึ้นอยู่กับช่วงเวลาของชุดข้อมูล')
    rain=obs.loc[obs.parameter.eq('rainfall')].copy()
    if rain.empty:st.warning('ไม่มีข้อมูลฝน')
    else:
        rain['date_th']=rain.observed_at.dt.tz_convert('Asia/Bangkok').dt.date
        a,b,c=st.columns(3)
        a.metric('สถานีที่มีข้อมูลฝน',rain.station_id.nunique())
        b.metric('จำนวนระเบียนฝน',len(rain))
        c.metric('ค่าสูงสุดต่อระเบียน',f'{rain.value.max():,.1f} มม.')
        types=['ทุกสถานี']+sorted(rain.station_id.unique().tolist())
        selected=b.selectbox('เลือกสถานีฝน',types)
        r=rain if selected=='ทุกสถานี' else rain[rain.station_id==selected]
        fig=px.bar(r,x='date_th',y='value',color='station_id',labels={'date_th':'วันที่','value':'ฝน (มม.)','station_id':'สถานี'},title='ปริมาณฝนตามวันที่ของข้อมูลที่มี')
        st.plotly_chart(fig,use_container_width=True)
        summary=rainfall_summary(rain).merge(stations[['station_id','station_name','latitude','longitude','province']],on='station_id',how='left')
        st.dataframe(summary,hide_index=True,use_container_width=True)
        valid=summary.dropna(subset=['latitude','longitude'])
        if not valid.empty:st.map(valid,latitude='latitude',longitude='longitude',size=110)
        st.download_button('ดาวน์โหลดข้อมูลฝน CSV',r.to_csv(index=False).encode('utf-8-sig'),'rainfall.csv','text/csv')

elif page=='ข้อมูลจริงจาก RID':
    st.subheader('🛰️ ข้อมูลสาธารณะจากกรมชลประทาน')
    st.info('ตรวจสอบข้อมูลต้นทางใหม่ทุก 60 นาทีเมื่อมีผู้เปิดหน้าเว็บ (หรือกดรีเฟรชเอง) ไม่ได้หมายความว่าข้อมูลอ่างเก็บน้ำมีการตรวจวัดรายชั่วโมง')
    source=st.selectbox('เลือกชุดข้อมูลสาธารณะ',list(RID_FEEDS))
    st.caption('แหล่งข้อมูล: '+RID_FEEDS[source])
    if st.button('ดึงข้อมูลใหม่ทันที',key='refresh_rid_source'):
        cached_public_rid.clear()
    try:
        feed_df,retrieved_at=cached_public_rid(source)
        st.success('เชื่อมต่อและรับข้อมูลจาก API สำเร็จ')
        st.caption('เวลาที่เว็บไซต์ดึงข้อมูล: '+retrieved_at+' | โปรดตรวจวันที่รายงานในข้อมูลต้นทางแยกต่างหาก')
        st.metric('จำนวนรายการที่อ่านได้',len(feed_df))
        st.dataframe(feed_df,use_container_width=True,hide_index=True)
        st.download_button('ดาวน์โหลดข้อมูลที่ดึงได้เป็น CSV',feed_df.to_csv(index=False).encode('utf-8-sig'),file_name='rid_public_feed.csv',mime='text/csv')
        with st.expander('ดูชื่อคอลัมน์ข้อมูลจาก API'):
            st.write(feed_df.columns.tolist())
    except Exception as exc:
        st.error('ไม่สามารถโหลด API ได้ในขณะนี้: '+str(exc))
        st.warning('ไม่มีการแสดงค่าจำลองแทนข้อมูลจริงโดยอัตโนมัติ')
    st.divider()
    st.subheader('📡 ข้อมูลโทรมาตรรายชั่วโมง')
    st.warning('ยังไม่เปิดเชื่อม TeleHydro โดยตรง: ต้องยืนยัน API ที่ใช้ได้จริงและสิทธิ์เรียกข้อมูลก่อน')
    st.markdown('ดูข้อมูลต้นทาง: [TeleHydro](https://telehydro.rid.go.th/) | [เอกสาร SWOC REST API](https://swoc-api-service.rid.go.th/api/docs/)')
    st.caption('เมื่อได้รับ API รายชั่วโมงที่ได้รับอนุญาต จะเพิ่มรหัสสถานี เวลาอ่านค่า ระดับน้ำ อัตราการไหล และฝน โดยไม่สร้างค่าแทรกระหว่างชั่วโมง')

elif page=='เขื่อน / อ่างเก็บน้ำ':
    st.subheader('ข้อมูลเขื่อนและอ่างเก็บน้ำ')
    st.markdown('**เชื่อมต่อข้อมูลจริงจาก API สาธารณะกรมชลประทาน**')
    kind=st.radio('แหล่งข้อมูล',list(FEEDS),horizontal=True)
    st.caption('ที่มา: '+FEEDS[kind]+' | อัปเดตแคชทุก 15 นาที; ความใหม่ของตัวเลขขึ้นกับข้อมูลต้นทาง')
    if st.button('ดึงข้อมูลกรมชลประทาน',type='primary'):
        try:
            live=live_reservoir(kind);st.session_state['rid_live']=live;st.session_state['rid_live_kind']=kind
            st.success(f'ได้รับข้อมูล {len(live)} รายการจาก API กรมชลประทาน')
        except Exception as e:
            st.error('เชื่อม API ไม่สำเร็จหรือรูปแบบข้อมูลเปลี่ยน: '+str(e))
            st.warning('ไม่มีการแสดงข้อมูลสาธิตแทนข้อมูลจริงโดยอัตโนมัติ')
    if 'rid_live' in st.session_state and st.session_state.get('rid_live_kind')==kind:
        live=st.session_state['rid_live']
        st.dataframe(live,hide_index=True,use_container_width=True)
        st.download_button('ดาวน์โหลดข้อมูล RID CSV',live.to_csv(index=False).encode('utf-8-sig'),file_name='rid_reservoir_api.csv',mime='text/csv')
    st.divider()
    st.markdown('**กราฟ Rule Curve จากไฟล์ข้อมูล**')
    rc=st.session_state.rule_curve.copy()
    rc['date']=pd.to_datetime(rc['date'],errors='coerce');rc=rc.dropna(subset=['date'])
    if not rc.empty:
        fig=go.Figure()
        for col,label in [('storage','ปริมาณน้ำ'),('upper_rule_curve','Upper Rule Curve'),('lower_rule_curve','Lower Rule Curve')]:
            if col in rc.columns:fig.add_trace(go.Scatter(x=rc.date,y=pd.to_numeric(rc[col],errors='coerce'),mode='lines',name=label))
        fig.update_layout(height=370,xaxis_title='วันที่',yaxis_title='ล้าน ลบ.ม.',margin=dict(l=20,r=20,t=20,b=20))
        st.plotly_chart(fig,use_container_width=True)
    st.caption('เส้น Rule Curve เป็นข้อมูลที่นำเข้าหรือข้อมูลสาธิต ไม่ใช่ค่าจาก RID API โดยอัตโนมัติ')
    st.divider()
    st.subheader('📅 แผนการระบายน้ำและการจัดการน้ำตามฤดู (จำลอง)')
    st.warning('ตัวเลขแผนและน้ำเข้าเป็นข้อมูลสาธิต การปรับแผนนี้เป็นการจำลองสมดุลน้ำ ไม่ใช่แผนระบายที่อนุมัติแล้ว')
    c1,c2,c3=st.columns(3)
    capacity=c1.number_input('ความจุอ่าง (ล้าน ลบ.ม.)',min_value=1.0,value=9510.0,step=10.0)
    initial=c2.number_input('ปริมาณน้ำเริ่มต้น (ล้าน ลบ.ม.)',min_value=0.0,max_value=float(capacity),value=min(6826.0,float(capacity)),step=10.0)
    modifier=c3.slider('ปรับการระบายจากแผน (%)',-80,100,0,step=5)
    plan=st.data_editor(st.session_state.release_plan,hide_index=True,num_rows='dynamic',use_container_width=True,key='edit_release_plan')
    try:
        active=validate_release_plan(plan)
        adjusted=active.copy();adjusted['release_cms']=adjusted['release_cms']*(1+modifier/100)
        results=simulate_release(adjusted,initial,capacity)
        st.session_state.release_plan=active
        p,q,r=st.columns(3)
        p.metric('น้ำคงเหลือปลายแผน',f'{results.storage_mcm.iloc[-1]:,.1f} ล้าน ลบ.ม.')
        q.metric('สัดส่วนความจุปลายแผน',f'{results.storage_pct.iloc[-1]:.1f}%')
        r.metric('การระบายเฉลี่ย',f'{adjusted.release_cms.mean():,.1f} ลบ.ม./วินาที')
        chart=go.Figure()
        chart.add_trace(go.Scatter(x=results.date,y=results.storage_mcm,name='ปริมาณน้ำคงเหลือจำลอง',mode='lines+markers'))
        chart.update_layout(height=330,yaxis_title='ล้าน ลบ.ม.',margin=dict(l=10,r=10,t=15,b=10))
        st.plotly_chart(chart,use_container_width=True)
        left,right=st.columns(2)
        with left:
            st.success('🌧️ ฤดูฝน (พฤษภาคม–ตุลาคม)')
            st.write('ติดตามฝนและน้ำไหลเข้า ควบคุมปริมาณกักเก็บตาม Rule Curve และพิจารณาความสามารถรองรับน้ำหลาก')
        with right:
            st.info('☀️ ฤดูแล้ง (พฤศจิกายน–เมษายน)')
            st.write('สำรองน้ำเพื่ออุปโภคบริโภค เกษตรกรรม และระบบนิเวศ โดยวางแผนจัดสรรน้ำตามน้ำต้นทุน')
        st.dataframe(results,hide_index=True,use_container_width=True)
        st.download_button('ดาวน์โหลดผลจำลอง CSV',results.to_csv(index=False).encode('utf-8-sig'),'release_simulation.csv','text/csv')
    except Exception as e:st.error('ตรวจสอบแผนระบาย: '+str(e))


elif page=='ประตูระบายน้ำ':
    st.subheader('ประตูระบายน้ำและอาคารชลศาสตร์')
    st.warning('ตารางเริ่มต้นเป็นข้อมูลสาธิต ต้องนำเข้าข้อมูลที่มีสิทธิ์ใช้งานจริงจากเมนูนำเข้าข้อมูล')
    st.dataframe(st.session_state.gates,hide_index=True,use_container_width=True)
    st.caption('ค่าระยะยกบานและการระบายเป็นข้อมูลแสดงผลเท่านั้น ไม่ได้ส่งคำสั่งควบคุมอาคาร')

elif page=='สถานีสูบน้ำ':
    st.markdown('<div class="section-band">🚰 ข้อมูลสถานีสูบน้ำ</div>',unsafe_allow_html=True)
    st.warning('ข้อมูลเริ่มต้นทั้งหมดเป็นข้อมูลจำลองเพื่อทดลองระบบ ไม่ใช่สถานะเครื่องสูบหรือค่าการสูบจริงของกรมชลประทาน')
    pumps=st.session_state.pumps
    operations=st.session_state.pump_obs
    b1,b2,b3=st.columns(3)
    b1.metric('สถานีสูบน้ำในชุดข้อมูล',f'{len(pumps):,} แห่ง')
    b2.metric('เครื่องสูบที่ติดตั้ง',f'{int(pumps.total_pumps.sum()):,} เครื่อง')
    b3.metric('กำลังสูบตามแบบรวม',f'{pumps.rated_capacity_cms.sum():,.2f} ลบ.ม./วินาที')
    prov=st.selectbox('เลือกจังหวัด',['ทั้งหมด']+sorted(pumps.province.unique().tolist()),key='pump_province')
    filtered=pumps if prov=='ทั้งหมด' else pumps[pumps.province==prov]
    left,right=st.columns([1,1.6],gap='medium')
    with left:
        st.markdown('#### 📍 แผนที่ตำแหน่งสถานีสูบน้ำ')
        if len(filtered):
            st.map(filtered,latitude='latitude',longitude='longitude',size=130)
        else:st.info('ไม่มีสถานีในพื้นที่ที่เลือก')
        st.dataframe(filtered[['pump_id','pump_name','province','purpose','total_pumps','rated_capacity_cms','source']],hide_index=True,use_container_width=True)
    with right:
        options=filtered.pump_id.tolist()
        if options:
            selected=st.selectbox('เลือกสถานีสูบน้ำ',options,format_func=lambda x: f"{x} — {pumps.set_index('pump_id').loc[x,'pump_name']}")
            selected_row=pumps.set_index('pump_id').loc[selected]
            history=operations[operations.pump_id.eq(selected)].sort_values('observed_at').copy()
            st.markdown(f"#### {selected_row['pump_name']}")
            st.caption(f"จังหวัด{selected_row['province']} · ลุ่มน้ำ{selected_row['basin']} · วัตถุประสงค์: {selected_row['purpose']} · แหล่งข้อมูล: {selected_row['source']}")
            if not history.empty:
                latest=history.iloc[-1]
                k1,k2,k3=st.columns(3)
                k1.metric('เครื่องที่กำลังเดิน',f"{int(latest.running_pumps)} / {int(selected_row.total_pumps)} เครื่อง")
                k2.metric('อัตราการสูบล่าสุด',f"{latest.flow_cms:,.2f} ลบ.ม./วินาที")
                k3.metric('สถานะล่าสุด',str(latest.status))
                st.caption('เวลาตรวจวัดล่าสุด (เวลาไทย): '+fmt_time(latest.observed_at)+' · '+str(latest.source))
                c1,c2,c3=st.columns(3)
                c1.metric('ระดับน้ำต้นทาง',f"{latest.upstream_m:,.2f} ม.")
                c2.metric('ระดับน้ำปลายทาง',f"{latest.downstream_m:,.2f} ม.")
                c3.metric('ปริมาณสูบสะสมช่วงข้อมูล',f"{pumping_volume_mcm(history):,.3f} ล้าน ลบ.ม.")
                st.caption('ปริมาณสูบสะสมคำนวณจากอัตราการสูบระหว่างเวลาที่บันทึกต่อเนื่อง โดยไม่สมมติว่าทุกแหล่งข้อมูลมีความถี่เท่ากัน; หากมีช่วงข้อมูลขาดหาย ควรตรวจสอบก่อนใช้งานจริง')
                hist=history.copy();hist['เวลาไทย']=hist.observed_at.dt.tz_convert('Asia/Bangkok')
                fig=go.Figure()
                fig.add_trace(go.Scatter(x=hist['เวลาไทย'],y=hist.flow_cms,mode='lines+markers',name='อัตราการสูบ (ลบ.ม./วินาที)'))
                fig.add_trace(go.Scatter(x=hist['เวลาไทย'],y=hist.running_pumps,mode='lines',name='จำนวนเครื่องเดิน',yaxis='y2'))
                fig.update_layout(height=330,xaxis_title='เวลา (ประเทศไทย)',yaxis=dict(title='อัตราการสูบ (ลบ.ม./วินาที)'),yaxis2=dict(title='เครื่อง',overlaying='y',side='right',rangemode='tozero'),legend=dict(orientation='h',y=-.3),margin=dict(l=10,r=10,t=20,b=10))
                st.plotly_chart(fig,use_container_width=True)
                st.dataframe(hist.sort_values('observed_at',ascending=False),hide_index=True,use_container_width=True)
                st.download_button('ดาวน์โหลดประวัติการเดินเครื่อง CSV',history.to_csv(index=False).encode('utf-8-sig'),file_name=f'{selected}_pump_history.csv',mime='text/csv')
            else:st.info('ยังไม่มีข้อมูลเดินเครื่องสำหรับสถานีนี้')
    st.info('ต้องการข้อมูลรายชั่วโมงจริง: ใช้เมนูนำเข้าข้อมูล → ข้อมูลสถานีสูบน้ำ/ประวัติเดินเครื่อง โดยต้องมีสิทธิ์ใช้ข้อมูลต้นทางก่อน')

elif page=='คุณภาพน้ำ':
    st.subheader('ข้อมูลคุณภาพน้ำ')
    st.warning('ตารางเริ่มต้นเป็นข้อมูลสาธิต ค่าตรวจวัดจริงต้องนำเข้าจากหน่วยงานที่อนุญาต')
    st.dataframe(st.session_state.quality,hide_index=True,use_container_width=True)
    st.caption('เกณฑ์คุณภาพน้ำต้องพิจารณาตามวัตถุประสงค์การใช้น้ำและมาตรฐานของหน่วยงานที่เกี่ยวข้อง')

elif page=='ผังน้ำและทิศทางการไหล':
    st.subheader('🗺️ ผังน้ำและทิศทางการไหล (ตัวอย่างเชิงแนวคิด)')
    st.info('ผังนี้เป็นตัวอย่างโครงข่าย ไม่ใช่แบบจำลองทางชลศาสตร์และไม่ได้ระบุความสัมพันธ์ต้นน้ำ–ท้ายน้ำที่ผ่านการตรวจสอบ')
    from plotly.subplots import make_subplots
    names=['พื้นที่ต้นน้ำ / ฝน','อ่างเก็บน้ำ','สถานีต้นน้ำ','ประตูระบายน้ำ','สถานีท้ายน้ำ','พื้นที่ปลายน้ำ']
    x=[0,1,2,3,4,5];y=[1,1,1,1,1,1]
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=x,y=y,mode='lines+markers+text',text=names,textposition='top center',marker=dict(size=26,color=['#4aa4c9','#156ec0','#55aee7','#167a8c','#4a9fce','#53bca4']),line=dict(width=5,color='#237dc3'),hovertemplate='%{text}<extra></extra>'))
    for i in range(5):fig.add_annotation(x=i+.6,y=1,ax=i+.4,ay=1,showarrow=True,arrowhead=3,arrowsize=2,arrowwidth=2,arrowcolor='#0759b5')
    fig.update_layout(height=310,xaxis=dict(visible=False,range=[-.3,5.3]),yaxis=dict(visible=False,range=[.55,1.45]),margin=dict(l=30,r=30,t=55,b=15),showlegend=False)
    st.plotly_chart(fig,use_container_width=True)
    st.markdown('**องค์ประกอบที่ใช้งานในผังต้นแบบ**')
    st.dataframe(pd.DataFrame({'ลำดับ':[1,2,3,4,5,6],'ประเภท':names,'ทิศทาง':['ต้นน้ำ → ปลายน้ำ']*6}),hide_index=True,use_container_width=True)
    st.caption('การใช้งานจริงต้องตรวจสอบพิกัด ลำน้ำ จุดบรรจบ การเชื่อมโยงระหว่างสถานี และทิศทางไหลกับแผนที่ GIS ทางการ')

elif page=='ประชาชนแจ้งเหตุ / ข้อเสนอแนะ':
    st.subheader('📣 ช่องทางประชาชนแจ้งเหตุและแสดงความคิดเห็น')
    st.warning('แบบฟอร์มทดลองเท่านั้น ไม่ส่งข้อมูลถึงกรมชลประทานหรือหน่วยฉุกเฉิน และข้อมูลจะอยู่ใน session นี้เท่านั้น')
    with st.form('citizen_form',clear_on_submit=True):
        c1,c2=st.columns(2)
        kind=c1.selectbox('ประเภทเรื่อง',['แจ้งเหตุน้ำท่วม','แจ้งเหตุน้ำแล้ง','คลองอุดตัน','ประตูระบายน้ำ/อาคารชำรุด','คุณภาพน้ำผิดปกติ','ข้อเสนอแนะ','อื่น ๆ'])
        province=c2.text_input('จังหวัด / พื้นที่',placeholder='เช่น น่าน')
        description=st.text_area('รายละเอียด',placeholder='ระบุสถานที่ ลักษณะเหตุการณ์ และวันเวลาที่พบ')
        c3,c4=st.columns(2)
        latitude=c3.number_input('พิกัดละติจูด (ไม่บังคับ)',min_value=-90.0,max_value=90.0,value=0.0,format='%.5f')
        longitude=c4.number_input('พิกัดลองจิจูด (ไม่บังคับ)',min_value=-180.0,max_value=180.0,value=0.0,format='%.5f')
        contact=st.text_input('ช่องทางติดต่อกลับ (ไม่บังคับ)',placeholder='เฉพาะสำหรับทดสอบ ไม่เผยแพร่ต่อสาธารณะ')
        evidence=st.file_uploader('แนบภาพ JPG/PNG (ไม่บังคับ ขนาดไม่เกิน 5 MB)',type=['jpg','jpeg','png'])
        consent=st.checkbox('รับทราบว่าเป็นระบบทดลอง ไม่ใช่ช่องทางแจ้งเหตุจริง')
        submit=st.form_submit_button('บันทึกเรื่องทดลอง',type='primary')
    if submit:
        if not province.strip() or len(description.strip())<10:st.error('ระบุพื้นที่และรายละเอียดอย่างน้อย 10 ตัวอักษร')
        elif not consent:st.error('โปรดยืนยันการรับทราบข้อจำกัดของระบบทดลอง')
        elif evidence is not None and evidence.size>5*1024*1024:st.error('ไฟล์ภาพต้องไม่เกิน 5 MB')
        else:
            ticket='DEMO-'+uuid.uuid4().hex[:8].upper()
            record={'ticket':ticket,'kind':kind,'province':province.strip(),'description':description.strip(), 'contact':contact.strip(),'latitude':latitude or None,'longitude':longitude or None, 'file_name':evidence.name if evidence else '', 'created_at':datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),'status':'รับเรื่องทดลอง'}
            st.session_state.tickets.append(record)
            st.success(f'บันทึกในระบบทดลองแล้ว เลขอ้างอิง: {ticket} (ไม่ใช่เลขรับเรื่องของกรมชลประทาน)')
    if st.session_state.tickets:
        st.markdown('**ค้นหาสถานะด้วยเลขอ้างอิงทดลอง**')
        lookup=st.text_input('เลขอ้างอิง',placeholder='DEMO-XXXXXXXX')
        if lookup:
            matches=[t for t in st.session_state.tickets if t['ticket'].upper()==lookup.strip().upper()]
            if matches:st.info('สถานะ: '+matches[0]['status'])
            else:st.warning('ไม่พบเลขอ้างอิงใน session ปัจจุบัน')
    st.caption('เหตุฉุกเฉินให้ติดต่อหน่วยงานฉุกเฉินในพื้นที่โดยตรง; ห้ามใช้แบบฟอร์มนี้แทนการแจ้งเหตุจริง')

elif page=='ติดต่อกรมชลประทาน':
    st.markdown('<div class="section-band">☎️ ติดต่อกรมชลประทาน</div>',unsafe_allow_html=True)
    st.caption('ข้อมูลติดต่อจากเว็บไซต์ทางการกรมชลประทาน (ตรวจสอบ พฤศจิกายน 2569)')
    c1,c2,c3=st.columns(3,gap='medium')
    with c1:
        with st.container(border=True):
            st.markdown('### 📍 ที่ตั้งสำนักงาน')
            st.write('กรมชลประทาน (สามเสน)')
            st.write('เลขที่ 811 ถนนสามเสน แขวงถนนนครไชยศรี เขตดุสิต กรุงเทพมหานคร 10300')
            st.link_button('🗺️ เปิดแผนที่', 'https://www.google.com/maps/search/?api=1&query=กรมชลประทาน+สามเสน',use_container_width=True)
    with c2:
        with st.container(border=True):
            st.markdown('### ☎️ โทรศัพท์')
            st.markdown('**สำนักงาน:** 02-241-0020 ถึง 29')
            st.markdown('**สายด่วนกรมชลประทาน: 1460**')
            st.link_button('📞 โทรสายด่วน 1460','tel:1460',use_container_width=True)
            st.caption('หากอุปกรณ์รองรับ สามารถกดโทรออกได้โดยตรง')
    with c3:
        with st.container(border=True):
            st.markdown('### ✉️ ออนไลน์')
            st.write('อีเมลสารบรรณ: saraban@rid.go.th')
            st.link_button('✉️ ส่งอีเมล','mailto:saraban@rid.go.th',use_container_width=True)
            st.link_button('🌐 เว็บไซต์กรมชลประทาน','https://www.rid.go.th/',use_container_width=True)
    st.info('สำหรับแจ้งปัญหาด้านน้ำ สามารถติดต่อสายด่วนกรมชลประทาน 1460 ได้โดยตรง')
    st.warning('แบบฟอร์มแจ้งเหตุภายใน RID ONE WATER เป็นเพียงระบบทดลอง ยังไม่ได้ส่งเรื่องถึงกรมชลประทาน หากต้องการแจ้งเหตุจริงให้ใช้ช่องทางทางการข้างต้น')
    st.caption('แหล่งอ้างอิง: https://www.rid.go.th/th และ https://www.rid.go.th/th/rid_news/29013')

elif page=='จัดการเรื่องแจ้ง (สาธิต)':
    st.subheader('🗂️ เจ้าหน้าที่: สาธิตจัดการเรื่องแจ้ง')
    st.warning('ส่วนนี้ไม่มีระบบเข้าสู่ระบบหรือกำหนดสิทธิ์ ห้ามใช้กับข้อมูลจริงหรือเผยแพร่ข้อมูลส่วนบุคคล')
    if not st.session_state.tickets:st.info('ยังไม่มีเรื่องทดลองใน session นี้ สามารถไปกรอกที่เมนูประชาชนแจ้งเหตุ')
    else:
        reports=pd.DataFrame(st.session_state.tickets)
        st.dataframe(safe_comments_table(reports),hide_index=True,use_container_width=True)
        chosen=st.selectbox('เลือกรายการเพื่อปรับสถานะทดลอง',[t['ticket'] for t in st.session_state.tickets])
        record=next(t for t in st.session_state.tickets if t['ticket']==chosen)
        state=st.selectbox('สถานะการดำเนินงาน',['รับเรื่องทดลอง','กำลังตรวจสอบ','ส่งต่อหน่วยงาน','ดำเนินการแล้ว'],index=['รับเรื่องทดลอง','กำลังตรวจสอบ','ส่งต่อหน่วยงาน','ดำเนินการแล้ว'].index(record['status']))
        if st.button('ปรับสถานะใน session'):record['status']=state;st.success('ปรับสถานะทดลองแล้ว')
        st.caption('เพื่อเปิดรับเรื่องจริงต้องมีฐานข้อมูลถาวร ระบบยืนยันตัวตนเจ้าหน้าที่ สิทธิ์ผู้ใช้ นโยบายคุ้มครองข้อมูล และการป้องกันสแปม')

elif page=='แจ้งเตือน':
    st.subheader('สถานะข้อมูลและการแจ้งเตือนตัวอย่าง')
    st.caption('เกณฑ์ที่ผู้ใช้ตั้งเป็นเกณฑ์สาธิต ไม่ใช่เกณฑ์เตือนภัยอย่างเป็นทางการ')
    c1,c2,c3=st.columns(3)
    water_level_limit=c1.number_input('ระดับน้ำสูงกว่า (เมตร)',value=5.0,step=0.5)
    discharge_limit=c2.number_input('อัตราการไหลสูงกว่า (ลบ.ม./วินาที)',value=500.0,step=50.0)
    rainfall_limit=c3.number_input('ฝนรายระเบียนสูงกว่า (มม.)',value=30.0,step=5.0)
    alert_df=make_alerts(statuses,obs,{'water_level':water_level_limit,'discharge':discharge_limit,'rainfall':rainfall_limit})
    st.metric('จำนวนรายการแจ้งเตือน',len(alert_df))
    if alert_df.empty:st.success('ไม่มีรายการตามเกณฑ์ที่ตั้งไว้')
    else:st.dataframe(alert_df,hide_index=True,use_container_width=True)

elif page=='นำเข้าข้อมูล':
    st.subheader('นำเข้าข้อมูล CSV / Excel')
    st.info('อัปโหลดข้อมูลจะเก็บไว้เฉพาะ session ปัจจุบัน ยังไม่มีฐานข้อมูลถาวรหรือระบบบัญชีผู้ใช้')
    category=st.selectbox('ประเภทข้อมูล',['ทะเบียนสถานี','ข้อมูลตรวจวัด','Rule Curve','แผนระบาย','ประตูระบายน้ำ','สถานีสูบน้ำ','ประวัติเดินเครื่องสูบน้ำ','คุณภาพน้ำ'])
    templates={'ทะเบียนสถานี':'stations_demo.csv','ข้อมูลตรวจวัด':'observations_demo.csv','Rule Curve':'rule_curve_demo.csv','แผนระบาย':'release_plan_demo.csv','ประตูระบายน้ำ':'gates_demo.csv','สถานีสูบน้ำ':'pumping_stations_demo.csv','ประวัติเดินเครื่องสูบน้ำ':'pumping_operations_demo.csv','คุณภาพน้ำ':'quality_demo.csv'}
    fn=templates[category]
    st.download_button('ดาวน์โหลดตัวอย่างรูปแบบไฟล์',data=(BASE/'data'/fn).read_bytes(),file_name=fn,mime='text/csv')
    file=st.file_uploader('อัปโหลด CSV / XLSX',type=['csv','xlsx','xls'])
    if file and st.button('ตรวจสอบและนำเข้าข้อมูล',type='primary'):
        try:
            frame=load_table(file)
            if category=='ทะเบียนสถานี':
                new=validate_stations(frame);st.session_state.stations=pd.concat([st.session_state.stations,new]).drop_duplicates('station_id',keep='last').reset_index(drop=True)
            elif category=='ข้อมูลตรวจวัด':
                new=validate_observations(frame)
                known=set(st.session_state.stations.station_id)
                if not set(new.station_id).issubset(known):raise ValueError('พบ station_id ที่ยังไม่มีในทะเบียน: '+', '.join(sorted(set(new.station_id)-known)))
                new['source']='user_import'
                st.session_state.obs=pd.concat([st.session_state.obs,new]).drop_duplicates(['station_id','observed_at','parameter'],keep='last').reset_index(drop=True)
            elif category=='Rule Curve':
                needed={'date','storage','upper_rule_curve','lower_rule_curve'}
                if not needed.issubset(frame.columns):raise ValueError('Rule Curve ต้องมี: '+', '.join(sorted(needed)))
                frame['date']=pd.to_datetime(frame.date,errors='coerce');frame=frame.dropna(subset=['date'])
                if frame.empty:raise ValueError('วันที่ไม่ถูกต้อง')
                for col in needed-{'date'}:frame[col]=pd.to_numeric(frame[col],errors='coerce')
                st.session_state.rule_curve=frame
            elif category=='แผนระบาย':
                st.session_state.release_plan=validate_release_plan(frame)
            elif category=='ประตูระบายน้ำ':
                need=set(st.session_state.gates.columns)
                if not need.issubset(frame.columns):raise ValueError('คอลัมน์ไม่ครบ: '+', '.join(sorted(need)))
                st.session_state.gates=frame[list(st.session_state.gates.columns)]
            elif category=='สถานีสูบน้ำ':
                st.session_state.pumps=validate_pump_stations(frame)
                st.session_state.pump_obs=st.session_state.pump_obs[st.session_state.pump_obs.pump_id.isin(st.session_state.pumps.pump_id)].copy()
            elif category=='ประวัติเดินเครื่องสูบน้ำ':
                new=validate_pump_observations(frame,st.session_state.pumps)
                st.session_state.pump_obs=pd.concat([st.session_state.pump_obs,new],ignore_index=True).sort_values('observed_at').drop_duplicates(['pump_id','observed_at'],keep='last').reset_index(drop=True)
            else:
                need=set(st.session_state.quality.columns)
                if not need.issubset(frame.columns):raise ValueError('คอลัมน์ไม่ครบ: '+', '.join(sorted(need)))
                st.session_state.quality=frame[list(st.session_state.quality.columns)]
            st.success('นำเข้าและตรวจสอบรูปแบบไฟล์สำเร็จ สามารถไปดูข้อมูลในหน้าที่เกี่ยวข้องได้')
        except Exception as e:st.error(str(e))
    st.markdown('**คอลัมน์มาตรฐาน**')
    if category=='ทะเบียนสถานี':st.code(', '.join(STATION_COLUMNS))
    if category=='ข้อมูลตรวจวัด':st.code(', '.join(OBS_COLUMNS))
    if category=='Rule Curve':st.code('date, storage, upper_rule_curve, lower_rule_curve')
    if category=='แผนระบาย':st.code('date, inflow_cms, release_cms')
    if category=='สถานีสูบน้ำ':st.code(', '.join(PUMP_COLUMNS))
    if category=='ประวัติเดินเครื่องสูบน้ำ':st.code(', '.join(PUMP_OBS_COLUMNS))

else:
    st.subheader('ส่งออกรายงานและชุดข้อมูล')
    data={'Stations':stations,'Observations':obs,'Station_Status':statuses.drop(columns=['color','age_hours'],errors='ignore'),
          'Water_Gates':st.session_state.gates,'Pumping_Stations':st.session_state.pumps,'Pump_Operations':st.session_state.pump_obs,'Water_Quality':st.session_state.quality,'Rule_Curve':st.session_state.rule_curve,'Release_Plan':st.session_state.release_plan}
    if 'rid_live' in st.session_state:data['RID_Reservoir_API']=st.session_state.rid_live
    if st.session_state.tickets:data['Citizen_Demo_Tickets']=safe_comments_table(pd.DataFrame(st.session_state.tickets))
    st.caption('เอกสารส่งออกแสดงข้อมูลจากแหล่งจริง/นำเข้า/สาธิตตาม source ของแต่ละชุด ห้ามใช้ข้อมูลสาธิตประกอบการตัดสินใจปฏิบัติการ')
    st.download_button('📗 ดาวน์โหลดรายงาน Excel',excel_bytes(data),'RID_ONE_WATER_Report.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',type='primary')
    selected=st.selectbox('เลือกชุดข้อมูลสำหรับ CSV',list(data))
    st.download_button('ดาวน์โหลด CSV',data[selected].to_csv(index=False).encode('utf-8-sig'),selected+'.csv',mime='text/csv')
    st.dataframe(data[selected].head(150),hide_index=True,use_container_width=True)

st.divider()
st.markdown('''<div style="background:#e4f1ff;border:1px solid #c8ddf5;padding:16px;border-radius:13px;color:#164575;margin-top:10px;font-size:13px">
<strong>☎️ ติดต่อกรมชลประทาน</strong> · 811 ถนนสามเสน แขวงถนนนครไชยศรี เขตดุสิต กรุงเทพฯ 10300<br>
โทร. 02-241-0020 ถึง 29 · <strong>สายด่วน 1460</strong> · <a href="mailto:saraban@rid.go.th">saraban@rid.go.th</a> · <a href="https://www.rid.go.th/" target="_blank">เว็บไซต์ทางการ</a></div>''',unsafe_allow_html=True)
st.caption('RID ONE WATER Full Demo UI 1.5 | Prototype only · ข้อมูลสาธิตไม่ใช่ข้อมูลทางการ · ช่องแจ้งเหตุภายในเว็บไม่ได้ส่งถึงกรม')
