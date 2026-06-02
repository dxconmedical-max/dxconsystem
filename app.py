import os
import random
import requests
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.secret_key = "dxcon_secret_key_master_system_v4"

# CẤU HÌNH KẾT NỐI POSTGRESQL CHÍNH THỨC
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://dxcon_admin:qmaBoXCBLanF3b3jZwDnhFk5P719JZ8C@dpg-d8f6psl9j78s73fsl6qg-a/dxcon_prod'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# DATABASE MODELS
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
    result_url = db.Column(db.String(500), default="https://dxcon.onrender.com/results/default.pdf")

class TestCatalog(db.Model):
    __tablename__ = 'test_catalogs'
    code = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    tube_type = db.Column(db.String(100))
    duration = db.Column(db.String(50))
    price = db.Column(db.String(150), default="0")
    function_desc = db.Column(db.Text)

# HÀM CHUYÊN GIA: TỰ ĐỘNG SỬA ĐỔI VÀ ĐỒNG BỘ CẤU TRÚC POSTGRESQL THỰC TẾ
def auto_migrate_database():
    with app.app_context():
        db.create_all()
        # Ép database bổ sung cột result_url vào bảng patients nếu chưa có (Tránh lỗi 500)
        try:
            db.session.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS result_url VARCHAR(500) DEFAULT 'https://dxcon.onrender.com/results/default.pdf';"))
            db.session.execute(text("ALTER TABLE test_catalogs ALTER COLUMN price TYPE VARCHAR(150);"))
            db.session.commit()
            print("--- ĐÃ TỰ ĐỘNG ĐỒNG BỘ CẤU TRÚC DATABASE THÀNH CÔNG ---")
        except Exception as e:
            db.session.rollback()
            print(f"Log migration: {str(e)}")

auto_migrate_database()

# ==========================================
# ROUTING CONTROLLER
# ==========================================

@app.route('/')
def customer_portal():
    return "<h3>Hệ thống DXCON đang hoạt động ổn định. Vui lòng truy cập /admin để vào cổng quản trị điều phối.</h3>"

@app.route('/login')
def bridge_login_to_admin():
    return redirect(url_for('admin_portal'))

@app.route('/admin')
def admin_portal():
    try:
        all_accounts = Account.query.order_by(Account.id.desc()).all()
        all_contracts = Contract.query.all()
        all_patients = Patient.query.order_by(Patient.sid.desc()).all()
        all_tests = TestCatalog.query.order_by(TestCatalog.code.asc()).all()
        
        return render_template('admin.html', 
                               accounts=all_accounts, 
                               contracts=all_contracts, 
                               crm_patients=all_patients,
                               tests=all_tests)
    except Exception as db_err:
        # Nếu database dính lỗi dữ liệu cũ nặng, trả về giao diện cứu hộ để dọn sạch bằng 1 click
        return f"""
        <div style='padding:40px; font-family:sans-serif; text-align:center;'>
            <h2 style='color:#dc2626;'>⚠️ Hệ thống phát hiện dữ liệu cũ xung đột cấu trúc bảng công nghệ!</h2>
            <p>Vui lòng bấm vào nút dưới đây để Chuyên gia hệ thống dọn sạch bảng và tái cấu trúc tự động:</p>
            <a href='/khoitaodatalab' style='background:#0066cc; color:white; padding:12px 25px; text-decoration:none; border-radius:5px; font-weight:bold; display:inline-block; margin-top:15px;'>👉 CLICK ĐỂ RESET & KHỞI TẠO LẠI HỆ THỐNG MỚI</a>
            <br><br><small style='color:#64748b;'>Chi tiết lỗi hệ thống: {str(db_err)}</small>
        </div>
        """

@app.route('/api/admin/logistics/dispatch', methods=['POST'])
def dispatch_driver():
    sid = request.form.get('trip_id')
    driver_name = request.form.get('driver_name')
    
    patient = Patient.query.get(sid)
    if patient and driver_name:
        patient.driver_name = driver_name
        patient.status = "Đang lấy mẫu"
        db.session.commit()
        
        driver_phones = {"Nguyễn Văn A": "0901234567", "Trần Văn B": "0912345678", "Lê Văn C": "0923456789"}
        driver_phone = driver_phones.get(driver_name, "")
        
        ZALO_OA_ACCESS_TOKEN = "YOUR_ZALO_ACCESS_TOKEN_HERE"
        zalo_url = "https://openapi.zalo.me/v3.0/oa/message/transaction"
        
        zalo_payload = {
            "recipient": {"phone": driver_phone},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "transaction",
                        "language": "VI",
                        "elements": [{
                            "title": f"LỆNH ĐIỀU PHỐI LẤY MẪU MỚI: {sid}",
                            "subtitle": f"Khách hàng: {patient.name}\\n📍 Địa chỉ: {patient.address}",
                            "image_url": "https://dxcon.onrender.com/static/logo.png"
                        }]
                    }
                }
            }
        }
        try: requests.post(zalo_url, json=zalo_payload, headers={"Content-Type": "application/json", "access_token": ZALO_OA_ACCESS_TOKEN}, timeout=5)
        except: pass
            
    return redirect(url_for('admin_portal'))

@app.route('/api/admin/logistics/send-result', methods=['POST'])
def send_patient_result():
    sid = request.form.get('trip_id')
    patient = Patient.query.get(sid)
    
    if patient and patient.phone:
        patient.status = "Đã báo kết quả qua Zalo"
        db.session.commit()
        
        ZALO_OA_ACCESS_TOKEN = "YOUR_ZALO_ACCESS_TOKEN_HERE"
        zalo_url = "https://openapi.zalo.me/v3.0/oa/message/transaction"
        
        zalo_payload = {
            "recipient": {"phone": patient.phone},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "transaction",
                        "language": "VI",
                        "elements": [{
                            "title": f"THÔNG BÁO KẾT QUẢ XÉT NGHIỆM: {patient.name}",
                            "subtitle": f"Mã kết quả: {sid}\\nKết quả xét nghiệm của bạn đã hoàn thành. Vui lòng bấm vào nút bên dưới để xem báo cáo chi tiết.",
                            "image_url": "https://dxcon.onrender.com/static/result_banner.png"
                        }],
                        "buttons": [{
                            "title": "Xem Kết Quả Chi Tiết",
                            "type": "oa.open.url",
                            "payload": {"url": patient.result_url}
                        }]
                    }
                }
            }
        }
        try: requests.post(zalo_url, json=zalo_payload, headers={"Content-Type": "application/json", "access_token": ZALO_OA_ACCESS_TOKEN}, timeout=5)
        except: pass
            
    return redirect(url_for('admin_portal'))

@app.route('/khoitaodatalab')
def create_master_test_data():
    try:
        # Xóa dữ liệu cũ dính cấu trúc lỗi
        db.session.query(Patient).delete()
        db.session.query(TestCatalog).delete()
        db.session.query(Account).delete()
        db.session.query(Contract).delete()
        
        # Khởi tạo bộ dữ liệu chuẩn mới tinh thích ứng 100%
        p01 = Patient(
            sid="TRIP_2026", 
            name="Nguyễn Văn Bệnh Nhân mẫu", 
            phone="0901234567", 
            address="Quận 1, TP. Hồ Chí Minh", 
            chosen_lab="Lab Trung Tâm", 
            total_amount="250,000 đ", 
            driver_name="Nguyễn Văn A", 
            temperature="22.8 °C", 
            battery="95%", 
            status="Chờ điều phối",
            result_url="https://dxcon.onrender.com/results/sid2026.pdf"
        )
        xn01 = TestCatalog(code="XN01", name="Xét nghiệm mẫu", category="Tổng quát", tube_type="Ống EDTA", duration="2 giờ", price="250,000 đ")
        
        db.session.add(p01)
        db.session.add(xn01)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return f"Lỗi khởi tạo lại: {str(e)}"
    return redirect(url_for('admin_portal'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
