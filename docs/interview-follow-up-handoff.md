# Bàn giao câu hỏi tiếp nối tự động có chọn lọc

Triển khai trên nhánh `feat/interview-follow-up`, bắt đầu từ main `2e1ad39`.

Sau khi nộp câu chính, ứng dụng tự kiểm tra có cần hỏi sâu không. Nếu có, câu phụ dùng khung Yori, ô trả lời, microphone và Replay như câu chính. Người dùng trả lời trước khi đi tiếp. Nếu đáp án đã đủ hoặc AI lỗi, ứng dụng chuyển tiếp. Chờ quá 15 giây thì bỏ lượt chọn đang chạy; kết quả đến sau không được chen vào câu mới. Giới hạn hai câu phụ được chọn cho cả buổi và một câu phụ cho mỗi câu chính, kể cả sau khi sửa đáp án.

**Cập nhật 29/11:** Câu phụ đã được chấm chung với đáp án gốc theo tiêu chí của câu gốc. Báo cáo gom cả hai phần vào cùng một thẻ và tính một điểm cho câu gốc. Các sửa lỗi giao diện của nhánh playtest đã được đưa sang đây và kiểm thử lại. Nhóm có thể review và merge nhánh follow-up này; không cần ghép nhánh playtest riêng để lấy những sửa lỗi được liệt kê trong [bàn giao mới](follow-up-ui-and-grading-2026-11-29.md).

## Cách chọn câu

Lượt NVIDIA đầu tiên đánh dấu từng tiêu chí là đã có thông tin, còn thiếu, chưa chắc hoặc không áp dụng, kèm trích dẫn làm căn cứ. Backend chỉ cho xét những khoảng thiếu rõ ràng. Ba loại thông tin được hỗ trợ là hành động cá nhân, lý do lựa chọn và cách xác nhận kết quả.

Lượt thứ hai đọc lại độc lập toàn bộ đáp án và tiêu chí rồi viết câu hỏi nếu cũng xác nhận còn thiếu. Hai lượt dùng JSON Schema có ràng buộc và backend kiểm tra lại dữ liệu. Trích dẫn từ câu phụ trước có thể chứng minh thông tin đã đủ, còn đoạn làm căn cứ hỏi mới phải nằm trong đáp án hiện tại.

## Lưu trữ và các trường hợp được xử lý

Trạng thái bổ sung nằm trong danh sách `follow_ups` của JSON buổi phỏng vấn, gắn với chỉ số câu chính và mã lần nộp. Báo cáo có `report.follow_ups`. Trường `follow_up` vẫn cung cấp phần tử mới nhất để hỗ trợ dữ liệu bản trước. SQL LOCAL-09 lưu nguyên JSON nên dùng lại được cấu trúc hiện tại. Workflow backend chạy thêm các bài RPC trên PostgreSQL localhost.

Câu phụ được dành chỗ trong cùng thao tác nộp đáp án chính. Gửi trùng tái sử dụng cùng quyết định. Khi sửa hoặc nộp lại đáp án gốc, quyết định cũ được vô hiệu hóa. Kết quả AI về muộn phải khớp mã yêu cầu, lần nộp và trạng thái đang chờ. Khi hai tác vụ cùng hoàn thành, kiểm tra lại hạn mức trước khi ghi. Câu đã từng được chọn vẫn tính vào hạn mức khi người dùng sửa đáp án. Nếu tác vụ bị ngắt, yêu cầu hết hạn sau 15 phút và có thể thử lại.

Bản nháp câu phụ nằm trong sessionStorage theo buổi và mã yêu cầu, nên mỗi tab giữ bản nháp riêng. Khi người dùng chọn lưu rồi thoát hoặc đăng xuất, ứng dụng chờ lưu cả lời đáp phụ và tiến độ chính. Chỉ hiện nội dung AI bằng text.

## Kết quả kiểm tra cục bộ

Bản sửa cách chọn và phép đo trước/sau trên 204 mẫu nằm tại [báo cáo sửa lỗi và stress test](follow-up-coverage-fix-stress-test.md). Báo cáo ghi cả các lỗi còn lại và phép kiểm tra sáu mẫu sau bản vá nguồn trích dẫn.

Lượt thử lớn hơn đã phát hiện hỏi thừa và chọn nhầm tiêu chí. Xem [báo cáo 132 trường hợp cùng sáu lượt chẩn đoán](follow-up-large-test-2026-11-28.md) trước khi dùng kết quả bộ 24 mẫu bên dưới để đánh giá chất lượng.

- Bộ mặc định hiện có 310 bài đã qua, gồm chấm chung, nộp lặp, thử chấm lại, kết quả chấm về muộn và sửa đáp án khi đang chấm. Có một cảnh báo TestClient đang dùng API cũ.
- 17 bài Chrome đã qua, gồm chín bài từ playtest, một bài chặn nhập khi trang tạo buổi chưa khởi tạo xong và bảy bài cho câu phụ: dùng chung Yori/Replay/microphone, F5, báo cáo, đăng xuất, lỗi lưu, AI chậm, mất phản hồi sau khi đã lưu, và sửa câu gốc ở tab khác.
- NVIDIA thật đã chấm một cặp đáp án giả cho bản chấm chung: điểm trước 5,5/10, sau bổ sung 8,5/10; không dùng điểm mẫu và toàn bộ trích dẫn khớp nội dung. Đây là kiểm tra đường chạy, không phải phép đo độ chính xác tổng quát.
- NVIDIA thật đã chạy 24 đáp án giả có kỳ vọng trước, gồm 12 bản thiếu thông tin và 12 bản đã giải thích đủ. Lượt này không hỏi thừa, không bỏ sót, không chọn sai loại thiếu thông tin và không gặp lỗi nhà cung cấp. Trung bình 1,29 giây cho bước chọn và kiểm tra. Bộ mẫu này cần được mở rộng bằng đáp án đa dạng hơn khi nhóm dùng thử.
- Chạy lại đánh giá bằng `python eval/follow_up_eval.py`, dùng các mẫu trong `eval/follow_up_cases.json` và cấu hình NVIDIA trên máy.
- CI của luồng tự chọn đã qua bộ mặc định và chín bài RPC trên PostgreSQL thử. Kiểm thử ghi lên Supabase chung và website triển khai cần nhóm chạy sau khi review. [Kết quả CI của commit 75730c2](https://github.com/Mcrvc/assistant-team06/actions/runs/46131469285)

Chạy bộ mặc định bằng `python -m pytest`. Chạy Chrome bằng `python -m pytest -m slow tests/test_follow_up_browser.py`, với Playwright và Chrome đã cài. Chạy RPC bằng `python -m pytest -m slow tests/test_supabase_interview_storage.py` khi có `INTERVIEW_TEST_POSTGRES_URL` trỏ tới localhost, tên database bắt đầu bằng `yourin_interview_test`.

## Trả lời Nhân về CV

Đã thử bằng CV hoàn toàn giả với chế độ gửi CV được bật riêng trong tiến trình kiểm tra. NVIDIA tạo bảy câu hỏi, gồm hai câu dùng đúng chi tiết trong CV. Một câu nhắc “Built a FastAPI reservation service for 200 students” và hỏi cách thiết kế dịch vụ, lý do dùng Redis. Câu còn lại nhắc “reduced search latency from 600 ms to 180 ms” và hỏi cách đo cùng phạm vi bài test.

Code của Duy đã hỗ trợ câu hỏi dựa trên CV, có kiểm tra trích dẫn nguyên văn cho câu ở phần CV. Tuy nhiên, `.env` trên máy ở lượt thử đang tắt gửi CV. Backend chỉ gửi CV khi `INTERVIEW_ALLOW_CV_TO_AI=1`. Cần kiểm tra cờ này trên môi trường nhóm đang demo để biết CV có thực sự được dùng ở đó.

## Lưu ý cho nhóm review

Nhánh này đã đưa sang các sửa lỗi playtest bằng cách sửa trên giao diện hiện tại, không chép đè phiên bản giao diện cũ. Bản nháp chính qua F5/hai tab, chờ nộp thành công trước khi Next và chờ lưu trước khi thoát đều đã được kiểm tra. Mã đăng nhập, module AI chung và SQL hiện tại được dùng qua các điểm nối có sẵn. Chưa kiểm thử ghi trên Supabase chung hoặc website triển khai cho lượt sửa này.
