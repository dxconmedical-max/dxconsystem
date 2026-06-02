import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "dxcon_secret_key_master_system"

# ==========================================
# CẤU HÌNH KẾT NỐI POSTGRESQL CHÍNH THỨC
# ==========================================
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://dxcon_admin:qmaBoXCBLanF3b3jZwDnhFk5P719JZ8C@dpg-d8f6psl9j78s73fsl6qg-a/dxcon_prod'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# ĐỊNH NGHĨA CÁC BẢNG LƯU TRỮ (DATABASE MODELS)
# ==========================================

class Account(db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    partner = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class Contract(db.Model):
    __tablename__ = 'contracts'
    id = db.Column(db.String(50), primary_key=True)
    partner_name = db.Column(db.String(200), nullable=False)
    discount = db.Column(db.Float, default=0.0)
    lab_result_url = db.Column(db.String(500))
    lab_account_shared = db.Column(db.String(200))

class Patient(db.Model):
    __tablename__ = 'patients'
    sid = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50))
    address = db.Column(db.String(500))
    chosen_lab = db.Column(db.String(200))
    total_amount = db.Column(db.String(50), default="0")
    ai_suggested = db.Column(db.Text, default="Chờ phân tích...")
    driver_name = db.Column(db.String(150), default="Chưa chỉ định")
    temperature = db.Column(db.String(50), default="22.5 °C")
    battery = db.Column(db.String(50), default="100%")
    status = db.Column(db.String(100), default="Chờ điều phối")

class TestCatalog(db.Model):
    __tablename__ = 'test_catalogs'
    code = db.Column(db.String(50), primary_key=True) # Mã XN
    name = db.Column(db.String(200), nullable=False)   # Tên đầy đủ
    category = db.Column(db.String(100))               # Phân hệ
    tube_type = db.Column(db.String(100))              # Ống thu mẫu
    duration = db.Column(db.String(50))                # Thời gian cần
    price = db.Column(db.String(50), default="0")      # Bảng giá
    function_desc = db.Column(db.Text)                 # Ý nghĩa

with app.app_context():
    db.create_all()


# ==========================================
# ĐIỀU HƯỚNG CÁC TRANG (ROUTES & TRAFFIC)
# ==========================================

# 1. GIAO DIỆN KHÁCH HÀNG / BỆNH NHÂN VÃNG LAI (Trang chủ chính thức)
@app.route('/')
def customer_portal():
    # Lấy danh mục gói xét nghiệm từ Postgres ra cho khách hàng vãng lai lựa chọn đặt lịch
    available_tests = TestCatalog.query.all()
    return render_template('index.html', tests=available_tests)


# Đăng ký thông tin từ trang vãng lai đẩy về két sắt CRM
@app.route('/api/customer/register', methods=['POST'])
def customer_register():
    import random
    new_sid = f"SID{random.randint(100000, 999999)}"
    
    new_p = Patient(
        sid=new_sid,
        name=request.form.get('name'),
        phone=request.form.get('phone'),
        address=request.form.get('address'),
        chosen_lab=request.form.get('chosen_lab'),
        total_amount=request.form.get('total_amount', '0đ'),
        status="Chờ điều phối"
    )
    db.session.add(new_p)
    db.session.commit()
    return f"Đăng ký thành công! Mã bệnh nhân của bạn là: {new_sid}. DXCON sẽ liên hệ để lấy mẫu."


# 2. BẢNG ĐIỀU PHỐI TRUNG TÂM (Trang Admin quản trị tối cao)
# CẦU NỐI SỬA LỖI NÚT CHUYỂN HỆ THỐNG TRÊN GIAO DIỆN
@app.route('/login')
def redirect_to_admin():
    return redirect('/admin')
@app.route('/admin')
def admin_portal():
    all_accounts = Account.query.order_by(Account.id.desc()).all()
    all_contracts = Contract.query.all()
    all_patients = Patient.query.order_by(Patient.sid.desc()).all()
    all_tests = TestCatalog.query.order_by(TestCatalog.code.asc()).all()
    
    return render_template('admin.html', 
                           accounts=all_accounts, 
                           contracts=all_contracts, 
                           crm_patients=all_patients,
                           tests=all_tests)


# ==========================================
# CÁC ROUTE XỬ LÝ DỮ LIỆU THỰC TẾ
# ==========================================

# XỬ LÝ TAB 3.4: THÊM / CẬP NHẬT GÓI XÉT NGHIỆM ĐỒNG BỘ 100% GIAO DIỆN
@app.route('/api/admin/tests/add', methods=['POST'])
def add_test_catalog():
    # Khớp chính xác theo name thuộc tính của các ô Input trong file HTML của anh
    code = request.form.get('code')
    name = request.form.get('name')
    category = request.form.get('category')
    tube_type = request.form.get('tube_type')
    duration = request.form.get('duration')
    price = request.form.get('price', '0')
    function_desc = request.form.get('function_desc')
    
    if code and name:
        test = TestCatalog.query.get(code)
        if not test:
            test = TestCatalog(code=code)
            db.session.add(test)
            
        test.name = name
        test.category = category
        test.tube_type = tube_type
        test.duration = duration
        test.price = price
        test.function_desc = function_desc
        
        db.session.commit()
    return redirect('/admin')

@app.route('/api/admin/tests/delete/<string:code>')
def delete_test_catalog(code):
    test = TestCatalog.query.get(code)
    if test:
        db.session.delete(test)
        db.session.commit()
    return redirect('/admin')


# XỬ LÝ TAB 3.5: ĐIỀU PHỐI TÀI XẾ & PHÁT LỆNH SANG ZALO
@app.route('/api/admin/logistics/dispatch', methods=['POST'])
def dispatch_driver():
    sid = request.form.get('trip_id')
    driver_name = request.form.get('driver_name')
    
    patient = Patient.query.get(sid)
    if patient and driver_name:
        patient.driver_name = driver_name
        patient.status = "Tài xế nhận ca - Đang di chuyển"
        db.session.commit()
        
        # --- ĐOẠN ĐẨY LỆNH SANG ZALO (WEBHOOK) ---
        # Sau này anh cấu hình token Zalo OA vào đây để tự gửi tin nhắn cho tài xế
        print(f"👉 Hệ thống phát lệnh Zalo: Gửi yêu cầu đón bệnh nhân {patient.name} tới tài xế {driver_name}")
        
    return redirect('/admin')

# NÚT BẤM GỬI LẠI LỆNH ZALO THỦ CÔNG TRÊN GIAO DIỆN
@app.route('/api/admin/logistics/resend_zalo/<string:sid>')
def resend_zalo(sid):
    patient = Patient.query.get(sid)
    if patient:
        # Giả lập lệnh gọi tổng đài API Zalo ZNS
        print(f"🔄 Gửi lại lệnh Zalo điều phối cho mã chuyến: {sid}")
    return redirect('/admin')


# CỔNG API KẾT NỐI VỚI THIẾT BỊ IOT HỘP LẠNH (ĐỂ KẾT NỐI SAU NÀY)
# Sau này thiết bị IoT phần cứng lắp sim 4G chỉ cần Bắn lệnh POST dạng JSON lên link này là cập nhật ngay
@app.route('/api/iot/update', methods=['POST'])
def iot_update():
    data = request.json
    sid = data.get('sid')
    temp = data.get('temperature')
    batt = data.get('battery')
    
    patient = Patient.query.get(sid)
    if patient:
        if temp: patient.temperature = f"{temp} °C"
        if batt: patient.battery = f"{batt}%"
        db.session.commit()
        return jsonify({"status": "success", "message": "Dữ liệu IoT đã khóa chặt vào Postgres"}), 200
    return jsonify({"status": "error", "message": "Không tìm thấy mã bệnh nhân"}), 404


# API MODULE 3.1: THÊM & XÓA TÀI KHOẢN
@app.route('/api/admin/account/add', methods=['POST'])
def add_account():
    username = request.form.get('username')
    password = request.form.get('password')
    partner = request.form.get('partner')
    role = request.form.get('role')
    if username and password:
        exists = Account.query.filter_by(username=username).first()
        if not exists:
            new_acc = Account(username=username, password=password, partner=partner, role=role)
            db.session.add(new_acc)
            db.session.commit()
    return redirect('/admin')

@app.route('/api/admin/account/delete/<int:id>')
def delete_account(id):
    acc = Account.query.get(id)
    if acc:
        db.session.delete(acc)
        db.session.commit()
    return redirect('/admin')


# API MODULE 3.2 & 3.6: QUẢN LÝ ĐỐI TÁC
@app.route('/api/admin/contract/add', methods=['POST'])
def add_contract():
    hd_id = request.form.get('hd_id')
    partner_name = request.form.get('partner_name')
    discount_str = request.form.get('discount', '0')
    lab_result_url = request.form.get('lab_result_url')
    lab_account_shared = request.form.get('lab_account_shared')
    
    if hd_id and partner_name:
        contract = Contract.query.get(hd_id)
        if not contract:
            contract = Contract(id=hd_id)
            db.session.add(contract)
        contract.partner_name = partner_name
        contract.discount = float(discount_str) if discount_str else 0.0
        contract.lab_result_url = lab_result_url
        contract.lab_account_shared = lab_account_shared
        db.session.commit()
    return redirect('/admin')


# TẠO NHANH DATA MẪU BAN ĐẦU ĐỂ CHẠY HỆ THỐNG
@app.route('/khoitaodatalab')
def create_master_test_data():
    # 1. Tạo gói xét nghiệm mẫu
    if not TestCatalog.query.get("XN01"):
        xn01 = TestCatalog(code="XN01", name="Xét nghiệm Công thức máu", category="Huyết học", tube_type="Ống EDTA (Tím)", duration="2 giờ", price="250,000 đ", function_desc="Đánh giá tình trạng thiếu máu, bạch cầu, nhiễm trùng cơ thể")
        db.session.add(xn01)
    # 2. Tạo hành trình điều phối mẫu
    if not Patient.query.get("TRIP_2026"):
        p01 = Patient(sid="TRIP_2026", name="Nguyễn Văn A", phone="0901234567", address="Quận 1, TP. Hồ Chí Minh", chosen_lab="Hệ Thống Lab Hoàn Mỹ", total_amount="250,000đ", driver_name="Nguyễn Văn A", temperature="22.8 °C", battery="95%", status="Tài xế nhận ca - Đang di chuyển")
        db.session.add(p01)
        
    db.session.commit()
    return redirect('/admin')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
