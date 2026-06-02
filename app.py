import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'dxcon_secret_key' # Anh có thể thay đổi key này

# Cấu hình Database từ biến môi trường Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODEL (Đã gộp chung vào app.py để không cần file models.py) ---
class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    sid = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(100))
    address = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    status = db.Column(db.String(50))
    distance = db.Column(db.Float, default=0.0)

# Tự động tạo bảng nếu chưa có
with app.app_context():
    db.create_all()

# --- ROUTES ---

@app.route('/')
def index():
    return "DXCON Server is Running - System Ready"

@app.route('/admin')
def admin_portal():
    patients = Patient.query.all()
    return render_template('admin.html', crm_patients=patients)

# Route khởi tạo dữ liệu mẫu (Truy cập link này để reset data)
@app.route('/khoitaodatalab')
def khoitaodatalab():
    db.session.query(Patient).delete()
    sample = Patient(sid='SID060201', name='Nguyễn Văn Bệnh Nhân', address='Quận 1, TP. HCM', status='Mới')
    db.session.add(sample)
    db.session.commit()
    return redirect(url_for('admin_portal'))

@app.route('/api/admin/logistics/dispatch', methods=['POST'])
def dispatch_logistics():
    # Logic xử lý điều phối tại đây
    flash("Đã đẩy lệnh Zalo thành công!")
    return redirect(url_for('admin_portal'))

if __name__ == '__main__':
    app.run(debug=True)
