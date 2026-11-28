# Bàn giao câu hỏi tiếp nối

Triển khai trên nhánh `feat/interview-follow-up`, bắt đầu từ main `2e1ad39`.

Sau khi nộp câu 1 và sang câu 2, người dùng có thể chọn **Practise my first answer**. Khung luyện thêm hiện đoạn trích và một câu hỏi bám theo câu trả lời vừa nộp. Có thể lưu lời đáp hoặc bỏ qua. Báo cáo đặt phần luyện thêm dưới câu 1 và ghi rõ phần này được loại khỏi điểm chung.

## Lưu trữ và các trường hợp được xử lý

Trạng thái bổ sung nằm trong `follow_up` của JSON buổi phỏng vấn. Câu phụ đã trả lời cũng được chụp vào `report.follow_up`. SQL LOCAL-09 lưu nguyên JSON nên dùng lại được cấu trúc hiện tại. SQLite đã kiểm thử đọc lại. Bài kiểm thử RPC mới trong `tests/test_supabase_interview_storage.py` xác nhận cả trạng thái và báo cáo qua hàm SQL trên PostgreSQL thử. Workflow backend chạy thêm các bài RPC bằng dịch vụ localhost của CI.

Gọi tạo trùng tái sử dụng cùng câu hỏi. Khi sửa hoặc nộp lại đáp án gốc, phần luyện thêm cũ được xóa. Kết quả AI về sau lúc bỏ qua, sửa đáp án hoặc kết thúc buổi sẽ bị bỏ qua. Nếu tác vụ bị ngắt, yêu cầu đang tạo hết hạn sau 15 phút và có thể thử lại. Lỗi AI cho trạng thái unavailable, người dùng tiếp tục được buổi tập.

Bản nháp câu phụ nằm trong sessionStorage theo buổi và mã yêu cầu, nên mỗi tab giữ bản nháp riêng. Khi người dùng chọn lưu rồi thoát hoặc đăng xuất, ứng dụng chờ lưu cả lời đáp phụ và tiến độ chính. Chỉ hiện nội dung AI bằng text.

## Kết quả kiểm tra cục bộ

- 280 bài kiểm thử mặc định qua. Có một cảnh báo TestClient đang dùng API cũ.
- Ba bài Chrome qua, gồm tạo câu phụ → F5 giữ bản nháp → lưu → hoàn thành → xem lại trong báo cáo, lỗi AI giữ bản nháp chính, và đăng xuất sau khi lưu đáp án phụ.
- NVIDIA thật với đáp án giả về cải thiện tốc độ 40% đã hỏi cách đo mức cải thiện. Với đáp án về bất đồng nhóm, AI hỏi tiêu chí dùng để so sánh hai đề xuất. Mỗi lượt mất khoảng một giây, cả hai đoạn trích khớp nguyên văn.
- Máy kiểm tra chưa có dịch vụ PostgreSQL localhost, nên bài RPC bổ sung cần xác nhận qua CI. Kiểm thử ghi lên Supabase chung và website triển khai cần nhóm chạy sau khi review.

Chạy bộ mặc định bằng `python -m pytest`. Chạy Chrome bằng `python -m pytest -m slow tests/test_follow_up_browser.py`, với Playwright và Chrome đã cài. Chạy RPC bằng `python -m pytest -m slow tests/test_supabase_interview_storage.py` khi có `INTERVIEW_TEST_POSTGRES_URL` trỏ tới localhost, tên database bắt đầu bằng `yourin_interview_test`.

## Trả lời Nhân về CV

Đã thử bằng CV hoàn toàn giả với chế độ gửi CV được bật riêng trong tiến trình kiểm tra. NVIDIA tạo bảy câu hỏi, gồm hai câu dùng đúng chi tiết trong CV. Một câu nhắc “Built a FastAPI reservation service for 200 students” và hỏi cách thiết kế dịch vụ, lý do dùng Redis. Câu còn lại nhắc “reduced search latency from 600 ms to 180 ms” và hỏi cách đo cùng phạm vi bài test.

Code của Duy đã hỗ trợ câu hỏi dựa trên CV, có kiểm tra trích dẫn nguyên văn cho câu ở phần CV. Tuy nhiên, `.env` trên máy ở lượt thử đang tắt gửi CV. Backend chỉ gửi CV khi `INTERVIEW_ALLOW_CV_TO_AI=1`. Cần kiểm tra cờ này trên môi trường nhóm đang demo để biết CV có thực sự được dùng ở đó.

## Lưu ý cho nhóm review

Đối chiếu các sửa lỗi giao diện trên nhánh playtest trước khi ghép. Tính năng này đã bổ sung chờ nộp thành công trước khi Next và chờ lưu trước khi thoát, nhưng các tình huống mất bản nháp chính qua hai tab hoặc F5 vẫn cần bản sửa playtest và lượt kiểm tra riêng. Mã đăng nhập, module AI chung và SQL hiện tại được dùng qua các điểm nối có sẵn.
