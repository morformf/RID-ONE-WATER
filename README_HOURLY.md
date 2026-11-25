# RID ONE WATER 1.6 — น้ำท่ารายชั่วโมง

## เพิ่มอะไร
- เมนู **🕐 น้ำท่ารายชั่วโมง** (ในเมนูเพิ่มเติมหรือแถบด้านข้าง)
- เลือกสถานี P.20, P.75, P.92, P.4A จากภาพตัวอย่างวันที่ 24 พ.ย. 2569
- กราฟระดับน้ำและอัตราการไหลรายชั่วโมง, ตาราง, CSV/Excel
- อัปโหลด CSV/Excel ของข้อมูลรายชั่วโมงจริง
- ตัวเชื่อมต่อ JSON API ที่กำหนดผ่าน Streamlit secrets (ยังไม่สามารถยืนยัน URL API ที่แน่นอนได้)

## วิธีอัปเดตบน GitHub Repository เดิม
1. ใช้ **ไฟล์ PATCH** เพิ่ม/แทนที่: `app.py`, `hourly_core.py`, `hourly_page.py`, `data/hourly_ping_screenshot_2569-11-24.csv` และ `README_HOURLY.md` โดยรักษาเส้นทางโฟลเดอร์ `data/` ไว้
2. **ห้ามลบ** ไฟล์เดิมอื่น ๆ โดยเฉพาะ `pump_core.py`, `rid_live.py`, `extras.py`, `requirements.txt` และ `data/` เดิม
3. Commit changes แล้ว Streamlit Community Cloud จะ redeploy จาก GitHub
4. เข้าที่ `https://rid-one-water.streamlit.app/` เปิดเมนูเพิ่มเติม → น้ำท่ารายชั่วโมง

## การเชื่อม API จริง
ข้อมูลจากภาพในขณะนี้ **ไม่ใช่ข้อมูลสด** และไม่ใช่ API ที่ตรวจสอบแล้ว เว็บไซต์ hyd-app-db.rid.go.th อาจสร้างตารางผ่าน JavaScript หรือ endpoint ภายใน ต้องขอข้อมูล endpoint ที่อนุญาตให้เชื่อมโยงก่อน

หากได้รับ JSON endpoint ที่มีรายการ `data` หรือ `records` และแต่ละรายการประกอบด้วย:

```
station_id, observed_at, water_level_m, discharge_cms
```

สามารถตั้งค่าใน Streamlit App settings > Secrets:

```toml
[RID_HOURLY_API]
url = "https://<verified-host>.rid.go.th/<verified-path>"
token = ""
```

ตัวเชื่อมต่อจำกัดเฉพาะ HTTPS ใต้ `rid.go.th`; ต้องแก้ field mappings หากข้อมูลจริงใช้ชื่อคอลัมน์คนละแบบ **ห้ามเปิดเผย token ใน GitHub**

ข้อมูล CSV ที่อัปโหลดแสดงเฉพาะในเซสชันของผู้เปิดเว็บ ไม่เขียนลงฐานข้อมูลกลาง

## ข้อมูลตัวอย่าง
ตาราง CSV จาก **ภาพหน้าจอที่ผู้ใช้ส่งมา** วันที่ 24 พ.ย. 2569 เวลา 01:00–12:00 น. รวม 4 สถานี 48 แถว; ใช้เพื่อทดลองหน้าจอเท่านั้น ตัวเลขยังไม่ได้ตรวจสอบย้อนกับฐานข้อมูลกรมโดยตรง

## การทดสอบ
- compileall ผ่าน
- pytest ชุดเดิม 8 รายการผ่าน
- ทดสอบอ่านข้อมูลตัวอย่าง และส่งออก CSV/Excel ผ่าน
- ยังไม่ได้ทดลอง UI บน Streamlit Cloud หรือยืนยันเชื่อม endpoint รายชั่วโมงจริง
