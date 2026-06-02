import requests
from flask import request, jsonify

# Giả định: Anh đã lưu ZALO_ACCESS_TOKEN và GOOGLE_MAPS_API_KEY vào Environment Variables trên Render

@app.route('/api/admin/logistics/dispatch', methods=['POST'])
def dispatch_logistics():
    trip_id = request.form.get('trip_id')
    driver_name = request.form.get('driver_name')
    
    # 1. Logic tính khoảng cách (Giả định gọi Google Maps API)
    # distance = calculate_distance_google_maps(start_addr, end_addr)
    distance = "6.5 km" # Demo: Sau này anh thay bằng hàm gọi API thật
    
    # 2. Logic gọi Zalo OA API
    zalo_url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    headers = {"access_token": "YOUR_ZALO_ACCESS_TOKEN"}
    data = {
        "recipient": {"phone": "090xxxxxxx"}, # Số điện thoại tài xế
        "message": {"text": f"Đơn hàng {trip_id} đã được điều phối cho tài xế {driver_name}. Khoảng cách: {distance}"}
    }
    
    response = requests.post(zalo_url, json=data, headers=headers)
    
    if response.status_code == 200:
        return "Đã gửi Zalo thành công cho tài xế!", 200
    else:
        return "Lỗi gửi Zalo", 500
        import os
import requests

def get_distance_km(origin_address, destination_address):
    # API Key được lấy từ biến môi trường (Bảo mật tuyệt đối)
    api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origin_address}&destinations={destination_address}&key={api_key}"
    
    try:
        response = requests.get(url).json()
        # Lấy giá trị distance tính bằng mét rồi đổi sang km
        distance_meters = response['rows'][0]['elements'][0]['distance']['value']
        return round(distance_meters / 1000, 1)
    except Exception as e:
        return 0.0 # Trả về 0 nếu lỗi API hoặc không tìm thấy địa chỉ
