# Bàn giao follow-up và sửa lỗi playtest — 29/11/2026

Nhánh bàn giao: `feat/interview-follow-up`. Bắt đầu từ main `2e1ad39`.
Các thay đổi ở đây nằm trên nhánh riêng để nhóm review.

## Hành vi mới

1. Nộp câu chính. Trang hiện dòng nhỏ “Checking your answer...” trong lúc kiểm tra có cần hỏi thêm.
2. Nếu cần, Yori đưa ra câu phụ liên quan đến đáp án vừa nộp. Câu phụ dùng chính khung câu hỏi, ô trả lời, microphone và Replay. Nhãn có dạng “1 of 3 - Follow-up”; số câu chính giữ nguyên.
3. Bấm Next để nộp câu phụ rồi sang câu chính kế tiếp. Previous cho xem lại câu gốc; sang câu khác sẽ không còn hiện phần phụ của câu trước. Bản nháp câu phụ vẫn còn khi tải lại trang.
4. Nộp câu phụ sẽ chấm lại câu gốc bằng cả hai phần trả lời và cùng bộ tiêu chí ban đầu. Điểm mới thay điểm cũ của câu đó. Tổng điểm chỉ tính câu gốc một lần.
5. Báo cáo đặt đáp án gốc, câu phụ, đáp án phụ và nhận xét trong cùng một thẻ. Điểm được in rõ trên nhãn; có thể mở mục bằng chứng để xem các trích dẫn.

Khi AI chọn câu phụ lỗi hoặc chưa xong sau 15 giây, trang chuyển tiếp. Kết quả chọn về sau bị bỏ qua. Câu phụ đã hiện vẫn cần được trả lời. Hạn mức vẫn là hai câu phụ mỗi buổi và một câu phụ mỗi câu chính.

## Những sửa lỗi playtest đã có trong nhánh này

- Chỉ mở ô trả lời sau khi tải xong câu hỏi.
- Trang tạo buổi cũng chờ khởi tạo xong mới cho nhập và bấm Continue. CI phát hiện tên người dùng đã hiện từ bộ nhớ trong khi form chưa sẵn sàng, khiến nhập sớm có thể mất hoặc bấm Continue làm tải lại trang.
- Báo rõ ngay dưới ô nhập khi bỏ trống; giữ nguyên câu khi nộp thất bại.
- Chặn nhấn Next liên tục khi đang gửi; thử lại sau mất mạng không nộp/chấm trùng.
- Giữ bản nháp chính khi F5 hoặc nhận kết quả chấm qua polling.
- Hai tab giữ bản nháp riêng; lỗi phiên bản không ghi đè bản nháp bằng nội dung từ tab kia.
- Khi rời trang, chờ xác nhận Save and leave rồi mới lưu đáp án. Lỗi lưu cho thử lại hoặc Keep answering; đăng xuất chờ lưu thành công.
- Kiểm tra màn hình hẹp và khoảng trống còn lại khi bàn phím chiếm màn hình.

Các thay đổi được đưa sang từ `fix/playtest-2026-11-18` rồi điều chỉnh cho giao diện/giọng đọc mới. Không cần merge nhánh playtest riêng để nhận các sửa lỗi trên. Tài liệu tái hiện ban đầu nằm tại [playtest ngày 18/11](playtest-2026-11-18.md).

Đã bỏ hành vi microphone tự điền đáp án mẫu khi không dùng được nhận dạng giọng nói. Trường hợp đó giờ báo để người dùng gõ câu trả lời.

## Cách chấm và lưu

- Lưu câu phụ và đổi mã tác vụ chấm trong cùng một lần ghi. Tác vụ chấm cũ chỉ được ghi khi mã còn khớp, nên điểm cũ không thể ghi đè điểm chấm chung.
- Đáp án gốc vẫn giữ nguyên. Đầu vào chấm là đáp án gốc, hai dấu xuống dòng, rồi đáp án phụ; câu hỏi phụ được gửi ở phần câu hỏi để AI hiểu ngữ cảnh. Bộ tiêu chí không đổi.
- Trích dẫn phải nằm nguyên văn trong phần văn bản đáp án đã ghép. Trích dẫn chỉ có trong câu hỏi hoặc do AI tự thêm sẽ bị từ chối, không được tính điểm.
- Khi đang chấm, finalize trả lỗi chờ chấm. Có nút Retry grading khi điểm chung còn chờ hoặc bị từ chối; thao tác này giữ nguyên hai đáp án và thử chấm chung lại.
- HTTP: `/follow-up/answer` lưu đáp án và tạo tác vụ chấm mới. `/follow-up/retry-grade` nhận `revision`, `request_id` để thử lại. Gửi lặp yêu cầu vừa được lưu không tạo thêm tác vụ.
- JSON buổi phỏng vấn vẫn lưu bằng RPC hiện có. Không cần thêm cột hoặc chạy lại SQL. `answers.text` giữ đáp án gốc; `follow_ups[].answer` giữ đáp án phụ; điểm chung nằm ở grade của đáp án gốc. Báo cáo mới có `items[].includes_follow_up=true` ở câu được chấm chung.
- Các cột quan hệ vẫn được RPC cập nhật như trước. Trích dẫn trong `grades.evidence_quoted` có thể đến từ đáp án phụ; khi đối chiếu cần đọc cả hai phần từ JSON của buổi. Không nên chỉ so với cột đáp án chính.
- Báo cáo cũ vẫn mở được. Báo cáo đã finalize ở phiên bản chưa chấm câu phụ sẽ giữ điểm lịch sử; ứng dụng không tự chấm lại dữ liệu cũ.

Save and leave lưu cả hai phần. Nếu đang nhập câu phụ và phần đó có nội dung, thao tác xác nhận lưu cũng nộp phần phụ để chấm chung. Nếu câu phụ còn trống, buổi vẫn giữ câu phụ đang chờ để tiếp tục sau.

## Kiểm tra lại

Đã chạy qua 310 bài kiểm tra mặc định và 17 bài Chrome. Các trường hợp thêm gồm kết quả chấm cũ về muộn, sửa đáp án trong lúc chấm, gửi lại sau khi mất phản hồi, AI chọn câu phụ quá chậm và câu gốc bị sửa từ tab khác. Kiểm thử trình duyệt dùng tài khoản, dữ liệu và AI giả trên localhost; phần kết nối microphone/Replay có kiểm tra bằng bộ mô phỏng giọng nói.

Đã thử riêng hai lượt chấm NVIDIA thật với dữ liệu hoàn toàn giả. Điểm trước là 5,5/10; điểm sau bổ sung là 8,5/10. Cả hai lượt không dùng điểm mẫu và trích dẫn khớp văn bản. Không suy ra AI luôn chấm đúng từ một mẫu này. Các hạn chế khi chọn câu phụ vẫn được ghi trong [báo cáo stress test 204 mẫu](follow-up-coverage-fix-stress-test.md).

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[web,dev,browser-test]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest -m slow tests/test_interview_browser.py tests/test_follow_up_browser.py
```

Các bài Chrome dùng Chrome đã cài trên máy. CI cài Chromium và chạy lại cả 17 bài, đồng thời chạy các bài RPC trên PostgreSQL thử ở localhost. Không có thử ghi lên Supabase chung hoặc deploy trong lượt này. Nhóm cần chạy lại luồng thật trên môi trường triển khai sau khi review và tích hợp.
