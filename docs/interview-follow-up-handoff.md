# Bàn giao câu hỏi tiếp nối tự động có chọn lọc

Triển khai trên nhánh `feat/interview-follow-up`, bắt đầu từ main `2e1ad39`.

Sau khi nộp câu chính, ứng dụng tự kiểm tra có cần hỏi sâu không. Nếu có, câu phụ hiện ngay tại câu chính đó và người dùng phải trả lời trước khi đi tiếp. Nếu đáp án đã đủ hoặc AI lỗi, ứng dụng chuyển tiếp. Trong lúc đợi chọn câu, người dùng có thể chọn tiếp tục mà không chờ. Giới hạn hai câu phụ được chọn cho cả buổi và một câu phụ cho mỗi câu chính, kể cả sau khi sửa đáp án. Báo cáo đặt từng câu phụ dưới đúng câu chính. Điểm chính theo cách chấm hiện có, câu phụ chưa được cộng vào điểm.

## Cách chọn câu

NVIDIA đọc toàn bộ đáp án, tiêu chí chấm và câu phụ đã hỏi. Đề xuất phải có chỉ số tiêu chí hợp lệ, một trong ba mã thiếu thông tin, đoạn trích nguyên văn, nội dung còn thiếu và câu hỏi. Ba loại thiếu thông tin là hành động cá nhân, lý do lựa chọn và cách xác nhận kết quả.

Backend kiểm tra kiểu dữ liệu, độ dài và đoạn trích. Chỉ với đề xuất hợp lệ, lượt gọi AI thứ hai kiểm tra riêng xem khoảng thiếu có liên quan tiêu chí không, đáp án đã giải thích ở đoạn khác chưa và câu hỏi có bổ sung thông tin hữu ích không. Kết quả không đạt hoặc sai định dạng sẽ bỏ qua câu hỏi phụ.

## Lưu trữ và các trường hợp được xử lý

Trạng thái bổ sung nằm trong danh sách `follow_ups` của JSON buổi phỏng vấn, gắn với chỉ số câu chính và mã lần nộp. Báo cáo có `report.follow_ups`. Trường `follow_up` vẫn cung cấp phần tử mới nhất để hỗ trợ dữ liệu bản trước. SQL LOCAL-09 lưu nguyên JSON nên dùng lại được cấu trúc hiện tại. Workflow backend chạy thêm các bài RPC trên PostgreSQL localhost.

Câu phụ được dành chỗ trong cùng thao tác nộp đáp án chính. Gửi trùng tái sử dụng cùng quyết định. Khi sửa hoặc nộp lại đáp án gốc, quyết định cũ được vô hiệu hóa. Kết quả AI về muộn phải khớp mã yêu cầu, lần nộp và trạng thái đang chờ. Khi hai tác vụ cùng hoàn thành, kiểm tra lại hạn mức trước khi ghi. Câu đã từng được chọn vẫn tính vào hạn mức khi người dùng sửa đáp án. Nếu tác vụ bị ngắt, yêu cầu hết hạn sau 15 phút và có thể thử lại.

Bản nháp câu phụ nằm trong sessionStorage theo buổi và mã yêu cầu, nên mỗi tab giữ bản nháp riêng. Khi người dùng chọn lưu rồi thoát hoặc đăng xuất, ứng dụng chờ lưu cả lời đáp phụ và tiến độ chính. Chỉ hiện nội dung AI bằng text.

## Kết quả kiểm tra cục bộ

Lượt thử lớn hơn đã phát hiện hỏi thừa và chọn nhầm tiêu chí. Xem [báo cáo 132 trường hợp cùng sáu lượt chẩn đoán](follow-up-large-test-2026-11-28.md) trước khi dùng kết quả bộ 24 mẫu bên dưới để đánh giá chất lượng.

- Bộ mặc định 291 bài đã qua. Đã bổ sung và chạy qua thêm kiểm thử hạn mức khi sửa lại một câu đã được chọn. Có một cảnh báo TestClient đang dùng API cũ.
- Bốn bài Chrome qua, gồm tự hỏi tại câu 1 và giữ bản nháp sau F5, tự đi tiếp khi lỗi AI, lưu trước khi đăng xuất, và chọn câu 2 để hỏi sâu rồi thử lưu lại sau lỗi mạng.
- NVIDIA thật đã chạy 24 đáp án giả có kỳ vọng trước, gồm 12 bản thiếu thông tin và 12 bản đã giải thích đủ. Lượt này không hỏi thừa, không bỏ sót, không chọn sai loại thiếu thông tin và không gặp lỗi nhà cung cấp. Trung bình 1,29 giây cho bước chọn và kiểm tra. Bộ mẫu này cần được mở rộng bằng đáp án đa dạng hơn khi nhóm dùng thử.
- Chạy lại đánh giá bằng `python eval/follow_up_eval.py`, dùng các mẫu trong `eval/follow_up_cases.json` và cấu hình NVIDIA trên máy.
- CI của luồng tự chọn đã qua bộ mặc định và chín bài RPC trên PostgreSQL thử. Kiểm thử ghi lên Supabase chung và website triển khai cần nhóm chạy sau khi review. [Kết quả CI của commit 75730c2](https://github.com/Mcrvc/assistant-team06/actions/runs/46131469285)

Chạy bộ mặc định bằng `python -m pytest`. Chạy Chrome bằng `python -m pytest -m slow tests/test_follow_up_browser.py`, với Playwright và Chrome đã cài. Chạy RPC bằng `python -m pytest -m slow tests/test_supabase_interview_storage.py` khi có `INTERVIEW_TEST_POSTGRES_URL` trỏ tới localhost, tên database bắt đầu bằng `yourin_interview_test`.

## Trả lời Nhân về CV

Đã thử bằng CV hoàn toàn giả với chế độ gửi CV được bật riêng trong tiến trình kiểm tra. NVIDIA tạo bảy câu hỏi, gồm hai câu dùng đúng chi tiết trong CV. Một câu nhắc “Built a FastAPI reservation service for 200 students” và hỏi cách thiết kế dịch vụ, lý do dùng Redis. Câu còn lại nhắc “reduced search latency from 600 ms to 180 ms” và hỏi cách đo cùng phạm vi bài test.

Code của Duy đã hỗ trợ câu hỏi dựa trên CV, có kiểm tra trích dẫn nguyên văn cho câu ở phần CV. Tuy nhiên, `.env` trên máy ở lượt thử đang tắt gửi CV. Backend chỉ gửi CV khi `INTERVIEW_ALLOW_CV_TO_AI=1`. Cần kiểm tra cờ này trên môi trường nhóm đang demo để biết CV có thực sự được dùng ở đó.

## Lưu ý cho nhóm review

Đối chiếu các sửa lỗi giao diện trên nhánh playtest trước khi ghép. Tính năng này đã bổ sung chờ nộp thành công trước khi Next và chờ lưu trước khi thoát, nhưng các tình huống mất bản nháp chính qua hai tab hoặc F5 vẫn cần bản sửa playtest và lượt kiểm tra riêng. Mã đăng nhập, module AI chung và SQL hiện tại được dùng qua các điểm nối có sẵn.
