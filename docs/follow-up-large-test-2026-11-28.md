# Kiểm thử lớn bộ chọn câu hỏi tiếp nối — 28/11/2026

Đã chạy NVIDIA thật trên **132 đáp án giả riêng biệt**, gồm 24 mẫu cũ và 108 mẫu bổ sung. Bộ thử có 78 đáp án tiếng Anh và 54 đáp án tiếng Việt. Có 54 trường hợp được gán kỳ vọng cần hỏi thêm và 78 trường hợp cần chuyển tiếp.

Code bộ chọn được thử ở commit `4fc05b0` trên nhánh `feat/interview-follow-up`, dùng model `nvidia/nemotron-3.5-super-vl-120b-a12b`. Đáp án và nhãn kỳ vọng được chuẩn bị trước khi gọi AI. Kết quả được giữ nguyên để nhóm kiểm tra lại.

## Kết quả theo nhãn kỳ vọng

| Kết quả | Số trường hợp |
|---|---:|
| Đúng cả quyết định hỏi và loại thông tin còn thiếu | 122/132, tương đương 92,42% |
| Hỏi thêm dù thông tin đã đủ | 7 |
| Bỏ qua khi còn thiếu thông tin | 2 |
| Có hỏi nhưng chọn sai tiêu chí và loại thông tin còn thiếu | 1 |
| Lỗi gọi nhà cung cấp hoặc dữ liệu trả về bị từ chối | 0 |

Thời gian trung bình cho bước chọn và kiểm tra là **1,56 giây** mỗi đáp án. 95% trường hợp hoàn thành trong **3,78 giây**, lâu nhất **8,46 giây**. Thời gian này chỉ đo bộ chọn câu phụ, chưa tính phần chấm điểm câu chính hoặc thao tác giao diện.

## Bộ thử đã bao gồm những gì?

- 120 mẫu mở rộng gồm cặp đáp án thiếu/đủ hành động cá nhân, lý do lựa chọn và cách kiểm tra kết quả. Có ví dụ về lập trình, phục vụ quán ăn, bàn giao thiết bị, nghiên cứu, thiết kế và robot.
- Các trường hợp khó gồm thông tin ở đầu câu trả lời nhưng kết luận nằm cuối, đoạn dài có nhiều thông tin phụ, tiếng Việt xen tiếng Anh, kết quả không cải thiện, bằng chứng quan sát không dùng số, câu phụ đã hỏi trước đó và nội dung yêu cầu AI bỏ qua hướng dẫn.
- 12 mẫu bổ sung dùng nhiều tiêu chí trong cùng một câu hỏi và cấu trúc rubric có tên, điểm, mô tả. Các mẫu kiểm tra cả việc bỏ qua một chi tiết không liên quan tiêu chí đang chấm.

## Các lỗi cụ thể

### Hỏi lại hành động đã được kể

Trong `edge-scattered-action-en` và bản tiếng Việt tương ứng, ứng viên đã nói mình tái hiện lỗi, viết test và nhờ một bạn kiểm tra bản sửa. AI vẫn hỏi thêm về hành động cá nhân. Hai bản `edge-long-context` cũng gặp vấn đề tương tự khi hành động nằm ở đầu một câu trả lời dài.

Đây là bốn trường hợp hỏi thừa. Việc trích dẫn đúng nguyên văn chưa đủ để bảo đảm AI hiểu rằng thông tin đã có trong đáp án.

### Đòi lý do sâu hơn mức tiêu chí yêu cầu

Trong `edge-scattered-reason-en` và bản tiếng Việt tương ứng, ứng viên đã giải thích cần một nơi lưu dữ liệu chung vì giữ hai bản gây xung đột. AI tiếp tục đòi lý do chọn PostgreSQL thay vì các giải pháp khác, trong khi tiêu chí chỉ yêu cầu giải thích cách lựa chọn giải quyết vấn đề.

Hai trường hợp này được gán là hỏi thừa. Nhóm nên thống nhất mức giải thích đủ để tránh AI tự nâng yêu cầu sau khi ứng viên đã trả lời.

### Hỏi lại cách đo đã nêu

Trong `edge-no-claimed-improvement-vi`, ứng viên nói chưa cải thiện được kết quả, đã so cùng 50 yêu cầu trên cùng máy trước và sau, trung vị vẫn là 300 mili giây. AI vẫn hỏi cách xác định trung vị. Đây là một trường hợp hỏi thừa nữa.

### Dễ nhầm khi có nhiều tiêu chí

Trong 12 mẫu nhiều tiêu chí có hai lần bỏ sót và một lần chọn sai loại thiếu thông tin. Trường hợp rõ nhất là `multi-vi-decision_reason_missing`. Ứng viên đã nói “Em viết tiến trình xử lý và thêm kiểm thử tích hợp”, nhưng AI lại hỏi người đó đã làm gì cụ thể, thay vì hỏi lý do chọn hàng đợi.

Hai lần bỏ sót là `multi-en-decision_reason_missing` và `multi-vi-result_evidence_missing`. Các nhãn này đòi ứng viên giải thích rõ lý do hoặc cách kiểm tra, nên cần được nhóm rà lại khi quyết định mức nào có thể chấp nhận bằng suy luận từ ngữ cảnh.

## Thử lặp để xác định bước lỗi

Ba trường hợp nhiều tiêu chí có lỗi được gọi lại hai lần mỗi trường hợp, thành **sáu lượt chẩn đoán bổ sung**. Các lượt này tách riêng khỏi 132 trường hợp phía trên.

Kết quả thay đổi giữa các lần gọi dù đặt temperature bằng 0. Có lượt bộ đề xuất chọn sai tiêu chí và bộ kiểm tra vẫn chấp nhận. Có lượt bộ kiểm tra nhận ra đáp án đã nói về hành động cá nhân rồi loại đề xuất, nhưng bước đầu không quay lại tìm khoảng thiếu ở tiêu chí khác. Trường hợp thiếu cách xác nhận kết quả bằng tiếng Việt tiếp tục bị bỏ qua ở cả hai lượt thử lại.

Vì hai bước dùng cùng model, các lỗi đọc hiểu có thể xuất hiện ở cả bước đề xuất lẫn bước kiểm tra. Kiểm tra cấu trúc và đối chiếu trích dẫn hiện vẫn hoạt động, nhưng cần cải thiện phần xác định thông tin đã có theo từng tiêu chí.

## Dữ liệu và cách chạy lại

Các file kết quả chứa câu hỏi phụ do AI đề xuất, mã trường hợp, quyết định thực tế và thời gian. Có mã băm bộ đầu vào để đối chiếu.

| Bộ | Đầu vào | Kết quả |
|---|---|---|
| 120 trường hợp | [follow_up_cases_expanded.json](../eval/follow_up_cases_expanded.json) | [follow_up_expanded_results.json](../eval/follow_up_expanded_results.json) |
| 12 trường hợp nhiều tiêu chí | [follow_up_cases_multicriteria.json](../eval/follow_up_cases_multicriteria.json) | [follow_up_multicriteria_results.json](../eval/follow_up_multicriteria_results.json) |
| Sáu lượt chẩn đoán | Ba mã trường hợp lỗi của bộ nhiều tiêu chí | [follow_up_diagnostic_results.json](../eval/follow_up_diagnostic_results.json) |

Từ thư mục repo có cấu hình NVIDIA, chạy các lệnh sau.

```powershell
.\.venv\Scripts\python.exe eval/follow_up_eval.py --cases eval/follow_up_cases_expanded.json --output eval/follow_up_expanded_results.json
.\.venv\Scripts\python.exe eval/follow_up_eval.py --cases eval/follow_up_cases_multicriteria.json --output eval/follow_up_multicriteria_results.json
.\.venv\Scripts\python.exe eval/follow_up_eval.py --cases eval/follow_up_cases_multicriteria.json --output eval/follow_up_diagnostic_results.json --ids multi-en-decision_reason_missing multi-vi-decision_reason_missing multi-vi-result_evidence_missing --repeat 2 --trace
```

Lệnh sẽ gọi NVIDIA và ghi đè file kết quả được chỉ định. Dùng tên đầu ra khác nếu muốn giữ lượt đo cũ.

## Phạm vi kết luận

Các nhãn do người viết bộ thử tự đặt, cần nhóm rà lại. Bộ mẫu có nhiều cặp cùng nội dung ở hai ngôn ngữ, nên các trường hợp chưa hoàn toàn độc lập. Tỷ lệ 92,42% mô tả lượt đo này theo các nhãn đó. Việc đánh giá đủ/chưa đủ thông tin vẫn cần thêm phản hồi từ sinh viên và giảng viên.

Lượt làm việc này bổ sung dữ liệu thử, công cụ ghi kết quả và báo cáo. Bộ chọn dùng trong ứng dụng vẫn ở đúng phiên bản được đo, để giữ lại các lỗi làm mốc đối chiếu cho lần sửa tiếp theo.
