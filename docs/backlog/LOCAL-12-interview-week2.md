# LOCAL-12 — Backend Interview, bug log từ 11/11/2026

Theo yêu cầu Trần Bảo Anh ngày 13/11: main đã nhận thay đổi env ở PR #56,
base 9555e4e; nhánh làm việc backend/interview. Không ghép nhánh thành viên.

Phạm vi: kiểm tra create -> answers -> progress -> finalize/report, chống
409 làm rớt lần lưu khi chấm nền/chồng yêu cầu, và báo lỗi account chưa được
DB tạo một cách rõ ràng. Không sửa UI/Auth/AI hoặc Profile/CV của người khác.

Quan sát ban đầu:
- Baseline 162 passed, 4 skipped, 1 failed: bài test unconfigured của Profile
  xóa env rồi bị .env thật nạp lại. Sửa fixture chung, không đổi code Profile.
- Hàm RPC cloud có md5 body 6828e209fb625f71e63c903ba8c16703, khớp chính xác
  SQL LOCAL-09 local; SECURITY INVOKER và service_role execute. Chỉ đọc metadata,
  không đọc dữ liệu người dùng hoặc ghi cloud.
- Service đã tách revision (lần sửa của user) và version (mọi lần ghi bao gồm
  AI); phải giữ quy tắc này. Không bỏ kiểm tra revision để che lỗi cạnh tranh.
- UI applyServerView/refreshServerInterview đang ghi toàn bộ đáp án từ server
  vào draft khi polling/409; Next/Previous không dừng khi submit thất bại.
  Chuyển phát hiện cho Khang trong báo cáo, không sửa UI trên nhánh backend.

Kiểm chứng cần có: retry cùng thao tác không lưu/chấm trùng; hai sửa khác nhau
vẫn bị chặn; submit/save trong khi grading không mất draft/grade; finalize
không gọi AI lần hai; SQL thực trên localhost, đối chiếu cloud chỉ đọc. Thử
ghi cloud end-to-end bằng tài khoản thử cần phối hợp Huy/Khang/người dùng,
không tự đọc token trình duyệt hoặc chạy SQL ghi trên Supabase chung.
