# Đề xuất cho Yourin — Hỏi tiếp dựa trên điều ứng viên vừa nói

Khi ứng viên kể một chi tiết đáng hỏi thêm, Yourin có thể dừng ở chi tiết đó và hỏi thêm một câu trước khi sang chủ đề tiếp theo. Ví dụ, nếu ứng viên nói “em làm cho trang tải nhanh hơn 40%”, người phỏng vấn có lý do để hỏi “Em đo thời gian tải trước và sau khi sửa như thế nào?”.

## Hiện tại Yourin còn thiếu gì?

Trên bản `main` tại commit `2e1ad39`, khi người dùng bắt đầu buổi phỏng vấn, Yourin đã tạo hoặc chọn sẵn cả bộ câu hỏi. Mỗi lần người dùng nộp câu trả lời, ứng dụng lưu nội dung, chuyển đến câu kế tiếp trong danh sách và cho AI chấm câu vừa nộp. Kịch bản kỹ thuật của nhóm có một mục mang tên *follow-up*, nhưng câu đó cũng được soạn trước khi ứng viên nói. Vì vậy, nếu ứng viên bất ngờ nhắc đến con số 40%, chi tiết ấy có thể xuất hiện trong nhận xét chấm điểm, còn câu hỏi kế tiếp vẫn theo danh sách ban đầu. [Code xử lý buổi phỏng vấn](https://github.com/Mcrvc/assistant-team06/blob/2e1ad39/src/assistant/interviews.py) · [Kịch bản tạo câu hỏi](https://github.com/Mcrvc/assistant-team06/blob/2e1ad39/src/assistant/aiworker.py#L562)

## Người dùng sẽ thấy gì?

Giả sử Yourin hỏi **“Hãy kể về một lần em giúp nhóm cải thiện một dự án.”** Hai người có thể nhận hai câu hỏi tiếp theo khác nhau.

| Ứng viên vừa trả lời | Yourin có thể hỏi tiếp |
|---|---|
| “Em sửa phần truy vấn và trang tải nhanh hơn 40%.” | “Em đo mức cải thiện 40% đó như thế nào?” |
| “Hai bạn trong nhóm bất đồng về thiết kế database nên em đứng ra giải quyết.” | “Cụ thể em đã làm gì để hai bạn đi đến thống nhất?” |

Người dùng có thể trả lời câu hỏi phụ hoặc chọn **Tiếp tục phỏng vấn**. Khi xem lại buổi tập, họ thấy câu hỏi phụ ngay dưới câu trả lời đã dẫn đến nó.

## Code hiện tại có làm được không?

**Có đủ nền tảng để làm một bản nhỏ.** Nhóm đã gọi được NVIDIA từ backend, đã lưu được câu trả lời và đã có cách kiểm tra một đoạn AI trích có xuất hiện nguyên văn trong lời ứng viên hay không. Phần cần bổ sung là dùng câu trả lời vừa nộp để tạo câu hỏi mới, lưu đúng cặp hỏi–đáp và quyết định lúc nào hiển thị cho người dùng.

| Phần | Thay đổi cần làm |
|---|---|
| AI | Gửi câu hỏi gốc và câu trả lời vừa nộp cho NVIDIA. Yêu cầu AI chọn một đoạn ngắn trong lời ứng viên và viết một câu nhằm làm rõ đoạn đó. Backend kiểm tra đoạn trích trước khi hiển thị. |
| Lưu và mở lại | Gắn câu hỏi phụ và lời đáp với câu chính đã dẫn đến nó. Hiện Yourin ghép danh sách câu hỏi và câu trả lời theo thứ tự. Lưu phần hỏi thêm riêng dưới câu chính sẽ tránh làm lệch số câu khi mở lại. Cần kiểm tra cả thao tác lưu và đọc trên Supabase. |
| Giao diện | Hiện câu hỏi phụ tại câu vừa trả lời. Nếu người dùng đã bấm đi tiếp khi AI mới trả kết quả, giữ họ ở câu đang làm. Khi tải lại trang, mở đúng phần đã lưu và tránh tạo câu phụ lần hai. |

## Vì sao đáng làm?

Sinh viên thường có thể chuẩn bị trước câu mở đầu, nhưng dễ lúng túng khi được hỏi *“Phần nào do chính em làm?”* hoặc *“Em biết kết quả tốt hơn bằng cách nào?”*. Chế độ này cho họ luyện đúng lúc phải giải thích thêm. Nó cũng giúp người học phân biệt hai kỹ năng: kể được mình đã làm gì và giải thích được căn cứ cho điều mình vừa nói.

Khi trình bày đồ án, nhóm có thể cho giảng viên thử lần lượt hai câu trả lời trong bảng trên. Giảng viên tự quan sát được ứng dụng chọn chi tiết nào, câu hỏi tiếp theo có sát chi tiết ấy không và ứng viên có cơ hội làm rõ điều gì.

## Phạm vi đề xuất cho bản đầu

Mỗi buổi có tối đa **một câu hỏi phụ**, ưu tiên sau câu hỏi về kinh nghiệm hoặc dự án. Câu phụ dùng để luyện giải thích thêm và chưa tính vào điểm chung. Nếu AI phản hồi chậm, lỗi hoặc không tìm được chi tiết phù hợp, người dùng vẫn có thể sang câu chính tiếp theo.

Có thể coi bản đầu đã đạt khi nhóm thử được ba việc: đổi nội dung câu trả lời thì câu hỏi phụ bám theo chi tiết mới, tải lại vẫn thấy đúng cặp hỏi–đáp, và buổi phỏng vấn vẫn hoàn thành được khi NVIDIA không trả câu hỏi phụ.
