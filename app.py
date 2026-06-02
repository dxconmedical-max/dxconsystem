import os
import requests
from flask import Flask, request, redirect, url_for, flash
from models import db, Patient # Giả định anh đã có file models.py

app = Flask(__name__)

# Hàm tính khoảng cách (Gọi Google Maps API)
def get_distance_km(origin, destination):
    api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origin}&destinations={destination}&key={api_key}"
    try:
        response = requests.get(url).json()
        meters = response['rows'][0]['elements'][0]['distance']['value']
        return round(meters / 1000, 1)
    except:
        return 0.0

# API Điều phối (Mục 3.5)
@app.route('/api/admin/logistics/dispatch', methods=['POST'])
def dispatch_logistics():
    trip_id = request.form.get('trip_id')
    driver_name = request.form.get('driver_name')
    
    # 1. Tìm bệnh nhân trong DB
    patient = Patient.query.filter_by(sid=trip_id).first()
    if patient:
        # 2. Tính khoảng cách từ Lab đến Bệnh nhân
        lab_address = "Địa chỉ phòng Lab của anh"
        patient.distance = get_distance_km(lab_address, patient.address)
        
        # 3. Gửi Zalo OA cho tài xế
        zalo_url = "https://openapi.zalo.me/v3.0/oa/message/cs"
        headers = {"access_token": os.environ.get('ZALO_ACCESS_TOKEN')}
        payload = {
            "recipient": {"phone": "09xxxxxxx"}, # SĐT tài xế
            "message": {"text": f"Lệnh điều phối mới: Đón bệnh nhân {patient.name} tại {patient.address}. Khoảng cách: {patient.distance}km"}
        }
        requests.post(zalo_url, json=payload, headers=headers)
        
        db.session.commit()
        flash("Điều phối thành công!")
        
    return redirect(url_for('admin_portal'))
