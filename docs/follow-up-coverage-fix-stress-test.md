# Sửa bộ chọn câu hỏi tiếp nối và so sánh trước/sau

Ngày kiểm tra là 28/11/2026. Bản cũ dùng commit `4fc05b0`. Phép đo đầy đủ của bản mới dùng `4b867c3`. Sau đó commit `b99dc06` sửa thêm việc xác nhận thông tin từ câu trả lời phụ trước, được kiểm tra riêng trên toàn bộ sáu mẫu có ngữ cảnh đó.

## Cách chọn đã thay đổi

Lượt AI đầu tiên đọc toàn bộ đáp án và đánh dấu từng tiêu chí là đã có thông tin, còn thiếu, chưa chắc hoặc không áp dụng. Mỗi nhận định phải chỉ ra đoạn văn làm căn cứ. Backend chỉ tạo danh sách ứng viên hỏi thêm từ những điểm còn thiếu có trích dẫn hợp lệ.

Lượt thứ hai nhận toàn bộ đáp án, tiêu chí và các cặp mã tiêu chí/loại thiếu thông tin. Nó đọc lại độc lập, rồi viết câu hỏi cho phần mà nó cũng xác nhận còn thiếu. Câu hỏi và giải thích của lượt đầu được giữ riêng khỏi đầu vào lượt hai để hạn chế việc đồng ý theo đề xuất trước.

Các hướng dẫn mới yêu cầu chấp nhận hành động cá nhân hoặc lý do đã nằm ở đoạn khác, chấp nhận cách đo đủ cụ thể và giữ yêu cầu đúng mức của tiêu chí. Ví dụ, tiêu chí giải thích lý do dùng một nguồn dữ liệu chung được đáp ứng khi ứng viên nói hai bản riêng gây xung đột.

Hai lượt dùng JSON Schema có ràng buộc từ NVIDIA và được kiểm tra lại bằng Pydantic ở backend. Cách này đã giải quyết vấn đề trả nhiều khối JSON liền nhau hoặc thiếu dấu đóng trong các thử nghiệm ban đầu. Bộ chọn dùng chung cấu hình và helper HTTP hiện có. [Tài liệu API NVIDIA cho model đang dùng](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-super-vl-120b-a12b-infer)

## Phép so sánh đầy đủ trên 204 mẫu

Đầu vào của mỗi cặp trước/sau có cùng mã băm và cùng thứ tự mã trường hợp. Các file gốc được giữ nguyên. Bộ so sánh tách kết quả bị từ chối kiểm tra khỏi trường hợp AI quyết định bỏ qua.

| Kết quả | Bản cũ | Bản mới tại 4b867c3 |
|---|---:|---:|
| Đúng quyết định và đúng loại thông tin cần hỏi | 180/204, 88,24% | 189/204, 92,65% |
| Hỏi thừa | 14 | 2 |
| Bỏ sót | 8 | 5 |
| Chọn sai tiêu chí hoặc loại thiếu thông tin | 2 | 2 |
| Kết quả không đạt kiểm tra dữ liệu | 0 | 6 |
| Thời gian trung bình mỗi đáp án | 1,43 giây | 1,99 giây |

Khi kết quả không đạt kiểm tra dữ liệu, ứng dụng cho tiếp tục buổi phỏng vấn. Các trường hợp đó được tính là lỗi trong bảng để giữ phép so sánh thận trọng.

| Nhóm đầu vào | Bản cũ đúng | Bản mới đúng |
|---|---:|---:|
| 120 mẫu mở rộng, gồm bộ cũ và các trường hợp khó | 113/120 | 117/120 |
| 12 mẫu có nhiều tiêu chí | 9/12 | 8/12 |
| 48 mẫu ở các bối cảnh bổ sung | 35/48 | 40/48 |
| 24 mẫu ở bối cảnh mới tiếp theo | 23/24 | 24/24 |

Nhóm nhiều tiêu chí còn yếu. Việc giảm hỏi thừa đi cùng một số trường hợp bị loại bởi bộ kiểm tra dữ liệu hoặc bỏ sót. Cần xem cả các cột lỗi khi đánh giá mức cải thiện.

Các lượt gọi được chạy trong nhiều tiến trình đánh giá, có lúc cùng hoạt động trên dịch vụ NVIDIA. Thời gian phản ánh các lượt đo này và có thể chịu ảnh hưởng của tải nhà cung cấp.

## Sáu nhãn được rà lại

Trong sáu mẫu đầu thuộc nhóm hành động cá nhân của bộ 48 mẫu, đáp án đã có các câu như “I counted…” hoặc “I compared…”. Đây là hành động do chính ứng viên làm, phù hợp tiêu chí dù phần triển khai trước đó được kể là việc của nhóm.

Nhãn của sáu trường hợp được sửa thành không cần hỏi. Cùng sáu sửa đổi được áp dụng cho cả bản cũ và bản mới qua [file rà nhãn](../eval/follow_up_label_review.json). Bộ đầu vào và các file kết quả nguyên bản vẫn giữ nhãn lúc tạo. Công cụ so sánh áp bản rà nhãn khi tính bảng phía trên.

Nhóm nên rà lại các nhãn còn lại, đặc biệt mức nào được coi là đã giải thích đủ lý do lựa chọn. Các nhãn trong lượt này do người viết bộ thử tự đặt.

## Sửa thêm nguồn trích dẫn sau phép đo đầy đủ

Năm trong sáu kết quả bị loại nằm ở mẫu đã có câu hỏi phụ trước đó. Model dẫn lại thông tin trong lời đáp phụ, nhưng bộ kiểm tra cũ chỉ tìm trích dẫn ở đáp án chính hiện tại.

Commit `b99dc06` cho phép dùng trích dẫn có thật từ lời đáp phụ trước để xác nhận rằng thông tin đã được cung cấp. Đoạn dùng làm căn cứ để hỏi câu mới vẫn phải xuất hiện trong đáp án hiện tại. Có bài kiểm thử riêng cho cả hai điều kiện.

Đã gọi lại toàn bộ sáu mẫu có ngữ cảnh câu phụ trước, gồm cả mẫu đã qua ở lượt đo đầy đủ. Kết quả là **6/6 qua**, không hỏi thừa, không lỗi dữ liệu. Dữ liệu nằm ở ba file `follow_up_previous_*_results.json`.

Bảng 204 mẫu ở trên giữ kết quả của lượt chạy đầy đủ, tách khỏi sáu lượt xác nhận bản vá cuối để tránh gộp các lần đo có chọn trường hợp thành một tỷ lệ mới.

## Kiểm tra độ ổn định

Năm mẫu khó được thử ba lần mỗi mẫu, thành 15 lượt bổ sung. Bốn mẫu cần bỏ qua được bỏ qua đúng cả 12 lượt. Mẫu cần hỏi về cách đo kết quả chỉ được hỏi đúng một trong ba lượt, hai lượt còn lại bị bỏ sót. Không có hỏi thừa, chọn sai tiêu chí hoặc lỗi dữ liệu trong nhóm thử lặp này.

Kết quả còn thay đổi giữa các lần gọi dù đặt temperature bằng 0. Dữ liệu các lần lặp nằm trong [follow_up_stability_final_results.json](../eval/follow_up_stability_final_results.json).

## Chạy lại và kiểm tra

- [Bảng so sánh cùng danh sách từng trường hợp lỗi](../eval/follow_up_coverage_comparison.json).
- Các đầu vào là `follow_up_cases_expanded.json`, `follow_up_cases_multicriteria.json`, `follow_up_cases_holdout.json` và `follow_up_cases_fresh.json` trong `eval/`.
- Kết quả trước/sau và sáu lượt xác nhận bản vá được lưu riêng trong `eval/`.
- Bộ mặc định cuối đã qua 304 bài, gồm kiểm thử nguồn trích dẫn từ câu phụ trước. Bốn bài Chrome cũng qua. CI backend tại `4b867c3` đã qua cả phần PostgreSQL. [Kết quả CI](https://github.com/Mcrvc/assistant-team06/actions/runs/46135108098)

Ví dụ chạy lại một bộ sẽ gọi NVIDIA thật và ghi vào đường dẫn được chỉ định.

```powershell
.\.venv\Scripts\python.exe eval/follow_up_eval.py --cases eval/follow_up_cases_expanded.json --output eval/my_new_expanded_run.json
```

Để tính lại bảng đã lưu, dùng lệnh sau.

```powershell
.\.venv\Scripts\python.exe eval/compare_follow_up_eval.py --before eval/follow_up_expanded_results.json eval/follow_up_multicriteria_results.json eval/follow_up_holdout_before_results.json eval/follow_up_fresh_before_results.json --after eval/follow_up_expanded_final_results.json eval/follow_up_multicriteria_final_results.json eval/follow_up_holdout_final_results.json eval/follow_up_fresh_final_results.json --label-review eval/follow_up_label_review.json --output eval/my_comparison.json
```

## Phạm vi kết luận

Các bộ mẫu đã được dùng trong quá trình phát triển và rà lỗi. Kết quả cho thấy giảm hỏi thừa trên những mẫu này, đồng thời vẫn còn bỏ sót và chọn sai tiêu chí. Cần thêm đáp án do nhóm hoặc người dùng tự viết để đánh giá rộng hơn. Phép đo tập trung vào quyết định hỏi tiếp và thời gian gọi AI. Phần lưu/mở lại được kiểm tra bằng bộ test backend và Chrome, còn website triển khai và Supabase chung cần được nhóm thử khi tích hợp.
