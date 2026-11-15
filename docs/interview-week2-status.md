# Backend Interview — bug log từ 11/11, kiểm tra ngày 13/11/2026

Base main 9555e4e (PR #56 env đã merge), nhánh backend/interview. Không xét lại
sự cố merge ngày 8/11, không ghép nhánh khác, không sửa UI/AI/Auth/Profile.

## Những lỗi đã sửa và tái hiện

1. Gửi lại thao tác vừa thành công có thể bị 409 dù dữ liệu giống nhau. Bốn
   regression tests đã fail trên base: retry answer, retry progress sau chấm,
   concurrent identical submit, concurrent finalize. Nay trả state hiện tại
   nếu revision ngay trước và nội dung yêu cầu đã được áp dụng. Không ghi
   thêm lần nữa, không tăng revision/version và không gọi AI trùng.
2. User có Auth nhưng thiếu public.accounts: RPC báo FK tạo buổi. Nay trả
   409 account_not_found rõ ràng khi đúng constraint sessions_user_id_fkey,
   không giấu thành 503 chung, không tạo account thay Huy hoặc lộ SQL/UUID.
3. Env template có inline owner tags, loader đọc auto # 273 thành giá trị cấu
   hình và startup fail. Chuyển tags sang dòng comment riêng, giữ giá trị;
   khai báo INTERVIEW_AI_PROVIDER/TIMEOUT_S/ALLOW_CV_TO_AI. Không sửa db.py,
   ai.py hay .env thật. Test nạp template qua loader và khởi động server.

Không bỏ revision guard: request khác nội dung hoặc quá cũ vẫn 409. Đây là
chặn ghi đè thật, cần frontend giữ draft khi nhận lỗi. Chấm nền chỉ tăng version,
không tăng revision. Gửi lại với revision mới nhất vẫn tạo job mới để retry
pending/rejected; duplicate với revision cũ không enqueue lại job cũ.

## Đã kiểm tra những gì

Kết quả cuối trên máy: **182 tests passed**, gồm 7 SQL/RPC tests trên PostgreSQL
thật localhost; một cảnh báo TestClient cũ. Không gọi AI/provider thật hoặc ghi
Supabase trong suite. Đây không phải kết quả kiểm thử giao diện/deploy.

- HTTP create -> submit 3 answers -> progress -> finalize -> resume/report;
  title/answer/report đọc lại đúng, không dùng tên hoặc đáp án mẫu cứng.
- Đáp án được lưu trước khi chấm; response 202 không phải chờ AI xong.
- Lưu draft đúng lúc AI ghi kết quả: service đọc lại sau CAS conflict, giữ cả
  draft mới lẫn grade; có kiểm tra SQLite và SQL/RPC PostgreSQL thật localhost.
- Hai submit cùng nội dung có đúng một job; hai finalize có cùng báo cáo,
  không chấm lại; stale edit khác vẫn bị chặn; owner khác không đọc/sửa được.
- RPC thật trên PostgreSQL thử kiểm tra mirror sessions/questions/answers/
  grades, rollback account FK không để dữ liệu nửa chừng; không thêm cột hay
  đổi schema để thực hiện bản sửa này.
- Baseline có lỗi bài test unconfigured vì .env máy được nạp lại; fixture
  chung nay cô lập việc đọc file thật. Không sửa code Profile để làm test qua.

## Supabase thật: chỉ đọc metadata

Hàm public.yourin_interview_v1 có body md5
6828e209fb625f71e63c903ba8c16703, khớp SQL LOCAL-09 trong repo. SECURITY INVOKER,
service_role được execute. Trigger on_auth_user_created gọi handle_new_user
sau INSERT auth.users, đang bật. FK sessions_user_id_fkey trỏ accounts(id).

Chưa đọc hàng auth.users/accounts hoặc kiểm tra backfill user cũ. Trigger có
tồn tại không chứng minh tất cả tài khoản đã có profile. Không có công cụ
logs/advisories trong kết nối MCP hiện tại. Không thay trigger/quyền/cột, không
gọi create/save/delete trên cloud trong phép thử. SQL local không thay thế
kiểm thử ghi Supabase thật bằng tài khoản test của nhóm.

## Phối hợp với Khang (không sửa UI trên nhánh này)

- ui/js/app.js applyServerView gán lại toàn bộ target.answers từ server, trong
  khi refreshServerInterview được polling mỗi 3s và được gọi sau 409. Draft
  người dùng đang gõ có thể bị thay bằng bản đã lưu cũ. Cần giữ draft chưa
  được server xác nhận, chỉ cập nhật grade/status cho dữ liệu tương ứng.
- Next/Previous vẫn tiếp tục gọi progress/chuyển câu khi submitCurrentAnswer
  trả false. Khi ghi lỗi phải dừng chuyển trang/câu và giữ nguyên draft.
- Nhiều nguồn ghi cùng lúc (Next, Previous, Save/Exit, pagehide) chưa có hàng
  đợi chung; cần serialize. Không tự retry bằng cách ghi đè snapshot cũ sau
  một xung đột thật. Nhánh backend chỉ loại bỏ 409 cho replay an toàn.
- Report HTML mặc định là phần Frontend: backend đã trả created_at, name,
  questions, answers và report qua GET interview/finalize. Loading/error phải
  hiển thị rõ nếu chưa lấy được dữ liệu, không tiếp tục render dữ liệu mẫu.

## Phối hợp với Huy và thử trực tiếp

Huy kiểm tra/backfill accounts cho tài khoản test và xác nhận trigger đúng.
Không cần chạy lại SQL LOCAL-09 để dùng bản backend này. Sau khi Khang cập nhật
chỗ giữ draft/đợi API, dùng tài khoản thử tạo buổi mới (không CV thật):

1. Tạo buổi có tên riêng, trả lời câu 1 và bấm tiếp nhanh khi AI còn chấm.
2. Gõ draft câu 2, để polling chạy, Save & Exit và vào lại: draft/vị trí còn đúng.
3. Trả lời đủ ba câu, finalize; xem đúng tên/ngày/đáp án/kết quả ở report.
4. Đăng nhập lại vẫn đọc được buổi; tài khoản khác không truy cập được.

Chưa khẳng định bốn bước cloud/UI này đã qua trong tuần mới. Người dùng hoặc
Huy/Khang cần thực hiện trên môi trường đã cấu hình; không yêu cầu gửi mật
khẩu/token vào chat. Bản sửa được bàn giao để review, không tự merge/deploy.
