# Tình trạng ghép backend interview

Cập nhật 08/11/2026 sau khi làm các phần độc lập theo yêu cầu của Trần Bảo Anh.
Đã commit checkpoint theo từng việc; chưa push, deploy hoặc ghi database cloud.

Nguồn đã ghép: `origin/frontend` (`08b8ceb`), chứa `AI` (`32d6f69`) và
`authen` (`aa81df6`). Nhánh làm việc: `feat/LOCAL-01-interview-lifecycle`.

## Đã làm được và kiểm tra local

1. [x] **Khớp cách chạy/cấu trúc.** Dùng chung một ASGI app, cài từ root;
   frontend nhóm ở `/app/`, prototype cũ giữ nguyên. Các đường dẫn config không
   ghim port 8000. Có contract và mapping UI/backend tại `docs/interview-api.md`.
2. [x] **Adapter AI của Phúc Duy.** Dùng generator của `aiworker.py`; giữ rubric
   có trọng số, yêu cầu grader trả evidence thật, kiểm tra output/timeout/fallback
   đúng 3 câu. Mock là mặc định, provider NVIDIA chỉ bật khi cấu hình rõ ràng.
3. [x] **Adapter Supabase Auth.** Xác minh Bearer token/JWKS, chữ ký RSA/ECDSA,
   issuer/audience/expiry/role/user ID và lọc quyền sở hữu. Demo cookie local giữ
   riêng. Chưa chứng minh đăng nhập thật với project nhóm.
4. [x] **Frontend interview.** Tạo buổi, lấy câu hỏi/ID server, autosave, Next/Prev,
   lưu dở/tiếp tục, chấm từng câu, polling, finalize và báo cáo đã lưu. Retry
   incomplete grading; evidence sai chặn báo cáo; đăng xuất đợi lưu draft.
5. [x] **Kiểm thử bản ghép local.** 114 tests passed, gồm 5 browser tests Chrome
   headless/Uvicorn/SQLite với network ngoài loopback bị chặn. Test provider code
   qua HTTP bằng completion giả; test JWT bằng key sinh riêng. check_env và
   pip check qua. Chi tiết checkpoint tại `docs/backend-progress.md`.

## Còn cần thông tin hoặc phối hợp trước khi tích hợp thật

6. [ ] **Schema/migrations từ Huy.** Supabase MCP chỉ đọc đã kết nối; lần khảo sát
   public có 0 bảng. Khi có schema, map repository và test trên PostgreSQL local,
   rồi mới ghép môi trường nhóm theo quyền đã thống nhất. Không tự tạo bảng chung.
7. [ ] **AI key và thử model thật.** Đường code đã có, chưa có API key thực tế để
   xác minh provider/chất lượng. Ngân hàng câu hỏi có nguồn/research chưa được bật.
8. [ ] **Auth/public config của project.** Cần URL/publishable key và signing-key
   config để thử login thật. Code nhánh nhóm dùng Supabase token, ảnh thiết kế
   cũ ghi session cookie/Argon2id: cần nhóm đối chiếu. Legacy HS256 và thu hồi
   session tức thì chưa được adapter JWKS hỗ trợ.
9. [ ] **Chính sách CV.** Draft frontend ghi CV không rời máy, trong khi code AI
   nhận CV. Mặc định không forward CV đến provider; chưa dùng CV thật để thử.
   PDF upload/parsing và tải URL JD còn thiếu, UI báo rõ giới hạn.
10. [ ] **Phần của Backend còn lại.** API history/list toàn bộ session, Profile/CV,
    rename/delete, report endpoint riêng và khảo sát. Storage hiện dùng ID cache
    trên browser; mất browser cache chưa thể liệt kê lại toàn bộ lịch sử.
11. [ ] **Chốt triển khai.** GitHub issue thật, teammate review/PR, Render entry
    point, CORS/HTTPS/env và kiểm thử cloud. Chưa push/deploy trong phiên này.

BackgroundTasks chưa phải durable queue. Có nút retry thủ công cho công việc
chưa chấm khi tiến trình dừng; tự khôi phục bằng job queue là việc nâng cấp sau.
Không chuyển sang chỉ chấm cả bài ở finalize: finalize tổng hợp kết quả hợp lệ
đã lưu, theo yêu cầu người dùng.

## Chạy để xem kết quả hiện tại

```powershell
$env:INTERVIEW_DEMO_ENABLED = "1"
.\.venv\Scripts\python.exe -m assistant --interview-api
```

Mở `http://127.0.0.1:8000/app/`, sign in `demo_user` / `demo12345`. Demo không
tạo tài khoản thật, không cần cloud key, giữ dữ liệu SQLite trong `data/private/`.
