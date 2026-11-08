# Trao đổi với Trương Bảo Anh: điểm dùng chung và schema mới

Ngày 08/11/2026. Đây là thông tin đã kiểm tra và đề xuất để nhóm xác nhận,
không phải thay đổi schema hoặc quyết định đã được toàn nhóm đồng ý.

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

Code hiện nằm ở nhánh local `feat/LOCAL-01-interview-lifecycle`, đã commit nhưng
**chưa push** nên teammate chưa pull được các module mới. Đề xuất hai người có
feature branch riêng từ cùng base tích hợp và ghép bằng PR; backend có thể là
nhánh tích hợp nếu nhóm đồng ý, không cùng sửa/push chồng trực tiếp lên một nhánh.

API_CONTRACT phía frontend gồm phần draft cũ và phần LOCAL-02 implementation
update. Đọc `docs/interview-api.md` cho contract interview đang chạy để tránh
hiểu rằng finalize mới gọi AI; hiện từng đáp án được chấm nền trước finalize.
