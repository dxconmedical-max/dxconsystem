import os
import sqlite3
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = "dxcon_super_secure_key_production_2026_v3"
DB_FILE = "dxcon_medical_v3.db"

UPLOAD_FOLDER = 'uploads'
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
    
    # Tài khoản hệ thống
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            partner TEXT,
            role TEXT NOT NULL,
            status TEXT DEFAULT 'Đang hoạt động'
        )
    ''')
    
    # Đối tác B2B / Phòng Lab liên kết
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contracts (
            id TEXT PRIMARY KEY,
            partner_name TEXT NOT NULL,
            discount REAL DEFAULT 0.0,
            contract_file TEXT,
            test_list_file TEXT,
            lab_result_url TEXT,       
            lab_account_shared TEXT,   
            status TEXT DEFAULT 'Đang hoạt động'
        )
    ''')
    
    # CRM Quản lý bệnh nhân
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crm_patients (
            sid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            chosen_lab TEXT,           
            lab_patient_barcode TEXT,  
            prescription_path TEXT,
            doctor_notes TEXT,
            revisit_date TEXT,
            clinic_owner TEXT DEFAULT 'Tự do',
            pickup_time_est TEXT,
            total_amount INTEGER DEFAULT 0,
            ai_suggested TEXT,
            last_interaction TEXT DEFAULT 'Khởi tạo đơn thành công'
        )
    ''')
    
    # Điều phối Logistics IoT
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS iot_logistics (
            trip_id TEXT PRIMARY KEY,
            sid TEXT NOT NULL,
            driver_name TEXT DEFAULT 'Chưa chỉ định',
            box_code TEXT DEFAULT 'IoT-BOX-01',
            status TEXT DEFAULT 'Chờ duyệt điều phối',
            iot_temp TEXT DEFAULT '22.8 °C',
            iot_battery TEXT DEFAULT '95%',
            zalo_msg TEXT
        )
    ''')
    
    # Danh mục xét nghiệm
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tests_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            category TEXT,
            tube_type TEXT,
            duration TEXT,
            price INTEGER DEFAULT 0,
            function_desc TEXT
        )
    ''')
    
    # Khởi tạo dữ liệu mẫu nếu bảng trống
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO accounts (username, password, partner, role) VALUES ('admin', 'admin123', 'DXCON HQ', 'Admin')")
        cursor.execute("INSERT INTO accounts (username, password, partner, role) VALUES ('doctor_sg', '123456', 'Phòng Khám Đa Khoa Sài Gòn', 'Bác sĩ')")
        
    cursor.execute("SELECT COUNT(*) FROM contracts")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO contracts (id, partner_name, discount, lab_result_url, lab_account_shared) 
            VALUES ('LAB_Q1', 'Trung tâm Xét nghiệm Quận 1', 10.0, 'https://labportal.example.com', 'DXCON_Q1')
        ''')

    cursor.execute("SELECT COUNT(*) FROM tests_catalog")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO tests_catalog (code, name, duration, price) VALUES ('XN01', 'Xét nghiệm Công thức máu', '2 giờ', 250000)")
        cursor.execute("INSERT INTO tests_catalog (code, name, duration, price) VALUES ('XN02', 'Xét nghiệm Đường huyết (Glucose)', '1.5 giờ', 120000)")

    conn.commit()
    conn.close()

init_db()

def ai_medical_engine(test_name):
    text = str(test_name).lower()
    if "đường huyết" in text or "glucose" in text:
        return "🤖 AI: Nguy cơ Đái tháo đường tuýp 2. Khuyến nghị theo dõi HbA1c."
    return "🤖 AI: Chỉ số bình thường, khuyến nghị kiểm tra định kỳ."

# --- GIAO DIỆN KHÁCH VÃNG LAI ĐĂNG KÝ (ẢNH 5) ---
@app.route('/')
def guest_portal():
    conn = get_db_connection()
    tests = conn.execute("SELECT * FROM tests_catalog").fetchall()
    labs = conn.execute("SELECT * FROM contracts").fetchall()
    search_sid = request.args.get('search_sid', '').strip()
    patient_info = None
    if search_sid:
        patient_info = conn.execute("SELECT * FROM crm_patients WHERE sid = ?", (search_sid,)).fetchone()
    conn.close()
    return render_template('index.html', tests=tests, labs=labs, patient_info=patient_info, search_sid=search_sid)

@app.route('/api/guest/book', methods=['POST'])
def guest_book_appointment():
    name = request.form.get('guest_name')
    phone = request.form.get('guest_phone')
    address = request.form.get('pickup_type', 'Điều phối nhân viên đến lấy mẫu tại nhà')
    test_id = request.form.get('chosen_test')
    chosen_lab = request.form.get('chosen_lab')
    
    conn = get_db_connection()
    test_item = conn.execute("SELECT * FROM tests_catalog WHERE id = ?", (test_id,)).fetchone()
    
    if name and phone and test_item:
        sid = f"SID{datetime.now().strftime('%m%d%H%M%S')}"
        trip_id = f"TRIP_{datetime.now().strftime('%M%S')}"
        price = test_item['price']
        
        lab_barcode = f"BAR-{sid}"
        ai_pred = ai_medical_engine(test_item['name'])
        
        raw_msg = f"📌 [DXCON] ĐƠN MỚI: {name} - Gửi mẫu đến: {chosen_lab}"
        encoded_msg = urllib.parse.quote(raw_msg)
        
        conn.execute('''
            INSERT INTO crm_patients (sid, name, phone, address, chosen_lab, lab_patient_barcode, total_amount, ai_suggested)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sid, name, phone, address, chosen_lab, lab_barcode, price, ai_pred))
        
        conn.execute('''
            INSERT INTO iot_logistics (trip_id, sid, zalo_msg) VALUES (?, ?, ?)
        ''', (trip_id, sid, encoded_msg))
        
        conn.commit()
        conn.close()
        return redirect(url_for('guest_portal', search_sid=sid))
    conn.close()
    return redirect(url_for('guest_portal'))

@app.route('/login', methods=['GET', 'POST'])
def system_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM accounts WHERE username = ? AND password = ?", (username, password)).fetchone()
        conn.close()
        if user:
            session['logged_in'] = True
            session['username'] = user['username']
            session['role'] = user['role']
            session['partner'] = user['partner']
            if user['role'] == 'Bác sĩ':
                return redirect(url_for('doctor_portal'))
            return redirect(url_for('admin_panel'))
        error = "Mật khẩu hoặc tài khoản chưa đúng!"
    return render_template('login.html', error=error)

@app.route('/logout')
def system_logout():
    session.clear()
    return redirect(url_for('system_login'))

@app.route('/doctor')
def doctor_portal():
    if not session.get('logged_in') or session.get('role') != 'Bác sĩ':
        return redirect(url_for('system_login'))
    conn = get_db_connection()
    patients = conn.execute("SELECT * FROM crm_patients").fetchall()
    conn.close()
    return render_template('doctor.html', patients=patients, doctor_name=session.get('username'))

@app.route('/api/doctor/get_lab_frame/<string:sid>')
def doctor_get_lab_frame(sid):
    conn = get_db_connection()
    row = conn.execute('''
        SELECT p.sid, p.chosen_lab, c.lab_result_url, c.lab_account_shared
        FROM crm_patients p LEFT JOIN contracts c ON p.chosen_lab = c.partner_name
        WHERE p.sid = ?
    ''', (sid,)).fetchone()
    conn.close()
    if row and row['lab_result_url']:
        url = f"{row['lab_result_url']}?agent={row['lab_account_shared']}&barcode=BAR-{sid}"
        return jsonify({'success': True, 'lab_name': row['chosen_lab'], 'embed_url': url})
    return jsonify({'success': False, 'message': 'Chưa cấu hình link kết quả cho Lab này.'})

@app.route('/admin')
def admin_panel():
    if not session.get('logged_in') or session.get('role') != 'Admin':
        return redirect(url_for('system_login'))
    conn = get_db_connection()
    accounts = conn.execute("SELECT * FROM accounts").fetchall()
    contracts = conn.execute("SELECT * FROM contracts").fetchall()
    patients = conn.execute("SELECT * FROM crm_patients").fetchall()
    conn.close()
    return render_template('admin.html', accounts=accounts, contracts=contracts, crm_patients=patients)

@app.route('/api/admin/contract/add', methods=['POST'])
def admin_add_contract():
    hd_id = request.form.get('hd_id')
    partner_name = request.form.get('partner_name')
    discount = request.form.get('discount', 0)
    lab_url = request.form.get('lab_result_url', '')
    lab_agent = request.form.get('lab_account_shared', '')
    
    conn = get_db_connection()
    conn.execute('''
        INSERT OR REPLACE INTO contracts (id, partner_name, discount, lab_result_url, lab_account_shared)
        VALUES (?, ?, ?, ?, ?)
    ''', (hd_id, partner_name, float(discount or 0), lab_url, lab_agent))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
