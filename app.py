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
    
    # 3.1 Quản lý tài khoản
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
    
    # 3.3 Quản lý hồ sơ đối tác B2B / Phòng Lab liên kết (MỞ RỘNG TRƯỜNG LINK KẾT QUẢ VÀ TÀI KHOẢN LAB)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contracts (
            id TEXT PRIMARY KEY,
            partner_name TEXT NOT NULL,
            discount REAL DEFAULT 0.0,
            contract_file TEXT,
            test_list_file TEXT,
            lab_result_url TEXT,       -- Link trang web tra cứu kết quả của Lab đối tác
            lab_account_shared TEXT,   -- Tài khoản/Mã đại lý dùng chung để đăng nhập Lab đó
            status TEXT DEFAULT 'Đang hoạt động'
        )
    ''')
    
    # 3.2 CRM Bệnh nhân (Thêm mã tra cứu nội bộ bên phía Phòng Lab nếu có)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crm_patients (
            sid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            chosen_lab TEXT,           -- Tên phòng Lab liên kết nhận mẫu xử lý
            lab_patient_barcode TEXT,  -- Mã Barcode/Mã tra cứu riêng bên phía Phòng Lab cấp
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
    
    # 3.5 Điều phối tài xế & IoT
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
    
    # 3.4 Danh mục gói xét nghiệm
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
    
    # Tạo tài khoản và Lab mẫu ban đầu để hệ thống chạy được ngay
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO accounts (username, password, partner, role) VALUES ('admin', 'admin123', 'DXCON HQ', 'Admin')")
        cursor.execute("INSERT INTO accounts (username, password, partner, role) VALUES ('doctor_sg', '123456', 'Phòng Khám Đa Khoa Sài Gòn', 'Bác sĩ')")
        
    cursor.execute("SELECT COUNT(*) FROM contracts")
    if cursor.fetchone()[0] == 0:
        # Giả lập tạo sẵn 1 Lab đối tác có cấu hình cổng kết quả web trực tuyến
        cursor.execute('''
            INSERT INTO contracts (id, partner_name, discount, lab_result_url, lab_account_shared) 
            VALUES ('LAB_HOAN_MY', 'Trung Tâm Xét Nghiệm Hoàn Mỹ', 15.0, 'https://labportal.example.com/results', 'DXCON_AGENT_01')
        ''')
        cursor.execute('''
            INSERT INTO contracts (id, partner_name, discount, lab_result_url, lab_account_shared) 
            VALUES ('LAB_MEDLATEC', 'Hệ Thống Phòng Lab Medlatec', 10.0, 'https://medlatec.vn/tra-cuu-ket-qua', 'MED_DXCON_SECRET')
        ''')

    conn.commit()
    conn.close()

init_db()

def ai_medical_engine(test_name, patient_notes=""):
    text = f"{test_name} {patient_notes}".lower()
    if "đường huyết" in text or "glucose" in text:
        return "🤖 AI Cảnh báo: Nguy cơ Đái tháo đường tuýp 2. Đề xuất: Theo dõi HbA1c, hạn chế tinh bột theo chuẩn ADA."
    elif "máu" in text or "huyết học" in text:
        return "🤖 AI Đề xuất: Theo dõi chỉ số Bạch cầu. Nếu tăng cao, cảnh báo nhiễm trùng cấp tính."
    return "🤖 AI Đề xuất: Khuyến nghị duy trì lối sống lành mạnh và tái khám sau 6 tháng."

# --- 1. PHÂN HỆ KHÁCH HÀNG VÃNG LAI ---
@app.route('/')
def guest_portal():
    conn = get_db_connection()
    tests = conn.execute("SELECT * FROM tests_catalog").fetchall()
    labs = conn.execute("SELECT * FROM contracts").fetchall() # Lấy danh sách Lab đối tác để chọn nơi gửi mẫu
    search_sid = request.args.get('search_sid', '').strip()
    patient_info = None
    if search_sid:
        patient_info = conn.execute("SELECT * FROM crm_patients WHERE sid = ? OR name LIKE ?", (search_sid, f"%{search_sid}%")).fetchone()
    conn.close()
    return render_template('index.html', tests=tests, labs=labs, patient_info=patient_info, search_sid=search_sid)

@app.route('/api/guest/book', methods=['POST'])
def guest_book_appointment():
    name = request.form.get('guest_name')
    phone = request.form.get('guest_phone')
    address = request.form.get('guest_address', 'Lấy mẫu tại phòng Lab')
    test_id = request.form.get('chosen_test')
    chosen_lab = request.form.get('chosen_lab') # Lab đích xử lý mẫu
    pickup_time = request.form.get('pickup_time_est', 'Ngay khi có thể')
    
    conn = get_db_connection()
    test_item = conn.execute("SELECT * FROM tests_catalog WHERE id = ?", (test_id,)).fetchone()
    
    if name and phone and test_item:
        sid = f"SID{datetime.now().strftime('%m%d%H%M%S')}"
        trip_id = f"TRIP_{datetime.now().strftime('%M%S')}"
        price = test_item['price']
        test_name = test_item['name']
        
        # Tạo barcode ngẫu nhiên mô phỏng mã gửi sang hệ thống Lab đối tác
        lab_barcode = f"BAR-{datetime.now().strftime('%H%M%S')}"
        ai_pred = ai_medical_engine(test_name)
        
        raw_msg = f"📌 [DXCON] ĐƠN ĐIỀU PHỐI\n- Mã chuyến: {trip_id}\n- Mã BN: {sid}\n- Khách hàng: {name}\n- SĐT: {phone}\n- Địa chỉ: {address}\n- Đích gửi mẫu: {chosen_lab}\n👉 Mang theo Hộp IoT nhận mẫu ngay!"
        encoded_msg = urllib.parse.quote(raw_msg)
        
        conn.execute('''
            INSERT INTO crm_patients (sid, name, phone, address, chosen_lab, lab_patient_barcode, last_interaction, pickup_time_est, total_amount, ai_suggested)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sid, name, phone, address, chosen_lab, lab_barcode, f"Đăng ký gửi mẫu đến {chosen_lab}", pickup_time, price, ai_pred))
        
        conn.execute('''
            INSERT INTO iot_logistics (trip_id, sid, status, zalo_msg)
            VALUES (?, ?, 'Chờ duyệt điều phối', ?)
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
            elif user['role'] == 'Admin':
                return redirect(url_for('admin_panel'))
        else:
            error = "Tài khoản hoặc mật khẩu không chính xác!"
    return render_template('login.html', error=error)

@app.route('/logout')
def system_logout():
    session.clear()
    return redirect(url_for('system_login'))

# --- 2. PHÂN HỆ BÁC SĨ & PHÒNG KHÁM: TRUY CẬP GIÁN TIẾP WEB KẾT QUẢ CỦA LAB ĐỐI TÁC ---
@app.route('/doctor')
def doctor_portal():
    if not session.get('logged_in') or session.get('role') != 'Bác sĩ':
        return redirect(url_for('system_login'))
        
    clinic = session.get('partner')
    search_query = request.args.get('search', '').strip()
    
    conn = get_db_connection()
    # Tìm kiếm nâng cao kết hợp kết nối chéo thông tin Hợp đồng Lab để lấy Link kết quả kết nối gián tiếp
    query_str = '''
        SELECT p.*, c.lab_result_url, c.lab_account_shared 
        FROM crm_patients p
        LEFT JOIN contracts c ON p.chosen_lab = c.partner_name
        WHERE p.clinic_owner = ?
    '''
    
    if search_query:
        query_str += " AND (p.sid = ? OR p.name LIKE ? OR p.phone LIKE ?)"
        patients = conn.execute(query_str, (clinic, search_query, f"%{search_query}%", f"%{search_query}%")).fetchall()
    else:
        patients = conn.execute(query_str, (clinic,)).fetchall()
        
    tests = conn.execute("SELECT * FROM tests_catalog").fetchall()
    labs = conn.execute("SELECT * FROM contracts").fetchall()
    conn.close()
    return render_template('doctor.html', patients=patients, tests=tests, labs=labs, clinic=clinic, doctor_name=session.get('username'))

# API endpoint để lấy thông tin nhúng Iframe trang Lab cho Bác sĩ gọi Ajax phản hồi nhanh
@app.route('/api/doctor/get_lab_frame/<string:sid>')
def doctor_get_lab_frame(sid):
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    row = conn.execute('''
        SELECT p.sid, p.name, p.lab_patient_barcode, c.partner_name, c.lab_result_url, c.lab_account_shared
        FROM crm_patients p
        JOIN contracts c ON p.chosen_lab = c.partner_name
        WHERE p.sid = ?
    ''', (sid,)).fetchone()
    conn.close()
    
    if row and row['lab_result_url']:
        # Giả lập trả về cấu hình link kèm tham số để tự động điền form tra cứu của Lab
        full_embedded_url = f"{row['lab_result_url']}?agent={row['lab_account_shared']}&barcode={row['lab_patient_barcode']}"
        return jsonify({
            'success': True,
            'lab_name': row['partner_name'],
            'barcode': row['lab_patient_barcode'],
            'account_shared': row['lab_account_shared'],
            'embed_url': full_embedded_url
        })
    return jsonify({'success': False, 'message': 'Phòng khám/Lab đối tác này chưa thiết lập hệ thống Web Portal kết nối kết quả.'})

@app.route('/api/doctor/action', methods=['POST'])
def doctor_submit_action():
    if not session.get('logged_in') or session.get('role') != 'Bác sĩ':
        return redirect(url_for('system_login'))
    sid = request.form.get('sid')
    notes = request.form.get('doctor_notes')
    revisit = request.form.get('revisit_date')
    
    prescription_file = request.files.get('prescription_file')
    filename = ""
    if prescription_file and prescription_file.filename != '':
        filename = f"prescription_{sid}_{prescription_file.filename}"
        prescription_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
    if sid:
        conn = get_db_connection()
        conn.execute('''
            UPDATE crm_patients SET doctor_notes = ?, revisit_date = ?, prescription_path = ? WHERE sid = ?
        ''', (notes, revisit, filename, sid))
        conn.commit()
        conn.close()
    return redirect(url_for('doctor_portal'))

@app.route('/api/doctor/new_order', methods=['POST'])
def doctor_create_order():
    if not session.get('logged_in') or session.get('role') != 'Bác sĩ':
        return redirect(url_for('system_login'))
    name = request.form.get('patient_name')
    phone = request.form.get('patient_phone')
    test_id = request.form.get('chosen_test')
    chosen_lab = request.form.get('chosen_lab')
    pickup_time = request.form.get('pickup_time_est', 'Ngay bây giờ')
    clinic = session.get('partner')
    
    conn = get_db_connection()
    test_item = conn.execute("SELECT * FROM tests_catalog WHERE id = ?", (test_id,)).fetchone()
    
    if name and phone and test_item:
        sid = f"SID{datetime.now().strftime('%m%d%H%M%S')}"
        test_name = test_item['name']
        price = test_item['price']
        lab_barcode = f"BAR-{datetime.now().strftime('%H%M%S')}"
        ai_pred = ai_medical_engine(test_name)
        
        conn.execute('''
            INSERT INTO crm_patients (sid, name, phone, address, chosen_lab, lab_patient_barcode, last_interaction, clinic_owner, pickup_time_est, total_amount, ai_suggested)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sid, name, phone, f"Chỉ định gửi mẫu từ cơ sở {clinic}", chosen_lab, lab_barcode, f"Bác sĩ lên lịch, chuyển tiếp Lab: {chosen_lab}", clinic, pickup_time, price, ai_pred))
        conn.commit()
    conn.close()
    return redirect(url_for('doctor_portal'))

# --- 3. PHÂN HỆ QUẢN TRỊ ADMIN MASTER ---
@app.route('/admin')
def admin_panel():
    if not session.get('logged_in') or session.get('role') != 'Admin':
        return redirect(url_for('system_login'))
    filter_clinic = request.args.get('filter_clinic', '').strip()
    conn = get_db_connection()
    accounts = conn.execute("SELECT * FROM accounts").fetchall()
    contracts = conn.execute("SELECT * FROM contracts").fetchall()
    tests_catalog = conn.execute("SELECT * FROM tests_catalog").fetchall()
    drivers = conn.execute("SELECT * FROM accounts WHERE role = 'Tài xế Logistics'").fetchall()
    stats = conn.execute("SELECT SUM(total_amount) as revenue, COUNT(*) as total_patients FROM crm_patients").fetchone()
    
    if filter_clinic:
        crm_patients = conn.execute("SELECT * FROM crm_patients WHERE clinic_owner = ?", (filter_clinic,)).fetchall()
    else:
        crm_patients = conn.execute("SELECT * FROM crm_patients").fetchall()
        
    iot_logistics = conn.execute('''
        SELECT iot_logistics.*, crm_patients.name, crm_patients.phone, crm_patients.address, crm_patients.pickup_time_est 
        FROM iot_logistics JOIN crm_patients ON iot_logistics.sid = crm_patients.sid
    ''').fetchall()
    conn.close()
    return render_template('admin.html', accounts=accounts, contracts=contracts, tests_catalog=tests_catalog,
                           drivers=drivers, crm_patients=crm_patients, iot_logistics=iot_logistics, stats=stats, filter_clinic=filter_clinic)

@app.route('/api/admin/account/add', methods=['POST'])
def admin_add_account():
    username = request.form.get('username')
    password = request.form.get('password')
    partner = request.form.get('partner')
    role = request.form.get('role')
    if username and password:
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO accounts (username, password, partner, role) VALUES (?, ?, ?, ?)", (username, password, partner, role))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/admin/account/delete/<int:id>')
def admin_delete_account(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM accounts WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/admin/patient/delete/<string:sid>')
def admin_delete_patient(sid):
    conn = get_db_connection()
    conn.execute("DELETE FROM crm_patients WHERE sid = ?", (sid,))
    conn.execute("DELETE FROM iot_logistics WHERE sid = ?", (sid,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

# 3.3 Thêm hợp đồng Lab đối tác: Lưu trữ link cấu hình web kết quả
@app.route('/api/admin/contract/add', methods=['POST'])
def admin_add_contract():
    hd_id = request.form.get('hd_id')
    partner_name = request.form.get('partner_name')
    discount = request.form.get('discount', 0)
    lab_result_url = request.form.get('lab_result_url', '')
    lab_account_shared = request.form.get('lab_account_shared', '')
    
    file_hd = request.files.get('contract_file')
    file_test = request.files.get('test_list_file')
    filename_hd = f"hd_{hd_id}_{file_hd.filename}" if file_hd and file_hd.filename != '' else ""
    filename_test = f"test_{hd_id}_{file_test.filename}" if file_test and file_test.filename != '' else ""
    
    if filename_hd: file_hd.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_hd))
    if filename_test: file_test.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_test))
        
    if hd_id and partner_name:
        conn = get_db_connection()
        conn.execute('''
            INSERT OR REPLACE INTO contracts (id, partner_name, discount, contract_file, test_list_file, lab_result_url, lab_account_shared) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (hd_id, partner_name, float(discount or 0), filename_hd, filename_test, lab_result_url, lab_account_shared))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/admin/contract/delete/<string:id>')
def admin_delete_contract(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM contracts WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/admin/tests/add', methods=['POST'])
def admin_add_test():
    code = request.form.get('code')
    name = request.form.get('name')
    category = request.form.get('category')
    tube_type = request.form.get('tube_type')
    duration = request.form.get('duration')
    price = request.form.get('price', 0)
    function_desc = request.form.get('function_desc')
    
    if code and name:
        conn = get_db_connection()
        conn.execute('''
            INSERT OR REPLACE INTO tests_catalog (code, name, category, tube_type, duration, price, function_desc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (code, name, category, tube_type, duration, int(price or 0), function_desc))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/admin/tests/upload_bulk', methods=['POST'])
def admin_upload_bulk_tests():
    file = request.files.get('bulk_file')
    if file and file.filename != '':
        lines = file.read().decode('utf-8').splitlines()
        conn = get_db_connection()
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 6:
                code, name, category, tube_type, duration, price = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip(), parts[4].strip(), parts[5].strip()
                desc = parts[6].strip() if len(parts) > 6 else "Xét nghiệm y khoa"
                try:
                    conn.execute('''
                        INSERT OR REPLACE INTO tests_catalog (code, name, category, tube_type, duration, price, function_desc)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (code, name, category, tube_type, duration, int(price or 0), desc))
                except:
                    pass
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/admin/tests/delete/<int:id>')
def admin_delete_test(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM tests_catalog WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/api/admin/logistics/dispatch', methods=['POST'])
def admin_dispatch_driver():
    trip_id = request.form.get('trip_id')
    driver_name = request.form.get('driver_name')
    box_code = request.form.get('box_code', 'IoT-BOX-MASTER')
    if trip_id and driver_name:
        conn = get_db_connection()
        conn.execute('''
            UPDATE iot_logistics SET driver_name = ?, box_code = ?, status = 'Đang di chuyển lấy mẫu (IoT Activated)' WHERE trip_id = ?
        ''', (driver_name, box_code, trip_id))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
