# OpenWorld — Tổng quan bằng tiếng Việt

**Trạng thái:** Dự án mã nguồn mở thực nghiệm, **chưa sẵn sàng cho production**.  
**Nguồn chuẩn:** [README tiếng Anh](../../README.md). **Đối chiếu:** 2026-10-31, từ nhánh main tại commit `6daaea93`; nội dung cần rà soát lại khi nguồn thay đổi.

OpenWorld nghiên cứu agent có danh tính riêng, bộ nhớ phân biệt bằng chứng với dự đoán, khả năng kiểm soát quyền và thế giới mô phỏng có thể phát lại. Đây **chưa** là framework LLM/MCP/A2A hoàn chỉnh hay hệ sinh thái agent hoạt động thực tế.

## Đã có gì, còn thiếu gì?

| Thành phần | Trạng thái thận trọng |
|---|---|
| HyperMemory | Có mã thử nghiệm bộ nhớ dự đoán và một luồng sự kiện chính xác; không phải trí nhớ thực được chứng thực |
| MathKernel | Có các mô hình xác suất hữu hạn để thử nghiệm; chưa chứng minh lý thuyết mới |
| World Runtime | Có thế giới mô phỏng và replay trên cùng máy; chưa phải hệ thống phân tán |
| Capability guard | Có kiểm tra quyền trong fixture; chưa phải định danh người dùng và đồng thuận production |
| Học quần thể P1–P6 | Có thí nghiệm tổng hợp, gồm cả kết quả âm; không chứng minh trí tuệ tập thể tổng quát |
| SuperKernel tích hợp | **Mục tiêu R0; chưa được nghiệm thu độc lập** |

## Bắt đầu

Xem [Hướng dẫn chạy thử](GETTING-STARTED.md), [Kiến trúc](ARCHITECTURE.md) và [Từ điển thuật ngữ](GLOSSARY.md).

Roadmap mới ưu tiên **R0: vòng đời một agent hoạt động trọn vẹn** thay vì mở rộng đồng thời nhiều nhánh. Xem [đặc tả R0 tiếng Anh](../R0-INTEGRATED-AGENT-VERTICAL-SLICE.md).

## Phạm vi và an toàn

Không đưa dữ liệu cá nhân thật, token, credential hoặc tác vụ ảnh hưởng thế giới thực vào demo. Các quan sát trong fixture là **SIMULATED**, suy luận là **INFERRED**; không được mô tả chúng như bằng chứng lịch sử **VERIFIED**. Mọi thử nghiệm cần kiểm tra quyền và ngân sách; không mặc định cho phép chia sẻ giữa các chủ sở hữu.

Tiếng Anh vẫn là nguồn chuẩn của giao thức, mã nguồn và tài liệu kỹ thuật. Trang này là tài liệu giải thích, không thay thế RFC/ADR.
