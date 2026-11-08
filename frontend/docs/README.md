# Interview AI Assistant — PoC

Bản HTML/CSS và JavaScript thuần để demo trên laptop. Mỗi frame ứng dụng
trong Figma Page 1 là một file HTML riêng; Moodboard chỉ là tài liệu thiết kế.

## Mở demo

1. Nếu nhận file ZIP: giải nén toàn bộ thư mục trước.
2. Mở **index.html** bằng Chrome hoặc Edge. Trang đầu là Sign in.
3. Tài khoản mẫu đã điền sẵn: **Eric Arthur Blair / demo1234**. Bấm Sign in.

Không cần Internet, server, Node.js hay cài thư viện. Giữ nguyên các thư mục
assets, css và js đi kèm. Bật JavaScript để dùng form và giữ dữ liệu giữa các trang.
Ưu tiên màn hình 1366 × 768 hoặc 1280 × 800, mức thu phóng trình duyệt 100%.
Một số trang dài như Report có cuộn dọc.

## Kịch bản trình diễn

1. **Create a new interview** → dán Job description, HTML hoặc link tuyển dụng; nếu không có, bấm nút chuyển sang nhập 4 trường thủ công. Có thể dùng CV tài khoản đã lưu hoặc bấm nút chuyển sang dán văn bản CV thuần / tải file PDF cho buổi phỏng vấn.
2. Bấm **Continue** bắt đầu câu hỏi 1.
3. Tùy chọn **Sync my saved CV with this interview** ở Job Profile quyết định
   có sao chép CV hiện tại vào buổi phỏng vấn mới hay không.
4. Nhập câu trả lời → **Next Question** / **Previous Question**.
   Có thể **Save and Quit** → **Back to home** → **View your interview**
   → **Continue**. Theo Figma, Continue mở lại câu hỏi 1; các câu trả lời vẫn được giữ.
5. Ở câu hỏi 3, **Finalize Interview** → đặt tên → **View Report**.
   **View CV feedback** mở phần CV. Nội dung phản hồi là mẫu cố định từ Figma.
6. Về Dashboard → **Rate our assistant** → nhập ý kiến → **Submit feedback**
   → trang Thank you.
7. Có thể mở **Profile**, nhập bất kỳ mật khẩu demo nào, bấm **Unlock editing**,
   sửa Username rồi **Save**. **Sign out** quay về Sign in.

CV của các buổi phỏng vấn đã lưu là bản sao tại lúc bắt đầu; sửa CV tài khoản
sau đó không thay đổi báo cáo cũ. Tài khoản demo khác có bộ dữ liệu riêng.

## Dữ liệu và giới hạn

- Sign in/Sign up/Profile chỉ mô phỏng; không xác thực thật, không lưu mật khẩu.
- Câu hỏi và phản hồi lấy từ nội dung mẫu của Figma, không phụ thuộc Job Profile. Report chỉ hiển thị kết quả phỏng vấn; CV được quản lý riêng ở Profile và chỉ là dữ liệu tùy chọn gắn vào buổi phỏng vấn.
- Các điều khiển chưa có hành vi trong Figma gốc được giữ không hoạt động,
  bao gồm Delete và Microphone. Đây là phạm vi PoC đã chốt, không phải yêu cầu còn thiếu.
- AI, nhập nội dung từ URL và thu âm nằm ngoài phạm vi PoC.
- Dữ liệu được lưu trong trình duyệt; có cách giữ trong cùng tab khi bộ nhớ
  localStorage bị chặn. Khi demo, đi bằng các nút trong cùng tab.
- Không bảo đảm dữ liệu đi theo khi chuyển tab, chuyển trình duyệt, di chuyển thư mục
  hoặc đóng trình duyệt. Bản ZIP chỉ chứa mã nguồn và dữ liệu mẫu ban đầu.
- Để có lượt demo sạch, mở cửa sổ ẩn danh mới sau khi đóng các cửa sổ ẩn danh cũ.
- Các phần chờ được liệt kê trong **PENDING.md**; không tự suy đoán hành vi còn thiếu.

## Các trang

| Nhóm | File |
| --- | --- |
| Tài khoản | sign-in.html, sign-up.html, profile.html |
| Trang chính / danh sách | dashboard.html, storage.html |
| Chuẩn bị | job-profile.html, cv.html |
| Phỏng vấn | interview-1.html, interview-2.html, interview-3.html |
| Lưu dở / hoàn tất | interview-interrupt.html, done-interview.html |
| Báo cáo | report.html |
| Phản hồi hệ thống | system-feedback.html, thank-you.html |

index.html là lối mở nhanh; css/styles.css và js/app.js dùng chung.
js/data.js chứa nguyên văn nội dung mẫu. Xem **TRANSITIONS.md** để đối chiếu liên kết.

## Nguồn và thay đổi thiết kế

[Figma — Interview AI Assistant](https://www.figma.com/design/o5OuPB8IL83NghsQZ03Dll/Interview-AI-Assistant?node-id=0-1).
Logo lấy từ Logo.svg do người dùng xuất từ Moodboard; hai họa tiết trang đăng nhập
lấy từ asset gốc của Figma. Font dùng Segoe UI/Arial có sẵn trên máy.
Biểu tượng microphone dùng file Mic icon.svg do người dùng xuất từ Figma,
lưu cục bộ tại assets/microphone.svg; nút chỉ minh họa.
Avatar dùng bản Avatar.svg đầy đủ do người dùng xuất từ Figma, lưu cục bộ tại
assets/avatar.svg, đặt trong header và trang Profile.

Áp dụng bảng màu được yêu cầu: #92C7CF, #AAD7D9, #FBF9F1, #E5E1DA.
Bố cục được điều chỉnh theo bảng góp ý của nhóm; nội dung và đích chuyển trang
dựa trên dữ liệu đã đọc. Chưa đối chiếu chi tiết toàn bộ thiết kế vì Figma MCP
hết lượt đọc; người dùng đã cho phép tiếp tục từ dữ liệu có sẵn.

Codex hỗ trợ viết mã, chuẩn bị tài liệu và kiểm tra. Đây là bản cục bộ để nhóm
duyệt trước khi hoàn thiện bài nộp.

## Đóng gói lại sau khi chỉnh sửa

Từ gốc repo, chạy PowerShell:

```powershell
Compress-Archive -Path ui/poc -DestinationPath ui/interview-poc.zip -Force
```

Gửi file ZIP, người nhận giải nén rồi mở poc/index.html.
