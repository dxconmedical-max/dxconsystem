import os
import random
import requests
from flask import Flask, render_template_string, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "dxcon_secret_key_master_system"

# CẤU HÌNH KẾT NỐI POSTGRESQL CHÍNH THỨC
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://dxcon_admin:qmaBoXCBLanF3b3jZwDnhFk5P719JZ8C@dpg-d8f6psl9j78s73fsl6qg-a/dxcon_prod'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ĐỊNH NGHĨA CÁC BẢNG LƯU TRỮ (DATABASE MODELS)
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

# GIAO DIỆN KHÁCH HÀNG VÃNG LAI
@app.route('/')
def customer_portal():
    return "<h3>Hệ thống DXCON đang hoạt động. Vui lòng truy cập /admin để vào cổng quản trị.</h3>"

@app.route('/login')
def bridge_login_to_admin():
    return redirect(url_for('admin_portal'))

# ==========================================
# GIAO DIỆN ADMIN TỰ ĐỘNG (ÉP RENDER HIỂN THỊ 100%)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>DXCON - Hệ Thống Quản Trị Tối Cao</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background: #f4f6f9; color: #333; }
        .header { background: #0066cc; color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .header h1 { margin: 0; font-size: 22px; }
        .container { padding: 25px; max-width: 1400px; margin: 0 auto; }
        .tab-menu { display: flex; background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 25px; gap: 10px; }
        .tab-btn { padding: 10px 18px; border: none; background: none; font-size: 14px; font-weight: 600; color: #64748b; cursor: pointer; border-radius: 6px; }
        .tab-btn.active { background: #0066cc; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .card h3 { margin-top: 0; margin-bottom: 15px; color: #1e3a8a; border-bottom: 2px solid #f1f5f9; padding-bottom: 8px; }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
        th { background: #f1f5f9; padding: 12px; font-weight: 600; color: #334155; border-bottom: 2px solid #e2e8f0; }
        td { padding: 12px; border-bottom: 1px solid #e2e8f0; vertical-align: middle; }
        tr:hover { background: #f8fafc; }
        .badge { padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; display: inline-block; background: #e0f2fe; color: #0369a1; }
    </style>
</head>
<body>

    <div class="header">
        <h1>🏥 DXCON MEDICAL MASTER PORTAL (BẢN CẬP NHẬT TRỰC TIẾP)</h1>
        <span style="font-size: 13px; background: rgba(255,255,255,0.2); padding: 5px 12px; border-radius: 20px;">⚙️ DB Connection: <b>Đã kết nối PostgreSQL</b></span>
    </div>

    <div class="container">
        <div class="tab-menu">
            <button class="tab-btn" onclick="switchTab(event, 'tab-crm')">👥 3.3 CRM Bệnh Nhân</button>
            <button class="tab-btn active" onclick="switchTab(event, 'tab-logistics')">🚚 3.5 Điều Phối Đơn & Zalo API</button>
        </div>

        <div id="tab-crm" class="tab-content">
            <div class="card">
                <h3>👥 Hồ Sơ CRM Bệnh Nhân</h3>
                <table>
                    <thead><tr><th>Mã SID</th><th>Họ Tên</th><th>Số Điện Thoại</th><th>Địa Chỉ</th><th>Tổng Tiền</th></tr></thead>
                    <tbody>
                        {% for p in crm_patients %}
                        <tr>
                            <td><b>{{ p.sid }}</b></td>
                            <td><b>{{ p.name }}</b></td>
                            <td>{{ p.phone }}</td>
                            <td>{{ p.address }}</td>
                            <td style="color: #059669; font-weight: bold;">{{ p.total_amount }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div id="tab-logistics" class="tab-content active">
            <div class="card">
                <h3>🚚 Điều Phối Tài Xế Nhận Ca & Bắn Lệnh Zalo Real-time</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Mã Đơn</th>
                            <th>Bệnh Nhân</th>
                            <th>📍 Vị Trí Bản Đồ</th>
                            <th>📏 Ước Tính</th>
                            <th>👤 Tài Xế Hiện Tại</th>
                            <th>🌡️ IoT Thùng Lạnh</th>
                            <th>🔋 Pin</th>
                            <th>Trạng Thái</th>
                            <th style="text-align: center;">Chỉ Định & Đẩy Lệnh</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in crm_patients %}
                        <tr>
                            <td style="font-weight: bold; color: #0066cc;">{{ p.sid }}</td>
                            <td><b>{{ p.name }}</b></td>
                            <td>
                                <a href="https://www.google.com/maps/search/?api=1&query={{ p.address }}" target="_blank" style="color: #0066cc; text-decoration: none; font-weight: bold;">
                                    🗺️ Xem Bản Đồ Goole
                                </a>
                            </td>
                            <td><span style="background: #fef3c7; color: #d97706; padding: 4px 8px; border-radius: 4px; font-weight: bold;">~6.5 km</span></td>
                            <td style="color: #059669; font-weight: bold;">{{ p.driver_name }}</td>
                            <td style="color: #dc2626; font-weight: bold;">{{ p.temperature }}</td>
                            <td>⚡ {{ p.battery }}</td>
                            <td><span class="badge">{{ p.status }}</span></td>
                            <td>
                                <form action="/api/admin/logistics/dispatch" method="POST" style="display: flex; gap: 5px; justify-content: center; margin: 0;">
                                    <input type="hidden" name="trip_id" value="{{ p.sid }}">
                                    <select name="driver_name" style="padding: 5px; border-radius: 4px;">
                                        <option value="Nguyễn Văn A">Nguyễn Văn A</option>
                                        <option value="Trần Văn B">Trần Văn B</option>
                                        <option value="Lê Văn C">Lê Văn C</option>
                                    </select>
                                    <button type="submit" style="background: #0066cc; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-weight: bold; cursor: pointer;">
                                        💬 Đẩy Zalo
                                    </button>
                                </form>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function switchTab(evt, tabId) {
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tab-content");
            for (i = 0; i < tabcontent.length; i++) { tabcontent[i].classList.remove("active"); }
            tablinks = document.getElementsByClassName("tab-btn");
            for (i = 0; i < tablinks.length; i++) { tablinks[i].classList.remove("active"); }
            document.getElementById(tabId).classList.add("active");
            evt.currentTarget.classList.add("active");
        }
    </script>
</body>
</html>
"""

@app.route('/admin')
def admin_portal():
    all_patients = Patient.query.order_by(Patient.sid.desc()).all()
    return render_template_string(HTML_TEMPLATE, crm_patients=all_patients)

@app.route('/api/admin/logistics/dispatch', methods=['POST'])
def dispatch_driver():
    sid = request.form.get('trip_id')
    driver_name = request.form.get('driver_name')
    
    patient = Patient.query.get(sid)
    if patient and driver_name:
        patient.driver_name = driver_name
        patient.status = "Tài xế nhận ca - Đang di chuyển"
        db.session.commit()
        
        # ĐẨY TIN NHẮN THẬT SANG ZALO TÀI XẾ
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
                            "title": f"LỆNH ĐIỀU PHỐI MỚI: {sid}",
                            "subtitle": f"Khách hàng: {patient.name}\\n📍 Địa chỉ: {patient.address}",
                            "image_url": "https://dxcon.onrender.com/static/logo.png"
                        }]
                    }
                }
            }
        }
        try:
            requests.post(zalo_url, json=zalo_payload, headers={"Content-Type": "application/json", "access_token": ZALO_OA_ACCESS_TOKEN}, timeout=5)
        except:
            pass
            
    return redirect(url_for('admin_portal'))

@app.route('/khoitaodatalab')
def create_master_test_data():
    if not Patient.query.get("TRIP_2026"):
        p01 = Patient(sid="TRIP_2026", name="Nguyễn Văn Bệnh Nhân", phone="0901234567", address="Quận 1, TP. Hồ Chí Minh", chosen_lab="Lab Trung Tâm", total_amount="250,000đ", driver_name="Nguyễn Văn A", temperature="22.8 °C", battery="95%", status="Chờ điều phối")
        db.session.add(p01)
        db.session.commit()
    return redirect(url_for('admin_portal'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
