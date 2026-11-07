# Giải thích kiến trúc OpenWorld

**Nguồn chuẩn:** [Architecture — Draft RFC-005](../ARCHITECTURE.md) và [R0 vertical slice](../R0-INTEGRATED-AGENT-VERTICAL-SLICE.md). **Đối chiếu:** 2026-10-31, `main` `6daaea93`. Tài liệu giải thích này không phải giao thức chuẩn hóa.

## Mô hình đơn giản

**Mục tiêu → Quan sát → Bộ nhớ/dự đoán → Chính sách → Kiểm tra quyền/ngân sách → Hành động mô phỏng → Nhật ký/replay.**

- **SuperKernel** là bộ điều phối vòng đời dự kiến. Chưa có một runtime chuẩn duy nhất xuất đầy đủ qua package.
- **HyperMemory** giữ riêng sự kiện cần lưu chính xác và trạng thái dự đoán. Tóm tắt dự đoán không thể thay thế mọi sự kiện lịch sử.
- **MathKernel** mô hình hóa xác suất/trạng thái theo nhiệm vụ, không cấp phép hoặc chứng thực sự kiện.
- **World Runtime** là thế giới thử nghiệm xác định, ghi đầu vào để phát lại; sự kiện được dán nhãn `SIMULATED`.
- **Capability guard** từ chối hành động không hợp lệ; token ký trong fixture không tự chứng minh danh tính người dùng thật.

## Bốn ranh giới bắt buộc

1. Danh tính agent độc lập với trọng số model, bộ nhớ và quyền.
2. Quan sát **SIMULATED**, suy luận **INFERRED** không biến thành **VERIFIED** chỉ vì có hash hay replay.
3. Hành động có hậu quả phải được cấp quyền rõ ràng; tương tác khác chủ vẫn từ chối.
4. World trong RAM và bộ nhớ SQLite **không** cùng một giao dịch nguyên tử. Không mô tả demo như hệ thống phân tán đáng tin cậy.

Định hướng R0 chỉ tích hợp đúng một chu trình agent với các test âm và baseline, không mở ngay federation, GPU hoặc MCP/A2A.
