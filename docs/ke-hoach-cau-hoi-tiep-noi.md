# Kế hoạch triển khai câu hỏi tiếp nối cho Yourin

Kế hoạch ban đầu bên dưới đã được mở rộng theo quyết định hỏi tiếp tự động có chọn lọc. Thiết kế và kiểm thử hiện tại nằm tại [tài liệu bàn giao](interview-follow-up-handoff.md).

**Mục tiêu.** Sau khi nộp một câu trả lời chính, ứng viên có thể chọn luyện thêm. Yourin hỏi một câu cụ thể về điều ứng viên vừa nói, lưu lời đáp và cho xem lại trong báo cáo. Bản đầu giới hạn một câu phụ cho mỗi buổi. Điểm, tiến độ và số câu chính vẫn được tính theo bộ câu hỏi ban đầu.

**Ví dụ nghiệm thu.** Với câu trả lời “Em tối ưu truy vấn và trang tải nhanh hơn 40%”, câu hỏi phụ có thể là “Em đo mức cải thiện 40% bằng cách nào?”. Màn hình hiển thị cả đoạn trích “trang tải nhanh hơn 40%”. Nếu ứng viên kể về một bất đồng trong nhóm, câu hỏi phụ phải bám vào chi tiết của câu trả lời mới.

## 1. Điểm bắt đầu trong repo

Kế hoạch dựa trên `origin/main` tại `2e1ad39`. Khi bắt đầu, lấy thông tin mới từ Git, đọc `AGENTS.md` và kiểm tra các thay đổi kể từ mốc này. Tạo nhánh tính năng riêng từ bản main nhóm đang dùng. Ghi một commit sau mỗi phần đã kiểm tra.

| Thành phần hiện tại | Nơi cần đọc | Tác động đến thiết kế |
|---|---|---|
| Tạo buổi, nộp đáp án, chấm nền, kết thúc | `src/assistant/interviews.py`, `web.py` | Danh sách câu được lập khi tạo buổi. Nộp đáp án đã có cơ chế chống lưu trùng và trả về vị trí kế tiếp. Giữ luồng này, thêm thao tác luyện riêng. |
| Gọi NVIDIA và kiểm tra trích dẫn | `src/assistant/ai.py`, `aiworker.py`, `interview_ai.py` | Có thể dùng hàm `complete()` và cách đối chiếu trích dẫn hiện tại. Phối hợp với Duy nếu thay đổi module AI chung. |
| Kiểu dữ liệu và lưu trữ | `interview_schemas.py`, `interview_store.py`, `interview_supabase.py` trong `src/assistant/` | Câu chính và câu trả lời đang ghép theo thứ tự. Câu phụ cần trường riêng. SQLite và hàm Supabase `yourin_interview_v1` đều phải đọc lại được trường này. |
| Giao diện làm bài và báo cáo | `ui/interview.html`, `ui/js/app.js`, `ui/report.html` | Kiểm tra nơi nộp bài, phục hồi bản nháp, hiển thị báo cáo. Đối chiếu với nhóm giao diện về các sửa lỗi trên `fix/playtest-2026-11-18`, nhất là chuyển câu trước khi lưu xong. |

## 2. Luồng người dùng đề xuất

1. Ứng viên nộp câu chính đầu tiên. Sau khi máy chủ xác nhận đã nhận đáp án, giao diện sang câu 2 như hiện tại và hiện lựa chọn **Luyện thêm về câu vừa trả lời**. Vị trí cố định này giúp bản đầu dễ dùng và dễ kiểm tra. Chỉ hiện lựa chọn khi buổi có ít nhất hai câu chính.
2. Người dùng có thể tiếp tục làm câu 2 ngay. Chỉ khi họ chọn luyện thêm, ứng dụng mới gọi NVIDIA. Khung luyện thêm hiển thị bên cạnh hoặc phía trên câu 2, ghi rõ nó thuộc câu 1. Giữ nguyên nội dung câu 2 người dùng đã gõ.
3. Khi có kết quả, khung hiển thị đoạn trích, câu hỏi phụ, ô trả lời và hai nút **Lưu câu trả lời** / **Bỏ qua**. Nếu AI chậm, người dùng vẫn có thể bỏ qua hoặc làm tiếp. Kết quả đến muộn không được đổi trang hay lấy mất con trỏ.
4. Khi mở lại buổi, hiển thị câu phụ đã tạo cùng lời đáp đã lưu. Trên báo cáo, hiển thị cặp hỏi–đáp dưới câu 1 nếu người dùng đã trả lời. Khi đó ghi rõ đây là phần luyện thêm, tránh khiến người đọc tưởng lời đáp phụ cũng được chấm.

## 3. Dữ liệu và API cần thống nhất trước khi viết giao diện

Thêm trường tùy chọn `follow_up` vào trạng thái buổi. Giá trị mặc định là `null` để buổi cũ mở được. Một buổi chỉ có một trường này. Các tên sau là đề xuất cho bản đầu.

| Dữ liệu | Ý nghĩa |
|---|---|
| `parent_index`, `parent_grading_id` | Câu chính và đúng lần nộp đã dùng để sinh câu phụ. Dùng mã lần nộp có sẵn để nhận biết đáp án đã được sửa hoặc nộp lại. |
| `request_id`, `started_at` | Nhận biết lần tạo đang chạy và phát hiện tác vụ bị ngắt khi khởi động lại máy chủ. |
| `status` | `generating`, `ready`, `answered`, `skipped` hoặc `unavailable`. |
| `quote`, `question`, `answer` | Đoạn trích gốc, câu hỏi phụ và lời đáp. Bản đầu giới hạn lần lượt 300, 500 và 10.000 ký tự. |

Dùng xác thực và kiểm tra chủ sở hữu như các route phỏng vấn hiện có. Trả về trạng thái buổi theo cùng kiểu với các thao tác lưu hiện tại.

| Thao tác đề xuất | Hành vi |
|---|---|
| `POST /api/interviews/{id}/follow-up` | Nhận `revision` và `parent_grading_id`. Kiểm tra đúng lần nộp câu 1 và buổi còn mở. Lưu trạng thái `generating` trước rồi mới giao việc gọi AI cho tác vụ nền. Trả `202` khi đang tạo hoặc `200` với câu đã có. Hai lần bấm cùng ý định chỉ tạo một tác vụ. |
| `GET /api/interviews/{id}` | Bổ sung `follow_up` vào phản hồi hiện có. Giao diện đọc lại khi đang đợi và khi mở lại buổi. Dừng hỏi máy chủ khi phần này đã có kết quả hoặc người dùng rời trang. |
| `POST /api/interviews/{id}/follow-up/answer` | Nhận `revision`, `request_id` và `text`. Chỉ nhận đáp án có nội dung cho câu đang ở trạng thái `ready`. Gửi lại cùng nội dung sau khi mất phản hồi phải trả về kết quả đã lưu. |
| `POST /api/interviews/{id}/follow-up/skip` | Nhận `revision` và `request_id`. Cho bỏ qua cả lúc đang chờ AI và sau khi câu phụ đã hiện. Bỏ qua nhiều lần cho cùng câu phải cho cùng kết quả. |

**Các trường hợp dễ mất dữ liệu.** Tận dụng cơ chế phiên bản đang có trong `InterviewService`. Thao tác của người dùng cập nhật `revision`. Tác vụ nền cập nhật phiên bản ghi nội bộ và chỉ ghi kết quả nếu `request_id`, lần nộp câu chính và trạng thái vẫn khớp. Nếu người dùng đổi đáp án chính, xóa liên kết câu phụ cũ trong cùng lần lưu. Áp dụng cả cho lưu tiến độ khi văn bản thay đổi và cho nộp lại. Nếu buổi đã kết thúc, giữ nguyên báo cáo khi tác vụ cũ trả lời. Khi hai tab gửi hai chỉnh sửa khác nhau, trả lỗi xung đột và giữ bản nháp để người dùng tự quyết định.

**Lỗi nhà cung cấp.** Nếu AI hết thời gian, trả sai định dạng hoặc đưa trích dẫn sai, chuyển sang `unavailable` và cho tiếp tục câu chính. Nếu máy chủ khởi động lại giữa chừng, dựa vào `started_at` và giới hạn thời gian gọi thực tế, kể cả các lần thử lại, để nhận ra tác vụ hết hạn. Cho người dùng chủ động thử lại với `request_id` mới. Hoàn thành buổi luôn được phép khi chỉ còn câu phụ đang chờ.

## 4. Thứ tự triển khai và kiểm tra từng bước

1. **Lưu được và đọc lại được.** Bổ sung kiểu dữ liệu, giá trị mặc định cho buổi cũ và phần dữ liệu dành cho báo cáo. Viết kiểm thử tạo → lưu → mở lại bằng SQLite. Đọc `docs/schema-proposals/LOCAL-09-supabase-api.sql`, chạy bộ kiểm thử RPC trên PostgreSQL localhost để xác nhận JSON của buổi giữ đủ trường sau mỗi lần ghi. Nếu cần thay SQL, chuẩn bị thay đổi để Huy review trước khi áp dụng vào database chung.
2. **Tạo đúng một câu hỏi từ đúng lời người dùng.** Thêm hàm nhận câu hỏi gốc và đáp án đã nộp, trả về `quote` và `question`. Dùng phía server để gọi NVIDIA. Kiểm tra hai trường là chuỗi có nội dung, đúng giới hạn và đoạn trích xuất hiện nguyên văn trong đáp án. Kết quả sai đi theo nhánh `unavailable`. Test bằng đáp án mẫu, gồm hai câu trả lời khác chủ đề, trích dẫn bịa, phản hồi rỗng và lỗi mạng.
3. **Nối API và tác vụ nền.** Cài các thao tác ở mục 3. Test trường hợp bấm hai lần, bỏ qua khi đang tạo, sửa câu chính khi AI đang chạy, mất phản hồi sau khi lưu, hai tab cùng sửa và kết thúc buổi trước khi AI trả kết quả. Dùng AI giả có thể chủ động giữ hoặc thả phản hồi để test ổn định.
4. **Nối màn hình phỏng vấn và báo cáo.** Tái sử dụng hàng đợi ghi và cách lưu bản nháp đang có trên bản UI được nhóm duyệt. Bắt buộc đợi nộp câu chính thành công mới hiện lựa chọn luyện thêm. Hiển thị lời người dùng và văn bản AI bằng text an toàn. Khi rời trang với lời đáp phụ đang gõ, dùng chung lựa chọn lưu/ở lại. Nếu người dùng chọn lưu rồi thoát, lưu lời đáp phụ thành công trước khi rời. Khi đang gõ dở, giữ bản nháp theo buổi, tab và `request_id` để F5 khôi phục đúng nội dung.
5. **Chạy lại như người dùng.** Chạy bộ mặc định bằng `python -m pytest`. Chạy thêm bài Chrome trên localhost với SQLite tạm, và bộ RPC trên PostgreSQL thử. Sau đó dùng một buổi mẫu gọi NVIDIA thật, ghi thời gian chờ, câu gốc, đáp án, đoạn trích và câu phụ vào kết quả thử. So sánh tổng số câu, tiến độ và điểm báo cáo giữa hai buổi có cùng kết quả chấm chính, một buổi dùng câu phụ và một buổi bỏ qua.

## 5. Điều kiện bàn giao

- [ ] Hai đáp án khác nội dung cho cùng câu chính nhận được câu hỏi phụ phù hợp với từng đáp án. Đoạn trích khớp nguyên văn.
- [ ] Bấm tạo hai lần hoặc F5 lúc đang đợi vẫn chỉ sinh một câu phụ cho lần nộp đó.
- [ ] Lưu lời đáp phụ, thoát, mở lại và xem báo cáo đều thấy đúng nội dung dưới đúng câu chính.
- [ ] Bỏ qua, lỗi NVIDIA hoặc tác vụ trả kết quả muộn đều cho phép tiếp tục buổi tập. Bản nháp câu chính đang gõ được giữ nguyên.
- [ ] Buổi tạo trước bản cập nhật vẫn mở và kết thúc được. Số câu chính và cách tính điểm giữ đúng kết quả cũ.
- [ ] Bàn giao bằng nhánh riêng, kèm commit đã kiểm tra, kết quả test và phần còn cần nhóm thử trên môi trường triển khai. Việc ghép nhánh và triển khai do nhóm quyết định.
