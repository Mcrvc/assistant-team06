# Backend phỏng vấn — bản tách để nhóm review

Nhánh `feat/LOCAL-11-interview-backend-clean` bắt đầu từ main `db822cf`.
Chỉ có phần của Trần Bảo Anh và các connector cần thiết. Không merge nguyên
nhánh cũ, không đưa lại các thay đổi Auth/UI/AI của hôm trước.

## Có gì trong nhánh này

| Phần | File |
| --- | --- |
| API, startup chung của nhóm | src/assistant/web.py |
| Luồng tạo/lưu/tiếp tục/chấm/finalize | src/assistant/interviews.py |
| Kiểu dữ liệu, revision, report | src/assistant/interview_schemas.py |
| Điểm gọi AI và kiểm tra/refusal | src/assistant/interview_ai.py |
| Hỏi Supabase xem token thuộc ai | src/assistant/auth.py |
| Ghi dữ liệu qua Supabase RPC | src/assistant/interview_supabase.py |
| Chọn storage; SQLite dành cho local/test | interview_runtime.py, interview_store.py |
| SQL Huy đã duyệt và cài | docs/schema-proposals/LOCAL-09-supabase-api.sql |

Không thay đổi bất kỳ file nào trong ui/, ai.py, db.py. Không mang code
aiworker.py của Duy, user_api.py của Trương, cây frontend/backend, login giả,
JWT verifier tự viết hoặc adapter PostgreSQL trực tiếp vào bản bàn giao này.

## Các điểm nối nhóm cần ghép riêng

**Hiển / Khang:** giữ đăng nhập Supabase hiện có. Khi gọi interview API, lấy
session access_token và gửi Authorization: Bearer. Backend tự hỏi Supabase
/auth/v1/user rồi lấy UUID; không tin user_id/owner_id trong JSON của browser.
API không tạo tài khoản, mật khẩu, session hoặc endpoint đăng nhập mới.

**Duy:** code AI là dependency của nhánh nvidia, không phải code của backend.
Nhóm review/tích hợp ai.py và aiworker.py từ nhánh AI riêng (đã xem 0637c2d).
Entry points:

- generate_questions(job_profile, cv, notes, sources, *, timeout_s): trả
  source/questions, mỗi câu question/rubric với max_score=10.
- grade_answer_with_evidence(question, answer, rubric, *, timeout_s): trả
  score/feedback/evidence/model/used_fallback; EvidenceRejected có code.

Chọn nvidia khi chưa có các module này thì startup báo thiếu dependency rõ
ràng, không âm thầm nhận toàn điểm mẫu. Mock mặc định cho kiểm tra độc lập,
luôn có cờ fallback. Không sửa prompt/tiêu chí của Duy trong nhánh này.
Nhãn Good từ 6/10 giữ quy tắc cũ, cần Duy xác nhận; không đổi grades.level.

**Trương Bảo Anh:** viết Profile/CV, history, API đọc report và feedback trong
nhánh riêng. Có sẵn get_current_user/get_service ở web.py; service.get và
service.list dùng cùng kho theo chủ tài khoản. Khi ghép router, include trước
catch-all /api và static mounts. Report cũng nằm trong GET interview/finalize,
để Trương đọc mà không gọi AI lại. Nhánh này không nhận vơ các API của Trương.

**Huy:** API/RPC LOCAL-09 đã cài trên project nhóm, không chạy SQL lại khi
startup. create/save ghi một giao dịch và mirror các bảng quan hệ; get/list
đọc interview_state. Mọi cập nhật buổi phải qua hàm chung để tránh lệch state.
Điểm 0–10 giữ trong state; grades.level chưa tự map. CV/feedback persistent
của phần khác không được triển khai thêm ở đây.

## API phần phỏng vấn

| Method | Path | Chức năng |
| --- | --- | --- |
| POST | /api/interviews | Job Profile + CV tùy chọn, tạo bộ câu hỏi theo kế hoạch (6-12 câu, tối đa 15), trả câu đầu |
| GET | /api/interviews/{id} | Đọc đầy đủ buổi để tiếp tục, gồm report nếu đã xong |
| POST | /api/interviews/{id}/progress | Lưu draft/vị trí với revision hiện tại |
| POST | /api/interviews/{id}/answers/{0..2} | Lưu trước, trả 202 pending rồi chấm nền |
| GET | /api/interviews/{id}/progress | Đếm answered/pending/graded/rejected |
| POST | /api/interviews/{id}/finalize | Tổng hợp 3 kết quả đã chấm, không gọi AI lại |

Tất cả cần tài khoản đã được xác nhận. Buổi không thuộc người gọi trả 404.
Lưu theo revision chống ghi đè; grading_id ngăn kết quả cũ ghi lên đáp án mới.
Finalize chưa đủ bài/chấm xong sẽ từ chối. Kết quả bị Duy từ chối không có điểm;
gửi lại đáp án với revision mới nhất để thử lại. BackgroundTasks không bền nếu
process chết; không tuyên bố có hàng đợi bền hoặc tự phục hồi tác vụ.

Frontend field mapping: job-source -> job_profile.description, job-title ->
title, position -> level, company/domain giữ tên. Xem /docs để thử schema chính
xác. Đây là checkout backend: UI từ main vẫn là prototype, chưa được nối bằng
các file UI của nhánh tích hợp cũ. Không dùng việc mở dashboard làm chứng cứ
đăng nhập hoặc lưu interview đã hoạt động trên checkout này.

## Chạy và kiểm tra

```powershell
python -m pip install -e ".[web,dev,postgres-test]"
python -m pytest -q
python -m assistant --ui --port 8002
```

Server dùng web.py, /docs là trang thử API. --interview-api là alias cùng server.
Render dùng PORT/RENDER để bind 0.0.0.0:$PORT, không tự mở browser. Không đổi
hosting hay deploy từ nhánh này. /api/health/config là thông tin cấu hình,
không phải chứng cứ đầy đủ mọi dịch vụ đã hoạt động.

Để lưu qua Supabase, điền .env riêng:

```dotenv
SUPABASE_URL=insert_project_url_here
SUPABASE_PUBLISHABLE_KEY=insert_public_key_here
SUPABASE_SECRET_KEY=insert_backend_secret_key_here
INTERVIEW_STORAGE=supabase
INTERVIEW_LOCAL_STORAGE=0
INTERVIEW_AI_PROVIDER=mock
```

Sau khi ghép module Duy, đặt INTERVIEW_AI_PROVIDER=nvidia và NVIDIA_API_KEY,
NVIDIA_MODEL; timeout adapter 1–60s, CV forwarding mặc định tắt. Không cần
DATABASE_URL, không dùng MCP token làm credential. Không commit .env/secret.

Test dùng resolver giả chỉ bên trong test, không có endpoint demo đăng nhập.
Không đọc config thật, không gọi mạng ngoài. SQL tests cần DB localhost tên
yourin_interview_test* qua INTERVIEW_TEST_POSTGRES_URL; tạo/xóa schema ngẫu
nhiên, không viết Supabase. Chưa cấu hình thì skip các SQL tests.

## Phục hồi khi AI hỏng (không im lặng trả mock)

Ba lớp phục hồi, để một lỗi chớp nhoáng không biến cả buổi phỏng vấn thành bộ
câu mẫu:

1. **aiwriter (aiworker.py)**: planner hỏng -> DEFAULT_PLAN 8 slot; một câu
   hỏng shape -> 3 lượt repair -> hỏng nữa thì **skip slot**, giữ các câu đã
   viết; provider chớp nhoáng (429/5xx/timeout) trên một slot -> thử lại slot
   đó một lần rồi skip. Chỉ khi **không có câu nào** viết được (provider chết
   thật) thì raise để service fallback có cờ used_fallback trung thực.
2. **SafeInterviewAI (interview_ai.py)**: bộ câu AI thật bị team schema từ chối
   (tên criterion >200 ký tự, dư field, 7 criteria, text >4000...) được **coerce
   có giới hạn** - trim đúng limit, bỏ câu/criterion không dùng được, cấp lại
   điểm cho rubric đúng tổng 10 - thay vì ném hết 5 câu tốt vào mock. Hết cứu
   thì mới mock, và **mọi fallback đều log lý do ra stderr**.
3. **UI (ui/js/app.js)**: interview không còn hard-code 3 câu/3 slot trả lời -
   số slot theo đúng số câu thật; khi question_generation.used_fallback là true
   thì hiện dòng "These are fallback questions..." để người dùng biết ngay là
   bộ câu dự phòng, không phải câu AI viết cho hồ sơ của họ.

Kiểm tra nhanh bản deploy: `python scripts/deploy_probe.py` (so asset Vercel,
gọi /api/config, tạo interview và in shape JSON); `python scripts/schema_gap_probe.py`
liệt kê các shape model hay trả mà team schema từ chối.

## Trạng thái bàn giao

Bản tích hợp cũ từng qua 264 tests; user đã thử Supabase + AI thật tới report.
Con số đó không tự áp dụng cho bản tách. Bản tách phải kiểm tra riêng, gồm
startup, API/service/owner isolation, refusal, Supabase transport và RPC SQL.
Kết quả bản tách: **63 tests passed**, gồm 4 SQL/RPC tests trên PostgreSQL thật
ở localhost; một cảnh báo TestClient cũ. Kiểm tra riêng với module Duy 0637c2d
và router history/report Trương nạp từ ngoài checkout cũng qua (provider giả,
SQLite tạm, không network/cloud writes). UI/ai.py/db.py không khác main.
Chưa có frontend tích hợp, chưa chạy cloud end-to-end ở checkout sạch. Nhóm
cần nhận các phần riêng sau review và thử lại bản ghép cuối trước khi deploy.
