import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

# 1. Khởi tạo App
app = Flask(__name__)
app.secret_key = 'dxcon_secret_key'

# 2. Cấu hình Database
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 3. Khởi tạo DB với App
db = SQLAlchemy(app)

# 4. Định nghĩa Model (Gộp chung để tránh lỗi ModuleNotFound)
class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    sid = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    address = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    status = db.Column(db.String(50))
    distance = db.Column(db.Float, default=0.0)

# Tạo bảng tự động
with app.app_context():
    db.create_all()

# 5. Các Route xử lý
@app.route('/')
def index():
    return "DXCON Server is Running - System Ready"

@app.route('/admin')
def admin_portal():
    patients = Patient.query.all()
    return render_template('admin.html', crm_patients=patients)

@app.route('/khoitaodatalab')
def khoitaodatalab():
    db.session.query(Patient).delete()
    sample = Patient(sid='SID060201', name='Nguyễn Văn Bệnh Nhân', address='Quận 1, TP. HCM', status='Mới')
    db.session.add(sample)
    db.session.commit()
    return redirect(url_for('admin_portal'))

@app.route('/api/admin/logistics/dispatch', methods=['POST'])
def dispatch_logistics():
    flash("Đã đẩy lệnh Zalo thành công!")
    return redirect(url_for('admin_portal'))

if __name__ == '__main__':
    app.run(debug=True)
    db_url = os.environ.get('DATABASE_URL')
print(f"DEBUG DATABASE URL: {db_url}") # Dòng này giúp anh kiểm tra trong Log

if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
