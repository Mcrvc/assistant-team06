# Báo cáo phần Backend của Trần Bảo Anh

Ngày cập nhật: 08/11/2026. Nhánh local: `feat/LOCAL-01-interview-lifecycle`.
Đã triển khai và kiểm tra bản chạy độc lập; chưa commit/push, chưa deploy hoặc ghép cloud.

## Đã xong trong bản local

- Backend riêng bằng FastAPI/Uvicorn, Pydantic kiểm tra input/output; Swagger `/docs`.
- Tạo buổi: snapshot Job Profile + CV text, lưu 3 câu hỏi kèm tiêu chí/nhãn nguồn,
  trả câu đầu tiên cho frontend. Nguồn hiện là câu mở từ mock.
- Lưu bản nháp/vị trí, lưu dở, đọc lại để tiếp tục; giữ dữ liệu qua lần khởi động lại.
- Nhận từng đáp án, lưu trạng thái chờ trước khi trả HTTP 202; gọi AI ở BackgroundTasks.
- Kiểm tra mọi trích dẫn của AI có nguyên văn trong đáp án. Từ chối bằng chứng bịa
  hoặc rỗng; kết quả bị từ chối không được đưa vào báo cáo.
- API theo dõi số đã trả lời, đã chấm, đang chờ và bị từ chối.
- Finalize khi đủ 3 câu đã chấm hợp lệ: lưu điểm trung bình, nhãn, nhận xét và bằng
  chứng; gửi lại finalize trả báo cáo cũ. Buổi finalized không sửa qua các API này.
- Có adapter AI mẫu và fallback cho lỗi provider/output sai; luôn đánh dấu mock.
- Lưu SQLite qua SQLAlchemy, nằm trong `data/private/` và được Git bỏ qua.
- Kiểm tra quyền sở hữu theo user ID do backend xác định; chống ghi đè do revision
  cũ, hai tác vụ chấm cùng lúc và tác vụ cũ của đáp án đã sửa.
- Cookie demo local có kiểm tra loopback/Origin; có điểm nối session cookie thật.
- Hướng dẫn tiếng Việt, contract JSON và script thử toàn bộ luồng bằng HTTP.

## Đã kiểm chứng

- `python -m pytest -q`: **41 passed**, gồm 5 smoke tests cũ và 36 tests mới.
- Test response 202 được gửi ra trong khi provider chấm vẫn đang bị giữ chờ.
- Test mở lại DB/app, lấy lại draft và đăng nhập demo lại sau restart.
- Test hai user, revision cũ, chấm đồng thời, output AI hỏng/timeout/NaN, quote bịa,
  bằng chứng tiếng Việt và adapter trả nguồn tham chiếu/kết quả thật theo contract.
- Chạy Uvicorn trên `127.0.0.1:8765` và `scripts/demo_interview.py`: toàn luồng qua
  HTTP thành công, gồm finalize retry. Server dùng để kiểm tra đã được dừng.
- `scripts/check_env.py`: tất cả kiểm tra qua; `pip check`: không xung đột dependency.
- CLI `hi`, office lookup, API legacy và static UI vẫn hoạt động.
- Môi trường kiểm tra: Python 3.14.7, FastAPI 0.162.2, Uvicorn 0.54.0,
  Pydantic 2.14.3, SQLAlchemy 2.0.57, pytest 9.2.0, HTTPX 0.28.1.
  Chưa chạy ma trận nhiều phiên bản Python.
- Có 1 deprecation warning từ Starlette TestClient dùng HTTPX; tests vẫn qua.
- `eval/run.py` cũ trả **Accuracy: 0.00%**. Rules và các file eval không thay đổi so
  với HEAD; bộ expected hiện hỏi các chức năng không khớp rules tra cứu văn phòng.
  Đây chưa phải bộ đo chất lượng Yourin, cần xây riêng khi có AI thật.

## Còn cần làm trước khi gọi là tích hợp hoàn chỉnh

Cập nhật khảo sát Supabase ngày 08/11/2026: **đã kết nối MCP chỉ đọc thành công**
vào project `ct-team06` (`qutiahnegjzgbxjopsqe`). Server xác nhận
`transaction_read_only=on`, role `supabase_read_only_user`. `list_tables` và
catalog PostgreSQL đều cho thấy **public có 0 bảng / 0 view**; chưa thấy schema
ứng dụng tùy chỉnh. Chỉ đọc metadata, không đọc dữ liệu tài khoản hoặc sửa DB.
Do đó hiện chưa có bảng interview thật để ánh xạ adapter. Kết quả này không cho
biết bạn Database đã có bản thiết kế/script chưa; cần kiểm tra lại lúc ghép.

1. **AI thật:** nối adapter với hàm của Phúc Duy, rubric/nguồn thực tế, đặt timeout;
   mock hiện chấm theo số từ, không dùng để kết luận năng lực ứng viên.
2. **Database nhóm:** ánh xạ repository sang schema PostgreSQL đã thống nhất,
   migrations và quyền truy cập. Chưa nối Supabase; không tạo bảng vào DB chung.
3. **Auth thật:** nối session cookie, expiry/revocation, CSRF/HTTPS; Argon2id ở phần
   đăng nhập của bạn Auth. Cookie local không thay thế đăng nhập thật.
4. **Frontend:** gọi API thay localStorage, map Job/CV, gửi cookie, polling tiến độ,
   xử lý loading, revision conflict và lỗi chấm. UI hiện chưa gọi backend này.
5. **Chấm bền vững khi server lỗi:** hiện có thể gửi lại đáp án pending để retry;
   chưa có hàng đợi tự khôi phục tác vụ bị mất khi tiến trình dừng.
6. **Ghép và review:** đối chiếu API/schema với nhóm, tạo/liên kết GitHub issue thật,
   PR và teammate review, kiểm thử tích hợp trên Render rồi mới merge/deploy.

Các mục Profile/CV API riêng, lịch sử, API report riêng và khảo sát vẫn thuộc phần
Backend còn lại theo cách chia người dùng đã chốt. PDF parsing/upload, tải URL JD
và ngân hàng câu hỏi thật chưa được làm trong phạm vi local này.

## Xem và chạy thử

- [Hướng dẫn khởi chạy + API contract](interview-api.md)
- [Backlog local và acceptance criteria](backlog/LOCAL-01-interview-lifecycle.md)
- `scripts/demo_interview.py`: script kiểm tra HTTP, tự dùng CV/đáp án giả.

Không có khóa API thật, tài liệu Word hoặc dữ liệu cá nhân nào được thêm vào code.
