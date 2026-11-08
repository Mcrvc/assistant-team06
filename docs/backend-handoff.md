# Trao đổi với Trương Bảo Anh: điểm dùng chung và schema mới

## Bản chia sẻ WIP — chưa hoàn thành tích hợp 100%

Nhánh chia sẻ: `feat/LOCAL-01-interview-lifecycle`. Người dùng đã cho phép push
nhánh riêng để Backend còn lại lấy code. Đây là bản phát triển để ghép tiếp;
không tự merge vào main/backend, áp dụng schema lên Supabase hoặc deploy.

**Đã có:** create/save/resume/submit/progress/finalize, kiểm tra trích dẫn,
adapter AI, verified token và PostgreSQL, giao diện interview gọi API.
**Kiểm chứng local:** 154 tests passed, gồm 13 PostgreSQL thật và 8 browser tests.
GitHub CI là kiểm chứng riêng; không suy ra đã qua CI từ kết quả local này.

**Còn làm trước khi hoàn tất với nhóm:**

1. Huy review cách lưu và SQL bổ sung đề xuất; chỉ áp dụng trên môi trường nhóm
   sau khi thống nhất. Schema Supabase hiện có chưa đủ cho adapter PostgreSQL.
2. Đối chiếu input/output tạo câu hỏi và chấm với Duy. Tiêu chí/thang điểm do AI
   phụ trách; quy ước score 0–10/ngưỡng 6 ở local cần được nhóm xác nhận/điều chỉnh.
3. Cấu hình DB test/Supabase/AI thật rồi kiểm thử toàn luồng. Demo SQLite và AI
   mẫu vẫn là mặc định; chưa kiểm chứng login hoặc model thật của project.
4. Ghép API Profile/CV/history/report riêng/feedback do Trương Bảo Anh phụ trách;
   chốt chính sách CV, review PR và cấu hình triển khai. BackgroundTasks còn dùng
   retry thủ công khi process dừng, chưa có durable queue.

### Lấy hàm kiểm tra token

Sau khi fetch nhánh này, cài dependencies từ root (`pip install -r requirements.txt`).
Các file dùng chung:

- `src/assistant/auth.py`: `SupabaseBearerAuth`, xác minh token và trả UUID user.
- `src/assistant/api.py`: `get_current_user` cho các route dùng app chung từ
  `create_app`; Supabase URL/JWKS đọc từ môi trường, demo phải tắt khi thử Auth thật.
- `tests/test_supabase_auth.py`: ví dụ kiểm tra chữ ký/claims và ownership.

Ví dụ dependency cho router dùng **app chung đã cấu hình**:

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from assistant.api import get_current_user

router = APIRouter()

@router.get("/api/profile")
def read_profile(user_id: Annotated[str, Depends(get_current_user)]):
    # Query the profile for this verified user_id.
    ...
```

Ví dụ trên chỉ minh họa cách nhận user đã xác minh, không phải API Profile đã
triển khai. Khi ghép router, cần đăng ký trước catch-all `/api/{unknown:path}`
và static mounts; tránh circular import giữa api.py và module router. Nếu dùng
app khác, tái sử dụng lớp verifier và cấu hình xử lý lỗi tương ứng.
Verifier hỗ trợ RS256/ES256; chưa hỗ trợ HS256 hay thu hồi session tức thì.
Backend không cung cấp đăng ký/đăng nhập hoặc tự thiết kế tiêu chí chấm.

## Bối cảnh khảo sát và đề xuất

Ngày 08/11/2026. Đây là thông tin đã kiểm tra và đề xuất để nhóm xác nhận,
không phải thay đổi schema hoặc quyết định đã được toàn nhóm đồng ý.

Cập nhật LOCAL-04: Trần Bảo Anh đã hoàn thiện adapter PostgreSQL và kiểm thử
độc lập. Mapping và SQL bổ sung **đề xuất để review** nằm ở
`docs/interview-postgres.md` / `docs/schema-proposals/LOCAL-04-interview.sql`.
Có đề xuất `sessions.report` để bên báo cáo đọc kết quả đã finalize và
`grades.result` giữ score/feedback/evidence/model đầy đủ. Chưa áp dụng lên cloud
và chưa tự map thang `grades.level`. Các nhận định thiếu cột bên dưới vẫn đúng
với schema nhóm đã khảo sát; adapter chỉ chạy sau khi có những bổ sung phù hợp.

## 1. FastAPI và chỗ đặt route

Code đã ghép local dùng một FastAPI app trong `src/assistant/api.py`;
`backend/app/main.py` chỉ import/re-export app đó. `src/assistant/web.py` là
server thư viện chuẩn cho prototype cũ. Đề xuất dùng APIRouter/module riêng
cho Profile/CV, history/report và feedback, rồi include vào app chung; không
viết thêm một ứng dụng FastAPI độc lập hoặc endpoint mới trong web.py.

Nếu nhóm muốn đặt router ở backend/app/, vẫn có thể include các router đó,
nhưng cần thống nhất import/package layout để hai entry point dùng cùng app.

## 2. Metadata Supabase hiện tại (đã đọc lại)

Project `ct-team06`, ref `qutiahnegjzgbxjopsqe`, hiện có 9 bảng trong public:
accounts, domains, rubrics, questions, sessions, session_questions, answers,
grades, feedback. Tất cả đang bật RLS. Chỉ đọc metadata, không đọc nội dung
tài khoản/CV và không sửa database. Snapshot public=0 bảng trước đây đã cũ.

| Chức năng | Schema đang có | Cần đối chiếu |
| --- | --- | --- |
| Profile | accounts: id UUID tham chiếu auth.users, username, created_at, updated_at | Chưa có cột CV mặc định của tài khoản |
| CV buổi phỏng vấn | sessions.parsed_cv (text) | Là CV theo session; không tự coi là CV mặc định của Profile |
| Lịch sử | sessions: id text, user_id UUID, domain_id, role, seniority, mode, voice, created, finished, finished_at, interview_seconds | Chưa có name/job snapshot/revision/current_question theo contract local |
| Báo cáo | Join sessions → session_questions/questions, answers, grades | Chưa có bảng reports hoặc JSON report hoàn chỉnh |
| Điểm/bằng chứng | grades: session_id, question_id, competency, level (smallint), evidence_quoted, accepted, created | Cần Huy/AI chốt scale của level và chỗ lưu feedback/score/model/fallback |
| Khảo sát | feedback: user_id, session_id, grade_rating (smallint), quality_rating (smallint), difficulty (text), comments (text), would_recommend (boolean), created | Khớp tên field trong draft contract; UI hiện vẫn có 4 câu trả lời tự do |

Backend local hiện dùng SQLite snapshot; **chưa ghi các bảng Supabase này**.
Schema DB mới không tự tương thích với report local (0–10, feedback/evidence,
rubric/model/fallback). Cần Huy xác nhận các cột bổ sung hoặc cách ánh xạ; không
tự đổi thang điểm hoặc nhét dữ liệu vào cột khác để chạy tạm.

## 3. Khảo sát

Đề xuất bám các field hiện đã có trong API_CONTRACT và bảng feedback:
grade_rating, quality_rating, difficulty, comments, would_recommend.
Giới hạn/range rating chưa được chốt bởi dữ liệu kiểu smallint; cần thống nhất
với Khang và schema constraints, không tự giả định là 1–5 hoặc 0–10.
Nếu giữ UI 4 câu tự do thì phải thống nhất một payload/schema riêng; không tự
chuyển câu trả lời tự do thành điểm số. Đây là quyết định còn cần nhóm xác nhận.

## 4. Cấu hình chạy thử

Nhờ Nhân gửi riêng cấu hình test theo cách nhóm thống nhất, không commit file
.env hoặc gửi secret vào chat. Supabase client cần URL/publishable key; backend
JWT/JWKS không cần service secret để xác minh chữ ký. Nếu dùng SQLAlchemy direct
connection như `backend/app/db/session.py`, còn cần DATABASE_URL cho môi trường
test. Các API Profile/history/feedback không cần key AI để được phát triển.
PAT MCP chỉ dùng khảo sát chỉ đọc, không thay credential runtime của backend.

## 5. Token dùng chung và branch

Trần Bảo Anh đã viết `SupabaseBearerAuth` trong `src/assistant/auth.py`; HTTP
dependency `get_current_user` ở `src/assistant/api.py` lấy user ID đã xác minh.
Tests đã kiểm tra chữ ký RS256/ES256, claims và quyền sở hữu. Chưa xác minh với
login thật vì chưa có runtime public config. Không cần hai người viết lại
verifier. Khi chia router, tách/import dependency dùng chung theo cách tránh
circular import; không chỉ decode JWT rồi tin user ID.

Code được chia sẻ qua nhánh riêng `feat/LOCAL-01-interview-lifecycle` theo yêu cầu
của người dùng. Đề xuất hai người có feature branch riêng từ cùng base tích hợp
và ghép bằng PR; backend có thể là
nhánh tích hợp nếu nhóm đồng ý, không cùng sửa/push chồng trực tiếp lên một nhánh.

API_CONTRACT phía frontend gồm phần draft cũ và phần LOCAL-02 implementation
update. Đọc `docs/interview-api.md` cho contract interview đang chạy để tránh
hiểu rằng finalize mới gọi AI; hiện từng đáp án được chấm nền trước finalize.
