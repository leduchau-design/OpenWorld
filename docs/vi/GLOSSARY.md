# Thuật ngữ OpenWorld (Anh–Việt)

**Nguồn chuẩn:** [Architecture](../ARCHITECTURE.md), [Memory contracts](../../src/openworld_superkernel/memory_contracts.py) và [R0](../R0-INTEGRATED-AGENT-VERTICAL-SLICE.md). **Đối chiếu:** 2026-10-31 với `6daaea93`.

| Thuật ngữ | Diễn giải tiếng Việt |
|---|---|
| Agent | Tác nhân phần mềm có trạng thái, mục tiêu hoặc chính sách ra quyết định |
| SuperKernel | Bộ điều phối dự kiến cho vòng đời, công cụ và ngân sách của agent |
| HyperMemory | Thiết kế bộ nhớ kết hợp luồng bằng chứng chính xác và trạng thái dự đoán |
| MathKernel | Nhóm mô hình toán hữu hạn phục vụ nghiên cứu |
| Provenance | Nguồn gốc/loại bằng chứng của một sự kiện hoặc kết quả |
| OBSERVED_RECORDED | Quan sát được ghi nhận; không tự động có xác thực nguồn |
| VERIFIED | Được xác minh theo một quy trình cụ thể; không suy từ hash đơn thuần |
| SIMULATED | Dữ liệu phát sinh từ môi trường mô phỏng, không phải sự kiện đời thực |
| INFERRED | Giá trị được suy luận/dự đoán, không phải quan sát thực tế |
| Exact event ledger | Nhật ký giữ sự kiện cần tra cứu chính xác theo phạm vi lưu giữ |
| Predictive state | Trạng thái tóm tắt để hỗ trợ dự báo, có thể mất thông tin |
| Capability | Quyền có phạm vi cụ thể, gắn với chủ thể, đối tượng, hành động và thời hạn |
| Replay | Phát lại các đầu vào đã ghi để kiểm tra trạng thái của mô hình |
| Baseline | Phương pháp đơn giản dùng làm mốc so sánh công bằng |
| Holdout seed | Seed chưa sử dụng để chọn/tinh chỉnh thuật toán trước phép đánh giá |
| Fail-closed | Mặc định từ chối khi quyền hoặc dữ liệu kiểm tra không rõ ràng |

Tên các thành phần và nhãn lập trình giữ nguyên tiếng Anh để tránh nhầm lẫn giữa tài liệu và mã.
