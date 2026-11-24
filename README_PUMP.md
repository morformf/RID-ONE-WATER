# RID ONE WATER 1.5 – สถานีสูบน้ำ

เพิ่มเมนู 🚰 สถานีสูบน้ำ ลงบนหน้าเว็บเดิม พร้อมแผนที่ จุดสถานี การเลือกจังหวัด/สถานี KPI กำลังสูบ จำนวนเครื่องที่เดิน กราฟเดินเครื่องรายชั่วโมง ระดับน้ำ และส่งออก CSV/Excel

## การอัปเดตเว็บไซต์เดิมบน GitHub
1. นำ `app.py` ใหม่ไปแทนไฟล์เดิม และอัปโหลด `pump_core.py` ใน root ของ repository
2. อัปโหลด `data/pumping_stations_demo.csv` และ `data/pumping_operations_demo.csv` **ภายในโฟลเดอร์ data**
3. Commit changes แล้วเปิด Streamlit URL เดิม ตรวจหน้า “🚰 สถานีสูบน้ำ”
4. `requirements.txt` เดิมยังใช้ได้ ไม่ต้องเปลี่ยน URL หรือสร้างแอปใหม่

## รูปแบบข้อมูลจริง
- ทะเบียนสถานี: `pump_id,pump_name,province,basin,latitude,longitude,purpose,total_pumps,rated_capacity_cms,source`
- ประวัติการเดินเครื่อง: `pump_id,observed_at,running_pumps,flow_cms,upstream_m,downstream_m,status,source`
- วันเวลารายชั่วโมงควรระบุ timezone เช่น `2026-11-23T15:00:00+07:00`
- `flow_cms`: อัตราสูบหน่วยลูกบาศก์เมตรต่อวินาที
- `rated_capacity_cms`: กำลังสูบติดตั้งรวมทั้งสถานี
- ระดับน้ำ `upstream_m`/`downstream_m` ต้องระบุ datum ของข้อมูลจริงเพิ่มเติมก่อนใช้งานด้านปฏิบัติการ

**ข้อจำกัด:** ข้อมูล CSV ที่แนบมีรหัส DEMO และเป็นข้อมูลจำลองเท่านั้น ไม่มีการเข้าถึงระบบเดินเครื่องสูบน้ำจริง ข้อมูลนำเข้าผ่าน Streamlit อยู่เฉพาะ session ไม่บันทึกถาวร
