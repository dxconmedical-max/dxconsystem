import os
import sqlite3
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = "dxcon_super_secure_key_production_2026"
DB_FILE = "dxcon_medical_v2.db"

# Cấu hình thư mục lưu trữ file upload (Đơn thuốc, Hợp đồng...)
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
    
    # 3.1 Quản lý phân quyền tài khoản (Admin, Bác sĩ, Tài xế)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            partner TEXT, -- Tên Phòng khám hoặc Đội xe quản lý
            role TEXT NOT NULL,
            status TEXT DEFAULT 'Đang hoạt động'
        )
    ''')
    
    # 3.3 Quản lý hồ sơ ký kết đối tác B2B
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contracts (
            id TEXT PRIMARY KEY,
            partner_name TEXT NOT NULL,
            discount REAL DEFAULT 0.0,
            contract_file TEXT, -- Đường dẫn file hợp đồng upload
            test_list_file TEXT, -- Đường dẫn file danh mục xét nghiệm riêng
            status TEXT DEFAULT 'Đang hoạt động'
        )
    ''')
    
    # 3.2 CRM Bệnh nhân (Mở rộng tổng tiền, chẩn đoán AI, phòng khám sở hữu)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crm_patients (
            sid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            chosen_lab TEXT,
            prescription_path TEXT, -- File đơn thuốc bác sĩ upload
            doctor_notes TEXT,
            revisit_date TEXT,
            clinic_owner TEXT DEFAULT 'Tự do',
            pickup_time_est TEXT,
            total_amount INTEGER DEFAULT 0, -- Số tiền gói xét nghiệm
            ai_suggested TEXT, -- Gợi ý chẩn đoán tự động từ AI
            last_interaction TEXT DEFAULT 'Khởi tạo đơn thành công'
        )
    ''')
    
    # 3.5 Điều phối tài xế & IoT Logistics
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
    
    # 3.4 Danh mục gói xét nghiệm niêm yết
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
    
    # Khởi tạo dữ liệu mẫu nếu hệ thống mới tinh
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO accounts (username, password, partner, role) VALUES ('admin', 'admin123', 'DXCON HQ', 'Admin')")
        cursor.execute("INSERT INTO accounts (username, password, partner, role) VALUES ('doctor_sg', '123456', 'Phòng Khám Đa Khoa Sài Gòn', 'Bác sĩ')")
        cursor.execute("INSERT INTO accounts (username, password, partner, role) VALUES ('driver_binh', '123456', 'Đội Xe Công Nghệ', 'Tài xế Logistics')")
        
    cursor.execute("SELECT COUNT(*) FROM tests_catalog")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO tests_catalog (code, name, category, tube_type, duration, price, function_desc) VALUES ('XN001', 'Xét nghiệm Công thức máu', 'Huyết học', 'Ống EDTA Tím', '2 giờ', 250000, 'Tầm soát thiếu máu, nhiễm trùng')")
        cursor.execute("INSERT INTO tests_catalog (code, name, category, tube_type, duration, price, function_desc) VALUES ('XN002', 'Xét nghiệm Đường huyết Glucose', 'Sinh hóa', 'Ống Fluoride Xám', '1 giờ', 120000, 'Tầm soát tiểu đường, hạ đường huyết')")

    conn.commit()
    conn.close()

init_db()

# --- MÔ PHỎNG ENGINE AI Y TẾ CHUẨN WHO & BỘ Y TẾ VIỆT NAM ---
def ai_medical_engine(test_name, patient_notes=""):
    text = f"{test_name} {patient_notes}".lower()
    if "đường huyết" in text or "glucose" in text:
        return "🤖 AI Cảnh báo: Nguy cơ Đái tháo đường tuýp 2. Đề xuất: Theo dõi HbA1c, hạn chế tinh bột, kiểm tra đường huyết đói định kỳ theo chuẩn ADA."
    elif "máu" in text or "huyết học" in text:
        return "🤖 AI Đề xuất: Theo dõi chỉ số Hồng cầu (RBC) và Bạch cầu. Nếu WBC tăng cao, cảnh báo nguy cơ nhiễm trùng cấp tính."
    elif "tổng quát" in text:
        return "🤖 AI Đề xuất: Tầm soát chuyên sâu chức năng Gan (AST/ALT) và Thận (Ure/Creatinine) để đánh giá toàn diện."
    return "🤖 AI Đề xuất: Kết quả hiện tại ổn định. Khuyến nghị bệnh nhân duy trì lối sống lành mạnh và tái khám sau 6 tháng."

# --- 1. PHÂN HỆ KHÁCH HÀNG VÃNG LAI ---
@app.route('/')
def guest_portal():
    conn = get_db_connection()
    tests = conn.execute("SELECT * FROM tests_catalog").fetchall()
    search_sid = request.args.get('search_sid', '').strip()
    patient_info = None
    if search_sid:
        patient_info = conn.execute("SELECT * FROM crm_patients WHERE sid = ? OR name LIKE ?", (search_sid, f"%{search_sid}%")).fetchone()
    conn.close()
    return render_template('index.html', tests=tests, patient_info=patient_info, search_sid=search_sid)

@app.route('/api/guest/book', methods=['POST'])
def guest_book_appointment():
    name = request.form.get('guest_name')
    phone = request.form.get('guest_phone')
    address = request.form.get('guest_address', 'Lấy mẫu tại phòng Lab')
    test_id = request.form.get('chosen_test')
    pickup_time = request.form.get('pickup_time_est', 'Ngay khi có thể')
    
    conn = get_db_connection()
    test_item = conn.execute("SELECT * FROM tests_catalog WHERE id = ?", (test_id,)).fetchone()
    
    if name and phone and test_item:
        sid = f"SID{datetime.now().strftime('%m%d%H%M%S')}"
        trip_id = f"TRIP_{datetime.now().strftime('%M%S')}"
        price = test_item['price']
        test_name = test_item['name']
        
        # Sinh chẩn đoán AI sơ bộ
        ai_pred = ai_medical_engine(test_name)
        
        # Tạo chuỗi lệnh điều phối gửi Zalo cho Tài xế
        raw_msg = f"📌 [DXCON] ĐƠN ĐIỀU PHỐI TÀI XẾ\n- Mã chuyến: {trip_id}\n- Mã BN (SID): {sid}\n- Khách hàng: {name}\n- SĐT: {phone}\n- Địa chỉ lấy mẫu: {address}\n- Giờ hẹn: {pickup_time}\n- Gói XN: {test_name}\n👉 Tài xế mang theo Hộp IoT nhận mẫu ngay!"
        encoded_msg = urllib.parse.quote(raw_msg)
        
        # Đẩy dữ liệu vào hệ thống CRM quản lý của Admin
        conn.execute('''
            INSERT INTO crm_patients (sid, name, phone, address, chosen_lab, last_interaction, pickup_time_est, total_amount, ai_suggested)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sid, name, phone, address, "Lab Trung Tâm", f"Đăng ký: {test_name}", pickup_time, price, ai_pred))
        
        # Tạo hàng đợi điều phối bên phân hệ logistics
        conn.execute('''
            INSERT INTO iot_logistics (trip_id, sid, status, zalo_msg)
            VALUES (?, ?, 'Chờ duyệt điều phối', ?)
        ''', (trip_id, sid, encoded_msg))
        
        conn.commit()
        conn.close()
        return redirect(url_for('guest_portal', search_sid=sid))
    conn.close()
    return redirect(url_for('guest_portal'))

# --- THỦ TỤC ĐĂNG NHẬP HỆ THỐNG ---
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

# --- 2. PHÂN HỆ BÁC SĨ & PHÒNG KHÁM QUẢN LÝ THÔNG TIN PHÂN QUYỀN ---
@app.route('/doctor')
def doctor_portal():
    if not session.get('logged_in') or session.get('role') != 'Bác sĩ':
        return redirect(url_for('system_login'))
        
    clinic = session.get('partner')
    search_query = request.args.get('search', '').strip()
    
    conn = get_db_connection()
    # Tìm kiếm nâng cao: Chỉ tìm kiếm trên nhóm bệnh nhân thuộc quyền quản lý của phòng khám
    if search_query:
        patients = conn.execute('''
            SELECT * FROM crm_patients 
            WHERE clinic_owner = ? AND (sid = ? OR name LIKE ? OR phone LIKE ?)
        ''', (clinic, search_query, f"%{search_query}%", f"%{search_query}%")).fetchall()
    else:
        patients = conn.execute("SELECT * FROM crm_patients WHERE clinic_owner = ?", (clinic,)).fetchall()
        
    tests = conn.execute("SELECT * FROM tests_catalog").fetchall()
    conn.close()
    return render_template('doctor.html', patients=patients, tests=tests, clinic=clinic, doctor_name=session.get('username'))

@app.route('/api/doctor/action', methods=['POST'])
def doctor_submit_action():
    if not session.get('logged_in') or session.get('role') != 'Bác sĩ':
        return redirect(url_for('system_login'))
        
    sid = request.form.get('sid')
    notes = request.form.get('doctor_notes')
    revisit = request.form.get('revisit_date')
    
    # Xử lý upload tệp đơn thuốc điện tử
    prescription_file = request.files.get('prescription_file')
    filename = ""
    if prescription_file and prescription_file.filename != '':
        filename = f"prescription_{sid}_{prescription_file.filename}"
        prescription_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
    if sid:
        conn = get_db_connection()
        conn.execute('''
            UPDATE crm_patients 
            SET doctor_notes = ?, revisit_date = ?, prescription_path = ?, last_interaction = 'Bác sĩ đã kết luận và đẩy đơn'
            WHERE sid = ?
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
    pickup_time = request.form.get('pickup_time_est', 'Ngay bây giờ')
    clinic = session.get('partner')
    
    conn = get_db_connection()
    test_item = conn.execute("SELECT * FROM tests_catalog WHERE id = ?", (test_id,)).fetchone()
    
    if name and phone and test_item:
        sid = f"SID{datetime.now().strftime('%m%d%H%M%S')}"
        test_name = test_item['name']
        price = test_item['price']
        
        # Kích hoạt AI đề xuất phương án điều trị dựa trên gói xét nghiệm chỉ định
        ai_pred = ai_medical_engine(test_name)
        
        conn.execute('''
            INSERT INTO crm_patients (sid, name, phone, address, chosen_lab, last_interaction, clinic_owner, pickup_time_est, total_amount, ai_suggested)
            VALUES (?, ?, ?, ?, 'Lab Trung Tâm', ?, ?, ?, ?, ?)
        ''', (sid, name, phone, f"Chỉ định tại {clinic}", f"Bác sĩ ra chỉ định: {test_name}", clinic, pickup_time, price, ai_pred))
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
    
    # 3.2 CRM: Thống kê tổng doanh thu & Đếm số lượng bệnh nhân
    stats = conn.execute("SELECT SUM(total_amount) as revenue, COUNT(*) as total_patients FROM crm_patients").fetchone()
    
    # 3.2 Filter nâng cao thông tin bệnh nhân theo phòng khám
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

# 3.1 Cấp tài khoản mới
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

# 3.1 Xóa tài khoản người dùng
@app.route('/api/admin/account/delete/<int:id>')
def admin_delete_account(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM accounts WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

# 3.2 Cập nhật & Xóa thông tin bệnh nhân trong CRM
@app.route('/api/admin/patient/delete/<string:sid>')
def admin_delete_patient(sid):
    conn = get_db_connection()
    conn.execute("DELETE FROM crm_patients WHERE sid = ?", (sid,))
    conn.execute("DELETE FROM iot_logistics WHERE sid = ?", (sid,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

# 3.3 Thêm và upload hồ sơ ký kết hợp đồng đối tác B2B
@app.route('/api/admin/contract/add', methods=['POST'])
def admin_add_contract():
    hd_id = request.form.get('hd_id')
    partner_name = request.form.get('partner_name')
    discount = request.form.get('discount', 0)
    
    file_hd = request.files.get('contract_file')
    file_test = request.files.get('test_list_file')
    
    filename_hd = f"hd_{hd_id}_{file_hd.filename}" if file_hd and file_hd.filename != '' else ""
    filename_test = f"test_{hd_id}_{file_test.filename}" if file_test and file_test.filename != '' else ""
    
    if filename_hd:
        file_hd.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_hd))
    if filename_test:
        file_test.save(os.path.join(app.config['UPLOAD_FOLDER'], filename_test))
        
    if hd_id and partner_name:
        conn = get_db_connection()
        conn.execute('INSERT OR REPLACE INTO contracts (id, partner_name, discount, contract_file, test_list_file) VALUES (?, ?, ?, ?, ?)',
                     (hd_id, partner_name, float(discount or 0), filename_hd, filename_test))
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

# 3.4 Thêm & Cập nhật danh mục xét nghiệm đơn lẻ
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

# 3.4 Upload hàng loạt danh mục xét nghiệm theo form mẫu (File .csv hoặc .txt có phân cách)
@app.route('/api/admin/tests/upload_bulk', methods=['POST'])
def admin_upload_bulk_tests():
    file = request.files.get('bulk_file')
    if file and file.filename != '':
        # Đọc dữ liệu thô từng dòng mô phỏng đọc file Excel/CSV mẫu
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

# 3.5 Điều phối tài xế Logistics, tích hợp mã hộp IoT và sinh lệnh Zalo share trực tiếp
@app.route('/api/admin/logistics/dispatch', methods=['POST'])
def admin_dispatch_driver():
    trip_id = request.form.get('trip_id')
    driver_name = request.form.get('driver_name')
    box_code = request.form.get('box_code', 'IoT-BOX-MASTER')
    
    if trip_id and driver_name:
        conn = get_db_connection()
        # Chuyển đổi trạng thái lệnh sang Đã điều ca
        conn.execute('''
            UPDATE iot_logistics 
            SET driver_name = ?, box_code = ?, status = 'Đang di chuyển lấy mẫu (IoT Activated)' 
            WHERE trip_id = ?
        ''', (driver_name, box_code, trip_id))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
