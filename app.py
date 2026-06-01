import os
import io
import csv
import sqlite3
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory

app = Flask(__name__)
DB_FILE = "dxcon_medical.db"
UPLOAD_FOLDER = "storage_contracts"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Tai khoan doi tac
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            partner TEXT,
            role TEXT,
            status TEXT DEFAULT 'Đang hoạt động'
        )
    ''')
    
    # 2. Hop dong B2B
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contracts (
            id TEXT PRIMARY KEY,
            partner_name TEXT NOT NULL,
            volume INTEGER DEFAULT 0,
            discount REAL DEFAULT 0.0,
            start_date TEXT,
            end_date TEXT,
            file_path TEXT,
            status TEXT DEFAULT 'Chờ duyệt'
        )
    ''')
    
    # 3. CRM Benh nhan vang lai
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crm_patients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            segment TEXT DEFAULT 'Tiềm năng',
            last_interaction TEXT,
            chosen_lab TEXT
        )
    ''')
    
    # 4. IoT Dieu phoi van chuyen
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS iot_logistics (
            trip_id TEXT PRIMARY KEY,
            driver_name TEXT NOT NULL,
            driver_phone TEXT,
            box_code TEXT,
            status TEXT DEFAULT 'Đã điều phối xe',
            zalo_msg TEXT
        )
    ''')
    
    # 5. Lich trinh Thu mau B2B Co dinh
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS b2b_fixed_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_name TEXT NOT NULL,
            pickup_time TEXT NOT NULL,
            trips_per_day INTEGER DEFAULT 1,
            route_note TEXT,
            assigned_driver TEXT DEFAULT 'Tài xế Tuyến cố định'
        )
    ''')
    
    # 6. Danh muc xet nghiem
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tests_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT,
            tube_type TEXT,
            storage TEXT,
            price INTEGER DEFAULT 0,
            function TEXT,
            eta TEXT,
            lab TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ================= GIAO DIEN PORTAL KHACH VANG LAI =================
@app.route('/')
def guest_portal():
    conn = get_db_connection()
    tests = conn.execute("SELECT * FROM tests_catalog").fetchall()
    conn.close()
    return render_template('index.html', tests=tests)

@app.route('/api/guest/book', methods=['POST'])
def guest_book_appointment():
    name = request.form.get('guest_name')
    phone = request.form.get('guest_phone')
    service_type = request.form.get('service_type')
    test_name = request.form.get('chosen_test')
    lab_facility = request.form.get('chosen_lab')
    
    if service_type == "at_home":
        address = request.form.get('guest_address')
        crm_address_text = f"🛵 Tại nhà: {address}"
        logistics_status = "● Đơn lấy mẫu tại nhà"
        raw_msg = f"[ĐIỀU PHỐI TẠI NHÀ]\nKhách hàng: {name}\nSĐT: {phone}\nĐịa chỉ: {address}\nGói XN: {test_name}\nGiao về: {lab_facility}"
    else:
        address = "Khách đến trực tiếp phòng Lab"
        crm_address_text = f"🏥 Đến trực tiếp: {lab_facility}"
        logistics_status = "● Đơn hẹn tại phòng Lab"
        raw_msg = f"[LỊCH HẸN TẠI LAB]\nKhách hàng: {name}\nSĐT: {phone}\nĐịa điểm: {lab_facility}\nGói XN: {test_name}\n-> Tài xế/Lab chuẩn bị tiếp đón mẫu."

    if name and phone:
        new_bn_id = f"BN_{datetime.now().strftime('%M%S')}"
        encoded_msg = urllib.parse.quote(raw_msg)
        trip_id = f"TRIP_{datetime.now().strftime('%M%S')}"
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO crm_patients (id, name, phone, address, last_interaction, chosen_lab)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (new_bn_id, name, phone, crm_address_text, f"Đặt lịch gói: {test_name}", lab_facility))
        
        conn.execute('''
            INSERT INTO iot_logistics (trip_id, driver_name, driver_phone, box_code, status, zalo_msg)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (trip_id, "Tài xế Trực ban", "0976791449", "001HCM010626", logistics_status, encoded_msg))
        
        conn.commit()
        tests = conn.execute("SELECT * FROM tests_catalog").fetchall()
        conn.close()
        return render_template('index.html', tests=tests, success_msg="🎉 Đăng ký lịch hẹn thành công! Đơn hàng phát sinh đã được đẩy sang danh sách điều phối xe của tài xế.")
    return redirect(url_for('guest_portal'))

# ================= GIAO DIEN TRANG QUAN TRI ADMIN =================
@app.route('/admin')
def admin_panel():
    conn = get_db_connection()
    accounts = conn.execute("SELECT * FROM accounts").fetchall()
    contracts = conn.execute("SELECT * FROM contracts").fetchall()
    crm_patients = conn.execute("SELECT * FROM crm_patients").fetchall()
    iot_logistics = conn.execute("SELECT * FROM iot_logistics").fetchall()
    tests_catalog = conn.execute("SELECT * FROM tests_catalog").fetchall()
    fixed_schedules = conn.execute("SELECT * FROM b2b_fixed_schedules ORDER BY pickup_time ASC").fetchall()
    conn.close()
    return render_template(
        'admin.html', accounts=accounts, contracts=contracts,
        crm_patients=crm_patients, iot_logistics=iot_logistics, 
        tests_catalog=tests_catalog, fixed_schedules=fixed_schedules
    )

@app.route('/api/schedule/add', methods=['POST'])
def add_fixed_schedule():
    partner_name = request.form.get('partner_name')
    pickup_time = request.form.get('pickup_time')
    trips_per_day = request.form.get('trips_per_day', 1)
    route_note = request.form.get('route_note')
    assigned_driver = request.form.get('assigned_driver')
    
    if partner_name and pickup_time:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO b2b_fixed_schedules (partner_name, pickup_time, trips_per_day, route_note, assigned_driver)
            VALUES (?, ?, ?, ?, ?)
        ''', (partner_name, pickup_time, int(trips_per_day), route_note, assigned_driver))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/schedule/delete/<int:schedule_id>', methods=['POST'])
def delete_schedule(schedule_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM b2b_fixed_schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/contract/add', methods=['POST'])
def add_contract():
    hd_id = request.form.get('hd_id')
    partner_name = request.form.get('partner_name')
    volume = request.form.get('volume
