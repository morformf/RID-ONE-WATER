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
from extras import rainfall_summary, validate_release_plan, simulate_release, season_for_month, safe_comments_table
import uuid
from datetime import datetime, timezone

BASE=Path(__file__).parent
st.set_page_config(page_title='RID ONE WATER | MVP 1.0',page_icon='🌊',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
.block-container{padding-top:1.2rem;} .stMetric{background:#edf5fb;border-radius:12px;padding:12px;}
[data-testid="stSidebar"]{background:#e8f2fa;} h1,h2,h3{color:#123b60;}
</style>''',unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def demo_data():
    s=validate_stations(pd.read_csv(BASE/'data'/'stations_demo.csv'))
    o=validate_observations(pd.read_csv(BASE/'data'/'observations_demo.csv'))
    return s,o

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
if 'tickets' not in st.session_state:st.session_state.tickets=[]
stations=st.session_state.stations; obs=st.session_state.obs

with st.sidebar:
    st.title('🌊 RID ONE WATER')
    st.caption('Integrated Water Intelligence · MVP 1.0')
    page=st.radio('เมนูหลัก',['🏠 ภาพรวมและ GIS','📡 สถานีและกราฟ','🌧️ ข้อมูลฝน','💧 เขื่อน / อ่างเก็บน้ำ','🚪 ประตูระบายน้ำ','🧪 คุณภาพน้ำ','🗺️ ผังน้ำและทิศทางการไหล','🔔 แจ้งเตือน','📣 ประชาชนแจ้งเหตุ / ข้อเสนอแนะ','🗂️ จัดการเรื่องแจ้ง (สาธิต)','📥 นำเข้าข้อมูล','📤 ส่งออกรายงาน'],label_visibility='collapsed')
    page=page.split(' ',1)[1]
    st.divider()
    st.caption('ข้อมูลตัวอย่างเป็นข้อมูลสมมติ · API ของกรมเป็นข้อมูลจากต้นทางเมื่อเชื่อมต่อสำเร็จ')
    threshold_hours=st.number_input('ข้อมูลล่าช้าหากเกิน (ชั่วโมง)',min_value=1,max_value=168,value=3)
    if st.button('คืนค่าชุดข้อมูลสาธิต',use_container_width=True):
        for key in ['stations','obs','gates','quality','rule_curve','release_plan','tickets']:
            if key in st.session_state:del st.session_state[key]
        st.rerun()

statuses=classify_status(obs,stations,threshold_hours)
st.title('🌊 RID ONE WATER')
st.caption('One Water • One Map • One Platform | ระบบสาธิตที่รวมข้อมูลน้ำและการมีส่วนร่วมของประชาชน · ไม่ใช่ระบบเตือนภัยหรือรับแจ้งเหตุทางการ')

if page=='ภาพรวมและ GIS':
    st.subheader('ภาพรวมสถานีและแผนที่ GIS')
    a,b,c,d=st.columns(4)
    a.metric('สถานีในทะเบียน',len(stations))
    b.metric('ข้อมูลทันเวลา',int((statuses.status=='ปกติ').sum()))
    c.metric('ข้อมูลล่าช้า',int((statuses.status=='ข้อมูลล่าช้า').sum()))
    d.metric('ไม่มีข้อมูล',int((statuses.status=='ไม่มีข้อมูล').sum()))
    provinces=['ทั้งหมด']+sorted(stations.province.dropna().unique().tolist())
    basin=['ทั้งหมด']+sorted(stations.basin.dropna().unique().tolist())
    x,y,z=st.columns(3)
    p=x.selectbox('จังหวัด',provinces); bsn=y.selectbox('ลุ่มน้ำ',basin)
    station_type=z.selectbox('ประเภทสถานี',['ทั้งหมด']+sorted(stations.station_type.unique().tolist()))
    show=statuses.copy()
    if p!='ทั้งหมด':show=show[show.province==p]
    if bsn!='ทั้งหมด':show=show[show.basin==bsn]
    if station_type!='ทั้งหมด':show=show[show.station_type==station_type]
    if show.empty:st.info('ไม่พบสถานีตามตัวกรอง')
    else:
        colors={'ปกติ':[20,145,110,180],'ข้อมูลล่าช้า':[240,160,50,200],'ไม่มีข้อมูล':[130,140,150,180],'เวลาไม่ถูกต้อง':[215,60,60,190]}
        show['color']=show.status.apply(lambda v:colors.get(v,[130,140,150,180]))
        st.pydeck_chart(pdk.Deck(map_style='https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
            initial_view_state=pdk.ViewState(latitude=float(show.latitude.mean()),longitude=float(show.longitude.mean()),zoom=6,pitch=0),
            layers=[pdk.Layer('ScatterplotLayer',show,get_position='[longitude, latitude]',get_fill_color='color',get_radius=7500,pickable=True,radius_min_pixels=5,radius_max_pixels=15)],
            tooltip={'html':'<b>{station_name}</b><br/>รหัส: {station_id}<br/>สถานะ: {status}<br/>แหล่ง: {source}'}),use_container_width=True)
        st.dataframe(show[['station_id','station_name','station_type','province','basin','status','source']],hide_index=True,use_container_width=True)
    st.info('สีบนแผนที่บอกความใหม่ของข้อมูล ไม่ใช่ระดับความเสี่ยงน้ำท่วม; จุดที่มี source=demo เป็นสถานีตัวอย่างสมมติ')

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
    category=st.selectbox('ประเภทข้อมูล',['ทะเบียนสถานี','ข้อมูลตรวจวัด','Rule Curve','แผนระบาย','ประตูระบายน้ำ','คุณภาพน้ำ'])
    templates={'ทะเบียนสถานี':'stations_demo.csv','ข้อมูลตรวจวัด':'observations_demo.csv','Rule Curve':'rule_curve_demo.csv','แผนระบาย':'release_plan_demo.csv','ประตูระบายน้ำ':'gates_demo.csv','คุณภาพน้ำ':'quality_demo.csv'}
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

else:
    st.subheader('ส่งออกรายงานและชุดข้อมูล')
    data={'Stations':stations,'Observations':obs,'Station_Status':statuses.drop(columns=['color','age_hours'],errors='ignore'),
          'Water_Gates':st.session_state.gates,'Water_Quality':st.session_state.quality,'Rule_Curve':st.session_state.rule_curve,'Release_Plan':st.session_state.release_plan}
    if 'rid_live' in st.session_state:data['RID_Reservoir_API']=st.session_state.rid_live
    if st.session_state.tickets:data['Citizen_Demo_Tickets']=safe_comments_table(pd.DataFrame(st.session_state.tickets))
    st.caption('เอกสารส่งออกแสดงข้อมูลจากแหล่งจริง/นำเข้า/สาธิตตาม source ของแต่ละชุด ห้ามใช้ข้อมูลสาธิตประกอบการตัดสินใจปฏิบัติการ')
    st.download_button('📗 ดาวน์โหลดรายงาน Excel',excel_bytes(data),'RID_ONE_WATER_Report.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',type='primary')
    selected=st.selectbox('เลือกชุดข้อมูลสำหรับ CSV',list(data))
    st.download_button('ดาวน์โหลด CSV',data[selected].to_csv(index=False).encode('utf-8-sig'),selected+'.csv',mime='text/csv')
    st.dataframe(data[selected].head(150),hide_index=True,use_container_width=True)

st.divider()
st.caption('RID ONE WATER Full Demo 1.1 | Prototype only · ข้อมูลสาธิตไม่ใช่ข้อมูลทางการ · API และการนำเข้าต้องเป็นไปตามสิทธิ์การใช้งาน')
