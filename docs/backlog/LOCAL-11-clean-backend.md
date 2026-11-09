# LOCAL-11 — tách backend phỏng vấn trên nền main sạch

Đây là ID công việc local theo yêu cầu của Trần Bảo Anh, không phải GitHub issue.
Base: main db822cf. Giữ nguyên bản tích hợp cũ để thử; không mang lại lịch sử
merge hoặc trách nhiệm Auth/UI/AI/Profile của các bạn khác.

Phạm vi bàn giao: lifecycle HTTP + service, schema đầu vào/đầu ra, ownership,
revision/CAS, chấm nền/evidence guard, finalize, local repository cho test,
Supabase Data API adapter và RPC Huy đã cài; connector xác nhận đăng nhập.

Kiểm chứng: service/HTTP/auth/storage/startup, PostgreSQL thật trong schema tạm,
đối chiếu phạm vi diff với main; thử điểm nối với module Duy bên ngoài checkout.
Checkpoint riêng sau code và sau hướng dẫn/CI. Không tự merge hoặc deploy.

Hướng dẫn bàn giao và giới hạn: docs/interview-handoff.md.
