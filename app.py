import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "dxcon_secret_key_bao_mat" # Khóa để chạy các lệnh thông báo (flash message)

# ==========================================
# CẤU HÌNH KẾT NỐI POSTGRESQL CHÍNH THỨC
# ==========================================
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://dxcon_admin:qmaBoXCBLanF3b3jZwDnhFk5P719JZ8C@dpg-d8f6psl9j78s73fsl6qg-a/dxcon_prod'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# ĐỊNH NGHĨA CÁC BẢNG LƯU TRỮ (DATABASE MODELS)
# ==========================================

# 1. Bảng lưu tài khoản (Module 3.1)
class Account(db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    partner = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)

# 2. Bảng lưu hợp đồng & Portal đối tác B2B (Module 3.2 & 3.6)
class Contract(db.Model):
    __tablename__ = 'contracts'
    id = db.Column(db.String(50), primary_key=True) # Mã hợp đồng / Mã định danh
    partner_name = db.Column(db.String(200), nullable=False)
    discount = db.Column(db.Float, default=0.0)
    lab_result_url = db.Column(db.String(500))
    lab_account_shared = db.Column(db.String(200))

# 3. Bảng lưu bệnh nhân CRM & Logistics (Module 3.3 & 3.5)
class Patient(db.Model):
    __tablename__ = 'patients'
    sid = db.Column(db.String(50), primary_key=True) # Mã bệnh nhân (SID)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50))
    address = db.Column(db.String(500))
    chosen_lab = db.Column(db.String(200))
    total_amount = db.Column(db.String(50), default="0")
    ai_suggested = db.Column(db.Text, default="Chờ phân tích...")
    driver_name = db.Column(db.String(150), default="Chưa chỉ định")
    temperature = db.Column(db.String(50), default="22.5 °C")
    battery = db.Column(db.String(50), default="95%")
    status = db.Column(db.String(100), default="Chờ điều phối")

# 4. Bảng lưu danh mục gói xét nghiệm (Module 3.4)
class TestCatalog(db.Model):
    __tablename__ = 'test_catalogs'
    code = db.Column(db.String(50), primary_key=True) # Mã XN
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    tube_type = db.Column(db.String(100))
    duration = db.Column(db.String(50))
    price = db.Column(db.Integer, default=0)
    function_desc = db.Column(db.Text)

# TỰ ĐỘNG KHỞI TẠO BẢNG TRÊN POSTGRESQL NẾU CHƯA CÓ
with app.app_context():
    db.create_all()


# ==========================================
# CÁC ĐƯỜNG DẪN ĐIỀU HƯỚNG VÀ API (ROUTES)
# ==========================================

# 1. TRANG CHỦ QUẢN TRỊ TRUNG TÂM (Đổ dữ liệu từ Database ra 6 Tab)
@app.route('/')
@app.route('/admin')
def admin_portal():
    # Lấy toàn bộ dữ liệu thực tế từ két sắt Postgres để hiển thị lên HTML
    all_accounts = Account.query.order_by(Account.id.desc()).all()
    all_contracts = Contract.query.all()
    all_patients = Patient.query.all()
    all_tests = TestCatalog.query.all()
    
    return render_template('admin.html', 
                           accounts=all_accounts, 
                           contracts=all_contracts, 
                           crm_patients=all_patients,
                           tests=all_tests)


# 2. API MODULE 3.1: THÊM & XÓA TÀI KHOẢN
@app.route('/api/admin/account/add', methods=['POST'])
def add_account():
    username = request.form.get('username')
    password = request.form.get('password')
    partner = request.form.get('partner')
    role = request.form.get('role')
    
    if username and password:
        # Kiểm tra trùng tên đăng nhập
        exists = Account.query.filter_by(username=username).first()
        if exists:
            return "Tài khoản đã tồn tại!", 400
            
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


# 3. API MODULE 3.2 & 3.6: LƯU ĐỐI TÁC HỢP ĐỒNG & CẤU HÌNH PORTAL LAB
@app.route('/api/admin/contract/add', methods=['POST'])
def add_contract():
    hd_id = request.form.get('hd_id')
    partner_name = request.form.get('partner_name')
    discount_str = request.form.get('discount', '0')
    lab_result_url = request.form.get('lab_result_url')
    lab_account_shared = request.form.get('lab_account_shared')
    
    try:
        discount = float(discount_str)
    except ValueError:
        discount = 0.0

    if hd_id and partner_name:
        # Nếu đã có mã hợp đồng này thì cập nhật thông số Portal, chưa có thì tạo mới
        contract = Contract.query.get(hd_id)
        if not contract:
            contract = Contract(id=hd_id)
            db.session.add(contract)
            
        contract.partner_name = partner_name
        contract.discount = discount
        contract.lab_result_url = lab_result_url
        contract.lab_account_shared = lab_account_shared
        
        db.session.commit()
    return redirect('/admin')

@app.route('/api/admin/contract/delete/<string:id>')
def delete_contract(id):
    contract = Contract.query.get(id)
    if contract:
        db.session.delete(contract)
        db.session.commit()
    return redirect('/admin')


# 4. API MODULE 3.3: QUẢN LÝ DỮ LIỆU BỆNH NHÂN CRM (Thêm test / Xóa)
@app.route('/testdata')
def add_test_patient():
    # Tạo nhanh dữ liệu mẫu để chạy thử nghiệm hệ thống
    test_patient = Patient(
        sid="SID060201",
        name="Nguyễn Văn Bệnh Nhân",
        phone="0901234567",
        address="Quận 1, TP. Hồ Chí Minh",
        chosen_lab="Hệ Thống Lab Hoàn Mỹ",
        total_amount="250,000",
        ai_suggested="Chẩn đoán thiếu máu nhẹ dựa trên chỉ số hồng cầu, đề xuất bổ sung sắt.",
        driver_name="Nguyễn Văn A",
        status="Đang lấy mẫu"
    )
    # Lưu vào Postgres
    exists = Patient.query.get(test_patient.sid)
    if not exists:
        db.session.add(test_patient)
        db.session.commit()
    return redirect('/admin')

@app.route('/api/admin/patient/delete/<string:sid>')
def delete_patient(sid):
    p = Patient.query.get(sid)
    if p:
        db.session.delete(p)
        db.session.commit()
    return redirect('/admin')


# 5. API MODULE 3.4: THÊM / CẬP NHẬT DANH MỤC GÓI XÉT NGHIỆM
@app.route('/api/admin/tests/add', methods=['POST'])
def add_test_catalog():
    code = request.form.get('code')
    name = request.form.get('name')
    category = request.form.get('category')
    tube_type = request.form.get('tube_type')
    duration = request.form.get('duration')
    price_str = request.form.get('price', '0')
    function_desc = request.form.get('function_desc')
    
    try:
        price = int(price_str)
    except ValueError:
        price = 0
        
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


# 6. API MODULE 3.5: ĐIỀU PHỐI CHỈ ĐỊNH TÀI XẾ LOGISTICS NHANH
@app.route('/api/admin/logistics/dispatch', methods=['POST'])
def dispatch_driver():
    sid = request.form.get('trip_id') # Form gửi mã bệnh nhân/mã chuyến đi lên
    driver_name = request.form.get('driver_name')
    
    patient = Patient.query.get(sid)
    if patient and driver_name:
        patient.driver_name = driver_name
        patient.status = "Tài xế nhận ca - Đang di chuyển"
        db.session.commit()
    return redirect('/admin')


# ==========================================
# KHỞI CHẠY ỨNG DỤNG
# ==========================================
if __name__ == '__main__':
    # Chạy cục bộ ở cổng 5000 để kiểm tra
    app.run(host='0.0.0.0', port=5000, debug=True)
