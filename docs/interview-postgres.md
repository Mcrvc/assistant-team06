# PostgreSQL interview: triển khai độc lập LOCAL-04

Đây là adapter đã chuẩn bị theo tên bảng nhóm và **đề xuất bổ sung schema**,
chưa phải schema đã được cả nhóm chấp thuận. Không có thay đổi nào được chạy
trên Supabase chung. API và giao diện interview giữ nguyên contract hiện tại.

## Dữ liệu đi đâu

| Dữ liệu | Nơi lưu |
| --- | --- |
| User sở hữu buổi | `sessions.user_id` → `accounts.id`; account phải có sẵn |
| CV theo buổi | `sessions.parsed_cv`; không phải CV mặc định ở Profile |
| Vai trò/cấp độ | `sessions.role`, `seniority`; job đầy đủ ở `job_profile` đề xuất |
| Câu hỏi sinh cho buổi | `questions`, nối qua `session_questions` |
| Rubric, nguồn, tiêu chí bất biến theo buổi | `session_questions.question_snapshot` đề xuất |
| Draft/đáp án | `answers.answer_text`, một hàng cho mỗi câu trong buổi |
| Pending/graded/rejected và ID tác vụ | Các cột `answers.grading_*`, `error_code` đề xuất |
| Kết quả hợp lệ | `grades.result` đề xuất: score, feedback, evidence[], model, used_fallback |
| Tên, trạng thái, vị trí, revision/version | Các cột `sessions` đề xuất |
| Báo cáo đã finalize | `sessions.report` JSONB đề xuất; `finished`/`finished_at` cũng được cập nhật |

File để Huy review: **`docs/schema-proposals/LOCAL-04-interview.sql`**. File này
chỉ bổ sung cột/index vào các bảng hiện có; không tạo account, không đổi quyền,
không xóa/backfill dữ liệu và không đoán thang `grades.level`. Kết quả câu hỏi
0–10 nằm trong `grades.result`; `level`/`competency` để NULL cho đến khi AI/DB chốt.
Nếu chỉ có một trích dẫn thì mirror vào `evidence_quoted`; với nhiều trích dẫn,
mảng nguyên văn đầy đủ nằm trong `result.evidence`, không nối thành một quote giả.

`interview_format=1` đánh dấu buổi do adapter này tạo. Buổi cũ có format NULL
không được tự nhập bằng dữ liệu mặc định. Ngân hàng câu hỏi/domain/rubric của
nhóm không bị sửa: mỗi câu AI sinh tạo một hàng question riêng; domain dạng text
được giữ trong job snapshot, chưa tự suy ra `domain_id`. Việc tái sử dụng ngân
hàng câu hỏi có thể thêm sau khi nhóm bàn giao cách chọn câu/nguồn và domain ID.

## Tính nhất quán

- Tạo session, 3 question/link và 3 answer trong cùng một transaction.
- Mọi lần lưu kiểm tra owner + version bằng UPDATE nguyên tử trước khi ghi
  child rows. Lỗi giữa chừng rollback cả revision, trạng thái, đáp án và điểm.
- GET đọc session/questions/answers/grades bằng cùng một SELECT snapshot;
  không ghép revision cũ với đáp án vừa cập nhật từ transaction khác.
- Giữ ID answer/grade khi cập nhật; sửa đáp án xóa grade cũ cùng transaction.
  Service vẫn kiểm tra grading_id để tác vụ cũ không phục hồi kết quả đã hủy.
- Background grading chỉ đổi version nội bộ; revision của người dùng giữ nguyên.
- Không gọi AI khi finalize; report được lưu và đọc lại sau khi mở connection mới.
- Không tự gọi create_all/migration lúc ứng dụng khởi động. Schema chưa phù hợp
  phải được báo lỗi; không tự chuyển qua SQLite để che lỗi PostgreSQL.

## Chọn PostgreSQL khi chạy ứng dụng

Sau khi schema đề xuất được review và áp dụng **trên database test**, cấu hình
trong `.env` local hoặc môi trường process:

```dotenv
INTERVIEW_DEMO_ENABLED=0
INTERVIEW_STORAGE=postgres
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
INTERVIEW_AI_PROVIDER=mock
```

Đồng thời cấu hình Supabase URL/publishable key để frontend đăng nhập và backend
xác minh token. `accounts.id` phải tồn tại cho user đã đăng nhập (Auth/Profile
chịu trách nhiệm tạo account); interview không tự tạo tài khoản. Khi test chỉ
trên loopback có thể dùng cấu hình SSL của PostgreSQL test tương ứng.

Chạy `python -m assistant --interview-api` như trước. Mặc định
`INTERVIEW_STORAGE=auto` vẫn giữ demo SQLite hoặc local opt-in cũ, không tự
kết nối chỉ vì có DATABASE_URL. Chỉ `postgres` mới mở kết nối; URL sai, DB lỗi,
thiếu driver hoặc schema chưa phù hợp làm startup thất bại với thông báo đã
lọc chi tiết riêng tư. Không tự fallback về SQLite. Startup chỉ kiểm tra cột
bằng SELECT LIMIT 0, không tự chạy SQL đề xuất hoặc đọc nội dung dữ liệu.

PostgreSQL không nhận demo user `local-demo`; demo cookie chỉ dùng với SQLite.
Nếu được truyền service riêng vào `create_app(service=...)` để kiểm thử, app
dùng service đó và không tự mở/đóng repository mà caller đang sở hữu.

## Chạy bộ kiểm thử

Cài `pip install -e ".[web,dev,postgres]"`. Chuẩn bị PostgreSQL chỉ trên loopback
và một database rỗng tên bắt đầu bằng `yourin_interview_test`:

```powershell
$env:INTERVIEW_TEST_POSTGRES_URL = "postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/yourin_interview_test"
.\.venv\Scripts\python.exe -m pytest -q tests/test_interview_postgres.py
```

URL thật chỉ đặt ở môi trường local; không commit thông tin đăng nhập. Mỗi test
tạo schema tên ngẫu nhiên riêng, chạy fixture baseline rồi SQL đề xuất, kiểm thử
và xóa đúng schema của nó. Suite từ chối host ngoài loopback và database không
có tiền tố test. Không đưa URL Supabase vào biến này. Nếu thiếu URL, các test
PostgreSQL được báo **skipped**, còn cùng contract chạy trên SQLite relational.

Fixture chỉ mô phỏng những cột team đang có mà adapter cần, không mô phỏng
`auth.users`, signup trigger hoặc RLS của Supabase. Kết quả local không chứng minh
quyền truy cập hay chính sách RLS trên cloud. Backend dùng direct PostgreSQL cần
role test phù hợp; owner luôn lấy từ Auth đã xác minh và lọc trong repository.

Đã kiểm thử trên PostgreSQL portable 17.11 chạy riêng tại loopback: 26 tests
(13 SQLite relational + 13 PostgreSQL), gồm apply đề xuất, Unicode, timezone,
resume/report qua connection mới, rollback, owner isolation, CAS và chấm đồng thời.
HTTP test dùng cấu hình runtime PostgreSQL, chấm đủ 3 câu và đọc lại report qua
hai instance app; retry pending sau mở kết nối mới, rollback create giữa chừng,
question snapshot/rubric và nhiều trích dẫn được giữ nguyên. Bộ kiểm thử cuối: **154 passed**,
gồm 8 browser tests; còn một warning TestClient/HTTPX đã có từ trước.
Binaries/database test ở `data/private/`, bị Git bỏ qua, không thành dependency
runtime của dự án. Nguồn binaries: [Zonky embedded PostgreSQL](https://github.com/zonkyio/embedded-postgres-binaries);
adapter dùng [SQLAlchemy psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg).

Workflow `.github/workflows/interview-tests.yml` đã được chuẩn bị để chạy suite
với PostgreSQL service và Chromium trên GitHub, không cần key Supabase/AI. Chưa
push nên chưa có kết quả runner/CI; kết quả 154 ở trên là chạy local trên Windows.
