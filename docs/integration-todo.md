# To-do ghép backend interview với các nhánh nhóm

Cập nhật 08/11/2026 sau khi fetch GitHub. Đây là kế hoạch tiếp theo, chưa phải
các thay đổi đã được triển khai. Bản local đã chạy được; chưa merge/commit/push.

Nguồn đối chiếu:

- `origin/AI`: `32d6f69`, có provider NVIDIA/TinyFish và `aiworker.py`.
- `origin/authen`: `aa81df6`, có Supabase Auth phía browser và FastAPI/SQLAlchemy/Alembic skeleton.
- `origin/frontend`: `08b8ceb`, chứa cả AI/authen, có draft API contract và wiring một phần.
- Supabase đã kết nối MCP chỉ đọc; lần kiểm tra gần nhất public chưa có bảng ứng dụng.
  Không suy ra Huy chưa có script/schema local. Theo ảnh trao đổi mới, thành viên
  báo có thể các bảng cũ đã bị xóa; chưa xác minh lịch sử thay đổi database.

## Việc làm được ngay, theo thứ tự

1. [ ] **Thống nhất cách ghép và contract tối thiểu.** Giữ nguyên bản local làm mốc;
   đưa code cần dùng từ các nhánh vào môi trường tích hợp. Chọn một entry point
   FastAPI, nơi phục vụ frontend và bộ dependencies; hiện có cả `backend/` với
   `src/assistant/`, `frontend/` với `ui/`. Đối chiếu SQLAlchemy 2.1.6 bên authen
   với `<2.1` local. Viết bảng mapping request/response, revision và trạng thái
   chấm trước khi thay các điểm nối. Mục tiêu: một lệnh chạy được luồng interview.

2. [ ] **Nối code AI của Phúc Duy.** Tái sử dụng `ai.py`/`aiworker.py` qua adapter;
   map Job/CV và question/rubric, giữ trọng số tiêu chí chấm. Bổ sung output
   `evidence` nguyên văn để Fabrication Guard kiểm tra; không tự gán trích dẫn
   giả cho kết quả AI. Sửa/bao lại fallback sinh đúng 3 câu, xử lý score=None,
   metadata model/fallback, timeout/retry và lỗi provider. Kiểm thử bằng provider
   giả trước; chạy model thật sau khi có key local do người dùng tự cấu hình.

3. [ ] **Nối đăng nhập theo nhánh authen.** Code hiện tại dùng Supabase Auth và
   Bearer token. Hướng ghép theo nhánh: backend xác minh chữ ký JWT/JWKS, issuer,
   audience, expiry và lấy user ID đã xác minh để lọc interview. Chưa thay cơ chế
   auth trong code ở bước lập kế hoạch này; cần cập nhật thỏa thuận vì ảnh thiết
   kế trước đó ghi session cookie/Argon2id. Có thể viết và kiểm thử adapter mà
   không đợi bảng interview trên cloud.

4. [ ] **Ghép luồng frontend interview.** Map `{job, cv, cvMode, cvPdf}` với request
   backend, chuẩn hóa response tạo/đọc session và ID thật. Nối gửi từng đáp án,
   lưu dở/tiếp tục, polling số đã chấm, finalize và bàn giao dữ liệu báo cáo.
   Giữ yêu cầu chấm từng câu ở background; draft frontend đang mô tả finalize
   có thể mới bắt đầu chấm nên cần điều chỉnh contract. Loading/error đã có trên
   nhánh frontend để sử dụng. Chạy trước với SQLite local và dữ liệu giả.

5. [ ] **Kiểm thử bản ghép.** Từ màn hình tạo buổi đến finalize; 401/token hết hạn,
   hai user, revision cũ, AI lỗi, evidence bịa, retry pending và đóng/mở lại server.
   41 tests đã qua là bằng chứng cho bản local, chưa cho bản ghép các nhánh.

## Phần phụ thuộc bên ngoài và chốt cuối

6. [ ] **Nối PostgreSQL theo schema của Huy.** Nhận SQL/migration hoặc kiểm tra lại
   schema khi Huy cập nhật; map repository và kiểm thử trên DB local trước. Sau
   đó mới cấu hình kết nối runtime và quyền ghi phù hợp để lưu dữ liệu thật.
   PAT MCP hiện tại chỉ phục vụ khảo sát; không dùng nó như credential runtime
   của ứng dụng. Không tự tạo/sửa bảng trong Supabase chung qua kết nối chỉ đọc.

7. [ ] **Bàn giao PR và deploy cùng nhóm.** Có GitHub issue thật, mô tả phạm vi,
   kiểm thử và AI use; teammate review; thống nhất entry point Render, CORS và
   env cần thiết; kiểm thử bản deploy sau khi các đầu nối đã sẵn sàng.

## Điểm cần làm rõ trong contract nhóm

- Auth: session cookie trong ảnh thiết kế hay Supabase token trong code nhánh?
  Kế hoạch ghép dựa trên code Supabase hiện có, không coi cả nhóm đã xác nhận đổi thiết kế.
- CV: draft frontend ghi CV không rời máy, trong khi payload/AI code dự kiến nhận
  CV. Chưa dùng CV thật để thử dịch vụ ngoài; cần thống nhất gửi text, bản rút gọn
  hay dữ liệu đã xử lý tại browser. PDF upload/parsing và fetch URL JD chưa có.
- Chấm: theo yêu cầu người dùng, gửi từng câu để chấm nền; finalize tổng hợp kết
  quả hợp lệ đã lưu. Không tự chuyển sang chỉ chấm cả bài khi finalize.

Profile/CV API riêng, danh sách lịch sử, report API riêng và khảo sát vẫn thuộc
phần Backend còn lại. Phối hợp payload/report với người phụ trách, không tự coi
các mục đó là nhiệm vụ mới của Trần Bảo Anh.
