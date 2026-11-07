# Bắt đầu với OpenWorld

**Nguồn chuẩn:** [README](../../README.md), [R0 acceptance plan](../R0-INTEGRATED-AGENT-VERTICAL-SLICE.md). **Đối chiếu:** 2026-10-31 với `main` tại `6daaea93`. Các lệnh demo bên dưới đã tồn tại trong mã nguồn; tài liệu này không khẳng định đã tự chạy lại tất cả trên máy khác.

## Chuẩn bị

Python 3.11+ và một bản clone repository. Không cần GPU, API key của model hay dịch vụ có phí.

    git clone https://github.com/CocAgent/OpenWorld.git
    cd OpenWorld
    python -m unittest discover -s tests -v
    python scripts/check_repository.py

## Hai demo đang có

Thế giới W3 nhỏ, mô phỏng các agent và kiểm tra replay:

    python examples/world/demo.py --agents 30 --ticks 20 --seed 2026

Tương tác mô phỏng giữa ba nhóm cùng chủ sở hữu, qua capability guard:

    python examples/populations/local_three_groups.py

Các chương trình này dùng dữ liệu tổng hợp và **không** chứng minh khả năng tự học hoặc giao dịch liên chủ sở hữu. Cách tạo vòng đời tích hợp Observe → Predict → Authorize → Act → Record → Replay là mục tiêu R0; chỉ sử dụng lệnh tích hợp sau khi có PR triển khai và kiểm thử độc lập.

## Phân biệt ba loại kết quả

- **Test PASS:** mã kiểm tra các trường hợp đã viết; không đồng nghĩa hệ thống có ích với người dùng.
- **Replay PASS:** phát lại input mô phỏng tái tạo trạng thái; không xác nhận một sự kiện đời thực.
- **Benchmark:** phải nêu baseline, seed holdout, phần cứng, CPU/RAM/đĩa (kể cả SQLite WAL) và cả kết quả âm.

Đối với kiểm chứng độc lập W0/W1/W5, xem [Issue #11](https://github.com/CocAgent/OpenWorld/issues/11), hiện là cổng chưa hoàn tất.
