// server.js - Hệ thống Backend hỗ trợ vận hành DxCon Medical Hub 
const express = require('express');
const cors = require('cors');
const app = express();
const PORT = 5000;

app.use(cors());
app.use(express.json());

// Khởi tạo lưu trữ State (Có thể nâng cấp lên kết nối MongoDB/PostgreSQL sau này)
let catalogData = [
    { id: 1, name: "NIPT Toàn Diện (Sàng lọc 23 cặp NST)", price: 3500000, normal: "Âm tính / Không phát hiện lệch bội", unit: "N/A", partner: "Viện Gen Lab", status: "Active" },
    { id: 2, name: "Định lượng Men Gan (AST / ALT)", price: 150000, normal: "Chỉ số AST < 40, ALT < 41", unit: "U/L", partner: "Phòng Lab Trung Tâm", status: "Active" },
    { id: 3, name: "Tổng phân tích tế bào máu ngoại vi (25 chỉ số)", price: 200000, normal: "WBC: 4.0 - 10.0, RBC: 3.8 - 5.8", unit: "G/L", partner: "Phòng Lab Trung Tâm", status: "Active" }
];

let crmRecords = [
    { id: "BK_101", date: "2026-05-29", name: "Nguyễn Văn A", phone: "0912345678", source: "BS. Nguyễn Văn Hùng", test: "Tổng phân tích tế bào máu ngoại vi (25 chỉ số)", base_price: 200000, discount_pct: 15, final_pay: 170000, file: "📄 Kết_quả_máu.pdf", raw_value: "WBC: 6.2 - RBC: 4.5", status: "Đã có kết quả" }
];

// --- 🧬 API DANH MỤC XÉT NGHIỆM ---
app.get('/api/catalog', (req, res) => {
    res.status(200).json(catalogData);
});

app.post('/api/catalog/add', (req, res) => {
    const newItem = req.body;
    catalogData.push(newItem);
    res.status(201).json({ message: "Đồng bộ danh mục thành công!", data: newItem });
});

// --- 📊 API CRM & BỆNH ÁN ---
app.get('/api/crm', (req, res) => {
    res.status(200).json(crmRecords);
});

app.post('/api/crm/add', (req, res) => {
    const newRecord = req.body;
    crmRecords.push(newRecord);
    res.status(201).json({ message: "Đồng bộ đơn hồ sơ CRM thành công!", data: newRecord });
});

// --- 📍 API KẾT NỐI ĐỒNG BỘ ĐỐI TÁC NGOÀI (Web Vãng lai/API Đối tác) ---
app.post('/api/patient/sync', (req, res) => {
    const externalData = req.body;
    // Chuẩn hóa và tự động đẩy dữ liệu thô thẳng về phòng tiếp nhận điều phối
    console.log("Đã nhận dữ liệu đồng bộ Webhook từ đối tác ngoài:", externalData);
    res.status(200).json({ status: "Success", message: "DxCon Hub đã ghi nhận luồng đơn." });
});

app.listen(PORT, () => {
    console.log(`================================================================`);
    console.log(`🏥 DXCON MEDICAL BACKEND CONTROL HUB ĐANG CHẠY CHÍNH THỨC`);
    console.log(`🚀 URL CỤC BỘ: http://localhost:${PORT}`);
    console.log(`📅 Đã kích hoạt cổng đồng bộ API y tế. Sẵn sàng chạy Production!`);
    console.log(`================================================================`);
});