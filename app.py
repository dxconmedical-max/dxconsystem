<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>DXCON Medical Master Portal - Quản trị hệ thống</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f4f6f9; margin: 0; }
        .sidebar { width: 250px; background: #1e293b; color: white; position: fixed; height: 100vh; padding: 20px; }
        .main-content { margin-left: 290px; padding: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        h2 { color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
        .section { margin-bottom: 30px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h3>DXCON ADMIN</h3>
        <nav>
            <p>3.1 Tổng quan Dashboard</p>
            <p>3.2 Quản lý Lab/Đối tác</p>
            <p>3.3 Quản lý Bệnh nhân (CRM)</p>
            <p>3.4 Danh mục Xét nghiệm</p>
            <p>3.5 Điều phối & Logistics</p>
            <p>3.6 Cấu hình hệ thống</p>
        </nav>
    </div>

    <div class="main-content">
        <div class="card section" id="section-3-1-3-2">
            <h2>3.1 & 3.2 Tổng quan & Đối tác</h2>
            <p>Hiển thị số lượng đơn hàng trong ngày và danh sách các Lab liên kết.</p>
        </div>

        <div class="card section" id="section-3-3">
            <h2>3.3 CRM Bệnh nhân</h2>
            <table>
                {% for p in crm_patients %}
                <tr><td>{{ p.sid }}</td><td>{{ p.name }}</td><td>{{ p.phone }}</td></tr>
                {% endfor %}
            </table>
        </div>

        <div class="card section" id="section-3-5">
            <h2>3.5 Điều phối Logistics</h2>
            <p>Tích hợp: Google Maps API (Đo Km), Zalo OA API (Thông báo tài xế & Bệnh nhân).</p>
            </div>
    </div>
</body>
</html>
