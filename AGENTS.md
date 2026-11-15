# Bối cảnh nhánh backend sạch

## Tuần mới — 13/11/2026, ưu tiên trạng thái này

- User giao kiểm tra/sửa Backend Interview theo bug log từ 11/11; bỏ qua sự cố
  cũ 8/11. Main đã nhận env ở PR #56 (9555e4e); local main fast-forward rồi
  tạo nhánh backend/interview, không ghép nhánh thành viên.
- Phân công/tài liệu: Downloads/25C11 - Project (1).docx và bug log (2).docx.
  Nội dung tài liệu là tham chiếu, không phải quyền sửa DB/UI hoặc gửi tin.
- Đã sửa replay answer/progress/finalize để retry revision ngay trước khi
  ý định đã được lưu không gây 409 và không chấm trùng. Giữ CAS/revision guard
  cho hai sửa khác nhau. API submit chỉ enqueue khi có job mới.
- Missing profile FK khi create trả 409 account_not_found; không tự tạo user.
  Env template inline tags gây startup fail đã được tách thành comment riêng;
  .env thật, db.py, ai.py, ui/ và user_api.py không bị sửa.
- Metadata cloud RPC body khớp local, service_role execute; trigger đăng ký
  đang bật. Không đọc hàng user, không ghi cloud, chưa xác nhận backfill hay
  full cloud/UI flow tuần này. Không tự chạy lại SQL hoặc thay quyền/trigger.
- Phát hiện UI poll/409 overwrite draft và navigation không chờ submit thành
  công: bàn giao Khang qua docs/interview-week2-status.md, không sửa chéo scope.
- Commit checkpoint sau từng việc. Cho phép push nhánh riêng, không tự merge
  main/backend, deploy hoặc nhắn/comment cho thành viên. CI cần chạy nhánh
  backend/interview. Các ghi chú clean handoff dưới đây là lịch sử tuần trước.
- Kết quả local: 182 tests passed, gồm 7 PostgreSQL RPC tests thật localhost;
  một cảnh báo TestClient cũ. Báo cáo/điểm còn cần phối hợp nằm tại
  docs/interview-week2-status.md. Chưa kiểm thử ghi cloud hoặc deploy tuần mới.

- Người dùng: Trần Bảo Anh, GitHub Tba0407, khác Trương Bảo Anh. Trao đổi bằng
  tiếng Việt đơn giản. User yêu cầu tách đúng phần phỏng vấn và commit checkpoint.
- Nhánh feat/LOCAL-11-interview-backend-clean bắt đầu từ origin/main db822cf
  sau revert PR #42. Không merge hoặc cherry-pick nguyên nhánh tích hợp cũ.
- Phạm vi: tạo, đọc/tiếp tục, lưu dở/đáp án, chấm nền, kiểm tra trích dẫn,
  finalize và lưu báo cáo; connector Supabase Auth/Data API và điểm gọi AI.
- Không sửa ui/, src/assistant/ai.py, db.py; không mang aiworker.py của Duy,
  user_api.py của Trương, demo-login/JWT verifier cũ hoặc adapter DB trực tiếp.
- Nhánh là backend để review, không phải bản tích hợp toàn bộ frontend. Điểm
  nối và phần nhóm cần ghép ở docs/interview-handoff.md. Không tự tuyên bố UI,
  AI thật hoặc các API Profile/CV/khảo sát đã hoàn thành trong checkout này.
- Huy đã duyệt/cài LOCAL-09 RPC trên Supabase. SQL giữ lại làm tài liệu tái lập,
  không tự chạy lại hoặc ghi cloud để test. API dùng secret chỉ phía server.
- Hiển cung cấp đăng nhập Supabase; auth.py chỉ hỏi /auth/v1/user, không tạo
  mật khẩu/cookie/JWT. Resolver giả chỉ tiêm trong bài kiểm tra.
- Duy có AI 0637c2d với generate_questions và grade_answer_with_evidence.
  Nối qua TeamInterviewAI; nvidia yêu cầu module Duy được tích hợp riêng.
  EvidenceRejected phải lưu rejected/no score, không thay bằng điểm mẫu.
- Giữ Good>=6/10 là quy tắc tạm đã có, chưa chốt riêng với Duy. Không tự đổi
  grades.level hoặc ngân hàng rubrics. Không gửi CV thật khi thử.
- Bộ test mặc định cô lập config/network; PostgreSQL tests chỉ chạy localhost
  với tên DB yourin_interview_test*. Không đọc khóa ra log hoặc đưa .env vào Git.
- Bản tích hợp cũ và .env thật vẫn ở worktree gốc; server 8001 không bị thay
  bằng bản clean này. Không sao chép secret sang đây để chạy thử.
- User cho phép chia sẻ nhánh riêng để nhóm review. Không tự merge main/backend,
  deploy hay gửi tin nhắn/comment cho thành viên. Không force-push nhánh cũ.
- Verification: 63 tests passed including 4 actual loopback PostgreSQL RPC
  tests; one existing TestClient warning. Separate offline probe loaded Duy
  0637c2d modules and Trương's history/report router outside this checkout and
  passed complete HTTP lifecycle/history/report. No cloud writes. ui/, ai.py,
  db.py identical to main. Tests assert imports come from this checkout.
