# Bối cảnh nhánh backend sạch

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
