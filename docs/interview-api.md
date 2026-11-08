# Interview backend: bản local để ghép với nhóm

Phạm vi của Trần Bảo Anh: tạo interview, lưu/tiếp tục, nhận đáp án, gọi AI chấm
nền, kiểm tra bằng chứng và finalize. Bản này chạy độc lập với **AI mẫu + SQLite
qua SQLAlchemy**. Không cần key hay truy cập Supabase.

Thiết kế cập nhật theo bản Backend người dùng cung cấp: Python 3.10+, FastAPI,
Uvicorn, Pydantic, SQLAlchemy; mục tiêu ghép PostgreSQL/psycopg và session cookie
của nhóm. Chấm từng câu ở BackgroundTasks, finalize chỉ tổng hợp kết quả đã chấm.
Không dùng cách chờ đến finalize mới gọi AI cho toàn bộ bài.

## Chạy trên Windows / PowerShell

Ở thư mục gốc repo:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:INTERVIEW_DEMO_ENABLED = "1"
.\.venv\Scripts\python.exe -m assistant --interview-api
```

Mở **http://127.0.0.1:8000/docs** để xem và thử API. Chạy
`POST /api/demo/session` bằng nút **Try it out → Execute** trước; browser nhận
cookie thử nghiệm. Sau đó có thể gọi các API interview trong cùng trang này.
Cookie demo không phải đăng nhập bằng mật khẩu; không có tài khoản thật.

Trong cửa sổ PowerShell thứ hai:

```powershell
.\.venv\Scripts\python.exe scripts/demo_interview.py
```

Script tự tạo cookie và thực hiện tạo → lưu dở → đọc lại → gửi 3 đáp án → chờ
chấm → finalize → thử finalize lần nữa. Dữ liệu đều là giả. Script tạo một buổi
mới mỗi lần chạy và giữ dữ liệu đó trong DB local.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

`python -m assistant --ui` vẫn chạy server/UI demo cũ, **không có API interview
mới**. Dùng `--interview-api` cho phần này. Frontend `ui/js/app.js` chưa được nối
với backend mới; có thể kiểm tra độc lập bằng Swagger và script ở trên.

## Lưu trữ và phiên thử nghiệm

- Mặc định tắt demo. Bật bằng `INTERVIEW_DEMO_ENABLED=1`; CLI chỉ cho bind loopback.
  API demo cũng kiểm tra địa chỉ client, Host và Origin; không dùng forwarded
  headers để giả lập client local. Không bật chế độ này trên Render hoặc sau proxy.
- Cookie `yourin_demo_session`: HttpOnly, SameSite=Strict, chỉ dùng HTTP local.
  Tất cả phiên demo thuộc một user giả `local-demo`, không mô phỏng nhiều tài khoản.
- Khởi động lại server thì gọi lại `/api/demo/session`. Dữ liệu buổi phỏng vấn vẫn
  còn, miễn là dùng cùng file DB và giữ lại `id`.
- File mặc định: `data/private/interviews.sqlite` (đã được `.gitignore` bỏ qua).
  Có thể đổi bằng `INTERVIEW_DB_PATH`; đường dẫn tương đối tính từ root repo.
- Các request không nhận `user_id`/`owner_id` từ client. Khi tích hợp Auth, truyền
  `auth_resolver(request)` vào `create_app(...)` để kiểm tra session cookie thật,
  hết hạn/thu hồi session và trả về user ID; khi thất bại trả 401. Production còn
  cần CSRF, HTTPS/Secure cookie và chính sách CORS của nhóm.
- Argon2id thuộc phần đăng ký/đăng nhập của bạn Auth, chưa được triển khai ở đây.
  Bản mới ưu tiên thiết kế session cookie người dùng vừa cung cấp; không tự ghép
  JWT Supabase trong Summary cũ vào một cơ chế auth khác.

## Contract đề xuất v1

Đây là contract local để các bên tham khảo, chưa khẳng định cả nhóm đã dùng nó.
Các endpoint cần cookie phiên. Chỉ số câu hỏi bắt đầu từ **0**.

| Method | Endpoint | Kết quả |
| --- | --- | --- |
| POST | `/api/demo/session` | 200, tạo cookie demo; chỉ bật local |
| POST | `/api/interviews` | 201, lưu 3 câu hỏi và trả câu đầu tiên |
| GET | `/api/interviews/{id}` | 200, snapshot đầy đủ để tiếp tục, gồm questions/answers/report |
| POST | `/api/interviews/{id}/progress` | 200, lưu draft/vị trí, lưu dở hoặc đánh dấu tiếp tục |
| POST | `/api/interviews/{id}/answers/{index}` | 202, lưu đáp án ở trạng thái pending rồi chấm nền |
| GET | `/api/interviews/{id}/progress` | 200, số đã trả lời/đã chấm/đang chờ/bị từ chối |
| POST | `/api/interviews/{id}/finalize` | 200, tổng hợp và lưu báo cáo khi 3 câu đã chấm hợp lệ |

### Tạo interview

```json
{
  "name": "Backend practice",
  "job_profile": {
    "title": "Python Backend Intern",
    "domain": "Software",
    "company": "Example",
    "level": "Intern",
    "description": "Build and test Python APIs."
  },
  "cv": "CV text, or null when not used"
}
```

Job cần ít nhất title hoặc description không rỗng. CV nhận text/null, chưa nhận
PDF hoặc tự truy cập URL JD. UI cũ cần map: `job-title` → title, `job-source` →
description, `position` → level; CV mảng 4 chuỗi có thể nối thành text trước khi gửi.

Response có `id`, `revision: 0`, `status: in_progress`, `total_questions: 3`,
`current_question: 0`, `question`, `question_generation`.

```json
{
  "text": "Describe a project relevant to this role.",
  "source_type": "open",
  "reference": null,
  "criteria": ["Relevant example", "Clear personal actions", "Outcome and reflection"]
}
```

Câu có nguồn dùng `source_type: reference` và reference gồm `title`, `locator`,
`excerpt`; Pydantic kiểm tra cấu trúc. Backend chưa xác minh tài liệu bên ngoài
hoặc xây ngân hàng câu hỏi. Mock hiện chỉ tạo câu mở. Adapter AI có thể tra ngân
hàng câu hỏi trước hoặc gọi model, rồi trả cùng contract.

### Lưu dở và tiếp tục

```json
{
  "revision": 0,
  "answers": ["Draft answer", "", ""],
  "current_question": 1,
  "status": "interrupted"
}
```

`answers` là tùy chọn; nếu gửi thì phải có 3 chuỗi. Đây là **lưu draft**, không tự
chấm. GET theo id để đọc lại; gửi progress với `status: in_progress` để đánh dấu
tiếp tục. Khi thay đổi text, điểm cũ và kết quả chấm đang chạy của text cũ bị vô hiệu.

### Gửi một đáp án để chấm nền

```json
{"revision": 1, "text": "I built a Python API and wrote tests with my team."}
```

Lưu đáp án trước, trả HTTP 202 với `grading_status: pending` và revision mới.
BackgroundTasks gọi AI sau khi gửi response. Có thể làm câu sau ngay. GET progress
để theo dõi, GET interview để đọc chi tiết. **Không coi 202 là đã chấm xong.**

Backend kiểm tra điểm 0–10, kết quả hữu hạn, feedback và bằng chứng đúng cấu trúc.
Mọi trích dẫn evidence phải không rỗng và có nguyên văn trong đáp án tương ứng
(phân biệt hoa/thường, khoảng trắng). Nếu không, trạng thái `rejected`,
`error_code: evidence_not_found`, không lưu điểm sai và không cho finalize.
So khớp nguyên văn chỉ xác minh đoạn trích tồn tại, không chứng minh nhận xét AI
đúng hoặc tiêu chí chấm đủ tốt.

Nhà cung cấp lỗi/trả cấu trúc hỏng thì dùng mock có `used_fallback: true`,
`model: local-mock`. Mock chấm theo **số từ** để thử luồng, không đánh giá năng lực.
Kết quả và báo cáo luôn gắn thông tin fallback.

BackgroundTasks chạy trong tiến trình server, không phải hàng đợi bền vững. Nếu
tắt server giữa lúc chấm, đáp án vẫn còn `pending`. Sau khi bật lại, gửi lại cùng
text với revision mới nhất để xếp tác vụ mới. Cách này cũng dùng để thử lại câu
`rejected`. Mã `grading_id` ngăn tác vụ cũ ghi đè câu đã sửa/gửi lại. Chưa có
timeout hoặc retry tự động cho nhà cung cấp thật; adapter tương lai phải đặt
network timeout và cần job queue nếu muốn tự khôi phục sau sự cố.

### Finalize

```json
{"revision": 4, "name": "My completed practice"}
```

Chỉ thành công khi 3 đáp án không rỗng và đã `graded`. Không gọi AI lại tại đây.
Báo cáo gồm điểm trung bình, từng câu/đáp án, tiêu chí, bằng chứng, nhận xét,
model, nhãn `Good` (điểm >= 6) / `Needs Improvement` và cờ fallback. Thang điểm
0–10 và ngưỡng 6 là quy ước local cần thống nhất lại với AI/Frontend.
Buổi đã finalize không sửa được qua các API này. Gửi lại finalize trả cùng báo cáo;
đổi tên trong lần retry bị từ chối. Chưa có endpoint báo cáo riêng/lịch sử/khảo sát.

### Revision và lỗi

Mọi request ghi sau create phải gửi revision từ response gần nhất. Lưu user làm
tăng revision, chấm nền chỉ tăng version DB nội bộ nên không tự gây conflict cho
frontend. Revision cũ trả 409: đọc lại session và quyết định dữ liệu cần gửi lại,
không tự ghi đè bằng draft cũ. Hai tác vụ chấm nền dùng cập nhật nguyên tử để tránh
làm mất điểm của nhau.

Lỗi theo dạng `{"error": {"code": "...", "message": "..."}}`:

- 400: dữ liệu sai, thiếu đáp án; 401: thiếu/sai cookie.
- 403: truy cập demo từ xa hoặc Origin khác; 404: sai id hoặc buổi không thuộc user.
- 409: revision cũ, chấm chưa đủ hoặc sửa buổi finalized.
- 503: storage lỗi hoặc chưa cấu hình Auth thật khi demo tắt.

Không trả CV/đáp án đầu vào trong lỗi validation. Các field lạ bị từ chối. Text
giới hạn: JD 20.000 ký tự, CV 40.000, đáp án 20.000/câu; name/title/domain/company/
level tối đa 200. API không nhận owner ID của client.

## Điểm nối cho nhóm

| Phần | Đã có | Còn cần ghép |
| --- | --- | --- |
| AI | `InterviewAI` trong `interview_ai.py`, validation + fallback | Adapter gọi hàm của Phúc Duy trong `ai.py`; timeout; rubric/nguồn thật |
| Database | `InterviewRepository` trong `interviews.py`, adapter SQLAlchemy local | Schema PostgreSQL, migrations và quyền truy cập của nhóm |
| Auth | `get_current_user`, `auth_resolver`, lọc quyền sở hữu | Session cookie thật và tích hợp Auth/Argon2id của nhóm |
| Frontend | Contract, `/docs`, script thử HTTP | Gọi API thay localStorage, gửi cookie, polling/loading/error |
| Deploy | ASGI factory `create_app(...)`; demo tắt mặc định | Cấu hình Render, CORS origin cụ thể, HTTPS và DB production |

Không chạy `metadata.create_all()` vào database chung. Table `local_interviews`
lưu JSON snapshot phục vụ phát triển độc lập, chưa phải schema production. Có
thể thay repository bằng adapter schema nhóm mà giữ service/API. Extra `postgres`
cài psycopg cho giai đoạn tích hợp; chưa có kết nối cloud trong bản này.

API legacy `/api/health`, `/api/config`, `/api/answer` vẫn có trên server mới.
Health chỉ phản ánh cấu hình, không phải bài test kết nối AI/DB.

Tham khảo kỹ thuật đã đối chiếu: [FastAPI BackgroundTasks](https://fastapi.tiangolo.com/tutorial/background-tasks/),
[FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/),
[Pydantic models](https://docs.pydantic.dev/latest/concepts/models/),
[SQLAlchemy SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html).
