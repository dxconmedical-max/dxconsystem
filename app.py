import os
import sqlite3
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
DB_FILE = "dxcon_medical.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Bảng tài khoản (Đầy đủ phân quyền y tế rộng)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            partner TEXT,
            role TEXT,
            status TEXT DEFAULT 'Đang hoạt động'
        )
    ''')
    
    # 2. Bảng quản lý hợp đồng đối tác B2B
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contracts (
            id TEXT PRIMARY KEY,
            partner_name TEXT NOT NULL,
            volume INTEGER DEFAULT 0,
            discount REAL DEFAULT 0.0,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'Đang hoạt động'
        )
    ''')
    
    # 3. Bảng CRM bệnh nhân (Tích hợp SID, đơn thuốc, lịch hẹn, bác sĩ dặn)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crm_patients (
            sid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            segment TEXT DEFAULT 'Tiềm năng',
            last_interaction TEXT,
            chosen_lab TEXT,
            prescription_path TEXT,
            doctor_notes TEXT,
            revisit_date TEXT
        )
    ''')
    
    # 4. Bảng Logistics IoT vận chuyển mẫu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS iot_logistics (
            trip_id TEXT PRIMARY KEY,
            driver_name TEXT NOT NULL,
            driver_phone TEXT,
            box_code TEXT,
            status TEXT DEFAULT 'Đã điều phối xe',
            sid TEXT,
            zalo_msg TEXT
        )
    ''')
    
    # 5. Bảng lịch trình thu mẫu cố định B2B
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS b2b_fixed_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_name TEXT NOT NULL,
            pickup_time TEXT NOT NULL,
            trips_per_day INTEGER DEFAULT 1,
            route_note TEXT,
            assigned_driver TEXT
        )
    ''')
    
    # 6. Bảng danh mục xét nghiệm niêm yết
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tests_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            price INTEGER DEFAULT 0,
            eta TEXT
        )
    ''')
    
    # Tạo dữ liệu bảng giá mẫu nếu trống
    cursor.execute("SELECT COUNT(*) FROM tests_catalog")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO tests_catalog (name, price, eta) VALUES ('Xét nghiệm Công thức máu', 250000, '2 giờ')")
        cursor.execute("INSERT INTO tests_catalog (name, price, eta) VALUES ('Xét nghiệm Đường huyết (Glucose)', 120000, '1.5 giờ')")
        cursor.execute("INSERT INTO tests_catalog (name, price, eta) VALUES ('Gói tổng quát chuyên sâu', 1200000, '3 giờ')")
        
    conn.commit()
    conn.close()

init_db()

# --- TRANG CHỦ & TRA CỨU SID ---
@app.route('/')
def guest_portal():
    conn = get_db_connection()
    tests = conn.execute("SELECT * FROM tests_catalog").fetchall()
    
    search_sid = request.args.get('search_sid', '').strip()
    patient_info = None
    if search_sid:
        patient_info = conn.execute("SELECT * FROM crm_patients WHERE sid = ?", (search_sid,)).fetchone()
        
    conn.close()
    return render_template('index.html', tests=tests, patient_info=patient_info, search_sid=search_sid)

@app.route('/api/guest/book', methods=['POST'])
def guest_book_appointment():
    name = request.form.get('guest_name')
    phone = request.form.get('guest_phone')
    service_type = request.form.get('service_type')
    test_name = request.form.get('chosen_test')
    lab_facility = request.form.get('chosen_lab')
    address = request.form.get('guest_address', 'Đến trực tiếp phòng Lab')

    if name and phone:
        sid = f"SID{datetime.now().strftime('%m%d%H%M%S')}"
        trip_id = f"TRIP_{datetime.now().strftime('%M%S')}"
        
        crm_address_text = f"🛵 Tại nhà: {address}" if service_type == "at_home" else f"🏥 Tại Lab: {lab_facility}"
        logistics_status = "● Đơn lấy mẫu lẻ tại nhà" if service_type == "at_home" else "● Đơn hẹn tại phòng Lab"
        
        raw_msg = f"[ĐƠN MỚI]\nMã SID: {sid}\nKhách hàng: {name}\nSĐT: {phone}\nĐịa chỉ: {address}"
        encoded_msg = urllib.parse.quote(raw_msg)
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO crm_patients (sid, name, phone, address, last_interaction, chosen_lab)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (sid, name, phone, crm_address_text, f"Đăng ký: {test_name}", lab_facility))
        
        conn.execute('''
            INSERT INTO iot_logistics (trip_id, driver_name, driver_phone, box_code, status, sid, zalo_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (trip_id, "Tài xế Trực ban", "0976791449", "IoT-BOX-01", logistics_status, sid, encoded_msg))
        
        conn.commit()
        conn.close()
        return redirect(url_for('guest_portal', search_sid=sid))
    return redirect(url_for('guest_portal'))

# --- PHÂN HỆ BÁC SĨ (DOCTOR PORTAL) ---
@app.route('/doctor')
def doctor_portal():
    conn = get_db_connection()
    patients = conn.execute("SELECT * FROM crm_patients").fetchall()
    conn.close()
    return render_template('doctor.html', patients=patients)

@app.route('/api/doctor/update', methods=['POST'])
def doctor_update_patient():
    sid = request.form.get('sid')
    notes = request.form.get('doctor_notes')
    revisit = request.form.get('revisit_date')
    prescription = request.form.get('prescription_text')
    
    if sid:
        conn = get_db_connection()
        conn.execute('''
            UPDATE crm_patients 
            SET doctor_notes = ?, revisit_date = ?, prescription_path = ?, last_interaction = 'Bác sĩ đã lên toa & hẹn lịch'
            WHERE sid = ?
        ''', (notes, revisit, prescription, sid))
        conn.commit()
        conn.close()
    return redirect(url_for('doctor_portal'))

# --- TRANG QUẢN TRỊ ADMIN (Khôi phục toàn bộ Module trước) ---
@app.route('/admin')
def admin_panel():
    conn = get_db_connection()
    accounts = conn.execute("SELECT * FROM accounts").fetchall()
    contracts = conn.execute("SELECT * FROM contracts").fetchall()
    crm_patients = conn.execute("SELECT * FROM crm_patients").fetchall()
    iot_logistics = conn.execute("SELECT * FROM iot_logistics").fetchall()
    fixed_schedules = conn.execute("SELECT * FROM b2b_fixed_schedules").fetchall()
    tests_catalog = conn.execute("SELECT * FROM tests_catalog").fetchall()
    
    # Lấy tài xế để chọn động
    drivers = conn.execute("SELECT * FROM accounts WHERE role = 'Tài xế Logistics'").fetchall()
    conn.close()
    return render_template('admin.html', accounts=accounts, contracts=contracts, 
                           crm_patients=crm_patients, iot_logistics=iot_logistics, 
                           fixed_schedules=fixed_schedules, tests_catalog=tests_catalog, drivers=drivers)

@app.route('/api/account/add', methods=['POST'])
def add_account():
    username = request.form.get('username')
    partner = request.form.get('partner')
    role = request.form.get('role')
    if username:
        try:
            conn = get_db_connection()
            conn.execute("INSERT INTO accounts (username, partner, role) VALUES (?, ?, ?)", (username, partner, role))
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            pass
    return redirect(url_for('admin_panel'))

@app.route('/api/contract/add', methods=['POST'])
def add_contract():
    hd_id = request.form.get('hd_id')
    partner_name = request.form.get('partner_name')
    volume = request.form.get('volume', 0)
    discount = request.form.get('discount', 0.0)
    if hd_id and partner_name:
        conn = get_db_connection()
        conn.execute('''
            INSERT OR REPLACE INTO contracts (id, partner_name, volume, discount)
            VALUES (?, ?, ?, ?)
        ''', (hd_id, partner_name, int(volume or 0), float(discount or 0.0)))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/tests/add', methods=['POST'])
def add_single_test():
    name = request.form.get('name')
    price = request.form.get('price', 0)
    eta = request.form.get('eta', '2 giờ')
    if name:
        conn = get_db_connection()
        conn.execute('INSERT OR REPLACE INTO tests_catalog (name, price, eta) VALUES (?, ?, ?)', (name, int(price or 0), eta))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/logistics/update_driver', methods=['POST'])
def update_driver_logistics():
    trip_id = request.form.get('trip_id')
    driver_name = request.form.get('driver_name')
    if trip_id and driver_name:
        conn = get_db_connection()
        conn.execute("UPDATE iot_logistics SET driver_name = ?, status = 'Đã cập nhật tài xế trực' WHERE trip_id = ?", (driver_name, trip_id))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/schedule/add', methods=['POST'])
def add_fixed_schedule():
    partner_name = request.form.get('partner_name')
    pickup_time = request.form.get('pickup_time')
    trips_per_day = request.form.get('trips_per_day', 1)
    assigned_driver = request.form.get('assigned_driver', 'Chưa chỉ định')
    if partner_name and pickup_time:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO b2b_fixed_schedules (partner_name, pickup_time, trips_per_day, assigned_driver)
            VALUES (?, ?, ?, ?)
        ''', (partner_name, pickup_time, int(trips_per_day or 1), assigned_driver))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
