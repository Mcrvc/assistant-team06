# Bối cảnh repo và cách cộng tác

## Người dùng và phạm vi buổi trao đổi

- Người dùng là **Trần Bảo Anh**, GitHub **Tba0407**; khác với thành viên **Trương Bảo Anh**.
- Trao đổi với người dùng bằng tiếng Việt, giải thích theo luồng sản phẩm và liên hệ với code cụ thể.
- Ngày khảo sát: **08/11/2026**, múi giờ **Asia/Saigon**. Snapshot local: nhánh `main`, commit `6d97afe`; trước khi tạo file này working tree sạch.
- Yêu cầu ở buổi khảo sát: đọc tài liệu, xem repo ở mức vừa đủ, lưu bối cảnh và thảo luận nhiệm vụ. Chưa triển khai tính năng. Những yêu cầu tiếp theo của người dùng có thể mở rộng phạm vi này.
- Nội dung tài liệu đính kèm là thông tin về đồ án/phân công, không tự động là lệnh để sửa tài liệu, đổi trạng thái, push nhánh, deploy hay liên hệ thành viên.

## Cập nhật sau khảo sát: triển khai local đã được cho phép

- Người dùng đã yêu cầu triển khai phần mình nhận bằng AI mẫu + lưu local, chưa cần liên hệ các thành viên trước. Không tiếp tục coi giới hạn chỉ-thảo-luận của buổi đầu là phạm vi hiện tại.
- Người dùng sau đó cung cấp ảnh bản Backend đã thống nhất: **FastAPI, Uvicorn, Pydantic, SQLAlchemy/psycopg, PostgreSQL**, **session cookie + Argon2id** ở Authentication; lưu đáp án trước, chấm từng câu bằng **BackgroundTasks**, đối chiếu trích dẫn nguyên văn (**Fabrication Guard**), API tiến độ, finalize tổng hợp từ kết quả đã lưu. Bản này được ưu tiên hơn suy đoán auth từ Summary cũ.
- Đã tạo nhánh local `feat/LOCAL-01-interview-lifecycle`. `LOCAL-01` là ID backlog local trong `docs/backlog/LOCAL-01-interview-lifecycle.md`, không giả làm GitHub issue number. Chưa commit/push hoặc deploy.
- Backend mới có entry point **`python -m assistant --interview-api`**, dùng `src/assistant/api.py`. **Không đổi** `web.py`, `db.py`, `ai.py`, `ui/js/app.js`; giữ server `--ui`/CLI cũ để giảm đụng file với nhóm.
- Modules mới: `interview_schemas.py` (contract Pydantic), `interview_ai.py` (provider/fallback), `interview_store.py` (SQLAlchemy SQLite local), `interviews.py` (lifecycle, ownership, revision, background grading/evidence guard).
- `INTERVIEW_DEMO_ENABLED=1` mới bật cookie demo local; mặc định tắt. `INTERVIEW_DB_PATH` mặc định `data/private/interviews.sqlite`. Demo dùng một user giả, không phải auth production; tắt demo khi deploy. Không dùng chế độ demo sau proxy.
- Điểm nối auth thật: `create_app(service=..., auth_resolver=...)`; resolver phải xác minh session cookie trước khi trả user ID. Argon2id/password login vẫn thuộc phần Auth của nhóm, chưa triển khai.
- Contract: create → 3 câu kèm criteria/source, response câu đầu; save progress/draft; GET để tiếp tục; submit từng đáp án → 202/pending rồi background grading; GET progress; finalize chỉ khi 3 câu đã graded, không gọi AI lại.
- Trích dẫn bịa bị rejected, không lưu điểm đó. Kết quả AI sai cấu trúc/provider lỗi dùng mock có cờ fallback. Mock chấm theo số từ, không đánh giá năng lực thật.
- Dữ liệu local bền qua restart; tác vụ BackgroundTasks không bền qua process crash. Re-submit cùng đáp án với revision mới nhất để retry pending/rejected. `grading_id` chặn output cũ sau khi sửa đáp án.
- Đã kiểm tra: **41 tests passed**; chạy script HTTP thành công qua Uvicorn; check_env và pip check qua. 1 warning deprecation từ Starlette TestClient/HTTPX. `eval/run.py` cũ báo 0% với source rules/eval không sửa; chưa phải bộ đánh giá interview.
- Hướng dẫn/contract: **`docs/interview-api.md`**; báo cáo đã xong/còn thiếu: **`docs/backend-progress.md`**; script demo: **`scripts/demo_interview.py`**.
- Chưa ghép PostgreSQL/schema nhóm, AI thật, Auth thật, Frontend, PDF/URL JD, câu hỏi có nguồn thật hoặc deployment. Không báo rằng tích hợp end-to-end cloud đã hoàn thành. Không đổi sang chấm toàn bài tại finalize vì trái luồng mới.
- Các mục dưới đây mô tả **snapshot trước khi triển khai**, dùng làm lịch sử; trạng thái hiện tại ở phần cập nhật này và báo cáo mới.

## Nguồn đã đọc

### Supabase MCP: đã xác nhận kết nối chỉ đọc

- Project nhóm: `ct-team06`, ref `qutiahnegjzgbxjopsqe`.
- OAuth từ tài khoản người dùng bị chặn bởi yêu cầu Owner/Admin của tổ chức. Không coi lời mời thành viên là đủ để approve ứng dụng OAuth.
- Người dùng đã tạo và copy PAT giới hạn một project, **Database Read**, thời hạn 7 ngày (đã xem trang review quyền, không xem giá trị token).
- Đã cập nhật riêng server `supabase` trong cấu hình Codex cấp user để dùng `bearer_token_env_var = "SUPABASE_MCP_READ_TOKEN"`; giữ URL `https://mcp.supabase.com/mcp?project_ref=qutiahnegjzgbxjopsqe&read_only=true&features=database,docs` và các cấu hình khác.
- Người dùng đã nhập token cục bộ và mở lại VS Code. Đã gọi Supabase MCP thành công ngày 08/11/2026; truy vấn xác nhận `transaction_read_only = on`, `database_role = supabase_read_only_user`. Không đọc/in giá trị token.
- Đã kiểm tra bằng `list_tables(public)` và đối chiếu catalog `pg_namespace`/`pg_class`: **public có 0 bảng, 0 view**. Các schema còn lại thấy được là auth, extensions, graphql, graphql_public, pgbouncer, realtime, storage, vault; chưa thấy schema ứng dụng tùy chỉnh hoặc bảng interview. Chỉ đọc metadata, không đọc hàng dữ liệu auth/CV/tài khoản.
- Đây là trạng thái cloud tại thời điểm kiểm tra, không chứng minh bạn Database chưa có bản thiết kế/script local. Phải kiểm tra lại schema khi chuẩn bị tích hợp vì thành viên khác có thể cập nhật.
- Chưa có bảng để ánh xạ repository local sang dữ liệu nhóm. Cần thống nhất/tạo schema qua phần Database và migration được duyệt trước khi nối lưu interview thật; không tự chạy CREATE/ALTER/INSERT hoặc cấp quyền trên project chung.
- Khi cần kiểm tra tiếp, ưu tiên metadata bảng/cột/khóa/quan hệ; không tự ghi database hoặc quét dữ liệu CV/tài khoản thật. Không in token, header Authorization hoặc toàn bộ cấu hình chứa secret.

### Kiểm tra các nhánh GitHub sau khi làm bản local

- Người dùng đã chọn hướng phối hợp dựa trên các nhánh nhóm trước khi có schema cloud. Đã fetch lại, các head dưới đây chưa đổi; kế hoạch tại `docs/integration-todo.md`: contract/cấu trúc chạy → AI adapter → Auth theo code Supabase hiện có (cần đối chiếu thiết kế cookie cũ) → frontend interview → kiểm thử bản ghép → DB schema của Huy → review/deploy. Đây là kế hoạch, chưa merge hay triển khai các điểm nối này.
- Đã `git fetch origin` và chỉ đọc bằng `git show`/`git diff`; không checkout/merge các nhánh, không sửa code của bản local trong bước kiểm tra này.
- Snapshot remote: `AI` = `32d6f69`, `authen` = `aa81df6`, `frontend` = `08b8ceb`, `setup` = `9d07415`, `main` = `6d97afe`. Kiểm tra lại head nếu tiếp tục tích hợp.
- `frontend` đã chứa cả hai commit của `AI` và `authen` (đã xác minh ancestor). Nó thêm cây `frontend/` và `backend/` bên cạnh `ui/` và `src/assistant/`; chưa thống nhất một cấu trúc duy nhất.
- `AI`: `ai.py` có code gọi NVIDIA và TinyFish, retry/timeouts; `aiworker.py` có `generate_questions(job_profile, cv, notes, sources)` và `grade_answer(question, answer, rubric)` để tận dụng qua adapter. Chưa chạy provider thật/kiểm thử nhánh remote.
- Contract AI chưa khớp local: question dùng `question` + rubric có trọng số thay vì `text` + criteria chuỗi; grading trả verdict/score/feedback nhưng **không có evidence nguyên văn**. Fallback generation hiện chỉ có **2 câu**, fallback grade `score=None`. Không tự thêm evidence giả để làm guard qua, hoặc coi map field là đủ tích hợp.
- `authen`: có FastAPI skeleton `backend/app/main.py` (chỉ `/api/config`), SQLAlchemy session qua `DATABASE_URL`, Alembic skeleton; chưa thấy schema/migration interview hoặc xác minh JWT phía backend. Auth thực tế trong JS dùng Supabase Auth, **khác session cookie/Argon2id trong ảnh thiết kế**. Không coi cơ chế auth production đã được nhóm chốt lại theo code.
- `frontend/docs/API_CONTRACT.md` là draft: dùng Supabase Bearer token, create `{job,cv,cvMode,cvPdf}`, GET bọc `{interview}`, PUT cập nhật session, finalize có thể xếp job để chấm; khác API local và luồng chấm từng câu. Còn ghi yêu cầu CV không rời máy (MVP 1.6), trong khi các payload dự kiến có CV; cần đối chiếu phạm vi dữ liệu khi ghép, không tự diễn giải thành quyền gửi CV thật.
- `frontend/js/app.js` đã có gọi createInterview/saveCV dạng mirror song song local state; chưa thấy gọi finalize/getReport/updateInterview trong app.js qua tìm kiếm các tên hàm. Không báo frontend đã nối hoàn chỉnh. Loading/error/404 có thể tái sử dụng.
- `setup` chủ yếu bổ sung URL Render cho `ui/js/api.js`; mức hữu ích thấp cho lifecycle. `authen` ghim SQLAlchemy 2.1.6 trong khi bản local dùng `<2.1`: cần đồng bộ dependency khi ghép.


Ba tài liệu do người dùng cung cấp nằm ngoài repo, ở thư mục Downloads trên máy hiện tại:

- `Summary.docx`: snapshot deploy, kiến trúc và quy ước thư mục.
- `about the project.docx`: yêu cầu học phần và các mốc đồ án.
- `25C11 - Project.docx`: phân công công việc đến 08/11/2026.

Các file này có thể không tồn tại trên máy khác. Bản ghi dưới đây tách hiện trạng đã thấy trong code khỏi thông tin do tài liệu báo cáo. Kiểm tra lại khi repo hoặc yêu cầu nhóm thay đổi.

## Sản phẩm và yêu cầu học phần

- Sản phẩm hiện tại là **Yourin — Interview AI Assistant**, ứng dụng web luyện phỏng vấn theo Job Profile và CV tùy chọn.
- Luồng chính: Profile/CV → Job Profile → tạo buổi phỏng vấn có **3 câu hỏi** → trả lời, lưu dở/tiếp tục → finalize → báo cáo nhận xét, điểm và nhãn `Good` / `Needs Improvement` → khảo sát.
- Yêu cầu học phần: UI, backend/API, database, tích hợp AI, đánh giá đo lường được và tài liệu/báo cáo; lớp bảo mật được liệt kê là tùy chọn.
- Tài liệu tổng quan ưu tiên độ phủ tính năng → tích hợp hệ thống → kiểm thử → tối ưu. Các mốc ghi trong tài liệu: Proposal/PoC tuần 5, MVP/demo tuần 8, user testing từ tuần 9, trình bày cuối tuần 11.

## Phân công trong tài liệu ngày 08/11/2026

- **Trần Bảo Anh và Trương Bảo Anh: Backend**. Chưa có chia nhỏ nhiệm vụ giữa hai người trong tài liệu.
- Sau khi thảo luận, người dùng đã chốt nhận: **tạo interview, lưu câu trả lời/lưu dở, tiếp tục interview, finalize và nối AI**. Tương ứng mục Backend con thứ 2 và thứ 3 trong tài liệu. Tiếp tục interview cần đọc lại session, câu hỏi và câu trả lời đã lưu, dù tài liệu không tách thành dòng riêng.
- Profile/CV, danh sách lịch sử, API đọc báo cáo và khảo sát nằm ngoài phần người dùng vừa nhận; đề xuất giao Trương Bảo Anh nhưng chưa có xác nhận của thành viên đó. Phân biệt finalize tạo/lưu báo cáo (phần người dùng) với API đọc báo cáo để hiển thị (phần còn lại).
- Nguyễn Phúc Duy: AI; Phan Văn Trường Huy: Database; Trần Đức Hiển: Authentication + Frontend; Nguyễn Duy Khang: Frontend; Đặng Vũ Thiện Nhân: Deploy và hỗ trợ.
- Deadline ghi cho đợt này: **21:00 Chủ nhật, 08/11/2026**. Đây là mốc trong tài liệu, không phải deadline tự động áp dụng cho công việc tương lai.
- Backend cần API: đọc/lưu CV; tạo interview từ Job Profile + CV và gọi AI sinh 3 câu hỏi; lưu buổi dở; finalize và gọi AI chấm điểm; danh sách lịch sử; báo cáo; gửi khảo sát.
- Tài liệu yêu cầu phối hợp với AI và DB/Auth; chưa xác định tên bảng, schema, JSON contract hay cách chia file giữa hai người Backend.
- Tài liệu nhắc push nhánh `backend`, trong khi `CONTRIBUTING.md` quy định nhánh `type/issue-number-description`. Trước khi tạo nhánh cho code mới, đối chiếu thỏa thuận thực tế của nhóm; không tự coi hai quy ước đã thống nhất.

## Kiến trúc: thông tin tài liệu và hiện trạng local

Theo Summary, nhóm đã thiết lập **Vercel (ui/) → Render (Python API) → Supabase (Postgres/Auth)**, và backend sẽ gọi nhà cung cấp AI. **Chưa kiểm tra deployment, URL live, schema cloud hay kết nối thực tế** trong buổi khảo sát.

Đã xác minh trong repo local:

- Repo nhỏ: **62 tracked files, khoảng 265 KB** tại snapshot trên. Không cần quét sâu assets/CSS hay đọc toàn bộ lịch sử để nắm backend. Nếu repo lớn thêm, kiểm kê và giới hạn phạm vi trước.
- `src/assistant/web.py`: server dùng thư viện chuẩn `ThreadingHTTPServer`/`SimpleHTTPRequestHandler`, phục vụ `ui/`; hỗ trợ `PORT`, `HOST`, `CORS_ORIGIN` và CORS. Hiện chỉ có `GET /api/health`, `GET /api/config`, `POST /api/answer`, cùng xử lý OPTIONS.
- `/api/health` chỉ phản ánh trạng thái cấu hình biến môi trường, không thử kết nối Supabase/AI.
- `src/assistant/db.py`: nạp `.env`, đọc cấu hình và xuất cấu hình công khai. **Chưa có kết nối/truy vấn DB, schema/migration hoặc xác thực JWT**.
- `src/assistant/ai.py`: `answer(...)` và dataclasses theo `docs/ai-interface.md`; hiện gọi `rules.reply()` với `used_fallback=True`. **Chưa gọi LLM, chưa có hàm sinh câu hỏi/chấm phỏng vấn**. Fallback này vẫn thuộc bài tra cứu văn phòng cũ.
- `ui/`: 13 trang HTML, `css/`, `js/`, `assets/`. Giữ cấu trúc thư mục con để bảo toàn đường dẫn.
- `ui/js/app.js`: controller PoC dùng `localStorage` và `window.name`; đăng nhập, CV, interview và khảo sát đều là demo local. Không gọi `YourinAPI` tại snapshot này.
- `ui/js/data.js`: câu hỏi, câu trả lời, feedback, CV và khảo sát mẫu; không phải kết quả AI thật.
- `ui/js/api.js`: helper cho health/config/answer; `RENDER_API_URL` còn trống, chỉ tự dùng origin khi chạy localhost/127.0.0.1. Không thể suy ra frontend live đã nối Render.
- UI chọn PDF hiện chỉ lưu metadata như tên/kích thước/ngày, **chưa upload file hoặc trích xuất nội dung PDF**. Cần chốt phạm vi PDF với nhóm trước khi tính là tính năng hoàn chỉnh.
- Chưa có `.env` ở root trong lúc khảo sát; không có khóa thật để kiểm tra tích hợp.

## Dữ liệu PoC để tham khảo khi chốt contract

- Account có `username`, `cv` (mảng 4 chuỗi), `cvMode`, `cvPdf`, `job`, `syncCV`, `activeId`, `feedback`, `interviews`. Password demo không phải thiết kế auth thật; không mang cách lưu password local sang backend.
- Job dùng các key UI: `job-source`, `job-title`, `domain`, `company`, `position`.
- Interview có `id`, `name`, `date`, `finished`, `answers` (3 chuỗi), snapshot `cv`, `cvPdf`, `cvMode`, `job`. Câu hỏi hiện lấy chung từ dữ liệu mẫu, chưa lưu theo session.
- Đây là shape demo, **chưa phải schema DB hoặc API contract được nhóm duyệt**. Khi triển khai cần thống nhất ID người dùng, trạng thái buổi phỏng vấn, questions, answers, report và snapshot Job/CV.

## Tài liệu cũ và điểm cần chốt

- `README.md`, `docs/team.md`, `docs/ai-interface.md` vẫn thiên về bài lab trợ lý tra cứu văn phòng. Không dùng phân công setup trong `docs/team.md` thay cho phân công Backend ngày 08/11.
- `docs/ui-transitions.md` ghi lại bản Figma cũ (có trang đã gộp/đổi và control nay đã hoạt động); đối chiếu HTML/JS hiện có trước khi dựa vào nó.
- Chưa chốt: xác nhận phần còn lại với thành viên Backend kia và cách chia file; schema/tên bảng và quyền truy cập với Database/Auth; input/output hai hàm AI; API contract với Frontend; PDF/URL JD ở mức nào cho MVP.
- Tại buổi khảo sát đầu chưa triển khai code. Sau đó đã triển khai bản local theo phần cập nhật ở trên; contract local còn cần nhóm đối chiếu khi ghép.

## Quy ước và kiểm chứng cho lần làm tiếp

- Đọc `CONTRIBUTING.md` trước khi sửa code: issue trong backlog, feature branch, PR có teammate review; không commit trực tiếp lên `main`. Buổi khảo sát này chỉ tạo tài liệu local, chưa commit/push.
- Definition of Done và review checklist hiện ở `lab02/templates/DEFINITION_OF_DONE.md` và `lab02/templates/REVIEW_CHECKLIST.md`; AI use cần được nêu trong PR theo DoD.
- Không đưa `LLM_API_KEY` hoặc `SUPABASE_SECRET_KEY` xuống UI, log hay Git. Dùng `.env` local / biến môi trường hosting; `.env.example` chỉ chứa placeholder. Không cần in giá trị `.env` để kiểm tra cấu hình.
- Các key hiện có: `LLM_API_KEY`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `SUPABASE_JWKS_URL`.
- Python yêu cầu >=3.10. Snapshot cũ dùng thư viện chuẩn; nay thêm optional extras `web` (FastAPI/Uvicorn/Pydantic/SQLAlchemy), `dev` (pytest/HTTPX), `postgres` (psycopg). `requirements.txt` cài `.[web,dev]`.
- Setup theo repo: tạo venv, `pip install -r requirements.txt`, `pip install -e .`.
- Chạy UI/backend local: `python -m assistant --ui` (tự mở browser); CLI lab cũ: `python -m assistant`.
- Các lệnh kiểm tra sẵn có: `python scripts/check_env.py`, `pytest -q`, `python eval/run.py`. Tests/eval hiện chủ yếu cho rules tra cứu văn phòng, **không chứng minh luồng phỏng vấn hoạt động**.
- Buổi khảo sát chỉ đọc tài liệu/code, không chạy server, tests, gọi cloud, sửa tài liệu Word hoặc triển khai chức năng. Khi sửa backend sau này, cần kiểm chứng validation, quyền sở hữu dữ liệu, lưu/đọc session và AI fallback phù hợp phạm vi thay đổi.
