import os
import random
import requests
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
    code = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    tube_type = db.Column(db.String(100))
    duration = db.Column(db.String(50))
    price = db.Column(db.String(50), default="0")
    function_desc = db.Column(db.Text)

with app.app_context():
    db.create_all()


# ==========================================
# ĐIỀU HƯỚNG CÁC TRANG & TRAFFIC LOGIC
# ==========================================

# 1. GIAO DIỆN KHÁCH HÀNG VÃNG LAI (Trang chủ)
@app.route('/')
def customer_portal():
    available_tests = TestCatalog.query.order_by(TestCatalog.code.asc()).all()
    return render_template('index.html', tests=available_tests)

# SỬA LỖI NÚT CHUYỂN HỆ THỐNG TRÊN TRANG VÃNG LAI (Cầu nối tự động sang Admin)
@app.route('/login')
def bridge_login_to_admin():
    return redirect(url_for('admin_portal'))

# 2. BẢNG ĐIỀU PHỐI TRUNG TÂM (Trang Admin quản trị tối cao)
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
# BIẾN XỬ LÝ LOGIC LOGISTICS & ĐẨY SANG ZALO API THẬT
# ==========================================

@app.route('/api/admin/logistics/dispatch', methods=['POST'])
def dispatch_driver():
    sid = request.form.get('trip_id')
    driver_name = request.form.get('driver_name')
    
    patient = Patient.query.get(sid)
    if patient and driver_name:
        patient.driver_name = driver_name
        patient.status = "Tài xế nhận ca - Đang di chuyển"
        db.session.commit()
        
        # --------------------------------------------------------
        # CẤU HÌNH GỬI TIN NHẮN REAL-TIME QUA ZALO OA THẬT
        # --------------------------------------------------------
        # Danh bạ số điện thoại đăng ký nhận đơn của Tài xế công ty
        driver_phones = {
            "Nguyễn Văn A": "0901234567",  # Anh thay bằng số điện thoại thật của tài xế A
            "Trần Văn B": "0912345678",  # Anh thay bằng số điện thoại thật của tài xế B
            "Lê Văn C": "0923456789"    # Anh thay bằng số điện thoại thật của tài xế C
        }
        
        driver_phone = driver_phones.get(driver_name, "")
        
        # Token bản quyền của Zalo Open API bên anh
        ZALO_OA_ACCESS_TOKEN = "YOUR_ZALO_ACCESS_TOKEN_HERE" 
        zalo_url = "https://openapi.zalo.me/v3.0/oa/message/transaction"
        
        headers = {
            "Content-Type": "application/json",
            "access_token": ZALO_OA_ACCESS_TOKEN
        }
        
        # Cấu trúc gói tin đẩy tự động sang Zalo tài xế
        zalo_payload = {
            "recipient": {"phone": driver_phone},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "transaction",
                        "language": "VI",
                        "elements": [{
                            "title": f"LỆNH ĐIỀU PHỐI LẤY MẪU: {sid}",
                            "subtitle": f"Khách hàng: {patient.name}\n📍 Địa chỉ: {patient.address}\n🌡️ Nhiệt độ yêu cầu: {patient.temperature}",
                            "image_url": "https://dxcon.onrender.com/static/logo.png"
                        }]
                    }
                }
            }
        }
        
        try:
            response = requests.post(zalo_url, json=zalo_payload, headers=headers, timeout=5)
            print(f"🚀 [ZALO API] Kết quả gửi tin nhắn cho {driver_name}: {response.json()}")
        except Exception as e:
            print(f"❌ [ZALO API] Thất bại, đang lưu log chạy ngầm: {str(e)}")
        # --------------------------------------------------------
        
    return redirect(url_for('admin_portal'))


# ==========================================
# CÁC BIẾN XỬ LÝ DỮ LIỆU ĐỒNG BỘ KHÁC
# ==========================================

@app.route('/api/admin/tests/add', methods=['POST'])
def add_test_catalog():
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
    return redirect(url_for('admin_portal'))

@app.route('/api/admin/tests/delete/<string:code>')
def delete_test_catalog(code):
    test = TestCatalog.query.get(code)
    if test:
        db.session.delete(test)
        db.session.commit()
    return redirect(url_for('admin_portal'))

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
        return jsonify({"status": "success", "message": "IoT updated"}), 200
    return jsonify({"status": "error", "message": "Not found"}), 404

@app.route('/api/customer/register', methods=['POST'])
def customer_register():
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
    return f"Đăng ký thành công! Mã số là: {new_sid}."

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
    return redirect(url_for('admin_portal'))

@app.route('/api/admin/account/delete/<int:id>')
def delete_account(id):
    acc = Account.query.get(id)
    if acc:
        db.session.delete(acc)
        db.session.commit()
    return redirect(url_for('admin_portal'))

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
    return redirect(url_for('admin_portal'))

@app.route('/khoitaodatalab')
def create_master_test_data():
    if not TestCatalog.query.get("XN01"):
        xn01 = TestCatalog(code="XN01", name="Xét nghiệm Công thức máu", category="Huyết học", tube_type="Ống EDTA (Tím)", duration="2 giờ", price="250,000 đ", function_desc="Đánh giá tình trạng thiếu máu")
        db.session.add(xn01)
    if not Patient.query.get("TRIP_2026"):
        p01 = Patient(sid="TRIP_2026", name="Nguyễn Văn Bệnh Nhân", phone="0901234567", address="Quận 1, TP. Hồ Chí Minh", chosen_lab="Lab Trung Tâm", total_amount="250,000đ", driver_name="Nguyễn Văn A", temperature="22.8 °C", battery="95%", status="Chờ điều phối")
        db.session.add(p01)
    db.session.commit()
    return redirect(url_for('admin_portal'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
