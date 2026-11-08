# Báo cáo phần Backend của Trần Bảo Anh

Ngày cập nhật: 08/11/2026. Nhánh local: `feat/LOCAL-01-interview-lifecycle`.
Đã triển khai và kiểm tra bản ghép local từ các nhánh nhóm. Đã commit checkpoint
sau từng việc theo yêu cầu người dùng; chưa push, deploy hoặc ghi vào cloud.

## Cập nhật LOCAL-04: phần độc lập đã hoàn thiện thêm

- `ee6ca7d`: adapter PostgreSQL relational + schema bổ sung đề xuất, 18 tests
  khi lưu checkpoint. Dùng bảng nhóm; lưu session/questions/answers/grades theo
  transaction, chống ghi đè và giữ question snapshot/báo cáo.
- `9e5950f`: nối lựa chọn PostgreSQL vào API startup, 148 tests ở checkpoint.
  `INTERVIEW_STORAGE=postgres` mới dùng DATABASE_URL; mặc định demo giữ SQLite.
  Không DDL tự động, không fallback SQLite khi DB hỏng; startup errors đã lọc.
- Kiểm chứng cuối: **154 tests passed**, gồm **13 PostgreSQL thật**, 13 contract
  tương ứng trên SQLite relational và 8 browser tests. Có full HTTP lifecycle,
  mở app mới đọc lại report, rollback create/save, owner isolation, CAS, concurrent
  grading, retry pending, hủy điểm cũ và rubric/multiple evidence không mất.
  check_env/pip check qua; warning TestClient/HTTPX cũ vẫn còn.
- SQL đề xuất: `docs/schema-proposals/LOCAL-04-interview.sql`; hướng dẫn/mapping
  tại `docs/interview-postgres.md`. Thang grades.level chưa được đoán; score
  local giữ trong result đề xuất. accounts phải do Auth/Profile tạo trước.
- Workflow CI PostgreSQL/Chromium đã chuẩn bị local, chưa chạy GitHub. Binaries
  PostgreSQL test/cluster nằm trong data/private và không được đưa vào Git;
  server test được dừng sau kiểm chứng, không cài Windows service.

**Còn trước khi tuyên bố hoàn tất tích hợp nhóm:** review/apply schema trên DB
test theo thống nhất với Huy; cấu hình DB/Auth/AI thật; thử toàn luồng với nhóm;
chốt CV/Auth/thang điểm, teammate review và deploy. Không còn cần chờ người khác
viết xong frontend/Profile/history/feedback để kiểm thử code interview local.
Các phần cũ bên dưới là mốc lịch sử, không thay thế cập nhật LOCAL-04 này.

## Các checkpoint đã hoàn thành

| Commit | Việc đã xong | Kiểm chứng lúc commit |
| --- | --- | --- |
| `3d89d55` | Lưu mốc backend local ban đầu | 41 tests |
| `7d1a195` | Ghép frontend/AI/authen, thống nhất FastAPI entry point và cách phục vụ UI | 72 tests |
| `0ce43cd` | Nối provider AI của nhóm, rubric có trọng số, structured evidence và CV opt-in | 82 tests |
| `7f45b59` | Xác minh Supabase Bearer token bằng chữ ký/JWKS và claims | 107 tests |
| `638b09d` | Nối giao diện nhóm với tạo/lưu/tiếp tục/chấm/finalize/report | 111 tests, gồm 4 browser tests |
| `3829658` | Sửa lưu draft trước đăng xuất; thêm kiểm thử provider qua HTTP và browser retry | 113 tests, gồm 5 browser tests |
| `f641cb8` | Không log/return nguyên văn lỗi provider có thể chứa dữ liệu riêng tư | 43 tests AI/adapter; bộ cuối 114 tests |

Code chạy chung qua `python -m assistant --interview-api` từ root hoặc
`uvicorn app.main:app` từ `backend/`. Frontend nhóm ở `/app/`; prototype cũ giữ
ở `/` và `/prototype/`. Các đoạn sau ghi lại bản local ban đầu; trạng thái mới
và phần còn thiếu được cập nhật ở các mục bên dưới.

## Hiện có thể làm được trên máy

LOCAL-03 sau khi người dùng thử giao diện: thiếu đáp án hiển thị khung đỏ có
icon ngay cạnh ô nhập, viền invalid và focus vào textarea (`ca9d61d`). Rời buổi
hỏi Save & exit / Leave without saving / Keep answering; không tự lưu khi gõ
hoặc khi vừa mở hộp hỏi. Discard hoạt động từ snapshot đã xác nhận, không cần
request server; lỗi Save giữ hộp hỏi và draft. Native tab-close/reload chỉ có
hộp cảnh báo của browser. Kiểm chứng mới nhất **117 tests, 8 browser tests**.

- Demo giao diện không cần CDN Supabase, tài khoản thật hay API key; vẫn gắn nhãn demo.
- Tạo buổi lấy ID/câu hỏi từ server; Next submit câu hiện tại, Previous giữ draft
  trên máy. LOCAL-03 bỏ autosave khi gõ, hỏi Save & exit / Leave without saving /
  Keep answering trước khi rời. Save thành công mới thoát/đăng xuất; discard
  giữ các câu đã submit và bỏ phần chưa gửi, không cần gọi server.
- Gửi từng đáp án trả 202 rồi chấm nền; hiển thị số đã lưu/đã chấm/đang chờ.
- Finalize chờ đủ kết quả hợp lệ và hiển thị điểm, nhận xét, bằng chứng đã lưu;
  không dùng timer hay feedback mẫu giả làm kết quả provider. Nút Retry incomplete
  grading cho phép thử lại pending/draft/rejected khi provider hoặc server phục hồi.
- Adapter thực tế dùng code `ai.py`/`aiworker.py` của Phúc Duy, giữ rubric trọng số
  tổng 10 và yêu cầu model đưa evidence. Default vẫn mock; chế độ NVIDIA opt-in,
  CV không chuyển tới model trừ khi chủ động cho phép. Không bật web research/fetch.
- Adapter Auth theo nhánh hiện có: RS256/ES256, JWKS cache/timeout, chữ ký, issuer,
  audience, expiry, role và UUID; không lấy owner ID do frontend khai báo.
- Các lỗi tạo buổi/ghi dữ liệu giữ người dùng ở trang hiện tại và giữ draft cục bộ;
  evidence sai chặn báo cáo. PDF/URL JD chưa được import thì báo rõ thay vì giả xử lý.

## Kiểm chứng mới nhất

- **117 tests passed**, trong đó 8 tests chạy Chrome headless với server Uvicorn
  và DB temp thật. Chặn network ngoài loopback trong browser tests.
- Browser: toàn luồng tạo → lưu dở → tiếp tục → chấm → report → reload; tạo buổi
  gặp 503 không sinh session giả; draft chỉ lưu sau lựa chọn; không cho bỏ trống đáp án;
  từ chối evidence bịa rồi retry khi provider phục hồi; lưu draft trước đăng xuất.
- Thêm kiểm tra Cancel không ghi, Discard không request server và vẫn giữ câu
  đã submit, Save lỗi không rời trang; Back/Tab/Shift+Tab/Escape hoạt động trong modal.
- Provider adapter: gọi generator/grader thật của nhóm bằng completion giả qua
  HTTP, giữ rubric và metadata, ra report `used_fallback=false` đúng contract.
  Không có request tới NVIDIA/TinyFish thật.
- Token RS256/ES256 ký bằng key sinh trong test; token hết hạn/sai chữ ký/issuer/
  audience/kid/role đều bị từ chối; hai user bị tách dữ liệu; lỗi JWKS trả 503.
- `scripts/check_env.py`: qua; `pip check`: không có dependency hỏng.
- Script `demo_interview.py` chạy qua entry point CLI sau khi ghép đã thành công;
  cả entry point root và `backend/app/main.py` dùng cùng một ASGI app. Server
  kiểm tra đã dừng; DB thử nằm trong `data/private/`, không được đưa vào commit.
- Kiểm tra tên file private và các mẫu credential phổ biến trước khi commit
  không phát hiện credential thật trong source; không in giá trị secret.
- Một warning deprecation từ Starlette TestClient dùng HTTPX; không làm test fail.
- Kiểm tra cấu hình chỉ in boolean: **chưa có AI key thật, Supabase runtime URL
  hoặc publishable key** trong cấu hình ứng dụng. PAT MCP không dùng làm credential
  cho app. Chưa xác minh đăng nhập thật hoặc chất lượng model thật.
- `eval/run.py` cũ vẫn không phải bộ đánh giá interview; không dùng 0% của bộ
  câu hỏi lab cũ để kết luận chất lượng phần tích hợp này.

## Đã xong trong bản local

- Backend riêng bằng FastAPI/Uvicorn, Pydantic kiểm tra input/output; Swagger `/docs`.
- Tạo buổi: snapshot Job Profile + CV text, lưu 3 câu hỏi kèm tiêu chí/nhãn nguồn,
  trả câu đầu tiên cho frontend. Nguồn hiện là câu mở từ mock.
- Lưu bản nháp/vị trí, lưu dở, đọc lại để tiếp tục; giữ dữ liệu qua lần khởi động lại.
- Nhận từng đáp án, lưu trạng thái chờ trước khi trả HTTP 202; gọi AI ở BackgroundTasks.
- Kiểm tra mọi trích dẫn của AI có nguyên văn trong đáp án. Từ chối bằng chứng bịa
  hoặc rỗng; kết quả bị từ chối không được đưa vào báo cáo.
- API theo dõi số đã trả lời, đã chấm, đang chờ và bị từ chối.
- Finalize khi đủ 3 câu đã chấm hợp lệ: lưu điểm trung bình, nhãn, nhận xét và bằng
  chứng; gửi lại finalize trả báo cáo cũ. Buổi finalized không sửa qua các API này.
- Có adapter AI mẫu và fallback cho lỗi provider/output sai; luôn đánh dấu mock.
- Lưu SQLite qua SQLAlchemy, nằm trong `data/private/` và được Git bỏ qua.
- Kiểm tra quyền sở hữu theo user ID do backend xác định; chống ghi đè do revision
  cũ, hai tác vụ chấm cùng lúc và tác vụ cũ của đáp án đã sửa.
- Cookie demo local có kiểm tra loopback/Origin; có điểm nối session cookie thật.
- Hướng dẫn tiếng Việt, contract JSON và script thử toàn bộ luồng bằng HTTP.

## Đã kiểm chứng

- `python -m pytest -q`: **41 passed**, gồm 5 smoke tests cũ và 36 tests mới.
- Test response 202 được gửi ra trong khi provider chấm vẫn đang bị giữ chờ.
- Test mở lại DB/app, lấy lại draft và đăng nhập demo lại sau restart.
- Test hai user, revision cũ, chấm đồng thời, output AI hỏng/timeout/NaN, quote bịa,
  bằng chứng tiếng Việt và adapter trả nguồn tham chiếu/kết quả thật theo contract.
- Chạy Uvicorn trên `127.0.0.1:8765` và `scripts/demo_interview.py`: toàn luồng qua
  HTTP thành công, gồm finalize retry. Server dùng để kiểm tra đã được dừng.
- `scripts/check_env.py`: tất cả kiểm tra qua; `pip check`: không xung đột dependency.
- CLI `hi`, office lookup, API legacy và static UI vẫn hoạt động.
- Môi trường kiểm tra: Python 3.14.7, FastAPI 0.162.2, Uvicorn 0.54.0,
  Pydantic 2.14.3, SQLAlchemy 2.0.57, pytest 9.2.0, HTTPX 0.28.1.
  Chưa chạy ma trận nhiều phiên bản Python.
- Có 1 deprecation warning từ Starlette TestClient dùng HTTPX; tests vẫn qua.
- `eval/run.py` cũ trả **Accuracy: 0.00%**. Rules và các file eval không thay đổi so
  với HEAD; bộ expected hiện hỏi các chức năng không khớp rules tra cứu văn phòng.
  Đây chưa phải bộ đo chất lượng Yourin, cần xây riêng khi có AI thật.

## Còn cần làm trước khi gọi là tích hợp hoàn chỉnh

**Cập nhật sau khi Trương Bảo Anh hỏi điểm ghép:** đã đọc lại Supabase và public
hiện có **9 bảng**, không còn là snapshot rỗng. Columns/FK và các điểm chưa
khớp CV/report/feedback được ghi tại [backend-handoff.md](backend-handoff.md).
Chưa sửa cloud hoặc ánh xạ repository runtime sang các bảng mới.

Cập nhật khảo sát Supabase ngày 08/11/2026: **đã kết nối MCP chỉ đọc thành công**
vào project `ct-team06` (`qutiahnegjzgbxjopsqe`). Server xác nhận
`transaction_read_only=on`, role `supabase_read_only_user`. `list_tables` và
catalog PostgreSQL đều cho thấy **public có 0 bảng / 0 view**; chưa thấy schema
ứng dụng tùy chỉnh. Chỉ đọc metadata, không đọc dữ liệu tài khoản hoặc sửa DB.
Do đó hiện chưa có bảng interview thật để ánh xạ adapter. Kết quả này không cho
biết bạn Database đã có bản thiết kế/script chưa; cần kiểm tra lại lúc ghép.

1. **Chạy dịch vụ AI thật:** adapter, rubric/evidence và timeout đã có; cần key
   local hợp lệ, xác minh model và đánh giá chất lượng. Mock chấm theo số từ,
   không dùng để kết luận năng lực. Ngân hàng câu hỏi/nguồn thực tế chưa ghép.
2. **Database nhóm:** ánh xạ repository sang schema PostgreSQL đã thống nhất,
   migrations và quyền truy cập. Chưa nối Supabase; không tạo bảng vào DB chung.
3. **Auth deployment:** adapter token theo nhánh Supabase đã có; cần public config
   của project để thử login thật, đối chiếu lại thiết kế cookie cũ với nhóm.
   Legacy HS256 và kiểm tra thu hồi session tức thì chưa hỗ trợ. HTTPS/CORS và
   tài khoản thử trên môi trường nhóm chưa được kiểm chứng.
4. **Các phần frontend/backend ngoài phạm vi:** luồng interview đã nối; API danh
   sách toàn bộ lịch sử, Profile/CV, rename/delete, report endpoint riêng và khảo
   sát vẫn chờ người phụ trách. Storage hiện dùng ID cache trên browser; không
   khẳng định khôi phục toàn bộ lịch sử sau khi xóa browser storage.
5. **Chấm bền vững khi server lỗi:** hiện có thể gửi lại đáp án pending để retry;
   chưa có hàng đợi tự khôi phục tác vụ bị mất khi tiến trình dừng.
6. **Ghép và review:** đối chiếu API/schema với nhóm, tạo/liên kết GitHub issue thật,
   PR và teammate review, kiểm thử tích hợp trên Render rồi mới merge/deploy.

7. **Chính sách CV:** draft frontend ghi CV không rời máy, trong khi code AI nhận
   CV. Giữ mặc định không forward CV tới provider cho đến khi nhóm thống nhất.

Các mục Profile/CV API riêng, lịch sử, API report riêng và khảo sát vẫn thuộc phần
Backend còn lại theo cách chia người dùng đã chốt. PDF parsing/upload, tải URL JD
và ngân hàng câu hỏi thật chưa được làm trong phạm vi local này.

## Xem và chạy thử

- [Hướng dẫn khởi chạy + API contract](interview-api.md)
- [Backlog local và acceptance criteria](backlog/LOCAL-01-interview-lifecycle.md)
- `scripts/demo_interview.py`: script kiểm tra HTTP, tự dùng CV/đáp án giả.

Không có khóa API thật, tài liệu Word hoặc dữ liệu cá nhân nào được thêm vào code.
