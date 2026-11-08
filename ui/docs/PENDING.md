# Phạm vi PoC và các phần chờ đối chiếu

Người dùng đã cho phép tiếp tục từ nội dung, ảnh và liên kết Figma đã đọc,
đồng thời yêu cầu để chờ những phần chưa chắc cách triển khai.

Quyết định đã chốt: những điều khiển chưa có hành vi trong Figma gốc tiếp tục
chưa có chức năng trong PoC. Không tự bổ sung xử lý hay coi đó là việc bắt buộc
phải hoàn thiện trước buổi demo. Delete và Microphone giữ trạng thái không hoạt động.

| Phần | Trạng thái hiện tại | Cần bổ sung |
| --- | --- | --- |
| Animation giữa các trang | Liên kết đúng đích, hiệu ứng vào trang nhẹ | Đối chiếu PUSH/SLIDE_IN/SMART_ANIMATE nếu cần tái hiện chi tiết |
| Chi tiết thị giác của 15 frame ngoài Sign in | Có nội dung và trang riêng từ metadata/ảnh đã đọc | Đối chiếu spacing, font và các chi tiết chưa lấy được design context |

Màn hình được dựng theo phần đã biết; không khẳng định khớp từng pixel với Figma.
Chỉ Sign in đã lấy được get_design_context đầy đủ trước khi công cụ hết quota.
Ảnh chụp kiểm tra bố cục nằm ở ../qa/results/ trong repo, không dùng làm ảnh nền ứng dụng.

Đã bổ sung assets/microphone.svg từ Mic icon.svg do người dùng xuất từ Figma.
Biểu tượng xuất hiện trong ba trang câu hỏi và phần nền của trang lưu dở;
nút tiếp tục không hoạt động đúng phạm vi PoC.
Đã bổ sung assets/avatar.svg từ bản Avatar.svg đầy đủ do người dùng xuất lại,
dùng cho 14 header và hình lớn trong Profile. Bản Mask group.svg thiếu đầu không được dùng.

Ghi chú nội dung bản gốc:

- Ngày mẫu **29/2/2026** trong Storage là câu đùa có chủ ý của người thiết kế,
  đã được người dùng xác nhận. Giữ nguyên; không phải lỗi hay việc còn chờ sửa.
- Nền của frame Interview loop - interupt có câu hỏi khác câu 1 của luồng chính.
  Demo giữ câu chữ nền gốc; tên buổi được cập nhật theo buổi đang lưu.
  Đây chỉ là khác biệt nội dung nền, không phải lỗi lưu câu trả lời.

Phần AI chấm thật, xác thực, backend, tải nội dung Job description và lưu database
nằm ngoài phạm vi PoC đã thống nhất.

---

## [DONE] Kế hoạch cải thiện nền trang Sign in / Sign up (Landing khi Sign out)

### 1. Vấn đề trước đây
- Phần nền cột thương hiệu (`.auth-brand`) trên `sign-in.html` và `sign-up.html` dùng màu phẳng `--mist` (`#AAD7D9`) kết hợp hai file `assets/decor-top.svg` và `assets/decor-bottom.svg` bị kéo giãn (`preserveAspectRatio="none"`), có mảng hình quạt màu xám đục (`#ACBAC4`, `fill-opacity="1"`) gây cảm giác lỗi hiển thị.
- Phần cột form (`.auth-panel`) bên phải chỉ có màu kem phẳng (`#FBF9F1`), thiếu chiều sâu và sự liên kết thị giác với cột bên trái.

### 2. Giải pháp đã triển khai (Giữ đúng bảng màu `#92C7CF`, `#AAD7D9`, `#FBF9F1`, `#E5E1DA` và chạy 100% offline)
- **Trạng thái: DONE (Đã hoàn thành)**
  - `poc/assets/decor-top.svg` & `poc/assets/decor-bottom.svg`: Đã thay thế toàn bộ bằng SVG sóng âm & vòng cung đồng tâm sắc nét, tỉ lệ chuẩn không méo, loại bỏ màu xám đục lệch chuẩn `#ACBAC4`.
  - `poc/css/styles.css`: Đã cập nhật mesh gradient đa tầng cho `.auth-brand`, quầng sáng nổi bật thương hiệu `.auth-brand-content`, nền họa tiết kỹ thuật tinh tế cho `.auth-panel`, và nâng cấp `.auth-form` thành thẻ nổi (elevated card) với hiệu ứng kính mờ (frosted glass) và đổ bóng mềm mại, đồng bộ responsive trên tablet và mobile.

---

## [DONE] Kế hoạch thiết kế lại bố cục Dashboard theo phong cách Google Showcase (`dashboard.html`)

### 1. Vấn đề trước đây
- Bố cục `.welcome` trên `dashboard.html` chia 2 cột đơn điệu: bên trái xếp chồng 3 nút bấm dọc (`.dashboard-actions`), bên phải lặp lại logo và khẩu hiệu.
- Ba nút bấm xếp chồng thiếu điểm nhấn thị giác, không thể hiện giá trị của từng tính năng và trông rời rạc.

### 2. Giải pháp đã triển khai (Lấy cảm hứng từ bố cục Google DeepMind / Google Showcase)
- **Trạng thái: DONE (Đã hoàn thành)**
  - `poc/dashboard.html`: Đã chuyển đổi hoàn toàn sang bố cục Hero Banner + Centered Editorial Copy + 3 Thẻ Banner tương tác (Feature Cards).
  - `poc/assets/dashboard-hero-banner.svg`: Tạo banner hero lớn trung tâm với quả cầu kính AI phát sáng (Glass Orb), vòng sóng âm và biểu tượng Yourin.
  - `poc/assets/card-banner-1.svg`: Tạo banner nhỏ minh họa hồ sơ công việc & CV đồng bộ cho thẻ "Create a new interview".
  - `poc/assets/card-banner-2.svg`: Tạo banner nhỏ nền tối tương phản cao với mạng hạt AI & báo cáo phân tích cho thẻ "View your interview".
  - `poc/assets/card-banner-3.svg`: Tạo banner nhỏ minh họa đánh giá sao & phản hồi trải nghiệm cho thẻ "Rate our assistant".
  - `poc/css/styles.css`: Đã bổ sung toàn bộ hệ thống lớp `.dashboard-hero`, `.hero-media-wrapper`, `.hero-banner`, `.hero-eyebrow`, `.hero-title`, `.hero-description`, `.btn-pill`, `.feature-grid`, `.feature-card`, `.feature-card-media`, `.feature-card-icon`, hiệu ứng nhấc thẻ hover và responsive trên desktop, tablet và mobile.
  - Đảm bảo 100% thuộc tính kỹ thuật (`data-username`, `data-new-interview`) và toàn bộ điều hướng khớp với `TRANSITIONS.md`.

---

## [DONE] Kế hoạch tinh chỉnh Hero Banner & Hiệu ứng cuộn trang (Scroll Rise-Up) trên Dashboard

### 1. Yêu cầu thay đổi từ người dùng
1. **Bỏ biểu tượng nút Play trên Hero Banner**:
   - Xóa hoàn toàn hình nút Play giả video trong `assets/dashboard-hero-banner.svg`, giữ lại cụm đồ họa quả cầu kính AI (Glass Orb), sóng âm và biểu tượng `Logo.svg`.
2. **Đưa Tên ứng dụng + Mô tả ngắn vào trong một Big Banner chia 2 bên (Split Hero Banner)**:
   - Gộp thành một **Big Hero Banner** lớn duy nhất chia 2 cột hài hòa:
     - **Một bên (Cột nội dung)**: Hiển thị huy hiệu thương hiệu **Yourin**, tiêu đề chính và đoạn mô tả ngắn gọn về trợ lý phỏng vấn AI, kèm nút bắt đầu phỏng vấn.
     - **Bên còn lại (Cột đồ họa)**: Tái sử dụng cụm thiết kế quả cầu kính AI, vòng sóng âm đồng tâm và biểu tượng Yourin (đã bỏ nút Play).
3. **Loại bỏ dòng `Welcome, <username>`**:
   - Xóa phần `Welcome, Eric Arthur Blair` khỏi Dashboard để giao diện tinh gọn, tập trung vào giá trị sản phẩm.
4. **Hiệu ứng "Rise Up" khi cuộn chuột xuống cho 3 Small Banners (`.feature-card`)**:
   - Khi cuộn trang xuống khu vực 3 thẻ tính năng, 3 thẻ sẽ trượt mượt mà từ dưới lên kèm hiệu ứng hiện dần (`opacity: 0; transform: translateY(44px)` → `opacity: 1; transform: translateY(0)`) với độ trễ nối tiếp nhau (`staggered delay`: `0s`, `0.12s`, `0.24s`).

### 2. Trạng thái triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
  - `poc/assets/dashboard-hero-banner.svg`: Đã loại bỏ hoàn toàn nút Play, cân đối lại tâm quả cầu kính và các vòng sóng âm.
  - `poc/dashboard.html`: Đã chuyển đổi sang cấu trúc `.dashboard-hero-banner` chia 2 cột (Content bên trái, Artwork bên phải), bỏ dòng Welcome + username, gắn class `.reveal-on-scroll` cho 3 thẻ tính năng.
  - `poc/css/styles.css`: Đã định nghĩa kiểu dáng `.dashboard-hero-banner`, `.hero-brand-badge`, `.hero-banner-title`, `.hero-banner-description`, và hệ thống hiệu ứng `body.js-scroll-ready .feature-card.reveal-on-scroll` (với staggered delays và giữ nguyên hiệu ứng nhấc thẻ hover khi đã hiện).
  - `poc/js/app.js`: Đã bổ sung `IntersectionObserver` (kèm fallback scroll listener) kích hoạt hiệu ứng trồi lên khi người dùng cuộn tới vị trí 3 thẻ.

---

## [DONE] Loại bỏ huy hiệu `.hero-brand-badge` (Logo + Nền huy hiệu) trên Hero Banner

### 1. Thay đổi
- **Trạng thái: DONE (Đã hoàn thành)**
  - Đã xóa hoàn toàn khối `.hero-brand-badge` (logo nhỏ và nền hình chữ nhật bo tròn) trên `poc/dashboard.html` và `poc/css/styles.css`.
  - Đưa tên ứng dụng trực tiếp vào tiêu đề chính (`Yourin: Your realistic and interactive AI interview assistant`) đúng theo bố cục tối giản của Google.

---

## [DONE] Xóa các dòng chữ hướng dẫn thừa (`.eyebrow`) & Thiết kế lại Header (`.site-header`)

### 1. Thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
  - **Xóa toàn bộ `.eyebrow`**: Đã loại bỏ hoàn toàn các nhãn chỉ dẫn thừa như `01 / Set up your interview`, `02 / Practice`, `03 / Review`, `01 / CV` .. `04 / CV`, `Interview AI Assistant` trên toàn bộ 14 trang HTML.
  - **Header dạng Floating Glassmorphic Pill Navbar**:
    - Chuyển thanh header phẳng cũ sang thanh điều hướng nổi dạng viên thuốc bo tròn (`border-radius: 100px`), hiệu ứng kính mờ (`backdrop-filter: blur(16px)`), đổ bóng nhẹ và dính cố định (`position: sticky; top: 14px`).
    - **Vùng trái**: Đặt `Logo.svg` trong khung tròn nhỏ màu xanh đậm tương phản cao đi cùng tên thương hiệu **Yourin** (chuyển về `dashboard.html`).
    - **Vùng giữa**: Cụm 3 tab điều hướng nhanh tinh gọn gồm **Dashboard**, **Your interview** và **System feedback**, tự động sáng active tương ứng từng trang.
    - **Vùng phải**: Nâng cấp nút Avatar thành Profile Pill với ảnh đại diện sắc nét và tên tài khoản `[data-username]`, loại bỏ huy hiệu `POC DEMO` thừa.
    - Tương thích responsive hoàn hảo trên tablet và mobile.

---

## [DONE] Điều chỉnh lại Header: Trải rộng toàn trang (Full-Width) & Dùng chữ thuần túy (Không đóng khung bo tròn)

### 1. Thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
  - **Full-Width Header**: Header trải rộng `100%` toàn trang, cố định dính trên cùng (`position: sticky; top: 0; width: 100%`), nền kính mờ sáng sạch (`rgba(255, 255, 255, 0.9)`, `backdrop-filter: blur(16px)`), viền mảnh bên dưới (`border-bottom: 1px solid var(--line)`).
  - **Plain Typography Links (Chữ thuần túy, không đóng khung)**:
    - Loại bỏ hoàn toàn nền và viền bo tròn của `.header-nav` và `.nav-link`.
    - Các liên kết **Dashboard**, **Your interview**, **System feedback** hiển thị dưới dạng chữ thuần túy, giãn cách thoáng (`gap: 36px`), chuyển màu mượt mà khi hover và có gạch chân active tinh tế khi ở trang hiện tại.
    - Cụm Profile bên phải loại bỏ khung bo tròn, hiển thị avatar sắc nét và tên người dùng sạch sẽ, tự nhiên.

---

## [DONE] Cải thiện trang Profile: Mở khóa xem/sửa Mật khẩu & Bổ sung mục Quản lý CV (4 trường văn bản + Tải file PDF)

### 1. Thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
  - **Account Credentials (`poc/profile.html`, `poc/js/app.js`)**:
    - **Username**: Có thể chỉnh sửa bất cứ lúc nào (bỏ `readonly`). Bấm **Save account** sẽ cập nhật tên ngay lập tức và đồng bộ trên toàn bộ trang (`[data-username]`).
    - **Mật khẩu (Password `"123"`)**:
      - Ban đầu trường `#account-password` ở trạng thái khóa (`readonly`, `type="password"`) hiển thị dấu chấm che `•••` và huy hiệu `🔒 Locked (masked)`.
      - Bổ sung ô xác thực `#verify-password` ("Verify current password to view & edit"). Khi người dùng nhập đúng `"123"` (hoặc mật khẩu mới đã đổi) và bấm **Unlock**:
        - Ô `#account-password` lập tức chuyển sang `type="text"` và bỏ `readonly` để người dùng **nhìn thấy rõ mật khẩu hiện tại (`123`) và có thể gõ mật khẩu mới**.
        - Huy hiệu chuyển sang `🔓 Unlocked (editable)`.
      - Khi bấm **Save account**, lưu lại mật khẩu mới vào `account.password` và tự động khóa bảo mật trở lại (`type="password"`).
  - **Saved Resume / CV Section bên dưới Account Panel (`poc/profile.html`, `poc/css/styles.css`)**:
    - Đặt panel `.profile-cv-panel` ngay bên dưới `.profile-panel`, kết nối tự nhiên với tùy chọn *"Sync my saved CV with this interview"* của `job-profile.html`.
    - **Bộ chuyển đổi 2 chế độ (Mode Switcher Tabs)**: Cho phép chuyển đổi mượt mà giữa **4 Sections** và **Upload PDF**, lưu trạng thái vào `account.cvMode`.
    - **Chế độ 1: 4 trường văn bản (Bố cục Editorial Resume Stack)**:
      - Thay thế hoàn toàn bố cục lưới 2×2 cứng nhắc của `cv.html` bằng bố cục xếp lớp ngang trực quan, sang trọng: mỗi mục (`01. Personal Profile`, `02. Education History`, `03. Work & Research Experience`, `04. Core Skills`) gồm cột trái chứa badge số thứ tự + tên mục + gợi ý ngắn gọn, cột phải là ô `<textarea data-cv="0..3">` rộng rãi, dễ đọc.
      - Tự động lưu (`auto-save`) và có nút **Save CV** đồng bộ 100% dữ liệu với `account.cv`.
    - **Chế độ 2: Tải lên file PDF (`.pdf`)**:
      - Vùng kéo thả / duyệt file `.cv-pdf-dropzone` tương tác trực tiếp (`Drag & drop` hoặc bấm chọn file `.pdf`).
      - Kiểm tra tính hợp lệ của file PDF và hiển thị **Thẻ File PDF (`.cv-pdf-card`)** chứa biểu tượng tài liệu PDF đỏ, tên file, kích thước file, thời gian đính kèm, cùng 2 nút thao tác **Replace** và **Remove**.

---

### 2. Giải pháp thiết kế & Bố cục chi tiết

#### A. Khu vực 1 — Account Section (`poc/profile.html` & `poc/js/app.js`)
Giữ bố cục thẻ `.profile-panel` gọn đẹp hiện tại ở phần trên của `profile.html`, nhưng tách rõ 2 cụm thao tác hợp lý:
1. **Chỉnh sửa Username tự do (Always Editable)**:
   - Trường `Username` (`#profile-username`) luôn cho phép nhập và chỉnh sửa trực tiếp (bỏ `readonly`), đi kèm nút **Save account** (`#save-profile`) luôn sẵn sàng.
   - Khi lưu, cập nhật ngay `account.username`, `state.currentAccount` và đồng bộ tức thì tên hiển thị trên toàn trang (`[data-username]`) kèm thông báo trạng thái tại chỗ (không tự động đá người dùng về `dashboard.html` để họ có thể tiếp tục chỉnh sửa CV bên dưới).
2. **Xem & Đổi Mật khẩu qua bước Xác thực (`Password = "123"`)**:
   - **Trường hiển thị/sửa mật khẩu tài khoản (`#account-password`)**:
     - Mặc định khởi tạo `account.password = account.password || "123"`.
     - Khi đang khóa: hiển thị dưới dạng `type="password"` (`readonly`, giá trị `"123"` được che thành `•••`).
   - **Khu vực mở khóa mật khẩu (`#password-unlock-box`)**:
     - Có một trường nhập riêng biệt: **Current password to unlock** (`#verify-password`, `type="password"`, placeholder: `"Enter current password (default: 123)"`) cùng nút **Unlock to view & edit** (`#unlock-password-btn`).
     - Khi người dùng bấm **Unlock to view & edit**:
       - Nếu nhập sai (khác `account.password`, mặc định là `"123"`): báo lỗi rõ ràng `"Incorrect password. Enter current password (123) to view and edit."`.
       - Nếu nhập đúng `"123"` (hoặc mật khẩu hiện tại của tài khoản):
         - Mở khóa trường `#account-password`: chuyển từ `type="password"` sang `type="text"` và bỏ `readonly`, giúp người dùng **nhìn thấy rõ mật khẩu hiện tại (`123`) và có thể gõ mật khẩu mới** ngay tại ô đó.
         - Ẩn cụm ô xác thực `#password-unlock-box` (hoặc hiển thị trạng thái *"Password unlocked — you can now view and edit your password"*).
         - Khi bấm **Save account**, lưu cả `Username` và mật khẩu mới (`account.password`) vào `localStorage`, đồng thời khóa lại `#account-password` về chế độ che (`type="password"`, `readonly`) để đảm bảo an toàn thị giác.

#### B. Khu vực 2 — Saved CV Section bên dưới Account Section (`poc/profile.html`)
Đặt một panel mới `<section class="panel profile-cv-panel">` ngay bên dưới `.profile-panel` với thanh chuyển đổi chế độ (**Segmented Mode Switcher**) gồm 2 tab rõ ràng:
- **Tab 1: Structured CV Builder (4 trường văn bản — Bố cục Editorial Stack + Section Navigation)**
  - Thay vì chia ô vuông 2×2 chật hẹp như `cv.html`, sử dụng bố cục **Vertical Editorial Resume Stack (hoặc Master-Detail Tabbed Sections)**:
    - Mỗi mục trong 4 mục (*01. Personal Profile*, *02. Education History*, *03. Work / Research Experience*, *04. Core Skills*) được thiết kế như một thẻ mục hồ sơ ngang rộng rãi (Full-width structured section row):
      - Cột trái của mục (hoặc thanh tiêu đề mục): Số thứ tự badge tinh tế, tên mục rõ ràng và dòng gợi ý ngắn (ví dụ: *Summary & career focus*, *Academic background*, *Projects & roles*, *Technical & soft skills*).
      - Cột phải của mục: Ô soạn thảo `<textarea data-cv="0..3">` rộng thoáng, dễ đọc, tự động đồng bộ hai chiều với `account.cv[0..3]`.
    - Có nút **Save CV** và tự động lưu khi nhập (`input` event), giúp dữ liệu CV ở `profile.html` và `cv.html` đồng nhất 100%.
- **Tab 2: Upload PDF Resume (Tải lên file `.pdf`)**
  - Giao diện **Dropzone tải file PDF** hiện đại (`.cv-pdf-dropzone`):
    - Cho phép kéo-thả (Drag & Drop) hoặc bấm chọn file từ máy tính qua `<input id="cv-pdf-input" type="file" accept=".pdf,application/pdf">`.
    - Kiểm tra định dạng `.pdf`: nếu chọn sai định dạng sẽ báo lỗi trực quan.
    - Khi tải file `.pdf` hợp lệ:
      - Lưu thông tin file vào `account.cvPdf = { name, size, updatedAt }` (và lưu chế độ ưu tiên `account.cvMode = "pdf"`).
      - Hiển thị **Thẻ File PDF đã lưu (Uploaded PDF Card)** gồm biểu tượng tài liệu PDF, tên file (ví dụ: `Eric_Blair_Resume.pdf`), dung lượng file (KB/MB), thời gian tải lên, cùng 2 nút thao tác: **Replace PDF** (đổi file khác) và **Remove PDF** (xóa file đính kèm).

---

### 3. Danh sách file sẽ cập nhật khi triển khai
1. **`poc/profile.html`**:
   - Cập nhật form `#profile-form` trong `.profile-panel`: mở khóa sẵn `#profile-username`, tách trường `#account-password` (hiển thị mật khẩu bị che `•••`) và cụm `#verify-password` + nút `#unlock-password-btn` để xác thực mật khẩu `"123"` trước khi xem/sửa.
   - Bổ sung `<section class="panel profile-cv-panel">` bên dưới `.profile-panel` với bộ chuyển đổi 2 chế độ (**Write 4 Sections** / **Upload PDF**) và bố cục CV mới.
2. **`poc/css/styles.css`**:
   - Thêm style cho cụm xác thực/mở khóa mật khẩu (`.password-field-group`, `.unlock-box`, trạng thái badge đã mở khóa).
   - Thêm style cho `.profile-cv-panel`, thanh chuyển tab `.cv-mode-tabs`, bố cục 4 trường CV dạng Editorial Horizontal Rows (`.profile-cv-list`, `.profile-cv-item`), vùng kéo thả `.cv-pdf-dropzone` và thẻ hiển thị file `.cv-pdf-card`.
3. **`poc/js/app.js`**:
   - Khởi tạo mặc định `account.password = account.password || "123"`, `account.cvMode = account.cvMode || "text"`, `account.cvPdf = account.cvPdf || null`.
   - Cập nhật logic trang `profile`:
     - Cho phép lưu `Username` bất kỳ lúc nào.
     - Kiểm tra `#verify-password === account.password` (mặc định `"123"`) khi bấm `#unlock-password-btn` để hiện mật khẩu thật (`type="text"`) và cho phép sửa `#account-password`.
     - Đồng bộ 4 trường `<textarea data-cv="0..3">` và xử lý sự kiện chọn/kéo-thả/xóa file PDF trên `profile.html`.

---

### 4. Trạng thái
- **DONE** — Đã triển khai phiên bản đầu tiên.

---

## [DONE] Tinh chỉnh lại giao diện trang Profile: Lược bỏ chi tiết thừa, cân bằng chiều cao cột Avatar & Gộp chung luồng "Your CV"

### 1. Thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
  - **Tiêu đề trang & Phần đầu trang (`poc/profile.html`)**:
    - Khôi phục `<title>Profile · Yourin</title>`.
    - **Loại bỏ hoàn toàn khối `.page-heading`** (tiêu đề và mô tả phụ đầu trang), trang mở ra liền mạch và hiện đại ngay từ thẻ thông tin cá nhân.
  - **Làm sạch Khu vực Account (`poc/profile.html`, `poc/css/styles.css`, `poc/js/app.js`)**:
    - Loại bỏ tiêu đề thừa `"Account Credentials"` và đoạn văn hướng dẫn.
    - Loại bỏ toàn bộ các ghi chú demo thừa (`Demo profile`, `Default demo password is 123.`).
    - Loại bỏ huy hiệu khóa `🔒 Locked (masked)` trên đầu ô mật khẩu, chỉ giữ nhãn `Password` tinh gọn.
    - **Cân bằng chiều cao cột trái và cột phải**: Áp dụng `align-items: stretch` trên `.profile-panel` và căn giữa dọc nội dung cột trái `.profile-summary` (`display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100%`), giúp khung xanh nhạt của Avatar kéo dài cân đối 1:1 với cột form bên phải.
  - **Khu vực CV gộp chung ("Your CV" — 4 Sections + PDF Upload)**:
    - Đổi tên thành **`Your CV`**.
    - Loại bỏ thanh chuyển tab: 4 mục CV văn bản (*01. Personal Profile*, *02. Education History*, *03. Work & Research Experience*, *04. Core Skills*) hiển thị ở trên, nối tiếp ngay bên dưới qua vạch ngăn cách **`OR you can upload your CV`** (`.cv-or-divider`) dẫn trực tiếp đến vùng kéo thả / tải file PDF và thanh nút **Save CV**.

---

### 2. Danh sách file sẽ cập nhật khi triển khai
1. **`poc/profile.html`**:
   - Khôi phục `<title>Profile · Yourin</title>` và xóa `.page-heading`.
   - Trong `.profile-panel`: xóa `<p class="demo-note">Demo profile</p>`, xóa `.profile-form-header`, xóa `#password-lock-badge`, xóa `<p class="unlock-hint">Default demo password is 123.</p>`.
   - Trong `.profile-cv-panel`: đổi tiêu đề thành `<h2>Your CV</h2>`, xóa `.cv-mode-switcher`, đặt khối tải PDF ngay bên dưới 4 mục văn bản qua vạch ngăn cách `<div class="cv-or-divider"><span>OR you can upload your CV</span></div>`.
2. **`poc/css/styles.css`**:
   - Cập nhật `.profile-panel` (`align-items: stretch`) và `.profile-summary` (`display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100%`) để cột xanh nhạt bên trái cao bằng cột phải.
   - Thêm style cho vạch ngăn cách `.cv-or-divider` (đường kẻ ngang 2 bên với chữ ở giữa) và dọn dẹp các class tab/badge không còn dùng.
3. **`poc/js/app.js`**:
   - Loại bỏ logic chuyển tab (`switchCvTab`) và cập nhật `#password-lock-badge` đã xóa; giữ nguyên luồng mở khóa xem/sửa mật khẩu khi nhập đúng `"123"`, tự động lưu 4 mục CV và tải/xóa file PDF trên cùng một mặt trang.

---

### 3. Trạng thái
- **DONE** — Đã hoàn thành triển khai phiên bản trước.

---

## [DONE] Thay đổi Thẻ nhỏ số 1 trên Dashboard: Chuyển từ "Create a new interview" sang "Manage your CV" dẫn thẳng tới mục CV trang Profile

### 1. Thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
  - **Dashboard Card 1 (`poc/dashboard.html`)**:
    - Chuyển đổi từ `Create a new interview` sang **`Manage your CV`**.
    - Cập nhật mô tả: *"Fill in your 4 structured CV sections or upload a PDF resume so it automatically syncs with your interviews."*
    - Đổi link sang `profile.html#your-cv`, loại bỏ trùng lặp với nút chính trên Hero Banner (`Start a new interview →`).
  - **Neo cuộn mượt (`poc/profile.html`, `poc/css/styles.css`)**:
    - Gắn `id="your-cv"` vào `<section class="panel profile-cv-panel">` trên `profile.html`.
    - Bổ sung `scroll-margin-top: 88px` và `html { scroll-behavior: smooth; }` để khi người dùng nhấn thẻ từ Dashboard, trang Profile tự động cuộn mượt xuống thẳng khung **Your CV** với khoảng cách chuẩn xác dưới Sticky Header.

---

### 2. Giải pháp thiết kế & Nội dung chi tiết

1. **Cập nhật Thẻ nhỏ số 1 trên `poc/dashboard.html`**:
   - **Liên kết (`href`)**: Đổi từ `href="job-profile.html" data-new-interview` sang `href="profile.html#your-cv"` (bỏ thuộc tính `data-new-interview`).
   - **Tiêu đề thẻ (`<h3>`)**: **`Manage your CV`** (hoặc **`Input your CV`**).
   - **Mô tả ngắn (`<p>`)**: *"Fill in your 4 structured CV sections or upload a PDF resume so it automatically syncs with your interviews."*
   - **Hình minh họa (`poc/assets/card-banner-1.svg`)**: Giữ nguyên (hoặc tinh chỉnh nhẹ biểu tượng tài liệu CV/PDF trên `card-banner-1.svg` cho khớp hoàn toàn với chủ đề hồ sơ CV & PDF).

2. **Bổ sung Neo định vị (`#your-cv`) trên `poc/profile.html` & Cuộn mượt (`poc/css/styles.css`)**:
   - Thêm `id="your-cv"` vào thẻ `<section id="your-cv" class="panel profile-cv-panel">` trên trang `poc/profile.html`.
   - Trong `poc/css/styles.css`, thêm `scroll-margin-top: 88px;` cho `#your-cv` (và `scroll-behavior: smooth;` trên `html`) để khi người dùng bấm từ Dashboard sang `profile.html#your-cv`, trình duyệt tự động trượt mượt xuống đúng khung **Your CV** mà không bị thanh Sticky Header che khuất.

---

### 3. Danh sách file sẽ cập nhật khi triển khai
1. **`poc/dashboard.html`**: Cập nhật nội dung và đường dẫn của Card 1 sang `profile.html#your-cv`.
2. **`poc/profile.html`**: Gắn `id="your-cv"` cho `<section class="panel profile-cv-panel">`.
3. **`poc/css/styles.css`**: Thêm `scroll-margin-top: 88px` cho `.profile-cv-panel` / `#your-cv` để neo cuộn chuẩn xác dưới thanh header cố định.

---

### 4. Trạng thái
- **DONE** — Đã hoàn thành triển khai và kiểm thử.

---

## [DONE] Gộp trang Input CV vào trang Job Profile: Xóa `cv.html`, tinh gọn tiêu đề & Bổ sung mục mở rộng (Expandable) nhập CV riêng cho buổi phỏng vấn

### 1. Thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
  - **Xóa trang `poc/cv.html`**: Đã xóa hoàn toàn file `cv.html` và gỡ bỏ đoạn xử lý sự kiện `if (page === "cv")` trong `poc/js/app.js`.
  - **Tinh gọn trang `poc/job-profile.html`**:
    - Loại bỏ khối `.page-heading` rời bên ngoài, đưa tiêu đề sạch đẹp `<h2>Job Profile</h2>` vào ngay đầu thẻ `.panel` (`.panel-header`).
    - Xóa bỏ dòng chú thích demo thừa *"The link is saved for this demo; its contents are not imported."*.
    - Xóa nút `Input CV (Optional)` ở đáy trang, căn phải nút chính **`Continue →`**.
  - **Bổ sung Mục mở rộng tùy chỉnh CV cho buổi phỏng vấn (`#custom-cv-expander`)**:
    - Ngay dưới hộp kiểm `Sync my saved CV with this interview`, bổ sung vạch ngăn cách tinh tế: **`OR customize a CV for this interview`**.
    - Nút đóng/mở `#custom-cv-toggle` với tiêu đề *"Input a custom CV for this interview"* và dòng mô tả *"Expand to enter 4 CV sections or upload a PDF specifically for this session"*.
    - Khi mở rộng: hiển thị đầy đủ bố cục chuẩn của phần **Your CV** (4 mục văn bản xếp lớp ngang: *01 Personal Profile*, *02 Education History*, *03 Work & Research Experience*, *04 Core Skills* + vạch ngăn cách + khu vực tải file PDF riêng cho buổi phỏng vấn).
    - Khi bấm `Continue →`, nếu người dùng mở rộng và nhập CV tùy chỉnh, buổi phỏng vấn mới sẽ tự động lưu và sử dụng bộ CV này.

---

### 2. Giải pháp thiết kế & Bố cục chi tiết

1. **Xóa trang `poc/cv.html` & Dọn dẹp luồng điều hướng**:
   - Xóa file `poc/cv.html`.
   - Xóa nút `<a class="btn btn-secondary" href="cv.html">Input CV (Optional)</a>` ở cuối form `job-profile.html`, đưa nút chính **`Continue →`** sang góc phải (`.form-bottom.align-end`).

2. **Tinh gọn Tiêu đề & Xóa dòng chú thích thừa trên `poc/job-profile.html`**:
   - **Xóa `.page-heading` bên ngoài card**: Bỏ `<div class="page-heading"><h1>Input Job Profile</h1></div>` phía trên panel; thay bằng tiêu đề nội bộ gọn đẹp `<div class="profile-cv-header"><h2>Job Profile</h2></div>` nằm ngay bên trong `.panel` (đồng bộ phong cách với thẻ `Your CV` ở trang Profile).
   - **Xóa dòng ghi chú thừa**: Xóa hoàn toàn `<p class="demo-note">The link is saved for this demo; its contents are not imported.</p>` bên dưới ô `Job description link (optional)`.

3. **Bổ sung Mục mở rộng (Expandable Custom CV Section) bên dưới ô "Sync my saved CV"**:
   - Ngay bên dưới hộp kiểm `Sync my saved CV with this interview`:
     - Đặt thanh dẫn hướng nhỏ gọn đồng bộ phong cách với trang Profile (`.cv-or-divider`):
       **`OR customize a CV for this interview`**
     - Ngay dưới thanh dẫn hướng là **Khối mở rộng (`#custom-cv-expander`)**:
       - **Thanh tiêu đề đóng/mở (Toggle Header Button)**: Hiển thị nhãn **`Input a custom CV for this interview`** kèm dòng mô tả ngắn (*"Expand to enter 4 CV sections or upload a PDF specifically for this session"*) và biểu tượng mũi tên đóng/mở (`▾`).
       - **Nội dung bên trong khi mở rộng (Expanded Panel)**: Sử dụng **cùng bố cục chuẩn của phần Your CV trên trang Profile**:
         1. **4 mục văn bản xếp lớp ngang (`.profile-cv-stack`)**: *01. Personal Profile*, *02. Education History*, *03. Work & Research Experience*, *04. Core Skills* (được điền sẵn bản nháp hoặc cho phép chỉnh sửa riêng cho buổi phỏng vấn này).
         2. **Vạch ngăn cách `.cv-or-divider`**: **`OR you can upload your CV`**.
         3. **Khối tải file PDF (`.cv-pdf-dropzone` & `.cv-pdf-card`)**: Cho phép kéo-thả hoặc chọn file `.pdf` riêng cho buổi phỏng vấn này.
       - **Tương tác thông minh với `Sync my saved CV`**:
         - Khi người dùng bấm mở rộng mục nhập CV riêng, hệ thống có thể tự động bỏ tích `Sync my saved CV` (hoặc khi người dùng sửa CV trong mục mở rộng này, buổi phỏng vấn mới tạo qua `startInterview()` sẽ lấy trực tiếp dữ liệu CV tùy chỉnh của buổi phỏng vấn đó thay vì CV mặc định trong Profile).

---

### 3. Danh sách file sẽ cập nhật khi triển khai
1. **`poc/cv.html`**: Xóa file `poc/cv.html`.
2. **`poc/job-profile.html`**:
   - Xóa `.page-heading` bên ngoài, đưa tiêu đề `<h2>Job Profile</h2>` vào trong `.panel`.
   - Xóa `<p class="demo-note">The link is saved for this demo; its contents are not imported.</p>`.
   - Bổ sung vạch dẫn **`OR customize a CV for this interview`** và khối đóng/mở `#custom-cv-expander` chứa bố cục 4 mục CV + tải file PDF ngay dưới `#sync-cv`.
   - Xóa nút `Input CV (Optional)` ở `.form-bottom`.
3. **`poc/css/styles.css`**:
   - Thêm style cho khối đóng/mở `.custom-cv-expander`, nút `.custom-cv-toggle`, hiệu ứng xoay mũi tên `.expander-chevron` và khung nội dung `.custom-cv-body`.
4. **`poc/js/app.js`**:
   - Gỡ bỏ đoạn xử lý `if (page === "cv")` cũ.
   - Cập nhật `if (page === "job-profile")`: xử lý đóng/mở `#custom-cv-expander`, xử lý tải file PDF riêng cho buổi phỏng vấn, và lưu bộ CV tùy chỉnh vào buổi phỏng vấn mới khi bấm `Continue →`.

---

### 4. Trạng thái
- **DONE** — Đã hoàn thành triển khai phiên bản đầu tiên.

---

## [DONE] Tinh gọn nút mở rộng (Extend Trigger) mục Custom CV trên trang Job Profile: Loại bỏ khung Panel lồng nhau, dùng thanh dẫn tương tác trực tiếp (Interactive Divider / Inline Trigger)

### 1. Thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
  - **Loại bỏ khung hộp panel lồng nhau (`poc/job-profile.html`, `poc/css/styles.css`)**:
    - Xóa bỏ khối hộp viền `.custom-cv-expander` và 2 dòng tiêu đề rườm rà.
    - Thay thế bằng **thanh phân cách tương tác duy nhất (`.cv-extend-divider`)**:
      `──────────  OR use a custom CV for this interview ▾  ──────────`
    - Nút `.cv-extend-trigger` dạng chữ hoa tinh tế nằm ngay giữa vạch phân cách, đổi màu và xoay mũi tên mượt mà (`▴ / ▾`) khi hover và click.
  - **Trải rộng tự nhiên trên mặt Panel chính**:
    - Khi mở rộng, khung 4 mục CV (*01 Personal Profile*, *02 Education History*, *03 Work & Research Experience*, *04 Core Skills*) và vùng tải PDF mở trực tiếp ngay trên bề mặt của form panel chính, không còn bị bó hẹp trong viền hộp lồng nhau.

---

### 2. Giải pháp thiết kế mới (Tinh gọn, không đóng khung Panel phụ)
Thay vì tách rời vạch chữ hướng dẫn và một khung hộp nút bấm cồng kềnh, **gộp trực tiếp dòng dẫn hướng và nút mở rộng thành một thanh phân cách tương tác duy nhất (Interactive Divider Toggle)**:
1. **Khi đang thu gọn (Collapsed)**:
   - Ngay bên dưới hộp kiểm `Sync my saved CV with this interview`, chỉ hiển thị **một đường kẻ phân cách ngang mảnh mai** (`.cv-extend-divider`) với nút chữ tương tác nằm ngay chính giữa hai đường kẻ (không có khung hộp panel bao quanh):
     `──────────  OR use a custom CV for this interview ▾  ──────────`
   - Khi di chuột vào dòng chữ `OR use a custom CV for this interview ▾`, chữ và mũi tên đổi màu sắc nét (`var(--ink)`), cho biết có thể bấm trực tiếp để mở rộng.
2. **Khi bấm mở rộng (Expanded)**:
   - Mũi tên `▾` xoay nhẹ thành `▴`.
   - Khung nhập **4 mục CV + tải file PDF** mở ra **trực tiếp trên nền `.panel` chính** (loại bỏ hoàn toàn viền hộp `.custom-cv-expander` và nền lồng nhau), giúp 4 mục CV và vùng tải PDF trải rộng tự nhiên, thoáng đãng giống hệt phần **Your CV** trên trang Profile.

---

### 3. Danh sách file sẽ cập nhật khi triển khai
1. **`poc/job-profile.html`**:
   - Xóa bỏ cấu trúc hộp `.custom-cv-expander` và 2 dòng tiêu đề phụ rườm rà.
   - Thay bằng thanh phân cách tương tác gọn nhẹ:
     ```html
     <div class="cv-extend-divider">
       <button type="button" class="cv-extend-trigger" id="custom-cv-toggle" aria-expanded="false" aria-controls="custom-cv-body">
         <span>OR use a custom CV for this interview</span>
         <span class="expander-chevron" aria-hidden="true">▾</span>
       </button>
     </div>
     ```
   - Khối `#custom-cv-body` nằm ngay bên dưới, hiển thị trực tiếp trên mặt panel chính mà không bị đóng khung lồng nhau.
2. **`poc/css/styles.css`**:
   - Thay thế các class `.custom-cv-expander`, `.custom-cv-toggle` cũ bằng `.cv-extend-divider` và `.cv-extend-trigger` (chữ thuần túy kết hợp đường kẻ mảnh 2 bên, hiệu ứng xoay mũi tên mượt mà).

---

### 4. Trạng thái
- **DONE** — Đã hoàn thành triển khai và kiểm thử.

---

## [DONE] Xóa các nhãn & chú thích Demo thừa trên trang Sign In, Sign Up và Footer toàn trang

### 1. Thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
  - **`poc/sign-in.html`**: Đã xóa hoàn toàn huy hiệu `<span class="badge">POC DEMO</span>` và dòng ghi chú `<p class="demo-note">Sample account prefilled · No real authentication.</p>`.
  - **`poc/sign-up.html`**: Đã xóa hoàn toàn huy hiệu `<span class="badge">POC DEMO</span>` và dòng ghi chú `<p class="demo-note">Demo account only · Passwords are not saved.</p>`.
  - **Footer toàn bộ 13 trang HTML**: Đã xóa hoàn toàn cụm `<span>Local demo · Sample data</span>` trong `<footer class="site-footer">` trên tất cả các trang.

---

## [DONE] Thiết kế lại trang Your Interview (`poc/storage.html`) — Bản cập nhật: Giữ cột Status rõ ràng, lấp đầy không gian lớn bằng bố cục 4 cột cân đối & Xóa nút Back to home

### 1. Thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
  - **Khôi phục toàn khung (`1120px`) & Xóa nút `Back to home` (`poc/storage.html`)**:
    - Trả lại container chuẩn `.page.storage-page` (`1120px`) giúp giao diện bề thế, tận dụng tối đa không gian màn hình lớn.
    - Xóa bỏ nút phụ `Back to home` ở cuối trang.
  - **Thanh Header tích hợp Thống kê & Nút Tạo Mới (`.storage-header`)**:
    - Hiển thị tiêu đề **`Your Interviews`** kết hợp huy hiệu thống kê động (`#storage-stats`: đếm tổng số buổi, số buổi Finished và In Progress).
    - Bổ sung nút hành động **`+ New interview`** ở góc phải dẫn thẳng tới `job-profile.html`.
  - **Duy trì đủ 4 Cột chuẩn xác (`NAME` | `DATE` | `STATUS` | `ACTIONS`)**:
    - Cột **`STATUS`** đứng độc lập, căn thẳng tắp với nhãn tiêu đề `STATUS` ở thanh header lưới.
    - Phân bổ tỷ lệ cột cân đối (`grid-template-columns: minmax(260px, 2.2fr) minmax(140px, 1.1fr) minmax(150px, 1.1fr) 220px`) cho cả thanh tiêu đề lưới `.storage-grid-head` và từng hàng `.storage-row-card`.
    - Xóa sổ hoàn toàn khoảng trống mênh mông: cột `Actions` co lại vừa vặn `220px` chứa gọn gàng cặp 2 nút đồng bộ chiều cao `38px` (**`View report` / `Continue`** với chiều rộng cố định `114px` + nút **`Delete`** viền mảnh hoạt động thật).
  - **Từng hàng phỏng vấn dạng Card Row (`.storage-row-card`)**:
    - Mỗi buổi phỏng vấn là một hàng thẻ sang trọng, bo góc `14px`, nền dịu `#f8fbfa` có icon đại diện buổi phỏng vấn nổi bật. Tự động hiển thị màn hình trống thân thiện nếu xóa hết dữ liệu.

---

### 2. Giải pháp thiết kế mới (Full-Width 1120px + 4 Cột Rõ Ràng + Hàng Thẻ Nổi Bật)

1. **Xóa nút `Back to home` & Giữ độ rộng toàn khung (`.page`, `max-width: 1120px`)**:
   - Xóa hoàn toàn `<div class="actions"><a class="btn btn-secondary" href="dashboard.html">Back to home</a></div>` ở cuối trang.
   - Trả lại độ rộng chuẩn `.page` (`1120px`) để giao diện bề thế, tận dụng tốt không gian màn hình lớn.

2. **Thanh Header của Panel kết hợp Thống kê & Nút Tạo Mới (`.storage-header`)**:
   - Bên trái: Tiêu đề **`Your Interviews`** kèm dòng mô tả ngắn hoặc bộ đếm số buổi phỏng vấn (ví dụ: huy hiệu `4 sessions` / `3 Finished · 1 Unfinished`).
   - Bên phải: Nút hành động **`+ New interview`** dẫn tới `job-profile.html`, giúp phần đầu bảng đầy đặn, có chiều sâu và hữu ích.

3. **Giữ nguyên 4 Cột rõ ràng (`NAME` | `DATE` | `STATUS` | `ACTIONS`) nhưng phân bổ tỷ lệ cột cân đối**:
   - Sử dụng lưới 4 cột chuẩn xác (`grid-template-columns: minmax(260px, 2.2fr) minmax(150px, 1.1fr) minmax(160px, 1.1fr) 230px`) cho cả **Thanh tiêu đề cột (`.storage-grid-head`)** lẫn **Từng hàng phỏng vấn (`.storage-row-card`)**:
     - **Cột 1 — `INTERVIEW NAME`**: Có icon đại diện buổi phỏng vấn (khung vuông bo góc màu xanh nhạt chứa icon mic/chat) + Tên buổi phỏng vấn in đậm (`Interview 1`) + nhãn phụ (`Mock Interview Session`).
     - **Cột 2 — `DATE`**: Hiển thị ngày tháng rõ ràng (`29/2/2026`).
     - **Cột 3 — `STATUS` (Cột độc lập có tiêu đề `STATUS` phía trên)**: Hiển thị huy hiệu trạng thái `● Finished` (xanh lá) hoặc `● Unfinished` (vàng hổ phách) căn thẳng hàng dọc theo đúng cột `STATUS`.
     - **Cột 4 — `ACTIONS` (`230px` vừa khít 2 nút)**:
       - Nhờ 3 cột `Name`, `Date`, `Status` được giãn đều hợp lý trên mặt bằng `1120px` và cột `Actions` có độ rộng cố định vừa khít cụm 2 nút (`230px`), khoảng cách giữa cột `Status` và 2 nút bấm trở nên cân đối tự nhiên, không còn khoảng trắng thừa.
       - **Thiết kế lại 2 nút đồng bộ, sắc nét**:
         - Nút 1 (**`View report`** / **`Continue`**): Độ rộng đồng nhất (`116px`), chiều cao `38px`, bo góc `10px`, nền màu nhấn rõ ràng để tất cả các hàng thẳng tắp từ trên xuống dưới.
         - Nút 2 (**`Delete`**): Không còn là chữ trôi nổi hay nút bị mờ, mà là nút viền mảnh đồng bộ chiều cao `38px` (`border: 1px solid var(--line)`, bo góc `10px`), khi di chuột vào chuyển sang viền và nền đỏ nhạt (`var(--danger)`), tạo thành một cặp nút song hành cân xứng.
   - **Từng hàng phỏng vấn dạng Card Row (`.storage-row-card`)**:
     - Thay vì các đường gạch mảnh đơn điệu trên nền trắng trống trải, mỗi dòng phỏng vấn là một dải thẻ nổi nhẹ (`background: #f8fbfa`, `border: 1px solid var(--line)`, `border-radius: 14px`, cách nhau `12px`), nổi bật hiệu ứng khi di chuột qua.

---

### 3. Danh sách file sẽ cập nhật khi triển khai
1. **`poc/storage.html`**:
   - Khôi phục `.page` (`1120px`), xóa nút `Back to home`.
   - Thêm `.storage-header` (tiêu đề + thống kê nhanh + nút `+ New interview`) và `.storage-grid-head` với đủ 4 cột `INTERVIEW NAME`, `DATE`, `STATUS`, `ACTIONS`.
2. **`poc/css/styles.css`**:
   - Định nghĩa lưới 4 cột `.storage-grid-head` và `.storage-row-card` (`grid-template-columns: minmax(260px, 2.2fr) minmax(150px, 1.1fr) minmax(160px, 1.1fr) 230px`), style thẻ hàng `.storage-row-card`, icon buổi phỏng vấn `.session-badge-icon`, và cặp nút `.btn-session-action` + `.btn-session-delete` đồng bộ kích thước.
3. **`poc/js/app.js`**:
   - Cập nhật `renderInterviews()` để render đủ 4 cột (`Name + icon`, `Date`, `Status`, `Actions`), cập nhật số lượng thống kê trên header và giữ tính năng xóa trực tiếp khi bấm `Delete`.

---

### 4. Trạng thái
- **DONE** — Đã hoàn thành triển khai phiên bản trước.

---

## [DONE] Tinh chỉnh lại trang Your Interview (`poc/storage.html`): Bỏ các chi tiết thừa, bỏ khung hộp từng dòng & Bo tròn (Pill) cặp nút thao tác

### 1. Các thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
1. **Loại bỏ các nhãn & nút phụ thừa**:
   - **Trên thanh Header của Panel (`.storage-header`)**:
     - Đã xóa huy hiệu thống kê `#storage-stats` (*"10 sessions · 6 Finished, 4 In Progress"*).
     - Đã xóa nút `+ New interview` ở góc phải, giữ lại tiêu đề **`<h2>Your Interviews</h2>`** tinh gọn, chuẩn xác.
   - **Trên từng dòng phỏng vấn**:
     - Đã xóa dòng chữ phụ `AI Interview Session` (`.session-subtext`) dưới tên buổi phỏng vấn.
     - Đã xóa biểu tượng chat (`.session-icon-badge`) phía trước tên buổi phỏng vấn, chỉ hiển thị trực tiếp tên buổi phỏng vấn (`.session-title`).
     - Đổi tên tiêu đề cột đầu tiên thành `Name`.
2. **Bỏ khung hộp bao quanh từng dòng (`.storage-row-card`)**:
   - Chuyển các dòng từ dạng đóng hộp viền (`background: #f8fbfa; border: 1px solid var(--line); border-radius: 14px`) sang hàng phẳng thanh lịch trên mặt panel trắng (`background: transparent; border-bottom: 1px solid #e8eeea`), đồng bộ padding với tiêu đề cột.
   - Vẫn duy trì hoàn hảo **lưới 4 cột cân xứng** (`grid-template-columns: minmax(260px, 2.2fr) minmax(140px, 1.1fr) minmax(150px, 1.1fr) 220px`).
3. **Bo tròn hoàn toàn (Pill Shape) cho cặp nút thao tác**:
   - Cập nhật cả 2 nút **`.btn-session-action`** (`View report` / `Continue`) và **`.btn-session-delete`** (`Delete`) sang bo cong mềm mại **`border-radius: 999px`**, kết hợp hài hòa với huy hiệu trạng thái `.status`.

---

### 2. Danh sách file đã cập nhật
1. **`poc/storage.html`**: Xóa `#storage-stats` và nút `+ New interview`, đổi nhãn cột đầu thành `Name`.
2. **`poc/js/app.js`**: Bỏ tạo badge icon và subtext trong `renderInterviews()`, loại bỏ thao tác với `#storage-stats`.
3. **`poc/css/styles.css`**: Làm phẳng hàng bảng, xóa border-radius hộp dòng và đặt `border-radius: 999px` cho cặp nút thao tác.

---

### 3. Trạng thái
- **DONE** — Đã hoàn thành triển khai phiên bản trước.

---

## [DONE] Thiết kế lại các trang Interview (`poc/interview-1.html`, `poc/interview-2.html`, `poc/interview-3.html`): Xử lý tiêu đề thừa, xóa ghi chú Demo & Tối ưu bố cục Câu hỏi – Trả lời

### 1. Các thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
1. **Loại bỏ tiêu đề `<h1>Interview</h1>` ngoài khung & Gom vào Header của Panel (`.interview-header`)**:
   - Đã xóa hoàn toàn khối `<div class="interview-top">` ngoài trang.
   - Bên trong `.interview-panel`, đưa vào thanh **`.interview-header`** tinh gọn: bên trái là tiêu đề câu hỏi **`<h2>Question X</h2>`** kèm huy hiệu `X of 3`, bên phải là thanh tiến trình số **`.step-track`** (`1 — 2 — 3`) căn thẳng hàng ngang hoàn hảo.
2. **Xóa sạch các dòng chú thích Demo thừa**:
   - Đã xóa ghi chú `<small id="mic-note">Not interactive in this PoC</small>` dưới nút Microphone.
   - Đã xóa thông báo `<span class="demo-note" id="answer-status">Answers are saved in this demo.</span>` ở cuối trang và loại bỏ dòng cập nhật tương ứng trong `poc/js/app.js`.
3. **Tối ưu bố cục Câu hỏi & Ô nhập câu trả lời Full-Width**:
   - **Khối Câu hỏi (`.question`)**: Giữ trọn chiều rộng 100%, viền điểm nhấn bên trái màu `var(--aqua)`, bo góc `12px` êm ái và cỡ chữ `17px` dễ đọc.
   - **Khu vực Trả lời (`.answer-section`)**:
     - Tạo thanh tiêu đề `.answer-header`: nhãn **`Your Answer`** bên trái, nút **`Microphone`** (`.btn-mic` bo tròn viên thuốc nhỏ gọn) bên phải.
     - Ô `<textarea>` mở rộng `100%` thẳng hàng tuyệt đối với khối câu hỏi bên trên, không còn bị khuyết một góc trống thừa `146px` như trước.
   - **Thanh điều hướng dưới cùng (`.interview-navigation`)**:
     - Tích hợp nút **`Save and Quit`** (dạng pill đỏ dịu `.btn-danger-subtle`) trực tiếp vào góc trái bên trong panel.
     - Cụm nút chuyển câu (`← Previous Question` và `Next Question →` / `Finalize Interview`) đặt gọn gàng ở góc phải.

---

### 2. Danh sách file đã cập nhật
1. **`poc/interview-1.html`, `poc/interview-2.html`, `poc/interview-3.html`, `poc/interview-interrupt.html`**: Cập nhật cấu trúc Header, Question, Answer và Navigation mới; xóa toàn bộ các ghi chú demo thừa.
2. **`poc/css/styles.css`**: Viết lại hệ thống CSS cho `.interview-header`, `.interview-step-badge`, `.answer-section`, `.btn-mic`, `<textarea>` full-width, `.interview-navigation`, và `.btn-danger-subtle`.
3. **`poc/js/app.js`**: Loại bỏ thao tác cập nhật `#answer-status`.

---

### 3. Trạng thái
- **DONE** — Đã hoàn thành triển khai phiên bản trước.

---

## [DONE] Hợp nhất 3 trang Câu hỏi thành 1 trang `poc/interview.html` duy nhất & Thiết kế lại nút Microphone nổi bật, rõ ràng

### 1. Giải pháp đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
1. **Hợp nhất thành 1 trang động duy nhất (`poc/interview.html`)**:
   - Đã tạo `poc/interview.html` và xóa bỏ hoàn toàn 3 file tĩnh dư thừa (`poc/interview-1.html`, `poc/interview-2.html`, `poc/interview-3.html`).
   - Cập nhật toàn bộ liên kết điều hướng từ `poc/job-profile.html` và `poc/storage.html` trỏ về `poc/interview.html`.
   - Trong `poc/js/app.js`: Xây dựng bộ điều khiển phỏng vấn động linh hoạt:
     - Tự động đọc và render câu hỏi từ `window.POC_DATA.questions`.
     - Cho phép nhảy qua lại giữa các câu hỏi bằng nút **`Next Question →`**, **`← Previous Question`**, hoặc **click trực tiếp vào từng bước số `1`, `2`, `3`** trên thanh tiến trình `.step-track`.
     - Tự động lưu câu trả lời vào bộ nhớ và đếm số ký tự trực tiếp (`X characters`).
     - Ở câu hỏi cuối cùng (Question 3), nút tiếp theo tự động đổi thành **`Finalize Interview`** để lưu và hoàn tất phiên phỏng vấn.
2. **Thiết kế lại khu vực Microphone nổi bật, thu hút & tương tác trực tiếp (`.answer-composer` + `.composer-voice-dock`)**:
   - Tích hợp ô nhập chữ và khu vực thu âm thành một khối hộp thống nhất `.answer-composer`.
   - Bổ sung thanh công cụ giọng nói `.composer-voice-dock` với nút **`.btn-mic-hero`** nổi bật:
     - Icon Microphone đặt trong vòng tròn màu xanh teal đậm `40px × 40px` nổi bật.
     - Tiêu đề chữ đậm rõ nét **`Record Answer with Microphone`** kèm phụ đề hướng dẫn.
     - Cụm dải sóng âm `.voice-waveform` chuyển động trực quan.
     - **Hiệu ứng thu âm mô phỏng sống động**: Khi click vào nút Mic, nút chuyển sang trạng thái `.is-recording` (vòng đỏ xung nhịp `mic-pulse`, dải sóng âm nhấp nhô, và tự động điền câu nói mẫu sau 2.4 giây). Bấm lần nữa để dừng thu âm.

---

### 2. Danh sách file đã cập nhật
1. **`poc/interview.html`**: Trang phỏng vấn động duy nhất với đầy đủ cấu trúc composer, voice dock và step buttons.
2. **`poc/interview-1.html`, poc/interview-2.html, poc/interview-3.html`**: Đã xóa bỏ an toàn.
3. **`poc/job-profile.html` & `poc/storage.html`**: Đổi luồng truy cập sang `interview.html`.
4. **`poc/js/app.js`**: Viết bộ điều khiển chuyển đổi câu hỏi động và tương tác microphone.
5. **`poc/css/styles.css`**: Styling cho `.answer-composer`, `.composer-voice-dock`, `.btn-mic-hero`, và hiệu ứng sóng âm/nhịp thở.

---

### 3. Trạng thái
- **DONE** — Đã hoàn thành triển khai phiên bản trước.

---

## [DONE] Tinh chỉnh trang Interview (`poc/interview.html`): Thay vòng tròn bước bằng huy hiệu `1 of 3` bên phải, bỏ nút Save & Quit và tự động bật màn hình Save khi thoát, đồng bộ màu & căn giữa 2 nút Prev/Next

### 1. Các thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
1. **Thay vòng tròn `1 — 2 — 3` bằng huy hiệu `1 of 3` nằm bên phải Header**:
   - Đã xóa bỏ cụm `.step-track` (`1 — 2 — 3` circles) giúp giao diện co giãn tối ưu khi phỏng vấn có số lượng câu hỏi lớn (kể cả 25+ câu).
   - Đặt tiêu đề `<h2 id="question-title">Question 1</h2>` ở bên trái và huy hiệu `<span class="interview-step-badge" id="question-badge">1 of 3</span>` bo cong tinh tế ở bên phải của `.interview-header`.
2. **Xóa nút `Save and Quit` & Tự động bật màn hình Save and Exit khi người dùng thoát**:
   - Xóa bỏ nút `Save and Quit` khỏi `.interview-navigation`.
   - Mỗi khi người dùng bấm vào các mục điều hướng ở header (Logo, Dashboard, Your interview, System feedback, Profile) hoặc nút Back của trình duyệt, hệ thống tự động lưu câu trả lời hiện tại và hiển thị ngay hộp thoại **Saved Dialog** (`#interview-exit-modal`: *"Your interview has been saved as..."*) kèm nút điều hướng an toàn.
3. **Đồng bộ màu sắc & Căn giữa 2 nút `← Previous Question` và `Next Question →`**:
   - Chuyển 2 nút sang dạng bo tròn hoàn toàn (pill shape `border-radius: 999px`).
   - Sử dụng gam màu trắng tinh tế kết hợp viền xanh lam nhạt (`background: #ffffff; border: 1.5px solid #b8d7dc; color: #245b65`), khi hover chuyển sang sắc xanh băng dịu nhẹ (`background: #f0f8f9`).
   - Căn giữa toàn bộ thanh `.interview-navigation` (`justify-content: center`).

---

### 2. Danh sách file đã cập nhật
1. **`poc/interview.html`**: Đưa `1 of 3` sang phải, xóa `.step-track`, xóa nút `Save and Quit`, tích hợp `#interview-exit-modal`.
2. **`poc/css/styles.css`**: Căn lề `.interview-header` (trái/phải), định dạng badge `1 of 3` lớn rõ, căn giữa `.interview-navigation`.
3. **`poc/js/app.js`**: Cập nhật controller render bước `1 of 3`, tự động bắt sự kiện thoát trang để lưu và bật popup xác nhận đã lưu.

---

### 3. Trạng thái
- **DONE** — Đã hoàn thành triển khai phiên bản trước.

---

## [DONE] Thiết kế lại trang Report (`poc/report.html`) & Hợp nhất trang CV Feedback (`poc/cv-feedback.html`): Làm nổi bật tên buổi phỏng vấn, xóa ghi chú thừa & Thiết kế bố cục CV 2 cột (Trái: 4 mục hoặc PDF / Phải: Nhận xét dạng bài viết)

### 1. Các thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
1. **Hợp nhất hoàn toàn CV Feedback vào `poc/report.html` & Xóa file `poc/cv-feedback.html`**:
   - Đã xóa an toàn file `poc/cv-feedback.html` và gỡ bỏ nút `View CV feedback` ở cuối trang báo cáo.
   - Toàn bộ kết quả phỏng vấn và đánh giá CV nay được xem tập trung, liền mạch trên một trang báo cáo duy nhất.
2. **Khắc phục vấn đề Tiêu đề & Làm nổi bật Tên Buổi Phỏng Vấn (`#report-name`)**:
   - Xóa bỏ khối tiêu đề `<h1>Report</h1>` trôi nổi kèm subtitle mờ nhạt.
   - Thay thế bằng **Thanh Tiêu Đề Báo Cáo Nổi Bật (`.report-hero-bar`)**:
     - Hiển thị nhãn huy hiệu `INTERVIEW REPORT` phía trên.
     - Tên buổi phỏng vấn (**`<h1 id="report-name">...</h1>`**, ví dụ: `New Interview 6`) trở thành tiêu đề chính cỡ lớn (`26px`, in đậm nổi bật).
     - Phía bên phải hiển thị ngày thực hiện (`#report-date`) và huy hiệu trạng thái `Finished` đồng bộ, sang trọng.
3. **Xóa toàn bộ các dòng ghi chú Demo thừa**:
   - Xóa bỏ banner `<p class="sample-banner">Sample feedback from the design · No AI analysis is performed.</p>`.
   - Xóa bỏ tất cả các nhãn `<span class="sample-tag">Sample</span>` trong các thẻ câu trả lời.
4. **Thiết kế lại bố cục CV Feedback chia 2 cột Trái – Phải (`.cv-report-split`)**:
   - Đặt trong khung `.panel.cv-report-panel` ngay dưới phần Interview Q&A:
     - **Cột Trái — CV của người dùng (`.cv-report-left`)**:
       - Hỗ trợ cả 2 định dạng: **4 Mục có cấu trúc** (`.cv-document-sheet`) hoặc **Bản xem trước tài liệu PDF** (`.cv-pdf-preview-sheet` hiển thị tên file PDF, dung lượng, và trang giấy tài liệu).
       - Có bộ nút chuyển đổi linh hoạt `4 Sections View` / `PDF Document View` ở thanh tiêu đề giúp dễ dàng xem trước cả hai chế độ.
     - **Cột Phải — Đánh giá của hệ thống (`.cv-report-right`)**:
       - Bỏ hoàn toàn các hộp xám `.feedback-block` nặng nề.
       - Trình bày dạng bài viết đánh giá chuyên sâu (`.cv-editorial-feedback`) gồm tiêu đề chính **`Our Feedback`** và các tiểu mục rõ ràng (`<h4>` + đoạn văn `<p>`), giúp trải nghiệm đọc thông suốt và trực quan.

---

### 2. Danh sách file đã cập nhật
1. **`poc/cv-feedback.html`**: Đã xóa bỏ an toàn.
2. **`poc/report.html`**: Tái cấu trúc thanh Hero Bar, xóa ghi chú demo, thêm phần CV Feedback 2 cột (Trái: 4 mục / PDF, Phải: Nhận xét dạng bài viết).
3. **`poc/css/styles.css`**: Styling cho `.report-hero-bar`, `.cv-report-panel`, `.cv-report-split`, `.cv-document-sheet`, `.cv-pdf-preview-sheet`, và `.cv-editorial-feedback`.
4. **`poc/js/app.js`**: Hỗ trợ lưu trữ `cvPdf` khi bắt đầu phỏng vấn, liên kết dữ liệu và bộ chuyển đổi hiển thị CV trên trang Report.

---

### 3. Trạng thái
- **DONE** — Đã hoàn thành triển khai phiên bản trước.

---

## [DONE] Tinh chỉnh trang Report (`poc/report.html`) & Cơ chế Loại Trừ Lẫn Nhau (Mutual Exclusivity) giữa 4 mục CV và tải file PDF trên toàn hệ thống

### 1. Các thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
1. **Tinh chỉnh trang Report (`poc/report.html`)**:
   - Đã xóa bỏ hoàn toàn 2 nút `Back to home` và `View all interviews` ở cuối trang.
   - Xóa bỏ trạng thái `Status: Finished` trong `.report-hero-bar`, chỉ giữ lại thông tin ngày tháng sạch sẽ.
   - Xóa bỏ các nhãn phụ thừa: `#cv-format-indicator` và `.editorial-subtext` (*AI Comprehensive Assessment*).
   - Xóa bỏ bộ nút chuyển đổi thủ công (`4 Sections View` / `PDF Document View`).
   - Cột bên trái tự động hiển thị đúng định dạng CV mà buổi phỏng vấn đã dùng (PDF hoặc 4 mục văn bản).
2. **Cơ chế Loại Trừ Lẫn Nhau (Mutual Exclusivity) khi nhập CV (Chỉ thay đổi hành vi, giữ nguyên layout)**:
   - **Trên trang Profile (`poc/profile.html` — `#your-cv`)**:
     - Bấm vào nút tải PDF hoặc tải/kéo thả file PDF: Tự động xóa sạch cả 4 ô mục CV văn bản (`account.cv = ["", "", "", ""]`), chuyển chế độ sang PDF và lưu lại.
     - Gõ chữ vào bất kỳ ô nào trong 4 mục CV hoặc bấm `Save CV`: Tự động xóa file PDF đang đính kèm (`account.cvPdf = null`) và chuyển về chế độ văn bản.
   - **Trên trang Job Profile (`poc/job-profile.html` — `#custom-cv-body`)**:
     - Bấm vào nút tải PDF hoặc tải/kéo thả file PDF tùy chỉnh: Tự động xóa sạch cả 4 ô mục CV tùy chỉnh.
     - Gõ chữ vào bất kỳ ô nào trong 4 mục CV tùy chỉnh: Tự động xóa file PDF tùy chỉnh đang đính kèm.
     - Khi bấm bắt đầu phỏng vấn: Lưu chính xác định dạng PDF hoặc 4 mục mà người dùng đã chọn.

---

### 2. Danh sách file đã cập nhật
1. **`poc/report.html`**: Xóa nút điều hướng đáy trang, xóa trạng thái Finished, xóa các nhãn phụ thừa và bộ nút chuyển đổi thủ công.
2. **`poc/css/styles.css`**: Dọn dẹp các class toggle view và format badge trong `.cv-report-header`.
3. **`poc/js/app.js`**: Triển khai cơ chế xóa trắng lẫn nhau giữa 4 mục CV và file PDF trên cả `profile` và `job-profile`; tự động hiển thị định dạng CV tương ứng trên trang `report`.

---

### 3. Trạng thái
- **DONE** — Đã hoàn thành triển khai và kiểm thử.

---

## [DONE] Tinh chỉnh Màn hình Ngắt Phỏng vấn (Interrupt Interview Modal): Làm mờ Toàn Trang (Full-Page Blur) & Đồng bộ Nút `Proceed`

### 1. Các thay đổi đã triển khai
- **Trạng thái: DONE (Đã hoàn thành)**
1. **Làm mờ Toàn Trang (Full-Page Blur Overlay)**:
   - Di chuyển phần tử `.dialog-backdrop` (`#interview-exit-modal`) ra khỏi `<main class="page">` (đặt trực tiếp dưới `<body>`) trên cả `poc/interview.html` và `poc/interview-interrupt.html` để không bị giới hạn vùng hiển thị bởi `transform` của `.page`.
   - Cập nhật `@keyframes page-enter` kết thúc ở `transform: none` thay vì `transform: translateY(0)`.
   - Tăng `z-index` của `.dialog-backdrop` lên `200` (cao hơn `.site-header` có `z-index: 50`), kết hợp `width: 100vw; height: 100vh; backdrop-filter: blur(5px)` giúp làm mờ toàn bộ màn hình (bao gồm cả thanh header, nội dung giữa và footer).
2. **Đồng bộ nhãn nút bấm thành `Proceed` trong mọi trường hợp**:
   - Đổi văn bản mặc định của nút `#exit-modal-confirm-btn` trên `poc/interview.html` và `poc/interview-interrupt.html` từ `Back to home` thành **`Proceed`**.
   - Trong `poc/js/app.js` (`triggerSaveAndExit`), luôn gán `exitModalConfirmBtn.textContent = "Proceed"` bất kể người dùng bấm thoát về Dashboard hay bất kỳ trang nào khác.

---

### 2. Danh sách file đã cập nhật
1. **`poc/interview.html`**: Đưa `#interview-exit-modal` ra cấp `body` và đổi nhãn nút thành `Proceed`.
2. **`poc/interview-interrupt.html`**: Đưa `.dialog-backdrop` ra cấp `body`, đồng bộ giao diện nền và đổi nhãn nút thành `Proceed`.
3. **`poc/css/styles.css`**: Nâng `z-index: 200`, `100vw/100vh`, `backdrop-filter: blur(5px)` cho `.dialog-backdrop` và sửa `@keyframes page-enter` thành `transform: none`.
4. **`poc/js/app.js`**: Luôn hiển thị nhãn `Proceed` cho nút xác nhận thoát phỏng vấn.

---

## [DONE] Sửa lỗi Highlight Header trên trang Report (`poc/report.html`) & Tinh chỉnh Bố cục Hàng Dọc (Polished Vertical Row Layout) trên trang System Feedback (`poc/system-feedback.html`)

### 1. Phân tích yêu cầu điều chỉnh từ người dùng
- **Không dùng lưới 2×2 (4 hộp chia 2 bên)** vì bố cục ngang–dọc đan xen gây rối mắt khi đọc tuần tự 4 câu hỏi khảo sát.
- **Giữ nguyên bố cục hàng dọc truyền thống (1 câu mỗi hàng từ `01` đến `04`)**, nhưng **trau chuốt và làm đẹp (polish)** để trông thoáng đãng, thanh lịch và hiện đại hơn.
- Giữ nguyên các cải tiến đã thống nhất:
  - Xóa highlight/gạch chân thừa của tab `Your interview` khi đang ở trang `report.html`.
  - Xóa tiêu đề thừa `<div class="page-heading"><h1>System Feedback</h1></div>` ngoài panel.
  - Xóa câu ghi chú thừa `<p class="demo-note">Feedback is saved locally for the demo; it is not sent to a server.</p>`.
  - Đưa nút **`Submit feedback →`** ra chính giữa ở cuối khung.

---

### 2. Giải pháp thiết kế & kỹ thuật đề xuất (Polished Row Layout)

#### A. Bố cục Hàng Dọc Tinh Chỉnh (`.survey-list` & `.survey-row`)
- Đặt trong khung `.panel.survey-panel` có độ rộng vừa vặn, dễ đọc (`max-width: 860px`).
- 4 câu hỏi xếp thành **4 hàng dọc nối tiếp từ trên xuống dưới (`.survey-row`)**, ngăn cách nhau bằng đường kẻ mảnh tinh tế (`border-bottom: 1px solid #eef3f0; padding-bottom: 24px; margin-bottom: 24px`, hàng cuối không có đường kẻ):
  1. **Dòng câu hỏi (`<label class="survey-label" for="feedback-0..3">`)**:
     - Bên trái là huy hiệu số thứ tự **`.survey-number`** (`01`, `02`, `03`, `04`) dạng ô vuông bo góc màu xanh aqua dịu (`width: 30px; height: 30px; border-radius: 8px; background: rgba(146, 199, 207, 0.25); color: #245b65; font-weight: 700; font-size: 13px`).
     - Bên cạnh là nội dung câu hỏi khảo sát rõ ràng (`font-size: 15.5px; font-weight: 600; color: var(--ink); line-height: 1.5`) — không thêm bất kỳ tiêu đề phụ/nhãn chủ đề thừa nào.
  2. **Ô nhập câu trả lời (`<div class="survey-field-input"><textarea id="feedback-0..3" rows="3">`)**:
     - Căn lề trái thẳng hàng với chữ câu hỏi phía trên (`padding-left: 42px` trên Desktop để tạo cột lề số thứ tự `01`–`04` tách biệt, thoáng mắt).
     - Ô `<textarea rows="3">` có nền sáng mịn (`background: #fafcfa`), viền êm (`border: 1px solid #c9d7d5; border-radius: 12px; padding: 12px 16px`), khi focus chuyển sang nền trắng kèm viền xanh dịu nhẹ.

#### B. Nút `Submit feedback →` Căn Giữa (`.survey-actions`)
- Đặt ở dưới cùng của form (`display: flex; justify-content: center; margin-top: 28px; padding-top: 24px; border-top: 1px solid var(--line)`).
- Nút **`Submit feedback →`** bo tròn dạng viên thuốc (`border-radius: 999px; min-width: 240px`).

---

### 3. Danh sách file đã cập nhật
1. **`poc/report.html` & `poc/thank-you.html`**: Gỡ bỏ class `is-active` trên thanh điều hướng Header.
2. **`poc/js/app.js`**: Cập nhật `navMap` để chỉ highlight tab khi người dùng ở đúng trang gốc (`dashboard`, `storage`, `system-feedback`, `profile`).
3. **`poc/system-feedback.html`**: Chuyển từ lưới 2×2 về danh sách hàng dọc `.survey-list` gồm 4 `.survey-row` tinh gọn, xóa `<h1>` ngoài khung, xóa hoàn toàn `.demo-note` và căn giữa nút Submit.
4. **`poc/css/styles.css`**: Áp dụng styling bố cục hàng dọc cho `.feedback-page`, `.survey-panel`, `.survey-list`, `.survey-row`, `.survey-label`, `.survey-number`, `.survey-text`, `.survey-field-input`, và `.survey-actions`.

---

### 4. Trạng thái
- **DONE** — Đã hoàn thành triển khai và kiểm thử.

---

## [DONE] Đồng bộ màu Avatar và huy hiệu Logo trong Header

### Vấn đề hiện tại
- `assets/avatar.svg` dùng màu `#30364F` cho đầu/thân và nét viền `black`, nên trông gần như đen trên Header và trang Profile, lệch khỏi bảng màu xanh aqua – kem của giao diện.
- Logo gốc `assets/logo.svg` đã phù hợp; phần gây lệch là nền chuyển sắc rất tối (`#1B363C` → `#274C54`) của `.brand-icon` trong `css/styles.css`. Bỏ nền hoàn toàn sẽ khiến phần hình màu kem `#FBF9F1` của Logo chìm vào Header trắng.

### Giải pháp đề xuất
1. **Giữ nguyên hình dạng Logo và Avatar.** Chỉ đổi màu và lớp nền hiển thị; không vẽ lại biểu tượng, không dùng CSS filter để đổi màu ảnh.
2. **Logo Header:** thay nền tối của `.brand-icon` bằng banner-inspired blue `#6AAEB8`, giữ dạng tròn, thêm viền mảnh `#AAD7D9` và bóng rất nhẹ. Giữ `assets/logo.svg` màu gốc, tăng hình trong badge từ `22px` lên khoảng `25–26px` nếu cần.
3. **Avatar:** đổi hai phần đầu/thân `#30364F` trong `assets/avatar.svg` sang cùng lighter banner-inspired blue `#6AAEB8`; đổi nét viền ngoài màu đen sang darker blue `#4F8F9B`. Đặt nền kem `#FBF9F1` và dùng cùng darker blue cho `.header-avatar` và `.profile-avatar-wrapper` để hình rõ ở cả kích thước nhỏ trong Header lẫn kích thước lớn trên Profile. Dùng cùng một SVG cho cả hai vị trí.
4. **Tương tác:** đổi màu viền khi hover của avatar sang teal; giữ nguyên liên kết Profile, tên người dùng, trạng thái active và focus bằng bàn phím. Logo ở Sign in/Sign up và favicon tiếp tục dùng SVG gốc.

### File và cách kiểm tra khi triển khai
- `assets/avatar.svg`: đổi màu fill/stroke, giữ nguyên path và mask.
- `css/styles.css`: cập nhật `.brand-icon`, `.brand-icon img`, `.header-avatar`, `.profile-link:hover .header-avatar` và `.profile-avatar-wrapper`; không cần sửa HTML.
- Mở Dashboard, Profile, một trang Interview và Report ở kích thước desktop/mobile. Kiểm tra Logo nhận ra ngay trên Header trắng; Avatar không còn cảm giác đen; viền/bóng không quá nặng; nút Profile và Logo vẫn điều hướng đúng. Kiểm tra lại Sign in/Sign up để bảo đảm Logo gốc không bị đổi màu.

**Trạng thái:** DONE — Đã triển khai và kiểm tra tĩnh.

---

## [DONE] Tách rõ luồng quản lý CV và luồng phỏng vấn

### 1. Mục tiêu và luồng sử dụng
- **Quản lý CV:** Dashboard → Manage your CV → Profile / Your CV → Save CV.
- **Luyện phỏng vấn:** Dashboard → Job Profile + CV tùy chọn → Interview → Interview Report.
- CV được dùng làm thông tin nền cho buổi phỏng vấn; báo cáo tập trung vào câu hỏi, câu trả lời và nhận xét câu trả lời. Trong PoC, nội dung câu hỏi và nhận xét vẫn là dữ liệu mẫu theo phạm vi đã thống nhất.
- Kế hoạch này thay thế quyết định trước đây về việc gộp CV Feedback vào Report. Các mục `[DONE]` trước đó được giữ làm lịch sử thay đổi.

### 2. Thay đổi giao diện và hành vi
1. **Report chỉ hiển thị kết quả phỏng vấn** (`report.html`):
   - Xóa toàn bộ phần `#cv-report` / “CV & Resume Feedback”, gồm bản xem CV dạng 4 mục, bản xem PDF và các đoạn nhận xét CV.
   - Giữ tên buổi phỏng vấn, ngày, câu hỏi, câu trả lời và nhận xét từng câu; chỉnh khoảng cách cuối trang sau khi bỏ phần CV.
2. **Quản lý CV tập trung tại Profile → Your CV** (`profile.html`):
   - Tiếp tục dùng 4 mục văn bản hoặc tải PDF và thao tác Save CV hiện có.
   - Thay CV tại Profile chỉ cập nhật CV tài khoản; bản CV đã gắn với buổi phỏng vấn cũ vẫn là bản sao tại thời điểm bắt đầu.
3. **Một lựa chọn CV rõ ràng trong Job Profile** (`job-profile.html`):
   - Giữ lại checkbox **“Use my saved CV for this interview”** và bố cục mở rộng CV cũ; đổi dòng mở rộng thành **“Customize CV for this interview”**.
   - Khi checkbox bật, sao chép đúng định dạng văn bản hoặc PDF đã lưu khi bắt đầu; khi tắt, bắt đầu phỏng vấn không gắn CV.
   - Khi khối Customize mở, chỉ dùng trình nhập 4 mục / tải PDF tùy chỉnh; tái sử dụng quy tắc loại trừ giữa văn bản và PDF đang có.
   - Khi khối Customize mở nhưng chưa nhập nội dung hoặc chọn PDF hợp lệ, hiển thị lỗi tại khu vực CV; checkbox tắt vẫn là cách bỏ qua CV.
   - Việc mở rộng hoặc thu gọn khối không ghi đè CV tài khoản; chỉ nguồn đang chọn được gắn vào buổi phỏng vấn mới.
   - Checkbox và nút mở rộng hỗ trợ bàn phím, nhãn đọc được và trạng thái ẩn/hiện rõ ràng; giữ bố cục phù hợp desktop/mobile.
4. **Đồng bộ nội dung Dashboard** (`dashboard.html`):
   - Sửa mô tả Hero để tập trung vào luyện phỏng vấn và nhận xét câu trả lời.
   - Sửa mô tả thẻ Your interview để nói về tiếp tục buổi đang dở và xem báo cáo phỏng vấn; bỏ lời hứa về CV analysis reports.
   - Giữ Manage your CV là lối vào riêng tới `profile.html#your-cv`.

### 3. Danh sách file và công việc kỹ thuật
- `report.html`: xóa phần CV và nhận xét CV.
- `job-profile.html`: khôi phục checkbox và khối mở rộng CV cũ, với nhãn mới cho nút Customize.
- `dashboard.html`: cập nhật nội dung mô tả.
- `js/app.js`: giữ cách đọc `#sync-cv` và xử lý `#custom-cv-toggle`, cập nhật lưu form, kiểm tra dữ liệu và `startInterview` để phân biệt Saved CV, Custom CV và No CV. Gỡ phần render CV/nhận xét CV/PDF dành riêng cho Report, bảo đảm phần render kết quả phỏng vấn vẫn chạy khi các node CV đã bị xóa.
- `js/app.js`: xử lý dữ liệu đã lưu theo hướng tương thích; có thể dùng giá trị `syncCV` cũ để khởi tạo lựa chọn nếu chưa có trạng thái mới, nhưng trạng thái mới quyết định nguồn CV của buổi tiếp theo. Giữ các buổi phỏng vấn cũ và dữ liệu tài khoản.
- `css/styles.css`: thêm style nhóm chọn nguồn CV theo bảng màu hiện tại; gỡ style chỉ phục vụ phần CV trên Report sau khi kiểm tra tham chiếu. Giữ các class đang dùng chung với trình nhập CV tại Profile/Job Profile.
- `js/data.js`: kiểm tra và gỡ dữ liệu `cvFeedback` nếu không còn nơi nào sử dụng.
- `docs/README.md` và `docs/TRANSITIONS.md`: cập nhật mô tả luồng hiện tại, loại bỏ hướng dẫn mở CV Feedback và ghi nhận Report chỉ có kết quả phỏng vấn.

### 4. Tiêu chí kiểm tra khi triển khai
- Báo cáo mới và báo cáo của buổi đã lưu đều mở bình thường; tên, ngày, câu trả lời và nhận xét phỏng vấn vẫn đúng; không còn CV preview hay nhận xét CV.
- Thử checkbox Saved CV với cả văn bản và PDF, mở rộng Custom CV với cả văn bản và PDF, và checkbox tắt cho No CV; mỗi buổi chỉ lưu nguồn được chọn.
- Tài khoản chưa có CV vẫn bắt đầu phỏng vấn được; Custom CV trống có lỗi rõ ràng và không tự lấy CV tài khoản.
- Chuyển giữa các lựa chọn, tiếp tục buổi đang dở, tải lại dữ liệu tài khoản cũ và sửa CV tài khoản sau khi bắt đầu buổi mới không gây mất dữ liệu hoặc thay đổi bản CV của buổi cũ.
- Kiểm tra checkbox và nút mở rộng bằng bàn phím và trên màn hình hẹp; kiểm tra Manage your CV vẫn dẫn đúng nơi và Dashboard không còn giới thiệu CV analysis trong luồng báo cáo.

**Trạng thái:** DONE — Đã triển khai luồng và kiểm tra tĩnh. Chức năng đánh giá CV độc lập vẫn là hướng phát triển sau.

---

## [DONE] Chốt màu Header và Avatar sau khi duyệt (2026-11-02)

- Người dùng đã duyệt màu lấy cảm hứng từ banner Dashboard.
- Nền tròn Logo Header: xanh sáng `#6AAEB8`, viền `#AAD7D9`; Logo giữ màu gốc và hiển thị rộng `25px`.
- Đầu/thân Avatar: xanh sáng `#6AAEB8`, nền kem `#FBF9F1`.
- Viền tròn Avatar: xanh đậm hơn `#4F8F9B`, đồng bộ trong SVG, Header và khung Avatar lớn tại Profile; hover Header dùng cùng màu viền.
- Đã kiểm tra SVG hợp lệ và `git diff --check`. Các kiểm tra này là kiểm tra tĩnh; chưa chạy kiểm tra trình duyệt tự động trong môi trường hiện tại.

**Trạng thái:** DONE — Đã được người dùng duyệt, sẵn sàng commit và push lên `main`.


---

## [DONE] Cải thiện trải nghiệm trang Job Profile (`job-profile.html`): Ưu tiên ô dán Job Description (Link / Text / HTML) trước, ẩn 4 trường nhập tay thành mục mở rộng dự phòng

### 1. Vấn đề hiện tại & Góp ý từ Giáo sư
- Hiện tại, ngay khi mở `job-profile.html`, người dùng lập tức phải đối mặt với 4 trường nhập tay bắt buộc (`Job title`, `Domain`, `Company`, `Position`), trong khi ô `Job description link` lại nằm bên dưới như một trường phụ tùy chọn.
- Giáo sư nhận xét bố cục này chưa thân thiện với người dùng thực tế: thông thường ứng viên đã có sẵn đường dẫn (link) tin tuyển dụng, văn bản mô tả công việc (plain text) hoặc mã HTML copy từ trang tuyển dụng. Việc bắt họ tự bóc tách và gõ lại 4 trường ngay từ đầu gây tốn thời gian.
- **Yêu cầu luồng mới**:
  1. **Hiển thị đầu tiên (Mặc định)**: Cung cấp vùng nhập chính để người dùng dán trực tiếp **Job Description (văn bản thuần, HTML hoặc đường dẫn URL)** để hệ thống quét thông tin *(lưu ý: chức năng quét/bóc tách tự động chưa triển khai trong phạm vi PoC, chỉ nhận và lưu nội dung người dùng nhập)*.
  2. **Trường hợp người dùng không có sẵn JD/Link (Fallback)**: Cho phép bấm mở rộng (hoặc chuyển sang) khu vực **4 trường bắt buộc** (`Job title`, `Domain`, `Company`, `Position`) để tự điền thủ công.

### 2. Giải pháp thiết kế & Bố cục chi tiết

#### A. Khu vực 1 — Ô nhập Job Description / Link ưu tiên hiển thị đầu tiên (`#job-primary-input`)
- Đặt ngay dưới tiêu đề `<h2>Job Profile</h2>`:
  - **Trường chính — `Job Description (Link, Text, or HTML)`** (`#job-source` hoặc kết hợp ô `#job-url` + `#job-raw`):
    - Sử dụng một vùng `<textarea id="job-source" rows="5">` rộng rãi, dễ dán nội dung (hoặc kèm ô URL/Text rõ ràng) với nhãn hướng dẫn thân thiện:
      - **Label**: `Paste job description, HTML, or job link`
      - **Hint / Placeholder**: *"Paste a job posting URL (https://...), raw job description text, or copied HTML here so we can scan the role details..."*
  - Trong phạm vi PoC offline: nội dung (link, text hoặc HTML) được lưu trực tiếp vào `account.job` và gắn với buổi phỏng vấn khi bấm `Continue →` (không gọi backend hay chạy trình phân tích thực tế).

#### B. Khu vực 2 — Mục mở rộng 4 trường bắt buộc khi không có sẵn JD/Link (`#manual-job-body`)
- Ngay bên dưới ô nhập Job Description chính, đặt thanh chuyển đổi / mở rộng đồng bộ với phong cách `.cv-extend-divider` của trang:
  `──────────  Don't have a job description or link? Enter 4 fields manually ▾  ──────────`
- **Trạng thái mặc định (Collapsed / Ẩn)**:
  - Khối `.form-grid` chứa 4 trường (`#job-title`, `#domain`, `#company`, `#position`) được ẩn (`class="form-grid is-hidden"`, `aria-hidden="true"`).
  - Bỏ thuộc tính HTML `required` cứng trên 4 thẻ `<input>` khi đang ẩn để trình duyệt không chặn submit khi người dùng đã dán JD/Link ở trên.
- **Trạng thái khi người dùng bấm mở rộng (Expanded / Hiện)**:
  - Hiển thị lưới 2×2 `.form-grid` gồm 4 trường bắt buộc:
    1. **Job title** (`#job-title`)
    2. **Domain** (`#domain`)
    3. **Company** (`#company`)
    4. **Position** (`#position`)
  - Khi người dùng chọn nhập theo cách thủ công này (hoặc khi ô JD/Link phía trên để trống), hệ thống yêu cầu điền đủ 4 trường trước khi sang trang phỏng vấn.

#### C. Logic kiểm tra hợp lệ (Validation) & Tương tác trong `js/app.js`
1. **Cơ chế ưu tiên & loại trừ rõ ràng**:
   - **Cách 1 (Mặc định — Dùng JD Text / HTML / Link)**: Nếu người dùng dán nội dung vào ô Job Description (text, HTML hoặc URL) và không mở (hoặc không dùng) 4 trường thủ công → Cho phép bấm `Continue →` ngay mà không bắt nhập 4 trường.
   - **Cách 2 (Dự phòng — Không có JD/Link, nhập 4 trường bắt buộc)**: Nếu người dùng mở khung 4 trường thủ công để nhập (hoặc để trống ô JD/Link), kiểm tra bắt buộc cả 4 trường `Job title`, `Domain`, `Company`, `Position` phải có giá trị; nếu thiếu báo lỗi rõ ràng tại `#job-error`.
2. **Tương thích dữ liệu (`account.job`)**:
   - Bổ sung khóa `job-source` (hoặc giữ tương thích với `job-url` và 4 khóa `job-title`, `domain`, `company`, `position`) trong `jobKeys` của `js/app.js`.
   - Khi tải lại trang `job-profile.html`: nếu dữ liệu đã lưu trước đó chỉ có 4 trường thủ công mà không có `job-source`, tự động mở sẵn khung 4 trường để người dùng thấy dữ liệu cũ.
3. **Giữ nguyên phần chọn CV bên dưới**:
   - Checkbox `Use my saved CV for this interview` và thanh mở rộng `Customize CV for this interview` giữ nguyên vị trí và hành vi phía dưới khu vực Job Profile.

### 3. Danh sách file dự kiến cập nhật khi triển khai
1. **`job-profile.html`**:
   - Đưa vùng nhập `Paste job description, HTML, or job link` (`#job-source`) lên đầu form `#job-form`.
   - Đặt thanh mở rộng `#manual-job-toggle` (*"Don't have a job description or link? Enter details manually"*) ngay bên dưới.
   - Đưa `.form-grid` (4 trường `Job title`, `Domain`, `Company`, `Position`) vào khối `#manual-job-body` (mặc định ẩn `.is-hidden`).
2. **`css/styles.css`**:
   - Tinh chỉnh style cho vùng `#job-source` (`textarea` cỡ vừa, font dễ đọc khi dán text/HTML/URL) và khoảng cách với thanh mở rộng `#manual-job-toggle` cùng khối `.form-grid` khi mở ra.
3. **`js/app.js`**:
   - Cập nhật `jobKeys` và hàm `saveJob()` để lưu cả nội dung JD/HTML/Link lẫn 4 trường thủ công.
   - Thêm sự kiện đóng/mở cho `#manual-job-toggle` / `#manual-job-body`.
   - Cập nhật kiểm tra submit của `#job-form`: hợp lệ khi người dùng đã nhập ô JD/HTML/Link **hoặc** đã điền đủ 4 trường bắt buộc.
4. **`docs/README.md` & `docs/TRANSITIONS.md`** (nếu cần):
   - Cập nhật mô tả ngắn về luồng nhập Job Profile mới.

### 4. Trạng thái
- **DONE** — Đã triển khai và kiểm tra tĩnh.


---

## [DONE] Tinh gọn trang Job Profile (`job-profile.html`): Bỏ hoàn toàn các nút mở rộng (Extend), dùng nút bấm thường để chuyển đổi sang 4 trường Job Profile & Đơn giản hóa CV tùy chỉnh thành dán Raw Text hoặc tải PDF

### 1. Vấn đề hiện tại
- **Lạm dụng thanh mở rộng (`.cv-extend-divider` / Extend Button)**: Việc có tới 2 thanh mở rộng (`▾`) nối tiếp nhau trên cùng một trang (`Don't have a job description... ▾` và `Customize CV for this interview ▾`) làm giao diện bị rối, khi mở ra khiến trang kéo dài và chồng chéo nhiều trường.
- **Nhập Job Profile chưa dứt khoát**: Khi bấm mở rộng, cả ô dán Job Description lớn lẫn 4 trường nhập tay cùng hiển thị một lúc khiến người dùng bối rối không biết hệ thống sẽ lấy dữ liệu nào. Cần **chuyển đổi (switch)** hẳn giữa 2 chế độ bằng một **nút bấm bình thường (normal button)** kèm dòng hướng dẫn ngắn.
- **Phần Customize CV trên `job-profile.html` quá nặng nề**: Việc lặp lại nguyên 4 mục CV lớn (`01 Personal Profile` .. `04 Core Skills`) ngay trong trang Job Profile là dư thừa và nặng nề. Trên trang `job-profile.html`, nếu người dùng muốn nhập CV riêng cho buổi phỏng vấn, chỉ cần cho phép **dán văn bản CV thuần (Raw Text) hoặc tải file PDF**.

---

### 2. Giải pháp thiết kế & Bố cục chi tiết (Chỉ áp dụng trên `job-profile.html`)

#### A. Khu vực 1 — Job Profile: Chuyển đổi trực tiếp giữa 2 chế độ bằng Nút bấm thường (Không dùng Extend)
Loại bỏ hoàn toàn thanh `.cv-extend-divider` (`▾`). Tại một thời điểm chỉ hiển thị **1 trong 2 khung**:

1. **Chế độ 1 (Mặc định) — Dán Job Description / HTML / Link (`#job-paste-mode`)**:
   - Hiển thị ô `<textarea id="job-source" rows="5">` với nhãn `Paste job description, HTML, or job link`.
   - Ngay bên dưới là thanh hướng dẫn nhỏ (`.mode-switch-bar`):
     - Chữ hướng dẫn nhỏ (`.mode-switch-hint`): *"Don't have a job description or link to paste?"*
     - **Nút bấm thường** (`<button type="button" class="btn btn-secondary btn-sm" id="switch-to-manual-job">Enter 4 fields manually</button>`).
   - Khi bấm nút **`Enter 4 fields manually`**: ẩn hoàn toàn `#job-paste-mode` và hiện `#job-manual-mode` ngay tại vị trí đó.

2. **Chế độ 2 (Khi chuyển sang) — Nhập 4 trường bắt buộc (`#job-manual-mode`, mặc định `.is-hidden`)**:
   - Hiển thị lưới 2×2 `.form-grid` gồm 4 trường bắt buộc: **Job title** (`#job-title`), **Domain** (`#domain`), **Company** (`#company`), **Position** (`#position`).
   - Ngay bên dưới là thanh hướng dẫn nhỏ (`.mode-switch-bar`):
     - Chữ hướng dẫn nhỏ (`.mode-switch-hint`): *"Have a job description, HTML, or link?"*
     - **Nút bấm thường** (`<button type="button" class="btn btn-secondary btn-sm" id="switch-to-paste-job">Paste job description instead</button>`) để quay lại chế độ dán nếu cần.

---

#### B. Khu vực 2 — CV cho buổi phỏng vấn: Bỏ nút Extend & Bỏ 4 trường CV, chỉ dùng Raw Text hoặc PDF
Loại bỏ hoàn toàn thanh `.cv-extend-divider` (`Customize CV for this interview ▾`) và xóa 4 thẻ mục CV (`01`–`04`) khỏi `job-profile.html`.

1. **Trạng thái mặc định — Dùng CV đã lưu (`#cv-saved-mode`)**:
   - Giữ hộp kiểm `.check-row`: **`Use my saved CV for this interview`** (*"Use a copy of the CV saved in my account."*).
   - Ngay bên dưới (hoặc tích hợp gọn gàng trong thanh hướng dẫn `.mode-switch-bar`):
     - Chữ hướng dẫn nhỏ: *"Want to use a different CV for this session?"*
     - **Nút bấm thường** (`<button type="button" class="btn btn-secondary btn-sm" id="switch-to-custom-cv">Paste raw CV or upload PDF</button>`).

2. **Khi bấm chuyển sang Custom CV (`#custom-cv-body`)**:
   - Ẩn khối chọn Saved CV (hoặc tự động bỏ chọn `Use my saved CV`) và hiển thị khung **Custom CV gọn nhẹ** gồm:
     - **Thanh tiêu đề phụ + Nút quay lại**: Nhãn **`Custom CV for this interview`** bên trái, kèm nút bấm thường `<button type="button" class="btn btn-secondary btn-sm" id="switch-to-saved-cv">Use saved CV instead</button>` bên phải.
     - **Ô dán văn bản CV thuần (Raw Text)**:
       - Một trường `<textarea id="job-cv-raw" rows="5" placeholder="Paste your raw CV or resume text here...">` duy nhất (thay thế hoàn toàn 4 ô `01`–`04` cũ).
     - **Vạch ngăn cách ngắn**: `OR you can upload your CV`
     - **Khối tải file PDF (`#interview-pdf-dropzone` & `#interview-pdf-card`)**: Kéo-thả hoặc chọn file `.pdf` từ máy tính.
     - **Cơ chế loại trừ lẫn nhau (Mutual Exclusivity)**:
       - Gõ/dán vào ô `#job-cv-raw` sẽ tự động gỡ file PDF đang đính kèm (nếu có).
       - Tải file PDF lên sẽ tự động xóa trắng ô `#job-cv-raw`.

---

### 3. Logic kiểm tra hợp lệ & Lưu dữ liệu (`js/app.js`)
1. **Kiểm tra Job Profile theo chế độ đang hiển thị (`jobInputMode`: `"paste"` | `"manual"`)**:
   - Nếu đang ở chế độ `"paste"`: yêu cầu `#job-source` không được để trống (báo lỗi: *"Paste a job description, HTML, or job link, or click 'Enter 4 fields manually'."*).
   - Nếu đang ở chế độ `"manual"`: yêu cầu điền đủ cả 4 trường (`Job title`, `Domain`, `Company`, `Position`); nếu thiếu báo lỗi: *"Enter a value for each of the 4 required job profile fields."*.
2. **Kiểm tra & Lưu CV theo chế độ đang chọn (`cvInputMode`: `"saved"` | `"custom"`)**:
   - Nếu đang ở chế độ `"saved"`: nếu `#sync-cv` được tích → sao chép CV đã lưu của tài khoản; nếu bỏ tích → bắt đầu phỏng vấn không kèm CV (`"none"`).
   - Nếu đang ở chế độ `"custom"`:
     - Nếu có `interviewPdf` → lưu PDF tùy chỉnh vào buổi phỏng vấn.
     - Nếu có nội dung trong `#job-cv-raw` → lưu vào `interview.cv = [rawText, "", "", ""]` (tương thích 100% với cấu trúc `strings(interview.cv, 4)` của `validState`).
     - Nếu cả `#job-cv-raw` và `interviewPdf` đều trống → báo lỗi yêu cầu dán CV hoặc tải PDF (hoặc bấm quay lại *Use saved CV instead*).

---

### 4. Danh sách file dự kiến cập nhật khi triển khai
1. **`job-profile.html`**:
   - Xóa cả 2 khối `.cv-extend-divider`.
   - Thiết lập `#job-paste-mode` và `#job-manual-mode` chuyển đổi qua lại bằng nút bấm thường (`#switch-to-manual-job` / `#switch-to-paste-job`) kèm dòng hướng dẫn nhỏ.
   - Thay thế 4 mục CV (`#job-cv-0..3`) trong `#custom-cv-body` bằng 1 ô `<textarea id="job-cv-raw">` duy nhất + vùng tải PDF, chuyển đổi bằng nút bấm thường (`#switch-to-custom-cv` / `#switch-to-saved-cv`).
2. **`css/styles.css`**:
   - Thêm style cho thanh chuyển đổi `.mode-switch-bar`, `.mode-switch-hint`, và header của `#custom-cv-body` (`.custom-cv-header`).
3. **`js/app.js`**:
   - Cập nhật controller trang `job-profile` để chuyển đổi mượt mà giữa `paste` ↔ `manual` (Job Profile) và `saved` ↔ `custom` (CV), áp dụng cơ chế loại trừ giữa `#job-cv-raw` và `interviewPdf`, và validate đúng theo chế độ đang hiển thị.

### 5. Trạng thái
- **DONE** — Đã triển khai và kiểm tra tĩnh.


---

## [DONE] Tinh chỉnh bố cục nút chuyển đổi Job Profile & Gộp phần CV thành một khung hộp thống nhất duy nhất (`job-profile.html`)

### 1. Phân tích vấn đề bố cục hiện tại
1. **Nút chuyển đổi của phần Job Profile đang bị đóng hộp thừa (`.mode-switch-bar` viền nét đứt)**:
   - Ngay dưới ô nhập Job Profile, thanh `.mode-switch-bar` dùng nền xám nhạt kèm viền nét đứt (`border: 1px dashed #cadad6`) và đẩy câu hướng dẫn sang tận mép trái còn nút bấm sang tận mép phải (`justify-content: space-between`), vừa tạo cảm giác nặng nề như một chiếc hộp phụ, vừa làm mắt người dùng phải đảo ngang cả chiều rộng form.
2. **Phần CV đang bị tách thành 2 hộp rời rạc (2 boxes)**:
   - Ở trạng thái mặc định (`#cv-saved-mode`), có **2 hộp xếp chồng lên nhau**: hộp 1 là `.check-row` (*"Use my saved CV for this interview"*) và ngay sát dưới là hộp 2 `.mode-switch-bar` (*"Want to use a different CV for this session?"* + nút bấm).
   - Ở trạng thái nhập CV tùy chỉnh (`#cv-custom-mode`), bên trong cũng tách thành **2 vùng hộp rời**: ô `<textarea id="job-cv-raw">` ở trên + vạch `OR` + hộp kéo thả `.cv-pdf-dropzone` to cồng kềnh ở dưới.

---

### 2. Giải pháp thiết kế lại (Re-layout & Merge)

#### A. Bố cục lại nút chuyển đổi của phần Job Profile (Không đóng hộp, gom cụm gọn gàng)
- **Bỏ hoàn toàn khung hộp viền nét đứt** dưới phần Job Profile.
- **Đặt cụm hướng dẫn ngắn + nút chuyển chế độ** thành một **hàng phẳng gọn gàng (`.job-mode-footer`)** nằm ngay dưới ô nhập (hoặc tích hợp thẳng lên góc phải thanh tiêu đề `.panel-header` / nhãn trường):
  - Hiển thị liền mạch trên nền trắng của panel (không viền, không màu nền hộp), căn phải hoặc căn trái gọn gàng (`display: flex; align-items: center; justify-content: flex-end; gap: 12px`):
    - Chế độ dán JD: `<span class="mode-switch-hint">Don't have a job description or link?</span>` đi liền ngay cạnh nút `<button type="button" class="btn btn-secondary btn-sm" id="switch-to-manual-job">Enter 4 fields manually</button>`.
    - Chế độ 4 trường: `<span class="mode-switch-hint">Have a job description, HTML, or link?</span>` đi liền ngay cạnh nút `<button type="button" class="btn btn-secondary btn-sm" id="switch-to-paste-job">Paste job description instead</button>`.

---

#### B. Gộp 2 hộp của phần CV thành MỘT Hộp Thống Nhất Duy Nhất (`.cv-unified-box`)
Toàn bộ phần CV trên `job-profile.html` chỉ nằm gọn trong **1 khung hộp duy nhất** ở cả 2 trạng thái:

1. **Khi ở trạng thái Saved CV (`#cv-saved-mode` — Gộp 2 hộp cũ thành 1 dòng hộp duy nhất)**:
   - Thay vì 1 hộp `.check-row` + 1 hộp `.mode-switch-bar` tách rời, **gộp chung vào một thẻ `.cv-unified-card` duy nhất** (`display: flex; align-items: center; justify-content: space-between; gap: 20px; background: var(--soft); border: 1px solid var(--line); border-radius: 14px; padding: 18px 22px`):
     - **Bên trái**: Hộp kiểm `<input type="checkbox" id="sync-cv" checked>` cùng tiêu đề **`Use my saved CV for this interview`** và dòng mô tả nhỏ *"Use a copy of the CV saved in my account."*
     - **Bên phải (ngay trong cùng hộp)**: Nhãn gợi ý nhỏ *"Or use another CV:"* (hoặc nút trực tiếp) đi kèm nút **`Paste raw CV or upload PDF`** (`#switch-to-custom-cv`).

2. **Khi bấm chuyển sang trạng thái Custom CV (`#cv-custom-mode` — Gộp ô dán Raw Text và tải PDF vào chung 1 hộp Composer duy nhất)**:
   - Thay vì tách ô `<textarea>` ở trên và một hộp `.cv-pdf-dropzone` khổng lồ ở dưới qua vạch `OR`, **hợp nhất thành một khung hộp `.cv-unified-composer` duy nhất** (tương tự bố cục `.answer-composer` trên trang Interview):
     - **Thanh tiêu đề hộp (`.cv-composer-header`)**:
       - Bên trái: Tiêu đề **`Custom CV for this interview`** kèm chú thích nhỏ *"Paste raw CV text below or attach a PDF file"*.
       - Bên phải: Nút **`Use saved CV instead`** (`#switch-to-saved-cv`) để quay về CV đã lưu.
     - **Phần thân hộp (`.cv-composer-body`)**:
       - Khi chưa đính kèm PDF: hiển thị ô `<textarea id="job-cv-raw" rows="5" placeholder="Paste your raw resume, CV text, or background summary here...">` nằm gọn bên trong hộp.
       - Khi đã chọn/kéo-thả file PDF: ẩn `<textarea>` và hiển thị ngay thẻ file PDF đã đính kèm (`#interview-pdf-card`: tên file, dung lượng, nút `Replace` / `Remove`) ngay trong lòng hộp.
     - **Thanh công cụ đáy hộp (`.cv-composer-dock` — tích hợp ngay đáy hộp, hỗ trợ cả bấm chọn lẫn kéo-thả PDF)**:
       - Bên trái: Biểu tượng tệp PDF nhỏ + dòng chữ *"Prefer a PDF file? Drag & drop here or"*
       - Bên phải: Nút bấm chọn file **`Upload PDF Resume`** (`#interview-browse-pdf-btn`, hỗ trợ `.pdf` tối đa 10MB).
       - Toàn bộ khung hộp `.cv-unified-composer` cũng nhận sự kiện `dragover` / `drop` để người dùng có thể kéo thả file `.pdf` trực tiếp vào hộp bất cứ lúc nào.

---

### 3. Danh sách file dự kiến cập nhật khi triển khai
1. **`job-profile.html`**:
   - Chuyển thanh nút của `#job-paste-mode` và `#job-manual-mode` sang hàng phẳng `.job-mode-footer` (không đóng hộp nét đứt).
   - Gộp `#cv-saved-mode` thành 1 hộp `.cv-unified-card` duy nhất chứa cả checkbox Saved CV (bên trái) và nút `Paste raw CV or upload PDF` (bên phải).
   - Gộp `#cv-custom-mode` thành 1 hộp `.cv-unified-composer` duy nhất tích hợp header + ô `textarea#job-cv-raw` / thẻ `#interview-pdf-card` + thanh đáy `.cv-composer-dock` tải PDF (xóa bỏ vạch `.cv-or-divider` và hộp `.cv-pdf-dropzone` rời bên dưới).
2. **`css/styles.css`**:
   - Thêm style cho `.job-mode-footer`, `.cv-unified-card`, `.cv-unified-composer`, `.cv-composer-header`, `.cv-composer-body`, và `.cv-composer-dock`.
3. **`js/app.js`**:
   - Cập nhật hiển thị trong `#cv-custom-mode`: khi đính kèm PDF thì ẩn `#job-cv-raw` và hiện `#interview-pdf-card` ngay trong cùng hộp; khi bấm `Remove` PDF hoặc nhập chữ thì hiện lại `#job-cv-raw`.

### 4. Trạng thái
- **DONE** — Đã triển khai và kiểm tra tĩnh.


---

## [DONE] Thiết kế lại vị trí nút chuyển đổi `Enter 4 fields manually` của phần Job Profile (`job-profile.html`)

### 1. Phân tích nguyên nhân khiến vị trí nút hiện tại chưa ổn
- Hiện tại, dòng `.job-mode-footer` (*"Don't have a job description or link?"* + nút **`Enter 4 fields manually`**) đang nằm ở góc dưới bên phải của ô nhập Job Profile, **ngay sát phía trên** góc phải của hộp CV (`.cv-unified-card` cũng có *"Want a custom CV?"* + nút **`Paste raw CV or upload PDF`** ở bên phải).
- Việc có **2 cụm `[Gợi ý + Nút phụ]` xếp chồng sát nhau ở cùng mép phải giữa trang** gây trùng lặp thị giác, làm người dùng dễ nhầm lẫn nút nào thuộc về Job Profile và nút nào thuộc về CV.
- Ngoài ra, khi để nút ở dưới đáy ô nhập, lúc người dùng bấm chuyển qua lại giữa 1 ô `<textarea>` và lưới 4 trường (`.form-grid`), chiều cao khung thay đổi làm nút bấm bị nhảy vị trí lên/xuống.
- Trong khi đó, thanh tiêu đề đầu trang `.panel-header` hiện chỉ có chữ `<h2>Job Profile</h2>` ở bên trái, bỏ trống hoàn toàn nửa bên phải.

---

### 2. Giải pháp thiết kế mới: Đưa cụm chuyển đổi chế độ Job Profile lên góc phải của `.panel-header`
Đặt cụm hướng dẫn ngắn + nút chuyển đổi chế độ **cố định trên thanh tiêu đề `.panel-header`** của khu vực Job Profile (đồng bộ hoàn toàn với bố cục Header Trái – Nút Phải của `.cv-composer-header` và `.interview-header`):

1. **Thanh tiêu đề `.panel-header` chia 2 bên cân đối (`display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap`)**:
   - **Bên trái (`.panel-header-title`)**:
     - Tiêu đề `<h2>Job Profile</h2>`.
   - **Bên phải (`.panel-header-action`)**:
     - Dòng gợi ý nhỏ `<span class="mode-switch-hint" id="job-mode-hint">Don't have a job description or link?</span>`
     - Nút chuyển đổi `<button type="button" class="btn btn-secondary btn-sm" id="job-mode-switch-btn">Enter 4 fields manually</button>`
2. **Trải nghiệm tương tác mượt mà & cố định vị trí**:
   - Khi người dùng bấm nút `#job-mode-switch-btn` ngay trên góc phải `.panel-header`:
     - Nút **đứng yên tại chỗ** (không bị nhảy lên/xuống theo chiều cao của form bên dưới).
     - Chữ gợi ý và nhãn nút tự động đổi sang:
       - Đang ở Paste Mode → `"Don't have a job description or link?"` + **`Enter 4 fields manually`**
       - Đang ở Manual 4-Field Mode → `"Have a job description, HTML, or link?"` + **`Paste job description instead`**
3. **Làm sạch khoảng cách giữa phần Job Profile và hộp CV**:
   - Xóa bỏ hoàn toàn các khối `.job-mode-footer` nằm lơ lửng giữa phần Job Profile và hộp `.cv-unified-card`.
   - Ô nhập Job Profile (`#job-paste-mode` hoặc `#job-manual-mode`) dẫn thẳng xuống hộp CV thống nhất bên dưới với khoảng cách thoáng đãng, tách bạch hoàn toàn 2 nút chức năng (1 nút ở Header trên cùng cho Job Profile, 1 nút nằm trong hộp CV bên dưới).

---

### 3. Danh sách file dự kiến cập nhật khi triển khai
1. **`job-profile.html`**:
   - Đưa `#job-mode-hint` và `#job-mode-switch-btn` vào bên phải của `<div class="panel-header">`.
   - Xóa 2 khối `.job-mode-footer` bên dưới `#job-paste-mode` và `#job-manual-mode`.
2. **`css/styles.css`**:
   - Cập nhật `.panel-header` thành flex container (`display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap`) và thêm `.panel-header-action` (`display: flex; align-items: center; gap: 12px`).
   - Dọn bỏ `.job-mode-footer` cũ.
3. **`js/app.js`**:
   - Cập nhật `setJobMode(mode)` để đổi trực tiếp nội dung của `#job-mode-hint` và `#job-mode-switch-btn` khi người dùng bấm chuyển đổi giữa `"paste"` và `"manual"`.

### 4. Trạng thái
- **DONE** — Đã triển khai và kiểm tra tĩnh.


---

## [DONE] Tinh chỉnh lại trang Job Profile (`job-profile.html`): Đổi nút chuyển 4 trường thành Hyperlink Text (kiểu Sign in / Sign up), đưa TOÀN BỘ phần CV (kể cả `Use my saved CV`) vào trong nút Extend `Use CV for this interview? ▾` & dùng lại hộp Upload PDF lớn kiểu cũ

### 1. Phân tích yêu cầu điều chỉnh từ người dùng
1. **Chuyển nút `Enter 4 fields manually` sang dạng Hyperlink Text (giống `Sign in` / `Sign up`)**:
   - Thay vì dùng nút bấm đóng khung (`.btn.btn-secondary`), sử dụng câu dẫn ngắn kèm **chữ gạch chân tương tác (`.text-link`)** giống hệt mẫu `<p class="auth-switch">Don't have an account? <a class="text-link">Sign up</a></p>` trên trang đăng nhập.
2. **Đưa TOÀN BỘ phần CV (bao gồm cả `Use my saved CV for this interview` lẫn phần Custom CV) vào bên trong một nút Extend duy nhất (`Use CV for this interview? ▾`)**:
   - Khi mới vào trang `job-profile.html` (trạng thái thu gọn):
     - Người dùng chỉ thấy phần **Job Profile** (ô dán JD + dòng hyperlink chuyển sang 4 trường) và ngay bên dưới là thanh mở rộng:
       `──────────  Use CV for this interview? ▾  ──────────`
     - Toàn bộ phần CV (kể cả hộp `Use my saved CV for this interview`) đều nằm gọn **bên trong** vùng mở rộng `#cv-extend-body` (ẩn khi chưa bấm mở rộng).
   - Khi bấm vào **`Use CV for this interview? ▾`** (trạng thái mở rộng):
     - Mở ra khung `#cv-extend-body` giữ nguyên bố cục hiện tại:
       - **Chế độ Saved CV (`#cv-saved-mode`)**: Hộp `.cv-unified-card` chứa checkbox **`Use my saved CV for this interview`** bên trái và nút **`Paste raw CV or upload PDF`** bên phải.
       - **Chế độ Custom CV (`#cv-custom-mode`)**: Khi bấm `Paste raw CV or upload PDF`, chuyển sang khung Custom CV có nút `Use saved CV instead` ở góc phải, bên dưới là ô dán **`Paste raw CV text`** (`#job-cv-raw`), vạch ngăn cách **`OR you can upload your CV`** (`.cv-or-divider`), và **hộp Upload PDF hình chữ nhật lớn kiểu cũ (`.cv-pdf-dropzone`)**.
3. **Khôi phục hộp Upload PDF hình chữ nhật lớn kiểu cũ (`.cv-pdf-dropzone`)**:
   - Trong `#cv-custom-mode`, thay thanh dock nhỏ ở đáy bằng **hộp chữ nhật lớn viền nét đứt kiểu cũ (`.cv-pdf-dropzone`)**: có icon SVG 40×40 ở giữa, tiêu đề `<h3>Upload your PDF Resume</h3>`, dòng chữ *"Drag and drop your file here, or browse from computer"* và *"Supports PDF only (up to 10MB)"* (hiển thị `.cv-pdf-card` khi đã đính kèm file).

---

### 2. Giải pháp thiết kế & Bố cục chi tiết trên `job-profile.html`

#### A. Phần 1 — Job Profile + Dòng chuyển đổi Hyperlink Text (`.job-switch-prompt`)
- **Tiêu đề Panel (`.panel-header`)**: Trả về tiêu đề sạch `<h2>Job Profile</h2>`.
- **Khung nhập Job Profile (`#job-paste-mode` ↔ `#job-manual-mode`)**:
  - **Mặc định (`#job-paste-mode`)**: Hiển thị ô `<textarea id="job-source" rows="5">` (*"Paste job description, HTML, or job link"*).
  - **Chuyển sang 4 trường (`#job-manual-mode`)**: Hiển thị lưới 2×2 `.form-grid` gồm 4 trường (`Job title`, `Domain`, `Company`, `Position`).
- **Dòng chuyển đổi dạng Hyperlink Text (`.job-switch-prompt`)** đặt gọn ngay dưới vùng nhập Job Profile:
  ```html
  <p class="job-switch-prompt">
    <span id="job-mode-hint">Don't have a job description or link?</span>
    <button type="button" class="text-link btn-link-inline" id="job-mode-switch-btn">Enter 4 fields manually</button>
  </p>
  ```

#### B. Phần 2 — Toàn bộ khu vực CV nằm trong Nút Mở Rộng (`Use CV for this interview? ▾`)
- Ngay dưới phần Job Profile là thanh mở rộng `.cv-extend-divider`:
  ```html
  <div class="cv-extend-divider">
    <button type="button" class="cv-extend-trigger" id="cv-section-toggle" aria-expanded="false" aria-controls="cv-section-body">
      <span>Use CV for this interview?</span>
      <span class="expander-chevron" aria-hidden="true">▾</span>
    </button>
  </div>
  ```
- **Khối nội dung mở rộng `#cv-section-body` (Mặc định ẩn `.is-hidden`, chứa TOÀN BỘ phần CV với bố cục hiện tại)**:
  1. **`#cv-saved-mode` (Giữ nguyên hộp `.cv-unified-card` hiện tại)**:
     - Bên trái: Checkbox `Use my saved CV for this interview` (`#sync-cv`).
     - Bên phải: Hint *"Want a custom CV?"* + nút **`Paste raw CV or upload PDF`** (`#switch-to-custom-cv`).
  2. **`#cv-custom-mode` (Giữ bố cục chuyển đổi hiện tại + Khôi phục hộp `.cv-pdf-dropzone` hình chữ nhật lớn kiểu cũ)**:
     - Thanh tiêu đề (`.cv-composer-header`): Tiêu đề **`Custom CV for this interview`** bên trái + nút **`Use saved CV instead`** (`#switch-to-saved-cv`) bên phải.
     - Ô dán văn bản CV thuần: `<div class="field"><label for="job-cv-raw">Paste raw CV text</label><textarea id="job-cv-raw" rows="5" ...></textarea></div>`
     - Vạch ngăn cách: `<div class="cv-or-divider"><span>OR you can upload your CV</span></div>`
     - **Hộp Upload PDF hình chữ nhật lớn kiểu cũ (`.cv-pdf-dropzone` `#interview-pdf-dropzone`)** + thẻ `#interview-pdf-card` khi đã chọn file.

---

### 3. Danh sách file dự kiến cập nhật khi triển khai
1. **`job-profile.html`**:
   - Đổi nút chuyển đổi 4 trường sang dòng `<p class="job-switch-prompt">` dùng `.text-link` (kiểu Sign in / Sign up).
   - Đặt thanh mở rộng `.cv-extend-divider` (`Use CV for this interview? ▾`) bao ngoài toàn bộ `#cv-section-body` (chứa cả `#cv-saved-mode` lẫn `#cv-custom-mode`).
   - Trong `#cv-custom-mode`, khôi phục `.cv-or-divider` + hộp chữ nhật lớn `.cv-pdf-dropzone` kiểu cũ.
2. **`css/styles.css`**:
   - Thêm `.job-switch-prompt` và `.btn-link-inline` cho hyperlink text.
   - Giữ style `.cv-unified-card` hiện tại và kết hợp hài hòa với `.cv-pdf-dropzone` lớn kiểu cũ trong `#cv-custom-mode`.
3. **`js/app.js`**:
   - Xử lý đóng/mở `#cv-section-toggle` (`#cv-section-body`).
   - Giữ nguyên chuyển đổi `#cv-saved-mode` ↔ `#cv-custom-mode` bên trong `#cv-section-body` và khôi phục sự kiện click/drag-drop trên `#interview-pdf-dropzone`.

### 4. Trạng thái
- **DONE** — Đã hoàn thành triển khai và kiểm tra trên `job-profile.html`, `css/styles.css` và `js/app.js`.

---

## [DONE] Đồng bộ mục "Your CV" trên trang Profile (`profile.html`): Bỏ 4 mục CV rời, thay bằng ô dán văn bản CV thuần (`Paste raw CV text`) giống trang Job Profile

### 1. Vấn đề hiện tại
- Trên trang `job-profile.html`, phần nhập CV đã được tối giản thành **1 ô dán văn bản thuần (`Paste raw CV text`)** kết hợp với hộp tải file PDF (`.cv-pdf-dropzone`).
- Tuy nhiên, tại mục **Your CV** (`#your-cv`) trên trang `profile.html`, giao diện vẫn đang hiển thị **4 mục tách rời** (`01 Personal Profile`, `02 Education History`, `03 Work & Research Experience`, `04 Core Skills`), gây thiếu đồng bộ trải nghiệm và buộc người dùng phải chia nhỏ CV thủ công khi lưu CV mặc định trong tài khoản.

---

### 2. Giải pháp đề xuất

#### A. Giao diện mục `Your CV` trên `profile.html` (`#your-cv`)
1. **Xóa 4 thẻ `.cv-section-card` trong `.profile-cv-stack`** (`#prof-cv-0`, `#prof-cv-1`, `#prof-cv-2`, `#prof-cv-3`).
2. **Thay bằng 1 ô dán văn bản CV thuần (`#prof-cv-raw`)** đồng bộ hoàn toàn với phần Custom CV trên `job-profile.html`:
   ```html
   <div class="field cv-raw-field">
     <label for="prof-cv-raw">Paste raw CV text</label>
     <textarea id="prof-cv-raw" rows="6" maxlength="15000" placeholder="Paste your raw resume, CV text, or background summary here..."></textarea>
   </div>
   ```
3. **Giữ nguyên phần tải PDF và thanh nút lưu bên dưới**:
   - Vạch ngăn cách `.cv-or-divider` (`OR you can upload your CV`).
   - Hộp kéo thả PDF hình chữ nhật lớn `.cv-pdf-dropzone` (`#cv-pdf-dropzone`) và thẻ hiển thị file đính kèm `.cv-pdf-card` (`#cv-pdf-card`).
   - Thanh hành động `.cv-actions-bar` với thông báo trạng thái `#cv-status` và nút **`Save CV`** (`#save-cv-btn`).

#### B. Logic lưu trữ & tương thích dữ liệu trong `js/app.js`
1. **Hiển thị dữ liệu CV đã lưu vào `#prof-cv-raw`**:
   - Nếu tài khoản đang ở chế độ văn bản (`!isPdfActive`), ghép các phần tử có nội dung trong `account.cv` (`account.cv.filter(s => s && s.trim()).join("\n\n")`) để hiển thị đầy đủ trong `#prof-cv-raw` (tương thích mượt với cả dữ liệu mẫu 4 phần trong `DATA.cv` lẫn dữ liệu 1 chuỗi mới).
2. **Lưu trữ tương thích với `validState` (`strings(account.cv, 4)`)**:
   - Cập nhật hàm `saveCV()` để lưu giá trị của `#prof-cv-raw` vào `account.cv = [profCvRaw.value, "", "", ""]`, đảm bảo cấu trúc mảng 4 chuỗi trong `localStorage` luôn hợp lệ và không làm hỏng dữ liệu cũ.
3. **Loại trừ lẫn nhau giữa Raw Text và PDF**:
   - Khi người dùng gõ vào `#prof-cv-raw` hoặc bấm `Save CV`: tự động xóa trạng thái PDF (`clearPdfFile()`), lưu văn bản vào `account.cv` và hiện `"Changes saved."` / `"CV saved successfully."`.
   - Khi người dùng tải lên file PDF (`handlePdfFile`): xóa trắng `#prof-cv-raw` (`clearCvSections()`), lưu metadata PDF vào `account.cvPdf` (`account.cvMode = "pdf"`) và hiển thị thông báo ``PDF "${file.name}" saved! Raw text cleared.``.

---

### 3. Danh sách file dự kiến cập nhật khi triển khai
1. **`profile.html`**:
   - Thay khối `.profile-cv-stack` (4 mục `#prof-cv-0..3`) bằng `.field.cv-raw-field` chứa `<textarea id="prof-cv-raw">`.
2. **`js/app.js`**:
   - Cập nhật `saveCV()`, `clearCvSections()`, và sự kiện khởi tạo/nhập liệu của `#prof-cv-raw` trong khối `if (page === "profile")`.
3. **`css/styles.css`**:
   - Tái sử dụng trực tiếp class `.cv-raw-field` đã định nghĩa cho `job-profile.html` (không cần thêm CSS dư thừa).

### 4. Trạng thái
- **DONE** — Đã hoàn thành triển khai: ô dán CV thuần trên Profile và `account.cv` mặc định để trống (blank) thay vì nạp sẵn dữ liệu mẫu `DATA.cv`.


---

## [DONE] Thiết kế lại bố cục trang Interview (`interview.html`): Bổ sung Robot 2D dễ thương diễn hoạt nhép miệng (Mime Animation) đọc câu hỏi phỏng vấn

### 1. Vấn đề hiện tại & Góp ý từ Giáo sư
- Hiện tại, trang phỏng vấn (`interview.html`) chỉ hiển thị một khối văn bản câu hỏi tĩnh (`<blockquote class="question">`) đặt phía trên ô nhập câu trả lời.
- Giáo sư phản hồi giao diện phỏng vấn hiện tại **nhàm chán và thiếu tính tương tác/cuốn hút (boring and not really engaging)** — người dùng có cảm giác đang điền một biểu mẫu văn bản hơn là đang tham gia một buổi phỏng vấn với trợ lý AI.
- **Yêu cầu từ Giáo sư**:
  1. Bổ sung một **nhân vật Robot 2D dễ thương (Cute 2D Robot Sprite)** đóng vai trò người phỏng vấn AI trực tiếp đặt câu hỏi.
  2. Robot có **hoạt ảnh diễn tả / nhép miệng theo câu hỏi (Mime / Lip-sync & Gesture Animation)** như đang đọc câu hỏi thành tiếng cho ứng viên.
  3. **Lưu ý phạm vi hiện tại**: Tính năng đọc giọng nói thật (Text-to-Speech / TTS) là yêu cầu cho giai đoạn sau nhưng **chưa triển khai trong bước này**. Hiện tại tập trung thiết kế lại bố cục (Re-layout) để dành không gian cho Robot, vẽ 2D Sprite Robot và lập trình hiệu ứng diễn hoạt (Mime Animation) khớp với luồng chuyển câu hỏi (sẵn sàng điểm neo để gắn TTS sau này).

---

### 2. Giải pháp thiết kế & Bố cục chi tiết (Re-layout + 2D Robot Sprite + Mime Animation)

#### A. Bố cục lại trang Interview (`.interviewer-stage` — Chia không gian cho Robot & Bong bóng câu hỏi)
Thay thế khối `<blockquote class="question">` đơn điệu bằng **Sân khấu Phỏng vấn AI (`.interviewer-stage`)** đặt ngay dưới `.interview-header` và phía trên `.answer-section`:

1. **Bố cục 2 cột cân đối trên Desktop (`grid-template-columns: 210px minmax(0, 1fr); gap: 24px; align-items: center`)**:
   - **Cột Trái — Khung Sân Khấu Robot (`.robot-stage-pod`)**:
     - Khung nền bo tròn mềm mại (`border-radius: 20px`), nền gradient xanh kem dịu (`radial-gradient` đồng bộ bảng màu `#92C7CF` / `#AAD7D9` / `#FBF9F1`) tạo chiều sâu như một buồng gọi video / sân khấu nhỏ của AI.
     - Chứa **2D Robot Sprite** ở trung tâm kèm bóng đổ lơ lửng bên dưới (`.robot-shadow`).
     - Phía dưới chân Robot là **Huy hiệu trạng thái động (`.robot-status-pill`)**:
       - Khi Robot đang diễn hoạt đọc câu hỏi: hiển thị chấm sáng nhịp thở + nhãn `Asking question...`
       - Khi Robot dừng đọc / chờ trả lời: hiển thị `Ready for your answer`
       - Khi ứng viên bật Mic thu âm: hiển thị `Listening to you...`
   - **Cột Phải — Bong Bóng Câu Hỏi Tương Tác (`.question-speech-card`)**:
     - Thiết kế khối câu hỏi như một **bong bóng thoại (Speech Bubble)** có mũi nhọn (`.speech-bubble-tail`) hướng trực tiếp về phía Robot bên trái, tạo cảm giác Robot đang thực sự nói ra câu hỏi đó.
     - **Thanh công cụ nhỏ đầu bong bóng (`.question-card-top`)**:
       - Bên trái: Nhãn nhỏ `AI INTERVIEWER` kèm dải sóng âm mini nhấp nhô khi Robot đang nhép miệng đọc câu hỏi.
       - Bên phải: Nút tương tác **`Replay question`** (`#robot-replay-btn` với icon loa/play nhỏ) để người dùng hoặc người thuyết trình demo có thể bấm cho Robot diễn hoạt đọc lại câu hỏi bất cứ lúc nào (đồng thời là nút kích hoạt TTS trong tương lai).
     - **Nội dung câu hỏi (`#question-text`)**: Giữ cỡ chữ lớn, dễ đọc (`17px–18px`, `line-height: 1.68`), kèm hiệu ứng xuất hiện mượt mà khi chuyển sang câu hỏi mới.

2. **Tương thích Responsive (Tablet / Mobile `< 720px`)**:
   - Tự động xếp dọc: Khung Robot nằm phía trên, mũi nhọn bong bóng thoại xoay hướng lên trên trỏ vào Robot, đảm bảo không bị tràn hay chật hẹp trên màn hình nhỏ.

---

#### B. Thiết kế Nhân vật Robot 2D (`assets/robot-interviewer.svg` + Inline SVG Layers)
Thiết kế vector 2D sắc nét, thân thiện và đồng bộ 100% với bảng màu thương hiệu **Yourin** (`#203D43` Ink, `#6AAEB8` Banner Blue, `#92C7CF` Aqua, `#AAD7D9` Mist, `#FBF9F1` Cream):
- **Cấu trúc tách lớp (Layered 2D Sprite)** để điều khiển chuyển động độc lập từng bộ phận bằng CSS/JS:
  1. **Ăng-ten phát sáng (`.robot-antenna`)**: Đỉnh đầu có ăng-ten nhỏ với quả cầu sáng màu xanh ngọc phát xung nhịp khi Robot đang nói.
  2. **Đầu & Màn hình khuôn mặt (`.robot-head` & `.robot-visor`)**: Đầu bo tròn bầu bĩnh màu kem/xanh sáng (`#FBF9F1` & `#AAD7D9`), mặt kính visor tối màu (`#203D43`) làm nổi bật mắt và miệng LED phát sáng (`#92C7CF`).
  3. **Đôi mắt biểu cảm (`.robot-eyes`)**: Đôi mắt LED to tròn dễ thương có hiệu ứng **chớp mắt tự nhiên** (`@keyframes robot-blink`), biết cong lên vui vẻ hoặc nheo nhẹ biểu cảm khi đang đặt câu hỏi.
  4. **Miệng nhép theo âm tiết (`.robot-mouth`)**:
     - Trạng thái nghỉ (`idle`): Miệng cười mỉm thân thiện (đường cong LED êm ái).
     - Trạng thái đọc câu hỏi (`miming`): Miệng đóng/mở liên tục kết hợp sóng âm LED biến thiên nhiều khẩu hình (`O`, `A`, `E`, `smile`) tạo hiệu ứng nhép miệng (lip-sync mime) sinh động.
  5. **Thân & Đôi tay cử chỉ (`.robot-torso`, `.robot-arm-left`, `.robot-arm-right`)**:
     - Thân nhỏ gọn lơ lửng nhẹ nhàng (`@keyframes robot-float`).
     - Hai cánh tay tách rời: khi đọc câu hỏi, tay phải vẫy nhẹ / đưa lên diễn đạt ý (mime gesture), đầu nghiêng nhẹ qua lại tạo thần thái tự nhiên, cuốn hút.

---

#### C. Kịch bản Hoạt ảnh Diễn tả (Mime Animation States) trong `css/styles.css` & `js/app.js`
1. **Trạng thái 1 — `is-miming` (Đang đọc / diễn tả câu hỏi)**:
   - **Khi nào kích hoạt**:
     - Tự động chạy ngay khi mở trang `interview.html` (Question 1).
     - Tự động chạy lại mỗi khi bấm **`Next Question →`** hoặc **`← Previous Question`** (`renderStep(index)`).
     - Chạy bất cứ khi nào người dùng bấm nút **`Replay question`** (`#robot-replay-btn`).
   - **Hiệu ứng thị giác**:
     - Class `.is-miming` gắn vào `#robot-stage`: kích hoạt chuỗi `@keyframes robot-mouth-mime` (nhép miệng đa nhịp), `@keyframes robot-head-talk` (nghiêng đầu nhẹ theo nhịp nói), `@keyframes robot-arm-gesture` (tay phải cử chỉ thuyết trình), và `@keyframes antenna-glow` (ăng-ten phát sáng).
     - Dải sóng âm nhỏ cạnh chữ `AI INTERVIEWER` trong bong bóng câu hỏi nhấp nhô đồng bộ.
   - **Thời lượng thông minh**:
     - Tự động tính thời gian diễn hoạt dựa trên độ dài câu hỏi (khoảng `3.5s – 5.5s`) rồi mượt mà chuyển về trạng thái nghỉ (`is-idle`), hoặc người dùng có thể bấm nút `#robot-replay-btn` để dừng/phát lại ngay lập tức.
2. **Trạng thái 2 — `is-idle` (Chờ ứng viên trả lời)**:
   - Robot lơ lửng nhẹ nhàng (`@keyframes robot-float`), mắt chớp tự nhiên định kỳ mỗi vài giây, miệng mỉm cười khích lệ.
3. **Trạng thái 3 — `is-listening` (Khi ứng viên bấm nút Microphone thu âm)**:
   - Khi người dùng bấm `#mic-toggle-btn` (`startRecording()`), Robot chuyển sang trạng thái chăm chú lắng nghe: đầu hơi nghiêng về phía trước, tai/ăng-ten sáng nhịp xanh-đỏ nhẹ, huy hiệu dưới chân hiện `Listening to you...`, tăng tính kết nối hai chiều giữa ứng viên và Robot.

---

### 3. Danh sách file đã cập nhật khi triển khai
1. **`interview.html` & `interview-interrupt.html`**:
   - Thay thế `<blockquote class="question">` đơn điệu bằng cấu trúc `.interviewer-stage` gồm `.robot-stage-pod` (Robot 2D Sprite phân lớp + bóng đổ + huy hiệu trạng thái động) và `.question-speech-card` (bong bóng thoại câu hỏi có đuôi hướng về phía Robot, nhãn AI INTERVIEWER với sóng âm, nút Replay question `#robot-replay-btn`, và nội dung câu hỏi).
2. **`css/styles.css`**:
   - Bổ sung toàn bộ hệ thống lớp `.interviewer-stage`, `.robot-stage-pod`, `.robot-visual`, `.robot-sprite`, `.robot-shadow`, `.robot-status-pill`, `.question-speech-card`, `.speech-bubble-tail`, `.mime-audio-bars`, `.btn-replay-question`.
   - Bổ sung chuỗi `@keyframes`: `robot-float` (lơ lửng), `robot-shadow-scale` (bóng co giãn), `robot-blink` (chớp mắt tự nhiên), `antenna-flash` (ăng-ten phát xung), `robot-head-talk` (nghiêng đầu khi nói), `robot-arm-gesture` (tay phải diễn đạt cử chỉ), `robot-mouth-mime` (nhép miệng đa nhịp), và hỗ trợ chế độ màn hình nhỏ `< 720px`.
3. **`js/app.js`**:
   - Triển khai `startRobotMime()` và `stopRobotMime()`: tự động kích hoạt diễn hoạt nhép miệng theo độ dài từng câu hỏi khi vào trang hoặc chuyển câu hỏi; nút `#robot-replay-btn` cho phép diễn hoạt lại bất kỳ lúc nào; đồng bộ trạng thái `is-listening` ("Listening to you...") khi ứng viên bật Microphone.

### 4. Trạng thái
- **DONE** — Đã hoàn thành triển khai và kiểm tra cấu trúc HTML/CSS/JS.



---

## [DONE] Tinh chỉnh Robot 2D trên trang Interview (`interview.html`): Xóa huy hiệu `Ready for your answer`, đổi tên `AI INTERVIEWER` thành `YORI` & gắn Logo Yourin lên bụng Robot

### 1. Các điểm điều chỉnh đã thực hiện
1. **Xóa bỏ huy hiệu trạng thái `Ready for your answer` (`.robot-status-pill`)**:
   - Đã xóa hoàn toàn `.robot-status-pill` khỏi `interview.html` và `interview-interrupt.html`.
   - Căn giữa Robot và bóng đổ lơ lửng ngay tâm khung `.robot-stage-pod`, giúp giao diện sân khấu gọn gàng, thoáng đãng và tập trung vào nhân vật.
2. **Đổi tên `AI INTERVIEWER` thành `YORI`**:
   - Nhãn trên đầu bong bóng câu hỏi (`.tag-title`) được đổi thành **`YORI`** — tên gọi thân thiện, ngắn gọn và đồng điệu với thương hiệu **Yourin**.
3. **Gắn Logo chính thức của Yourin (`assets/logo.svg`) lên bụng Robot**:
   - Đã thay thế cụm hình chữ nhật và hình tròn cũ bằng huy hiệu tròn xanh `#6AAEB8` sắc nét chứa vector Logo Yourin nguyên bản (bong bóng kem `#FBF9F1` và biểu tượng `#203D43`), tạo dấu ấn nhận diện thương hiệu tức thì.

---

### 2. Danh sách file đã cập nhật
1. **`interview.html` & `interview-interrupt.html`**:
   - Xóa `.robot-status-pill`.
   - Đổi `AI INTERVIEWER` thành `YORI`.
   - Thêm `.robot-belly-logo` (Vector Logo Yourin) vào `.robot-body-group`.
2. **`css/styles.css`**:
   - Đặt `.robot-stage-pod` thành `justify-content: center` và dọn dẹp các CSS rules của status pill.
3. **`js/app.js`**:
   - Gỡ bỏ các dòng gán text của `#robot-status-text`, giữ nguyên chuyển động diễn hoạt nhép miệng, chớp mắt, ăng-ten phát sáng và cử chỉ tay.

### 3. Trạng thái
- **DONE** — Đã hoàn thành triển khai và kiểm tra tĩnh.



---

## [DONE] Tinh gọn chiều cao khung Robot & khung Câu hỏi (`interview.html`): Đưa tên `YORI` sang khung Robot, bỏ khung trắng bao ngoài câu hỏi & chuyển cụm điều khiển (Icon, Sóng âm, nút Replay) xuống dưới câu hỏi

### 1. Phân tích vấn đề & Các thay đổi đã thực hiện
1. **Bỏ hoàn toàn khung chữ nhật trắng bao ngoài (`.question-speech-card` nền trắng)**:
   - Đã loại bỏ hộp trắng bao ngoài và lớp đệm kép, chuyển `.question-speech-card` thành một khối duy nhất có nền mềm `var(--soft)` và viền trái `4px solid var(--aqua)`.
   - Giúp giảm đáng kể chiều cao theo trục dọc (vertical height) của cả khung câu hỏi lẫn khung Robot bên trái mà không làm chật chội chiều ngang.
2. **Đưa tên `YORI` sang khung Robot (Robot Banner)**:
   - Nhãn tên **`YORI`** (`.robot-name-badge`) đã được chuyển trực tiếp sang khung Robot bên trái, đặt ngay bên dưới bóng đổ của Robot.
3. **Chuyển cụm UI (Biểu tượng Robot, Dải sóng âm, Nút `Replay`) xuống dưới câu hỏi**:
   - Nội dung câu hỏi (`#question-text`) được đặt lên trên đầu khung.
   - Ngay dưới câu hỏi là thanh điều khiển tinh gọn `.question-card-bottom` chứa biểu tượng avatar Robot, dải sóng âm nhấp nhô khi Robot nhép miệng đọc, và nút **`Replay`** ở góc phải.

---

### 2. Danh sách file đã cập nhật
1. **`interview.html` & `interview-interrupt.html`**:
   - Thêm `<span class="robot-name-badge">YORI</span>` vào `.robot-stage-pod`.
   - Đưa nội dung câu hỏi lên đầu `.question-speech-card` và gom icon, sóng âm, nút Replay vào `.question-card-bottom`.
2. **`css/styles.css`**:
   - Tối ưu kích thước `.interviewer-stage` (`160px minmax(0, 1fr)`), `.robot-stage-pod`, `.robot-visual`, và `.robot-name-badge`.
   - Cập nhật `.question-speech-card` thành dải phẳng nền `var(--soft)` viền aqua trái, xóa bỏ `.speech-bubble-tail` và hộp trắng cũ.

### 3. Trạng thái
- **DONE** — Đã hoàn thành triển khai và kiểm tra tĩnh.



---

## [DONE] Nâng cấp tương tác Yori & Bong bóng câu hỏi (`interview.html`): Đưa tên `YORI` lên trên đầu Robot, bo tròn + thêm đuôi nhọn (Speech Tail) cho khung câu hỏi & làm mắt/đầu Yori dõi theo khi ứng viên gõ chữ hoặc nói

### 1. Phân tích các yêu cầu & Thay đổi đã thực hiện
1. **Đưa nhãn tên `YORI` lên phía trên mô hình Robot**:
   - Đã di chuyển `<span class="robot-name-badge">YORI</span>` lên trên đỉnh khung `.robot-stage-pod`, nằm phía trên `.robot-visual`.
2. **Bo tròn khung câu hỏi & Thêm mũi nhọn hội thoại (Speech Bubble Tail)**:
   - Bo tròn đều 4 góc `.question-speech-card` (`border-radius: 18px; border: 1.5px solid #b8d7dc; background: var(--soft)`).
   - Gắn mũi nhọn `.speech-bubble-tail` đồng màu `var(--soft)` trỏ thẳng sang Yori (trên mobile xoay trỏ lên trên Yori), thể hiện rõ câu hỏi là lời nói của Yori mà vẫn giữ nguyên thiết kế 1 lớp gọn nhẹ.
3. **Hành vi đôi mắt & cử chỉ của Yori dõi theo người dùng khi gõ chữ hoặc thu âm**:
   - Tách riêng cụm `.robot-eyes-gaze` để điều khiển hướng nhìn độc lập với hiệu ứng chớp mắt.
   - **Khi gõ phím (`is-typing` / `is-watching`)**: Đầu Yori hơi cúi nhẹ về phía ô trả lời; đôi mắt nhìn xuống (`--eye-y: 3.5px`) và chuyển động quét ngang (`--eye-x`) theo vị trí con trỏ chữ của ứng viên theo thời gian thực.
   - **Khi thu âm (`is-listening`)**: Đầu Yori nghiêng lắng nghe (`3.5deg`), mắt nhìn chăm chú và ăng-ten phát sáng nhịp nhàng.

---

### 2. Danh sách file đã cập nhật
1. **`interview.html` & `interview-interrupt.html`**:
   - Di chuyển `YORI` lên trên Robot.
   - Thêm `.robot-eyes-gaze` và `.speech-bubble-tail`.
2. **`css/styles.css`**:
   - Style cho `.speech-bubble-tail`, bo tròn 18px cho `.question-speech-card`, và các trạng thái `.is-watching`, `.is-typing`, `.is-listening`, `.robot-eyes-gaze`.
3. **`js/app.js`**:
   - Triển khai `setRobotGaze()`, `resetRobotGaze()`, `updateGazeOnTyping()` bắt sự kiện `input`, `focus`, `blur`, `keyup`, `click` trên ô nhập câu trả lời `#answer` và đồng bộ khi thu âm.

### 3. Trạng thái
- **DONE** — Đã hoàn thành triển khai và kiểm tra tĩnh.

---

## [DONE] Tinh chỉnh Mũi nhọn Bong bóng thoại trỏ đúng miệng Yori, Thiết kế lại Avatar theo phong cách Yori & Bổ sung Cử chỉ Đưa tay lên tai Lắng nghe (`is-listening`)

### 1. Phân tích 3 điểm cần cải thiện từ phản hồi của người dùng
1. **Mũi nhọn bong bóng thoại (`.speech-bubble-tail`) hiện đang nằm hơi cao so với miệng của Yori**:
   - **Nguyên nhân**: Hiện tại `.speech-bubble-tail` đang đặt cố định ở `top: 38px`. Trong khi đó, do nhãn tên `YORI` nằm ở đầu khung `.robot-stage-pod` (`~27px` tính cả khoảng cách), phần đầu và miệng của Yori (`cy="74"` trong SVG cao `138px`) thực tế nằm ở độ cao khoảng **`86px–95px`** tính từ đỉnh khung (tương đương khoảng `50%–52%` chiều cao khung). Vì vậy ở `top: 38px`, mũi nhọn đang trỏ vào vùng trán/ăng-ten chứ chưa trỏ vào miệng Yori.
   - **Giải pháp**: Hạ vị trí `.speech-bubble-tail` xuống tầm ngang miệng của Yori (`top: 84px` / `top: 50%`) và tinh chỉnh góc vát của mũi nhọn hướng trực diện vào miệng Yori.
2. **Thiết kế lại Avatar Logo theo thẩm mỹ của Yori để thay thế Avatar bóng người (Silhouette Avatar) & Icon đơn điệu**:
   - **Hiện trạng**:
     - File [`assets/avatar.svg`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/assets/avatar.svg) (dùng trên thanh Header của 10 trang và khung lớn ở trang `profile.html`) chỉ là một hình bóng người (silhouette) gồm 1 hình tròn và 1 hình chữ nhật bo góc màu xanh `#6AAEB8`, trông đơn điệu và chưa ăn nhập với nhân vật Yori mới.
     - Ngoài ra, biểu tượng nhỏ `.tag-avatar` cạnh thanh sóng âm dưới câu hỏi (`interview.html`) đang dùng icon nét mảnh hình hộp chung chung.
   - **Giải pháp**:
     - Thiết kế lại [`assets/avatar.svg`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/assets/avatar.svg) thành **Yori Head Zoomed-in Avatar Logo** (chân dung cận cảnh phần đầu Yori phóng to chiếm trọn khung tròn giống các avatar logo chuẩn, thay vì vẽ cả thân người): khung tròn viền xanh ngọc chứa phần đầu Yori cận cảnh sắc nét (ăng-ten phát sáng, tai nghe hai bên, mặt kính visor `#203D43`, đôi mắt LED xanh ngọc `#92C7CF` to rõ có đốm sáng trắng, má hồng, nụ cười thân thiện và một phần nhỏ cổ áo ở rìa dưới).
     - Đồng bộ luôn biểu tượng `.tag-avatar` bên dưới câu hỏi trong `interview.html` và `interview-interrupt.html` sang hình **Yori Avatar** thu nhỏ thay cho icon hình hộp nét mảnh cũ.
3. **Hoạt ảnh lắng nghe (`is-listening`) còn khó nhận ra — Bổ sung cử chỉ Yori đưa tay lên tai để nghe**:
   - **Hiện trạng**: Khi ứng viên bật Microphone thu âm (`.interviewer-stage.is-listening`), Yori mới chỉ nghiêng đầu nhẹ `3.5deg` tĩnh và nhìn xuống `3px`, không có chuyển động tay hay hiệu ứng sóng âm ở tai nên rất khó nhận biết.
   - **Giải pháp**:
     - **Cử chỉ đưa tay lên tai (`@keyframes robot-arm-listen`)**: Khi ở trạng thái `.is-listening`, cánh tay phải của Yori (`.robot-arm-right`) nâng cao lên sát chụp tai phải (`transform-origin: 131px 108px`, xoay `-142deg` đến `-150deg` kết hợp dịch chuyển nhẹ lên trên) tạo dáng **"khum tay lên tai lắng nghe"** rõ ràng và nhịp nhàng.
     - **Nghiêng đầu & Sóng âm thu nhận ở tai (`.robot-ear-waves` + `@keyframes robot-head-listen`)**:
       - Đầu Yori nghiêng rõ hơn (`5deg` ↔ `8deg`) hướng về phía người nói.
       - Bổ sung các vòng cung sóng âm nhỏ (`.robot-ear-waves`) bên cạnh tai phải của Yori trong SVG: bình thường ẩn, khi `.is-listening` sẽ phát xung lan tỏa nối tiếp nhau, kết hợp đèn tai nghe và ăng-ten nhấp nháy sáng để người dùng nhìn thấy ngay lập tức Yori đang chăm chú nghe mình nói.

---

### 2. Danh sách file dự kiến cập nhật
1. **[`assets/avatar.svg`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/assets/avatar.svg)**:
   - Thay thế hình bóng silhouette đơn giản bằng vector **Yori Avatar Logo** sắc nét, chuẩn thẩm mỹ Yourin.
2. **[`interview.html`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/interview.html) & [`interview-interrupt.html`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/interview-interrupt.html)**:
   - Bổ sung cụm sóng âm ở tai `.robot-ear-waves` vào trong `.robot-head-group` của SVG Yori để hiển thị khi lắng nghe.
   - Cập nhật `.tag-avatar` dưới câu hỏi sử dụng avatar Yori mới.
3. **[`css/styles.css`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/css/styles.css)**:
   - Điều chỉnh `.speech-bubble-tail` (`top: 84px`) để mũi nhọn trỏ thẳng vào miệng Yori.
   - Bổ sung animation `.interviewer-stage.is-listening .robot-arm-right` (`@keyframes robot-arm-listen` đưa tay lên tai), `.interviewer-stage.is-listening .robot-head-group` (`@keyframes robot-head-listen`), và hiệu ứng sóng âm `.robot-ear-waves` (`@keyframes ear-wave-pulse`).

### 3. Trạng thái
- **DONE** — Đã hoàn thành triển khai và kiểm tra cấu trúc HTML/CSS/SVG.

---

## [DONE] Cải thiện UX/UI & Chuẩn hóa Form theo Feedback của Teammate (Sign In/Up, Header, Job Profile, Report)

### 1. Tổng hợp & Phân tích các điểm Feedback từ Teammate

| Khu vực | Vấn đề hiện tại | Đề xuất cải thiện từ Teammate |
| --- | --- | --- |
| **Sign In / Sign Up** (`sign-in.html`, `sign-up.html`) | 1. Không có nút ẩn/hiện mật khẩu.<br>2. Tiêu đề `<h2>Log in into your account</h2>` sai ngữ pháp (`into`) và lệch thuật ngữ với tab/nút `Sign in`.<br>3. Câu chuyển trang `Dont have an account?, Sign up` thiếu dấu nháy đơn và thừa dấu phẩy.<br>4. Các thẻ `<input>` chỉ có `id`, thiếu thuộc tính `name`.<br>5. Ô mật khẩu để `autocomplete="off"`. | 1. Thêm nút con mắt ẩn/hiện password.<br>2. Đổi thành `Sign in to your account` (đồng bộ với tab & nút `Sign in`).<br>3. Đổi thành `Don't have an account? Sign up.` (và đồng bộ bên `sign-up.html`).<br>4. Bổ sung `name="username"`, `name="password"` (và `name="confirm-password"`).<br>5. Đổi thành `autocomplete="current-password"` (và `new-password` ở trang đăng ký). |
| **Header toàn trang** (`.site-header` trên 9 trang) | Thiếu nút Đăng xuất (`Sign out` / `Log out`) nhanh trên Header; người dùng phải vào trang Profile mới đăng xuất được. | Bổ sung nút `Sign out` nhanh ở khu vực `.header-right`, nằm ngay bên phải cụm Avatar & Tên người dùng. |
| **Job Profile** (`job-profile.html`) | 1. Nhãn `Position` dễ bị hiểu trùng nghĩa với `Job title`.<br>2. Placeholder `Enter job title`, `Enter domain`... lặp lại nhãn, thiếu tính gợi ý.<br>3. Nút mở rộng `USE CV FOR THIS INTERVIEW? ▾` chỉ là chữ xám nhỏ giữa 2 gạch ngang, dễ bị nhầm là đường phân cách tĩnh. | 1. Đổi nhãn `Position` thành `Seniority / Level` (kèm ví dụ hoặc menu `<select>`).<br>2. Đổi Placeholder sang ví dụ cụ thể (`e.g., Data Engineer`, `e.g., FinTech`, `e.g., Shopee`, `e.g., Junior`).<br>3. Đổi màu chữ nút mở rộng CV sang xanh cổ vịt đậm, thêm viền nút bấm (pill button) nổi bật để nhận diện rõ là nút tương tác. |
| **Report** (`report.html`) | 1. Hộp `Our Feedback` chỉ có chữ thuần, khó nắm bắt nhanh mức độ đạt của từng câu trả lời.<br>2. Cuối trang báo cáo chưa có nút hành động tiếp theo (Next steps). | 1. Gắn thêm một badge nhỏ ở góc hộp `Our Feedback` (`Good` / `Needs Improvement`).<br>2. Thêm 2 nút ở cuối trang: **`Retake interview`** (khép kín vòng lặp luyện tập) và **`Rate this feedback →`** dẫn sang `system-feedback.html`. |

---

### 2. Giải pháp Thiết kế & Kỹ thuật Chi tiết

#### A. Trang Đăng nhập & Đăng ký (`sign-in.html`, `sign-up.html`, `css/styles.css`, `js/app.js`)

1. **Đồng bộ thuật ngữ & Chuẩn hóa câu chữ**:
   - Trên [`sign-in.html`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/sign-in.html):
     - Đổi `<h2>Log in into your account</h2>` → **`<h2>Sign in to your account</h2>`**.
     - Đổi `<p class="auth-switch">Dont have an account?, <a class="text-link" href="sign-up.html">Sign up</a></p>` → **`<p class="auth-switch">Don't have an account? <a class="text-link" href="sign-up.html">Sign up</a>.</p>`**
   - Trên [`sign-up.html`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/sign-up.html):
     - Đổi `<p class="auth-switch">Already have an account?, <a class="text-link" href="sign-in.html">Sign in</a></p>` → **`<p class="auth-switch">Already have an account? <a class="text-link" href="sign-in.html">Sign in</a>.</p>`**

2. **Chuẩn hóa thuộc tính HTML (`name` & `autocomplete`)**:
   - Trên [`sign-in.html`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/sign-in.html):
     - `#username`: bổ sung `name="username"`, `type="text"`, giữ `autocomplete="username"`.
     - `#password`: bổ sung `name="password"`, đổi `autocomplete="off"` thành **`autocomplete="current-password"`**.
   - Trên [`sign-up.html`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/sign-up.html):
     - `#username`: bổ sung `name="username"`, giữ `autocomplete="username"`.
     - `#password`: bổ sung `name="password"`, đổi `autocomplete="off"` thành **`autocomplete="new-password"`**.
     - `#confirm-password`: bổ sung `name="confirm-password"`, đổi `autocomplete="off"` thành **`autocomplete="new-password"`**.
   - Đồng bộ selector xử lý submit form trong [`js/app.js`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/js/app.js) (`const authForm = $("#auth-form, #sign-in-form, #sign-up-form");`) để đảm bảo sự kiện submit luôn bắt đúng cả 2 form.

3. **Bổ sung nút Ẩn / Hiện Mật khẩu (Show/Hide Password Button)**:
   - Bọc các ô `<input type="password">` trong `<div class="password-input-wrap">`:
     ```html
     <div class="password-input-wrap">
       <input id="password" name="password" type="password" autocomplete="current-password" placeholder="Password" value="demo1234" required>
       <button type="button" class="password-toggle-btn" data-toggle-password="password" aria-label="Show password" aria-pressed="false">
         <!-- SVG Eye / Eye-Off Icon -->
       </button>
     </div>
     ```
   - **Style (`.password-input-wrap` & `.password-toggle-btn`)**:
     - `.password-input-wrap { position: relative; display: flex; align-items: center; }`
     - Ô input có `padding-right: 44px;` để chữ không đè lên icon.
     - Nút `.password-toggle-btn` đặt tuyệt đối ở bên phải (`right: 8px`), kích thước `32px × 32px`, bo góc tròn nhẹ, màu `var(--muted)`, khi hover/active chuyển sang xanh cổ vịt `var(--ink)`.
   - **Logic trong `js/app.js`**:
     - Lắng nghe sự kiện click trên `$$("[data-toggle-password]")`: chuyển đổi `input.type` giữa `"password"` và `"text"`, cập nhật `aria-label` (`"Show password"` ↔ `"Hide password"`), `aria-pressed`, và đổi icon mắt mở ↔ mắt gạch chéo.

---

#### B. Bổ sung Nút Đăng xuất Nhanh trên Header Toàn Trang (`.site-header`)

1. **Vị trí & Cấu trúc HTML (`.header-right`)**:
   - Áp dụng đồng bộ trên toàn bộ 9 trang có `.site-header` (`dashboard.html`, `job-profile.html`, `interview.html`, `interview-interrupt.html`, `done-interview.html`, `report.html`, `storage.html`, `system-feedback.html`, `thank-you.html` và `profile.html`):
   - Đặt nút **Sign out** ngay bên phải liên kết Profile (Avatar + Username), ngăn cách bằng một đường kẻ dọc mảnh tinh tế:
     ```html
     <div class="header-right">
       <a class="profile-link" href="profile.html" aria-label="Profile" title="Profile" data-nav="profile">
         <img class="header-avatar" src="assets/avatar.svg" alt="">
         <span class="profile-name" data-username>Eric Arthur Blair</span>
       </a>
       <span class="header-divider" aria-hidden="true"></span>
       <a class="header-logout-link" href="sign-in.html" data-sign-out aria-label="Sign out" title="Sign out">
         <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
           <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
           <polyline points="16 17 21 12 16 7"></polyline>
           <line x1="21" y1="12" x2="9" y2="12"></line>
         </svg>
         <span class="logout-text">Sign out</span>
       </a>
     </div>
     ```
2. **Thiết kế thị giác (`.header-divider` & `.header-logout-link`)**:
   - `.header-divider`: rộng `1px`, cao `20px`, màu `var(--line)`.
   - `.header-logout-link`: hiển thị icon đăng xuất nhỏ gọn kèm chữ `Sign out` (`font-size: 13.5px; font-weight: 500; color: var(--muted)`), bo tròn nhẹ (`padding: 6px 10px; border-radius: 999px`). Khi di chuột vào chuyển sang sắc đỏ cam dịu (`color: var(--danger); background: rgba(153, 73, 65, 0.08)`).
   - Trên màn hình di động hẹp (`<= 720px`): ẩn chữ `.logout-text`, giữ lại nút icon tròn gọn gàng bên phải Avatar.
   - Tận dụng trực tiếp sự kiện `$$("[data-sign-out]")` sẵn có trong `js/app.js` để xóa phiên hiện tại và lưu trạng thái trước khi về `sign-in.html`.

---

#### C. Cải thiện Trang Thiết lập Hồ sơ Công việc (`job-profile.html`, `css/styles.css`, `js/app.js`)

1. **Phân biệt rõ `Job title` và `Seniority / Level` + Đổi Placeholder sang ví dụ cụ thể (`e.g., ...`)**:
   - Trong khối `#job-manual-mode` (4 trường nhập tay):
     - **Trường 1 (`#job-title`)**:
       - Nhãn: `Job title`
       - Placeholder: **`e.g., Data Engineer`** (thay cho `Enter job title`)
       - Thêm `name="job-title"`
     - **Trường 2 (`#domain`)**:
       - Nhãn: `Domain`
       - Placeholder: **`e.g., FinTech, E-Commerce`** (thay cho `Enter domain`)
       - Thêm `name="domain"`
     - **Trường 3 (`#company`)**:
       - Nhãn: `Company`
       - Placeholder: **`e.g., Shopee`** (thay cho `Enter company`)
       - Thêm `name="company"`
     - **Trường 4 (`#position`)**:
       - Đổi nhãn từ `Position` → **`Seniority / Level`** (tránh trùng nghĩa với `Job title`).
       - Placeholder: **`e.g., Intern, Junior, Senior`** (hoặc sử dụng `<select id="position" name="position" data-job>` với các mức `Intern`, `Fresher / Entry-level`, `Junior`, `Mid-level`, `Senior`, `Lead / Principal` — giữ `<input>` có `datalist` hoặc placeholder `e.g., Junior, Senior` giúp vừa chọn nhanh vừa gõ tự do không làm vỡ dữ liệu cũ).

2. **Tăng độ nhận diện cho nút `USE CV FOR THIS INTERVIEW? ▾` (`#cv-section-toggle`)**:
   - Thay vì chữ xám mờ dễ nhầm là đường kẻ phân cách tĩnh, nâng cấp `.cv-extend-trigger` thành **Nút bấm viên thuốc (Interactive Pill Toggle Button)** nổi bật giữa đường phân cách:
     - **Màu chữ**: Xanh cổ vịt đậm (`color: #245b65`).
     - **Viền & Nền**: Có viền nút bấm rõ ràng (`border: 1.5px solid #8bbdc5`), nền xanh ngọc dịu (`background: #f0f8f9`), bo tròn `border-radius: 999px`, `padding: 8px 20px`, `box-shadow: 0 2px 6px rgba(36, 91, 101, 0.08)`.
     - **Hiệu ứng Hover & Active (`.is-open`)**:
       - Khi hover: nền đậm hơn (`background: #e1f2f4; border-color: #4f8f9b; transform: translateY(-1px)`).
       - Khi đang mở (`.is-open`): nền chuyển sang màu nhấn (`background: #245b65; color: #ffffff; border-color: #245b65`) giúp người dùng nhìn thoáng qua là biết ngay khu vực CV đang được bật/mở.

---

#### D. Nâng cấp Trang Báo cáo Kết quả (`report.html`, `css/styles.css`, `js/app.js`)

1. **Gắn Badge đánh giá nhỏ (`Good` / `Needs Improvement`) ở góc hộp `Our Feedback`**:
   - Trong mỗi thẻ `.report-card` → `<section class="feedback-block">`, thay thẻ `<h3>Our Feedback</h3>` đơn lẻ bằng thanh tiêu đề `.feedback-block-header`:
     ```html
     <section class="feedback-block">
       <div class="feedback-block-header">
         <h3>Our Feedback</h3>
         <span class="feedback-eval-badge is-good" data-feedback-badge="0">Good</span>
       </div>
       <p>...</p>
     </section>
     ```
   - **Thiết kế 2 trạng thái Badge (`.feedback-eval-badge`)**:
     - **`Good` (`.is-good`)**: Nền xanh lá dịu `#e4f3e8`, chữ xanh đậm `#255c36`, viền `#b8dec2`, có chấm tròn nhỏ `●` phía trước (`● Good`).
     - **`Needs Improvement` (`.is-improve`)**: Nền vàng hổ phách dịu `#fcf0d5`, chữ nâu vàng `#85581A`, viền `#ebd096`, có chấm tròn nhỏ `●` phía trước (`● Needs Improvement`).
   - **Logic hiển thị thông minh trên PoC (`report.html` & `js/app.js`)**:
     - Mặc định trên giao diện mẫu: Câu 1 và Câu 2 hiển thị badge **`Good`**, Câu 3 hiển thị badge **`Needs Improvement`** (để buổi demo thấy rõ cả 2 loại badge trực quan).
     - Ngoài ra trong `js/app.js`: nếu câu trả lời nào của người dùng bị bỏ trống (`!ans || !ans.trim()`), tự động chuyển badge của câu đó sang **`Needs Improvement`**.

2. **Bổ sung 2 Nút Hành Động ở Cuối Trang Báo Cáo (`.report-bottom-actions`)**:
   - Đặt thanh hành động `.report-bottom-actions` ở cuối `<main id="main" class="page report-page">` (ngay bên dưới `.report-stack`):
     ```html
     <div class="report-bottom-actions">
       <a class="btn btn-secondary btn-pill-action" href="interview.html" id="retake-interview-btn">
         <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
           <polyline points="1 4 1 10 7 10"></polyline>
           <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
         </svg>
         <span>Retake interview</span>
       </a>
       <a class="btn btn-pill-action" href="system-feedback.html">
         <span>Rate this feedback</span>
         <span aria-hidden="true">→</span>
       </a>
     </div>
     ```
   - **Hành vi của 2 nút**:
     - **Nút 1 — `Retake interview` (`#retake-interview-btn`)**:
       - Khi bấm vào: trong `js/app.js`, tạo một phiên phỏng vấn mới giữ nguyên cấu hình `job` và `cv` của buổi báo cáo hiện tại (`startInterview(current.cv, current.cvPdf, ...)`), rồi chuyển thẳng sang `interview.html` (Câu 1) để người dùng luyện tập lại ngay lập tức mà không phải nhập lại Job Profile từ đầu — khép kín hoàn hảo vòng lặp luyện tập.
     - **Nút 2 — `Rate this feedback →`**:
       - Dẫn trực tiếp sang `system-feedback.html`, kết nối liền mạch trải nghiệm đọc nhận xét AI với biểu mẫu khảo sát đánh giá chất lượng chấm điểm của hệ thống.

---

### 3. Danh sách File Dự kiến Cập nhật khi Triển khai
1. **`sign-in.html` & `sign-up.html`**:
   - Sửa tiêu đề `<h2>Sign in to your account</h2>` và câu dẫn `Don't have an account? Sign up.` / `Already have an account? Sign in.`.
   - Thêm thuộc tính `name` cho các thẻ `<input>` và chuẩn hóa `autocomplete="current-password"` / `"new-password"`.
   - Bổ sung nút con mắt ẩn/hiện mật khẩu (`.password-toggle-btn`).
2. **Toàn bộ 9 file HTML có `.site-header`** (`dashboard.html`, `job-profile.html`, `interview.html`, `interview-interrupt.html`, `done-interview.html`, `report.html`, `storage.html`, `system-feedback.html`, `thank-you.html`, `profile.html`):
   - Bổ sung nút đăng xuất nhanh `.header-logout-link` (`[data-sign-out]`) ở bên phải `.profile-link` trong `.header-right`.
3. **`job-profile.html`**:
   - Đổi nhãn `Position` thành `Seniority / Level`.
   - Cập nhật placeholder của 4 trường sang ví dụ cụ thể (`e.g., Data Engineer`, `e.g., FinTech, E-Commerce`, `e.g., Shopee`, `e.g., Junior, Senior`).
4. **`report.html`**:
   - Thêm `.feedback-block-header` và huy hiệu `.feedback-eval-badge` (`Good` / `Needs Improvement`) ở góc phải trên của từng hộp `Our Feedback`.
   - Thêm cụm 2 nút `.report-bottom-actions` (`Retake interview` và `Rate this feedback →`) ở cuối trang.
5. **`css/styles.css`**:
   - Style cho `.password-input-wrap` và `.password-toggle-btn`.
   - Style cho `.header-divider` và `.header-logout-link` (kèm responsive mobile).
   - Nâng cấp style `.cv-extend-trigger` thành nút pill xanh cổ vịt có viền rõ ràng.
   - Style cho `.feedback-block-header`, `.feedback-eval-badge` (`.is-good`, `.is-improve`) và `.report-bottom-actions`.
6. **`js/app.js`**:
   - Bổ sung logic ẩn/hiện mật khẩu cho `[data-toggle-password]`.
   - Đồng bộ selector `#sign-in-form, #sign-up-form`.
   - Xử lý nút `#retake-interview-btn` và cập nhật trạng thái badge trên trang `report.html`.

### 4. Trạng thái
- **DONE** — Đã triển khai đầy đủ các góp ý từ Teammate trên toàn bộ các file HTML, CSS và JS.

---

## [DONE] Tinh chỉnh Huy hiệu Đánh giá (`Good` / `Needs Improvement`) trên trang Report (`report.html`): Hiển thị đủ cả 2 loại Badge trong mọi trường hợp & Đồng bộ Bố cục, Vị trí, Bảng màu theo Theme Yourin

### 1. Phân tích Nguyên nhân Khiến Huy hiệu Hiện tại Trông Chưa Ổn & Chưa Demo Đủ 2 Loại

1. **Vì sao chưa demo được cả 2 loại huy hiệu (`Good` & `Needs Improvement`)**:
   - **Nguyên nhân 1 (Logic JS ghi đè trong `js/app.js`)**: Đoạn code trong `js/app.js` (dòng 1126–1133) đang kiểm tra `if (!ans || !ans.trim())` và ép **tất cả các câu không nhập câu trả lời** chuyển hết thành `Needs Improvement`. Khi người dùng tạo một buổi phỏng vấn mới để chạy thử luồng demo và bấm `Next` → `Finalize` nhanh mà không gõ câu trả lời, cả 3 câu hỏi đều bị đổi sạch thành `Needs Improvement` (mất hoàn toàn huy hiệu `Good`).
   - **Nguyên nhân 2 (Vị trí câu có `Needs Improvement` nằm tuốt cuối trang)**: Ở dữ liệu mẫu, cả Câu 1 và Câu 2 đều để `Good`, còn `Needs Improvement` lại đặt ở Câu 3 (nằm sâu bên dưới màn hình đầu tiên), khiến khi mới mở trang Report chỉ nhìn thấy một loại badge.

2. **Vì sao màu sắc và bố cục/vị trí của huy hiệu trông "khá kì" so với Theme Yourin**:
   - **Lệch bảng màu (Color Clash)**:
     - Giao diện Yourin sử dụng tông màu dịu, trầm ấm và thanh lịch (`--aqua: #92c7cf`, `--mist: #aad7d9`, `--cream: #fbf9f1`, `--soft: #f0f7f5`, `--ink: #203d43`), tương tự cặp badge `.status` (`#e9f3ec` / `#38604a`) và `.status.unfinished` (`#f6efdd` / `#826731`) ở trang `Your interview`.
     - Trong khi đó, `.feedback-eval-badge` lại dùng màu xanh lá tươi (`#e6f5ea` / `#20633b`) và vàng tươi (`#fdf2d8` / `#8c5b16`) kèm ký tự text `●` thô (`font-size: 9px`), đặt đè lên nền xanh bạc hà `.feedback-block` (`#f0f7f5`), làm màu xanh–vàng bị chói và lạc quẻ khỏi bảng màu chung.
   - **Lệch dòng ngang giữa cột `Your Answer` và cột `Our Feedback` (Layout Misalignment)**:
     - Cột trái (`Your Answer`) dùng `<h3>Your Answer</h3>` cỡ `14px` với `margin-bottom` mặc định của trình duyệt, không có viền khung.
     - Cột phải (`Our Feedback`) lại đổi `h3` thành `15px`, bọc trong `.feedback-block-header` có chiều cao bị đẩy lệch bởi huy hiệu, khiến dòng chữ tiêu đề `Your Answer` — `Our Feedback` và đoạn văn nội dung bên dưới của 2 cột **không nằm trên cùng một đường thẳng ngang**.

---

### 2. Giải pháp Thiết kế, Bố cục & Bảng màu Mới

#### A. Luôn Demo Đầy Đủ Cả 2 Huy Hiệu (`Good` & `Needs Improvement`) Ngay Từ Màn Hình Đầu Tiên
1. **Bố trí xen kẽ ngay tại Câu 1 & Câu 2 trên `report.html`**:
   - **Question 1**: Hiển thị huy hiệu **`Needs Improvement`** (hoặc **`Good`**) — rất khớp với nội dung nhận xét vui của Câu 1 (*"Instead of listing objects, you delivered a bold manifesto... I have no idea what 'the one who knocks' means"*).
   - **Question 2**: Hiển thị huy hiệu **`Good`** (*"Thou hast answered with a fiery, proactive spirit... consider thyself hired at once"*).
   - **Question 3**: Hiển thị huy hiệu **`Good`** (hoặc **`Needs Improvement`**).
   - Nhờ vậy, ngay khi vừa mở `report.html`, người xem nhìn thấy **cả 2 loại huy hiệu (`Needs Improvement` và `Good`) xuất hiện song song ngay trên màn hình đầu tiên** mà không cần cuộn trang.
2. **Gỡ bỏ đoạn JS tự động ghi đè mất huy hiệu `Good` trong `js/app.js`**:
   - Xóa đoạn lệnh ép tất cả câu trống thành `Needs Improvement` trong `js/app.js`. Dù người thuyết trình mở buổi phỏng vấn mẫu hay tạo nhanh một buổi phỏng vấn mới để demo, trang `report.html` luôn giữ nguyên kịch bản hiển thị đầy đủ cả 2 loại huy hiệu `Good` và `Needs Improvement`.

---

#### B. Căn chỉnh lại Layout & Vị trí 2 Cột `Your Answer` – `Our Feedback`
1. **Đồng bộ thanh tiêu đề của cả 2 cột (`.report-col-header`)**:
   - Cả cột trái (`Your Answer`) và cột phải (`Our Feedback`) đều dùng chung cấu trúc thanh tiêu đề `.report-col-header` (`display: flex; align-items: center; justify-content: space-between; min-height: 28px; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid rgba(32, 61, 67, 0.08)`):
     - Cột trái: `<h3>Your Answer</h3>`
     - Cột phải: `<h3>Our Feedback</h3>` bên trái + Huy hiệu `.feedback-eval-badge` căn sát góc phải.
   - Nhờ có cùng `min-height: 28px`, cùng `font-size: 14px; font-weight: 700; color: var(--ink)` và đường kẻ phân cách mảnh bên dưới tiêu đề, hai tiêu đề **`Your Answer`** và **`Our Feedback`** cùng phần văn bản trả lời/nhận xét bên dưới sẽ **thẳng hàng ngang 100%**.
2. **Tinh chỉnh khung hộp `. report-columns > section` & `.feedback-block`**:
   - Cột trái (`.answer-block`): Nền trắng tinh sạch kết hợp viền mảnh `border: 1px solid #e6eeec; border-radius: 14px; padding: 20px 24px`.
   - Cột phải (`.feedback-block`): Nền kem–xanh dịu `background: var(--soft)` (`#f0f7f5`) kèm viền đồng bộ `border: 1px solid #d5e6e3; border-radius: 14px; padding: 20px 24px`.
   - Xóa bỏ thẻ `<div class="report-section-heading"></div>` rỗng đang tạo khoảng trống thừa `32px` phía trên danh sách câu hỏi.

---

#### C. Bảng Màu Huy Hiệu Đồng Bộ Tuyệt Đối với Theme Yourin (`.feedback-eval-badge`)
Sử dụng đúng ngôn ngữ thiết kế của huy hiệu `.status` trên trang `Your interview` (`storage.html`): chấm tròn nhỏ tạo bằng CSS `::before` (`width: 6px; height: 6px; border-radius: 50%`), chữ `12px`, `font-weight: 600`, `padding: 4px 12px`, `border-radius: 999px`:

1. **Huy hiệu `Good` (`.feedback-eval-badge.is-good` — Tông Deep Teal nổi bật chuẩn Yourin)**:
   - **Background**: `#245b65` (xanh cổ vịt đậm chủ đạo của Yourin, tạo độ tương phản sắc nét trên nền hộp `var(--soft)` `#F0F7F5`, không còn bị nhạt nhòa).
   - **Text color**: `#ffffff` (trắng sắc nét).
   - **Border**: `1px solid #1c4952` kèm `box-shadow: 0 2px 6px rgba(36, 91, 101, 0.16)`.
   - **Dot (`::before`)**: `#7ee8db` (chấm sáng xanh ngọc nổi bật trên nền xanh đậm).

2. **Huy hiệu `Needs Improvement` (`.feedback-eval-badge.is-improve` — Tông Warm Apricot-Beige & Orange)**:
   - **Background**: `#fef3e2` (vàng be / kem cam sáng sạch, tách biệt rõ trên nền `#f0f7f5`).
   - **Text color**: `#9e4c14` (cam hổ phách đậm rõ nét).
   - **Border**: `1px solid #f0c999` kèm `box-shadow: 0 2px 6px rgba(180, 88, 24, 0.1)`.
   - **Dot (`::before`)**: `#e8772e` (chấm cam tươi tắn).

---

### 3. Danh sách File Dự kiến Cập nhật khi Triển khai
1. **[`report.html`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/report.html)**:
   - Xóa `<div class="report-section-heading"></div>` rỗng.
   - Đồng bộ `.report-col-header` cho cả cột `Your Answer` và `Our Feedback` để căn thẳng hàng ngang.
   - Bỏ ký tự `●` cứng trong HTML, dùng `::before` chuẩn chỉnh; đặt Question 1 là `Needs Improvement` (hoặc `Good`), Question 2 là `Good` (hoặc `Needs Improvement`), Question 3 là `Good` để cả 2 huy hiệu luôn xuất hiện ngay nửa trên trang.
2. **[`css/styles.css`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/css/styles.css)**:
   - Cập nhật `.report-columns > section`, `.feedback-block`, `.report-col-header`, và hệ màu `.feedback-eval-badge.is-good` / `.feedback-eval-badge.is-improve` tiệp 100% với bảng màu Yourin.
3. **[`js/app.js`](file:///c:/Users/Mavc/Desktop/interview-poc/interview-poc/js/app.js)**:
   - Gỡ bỏ vòng lặp ghi đè `$$("[data-feedback-badge]")` khi câu trả lời trống để luôn bảo toàn việc demo cả 2 loại huy hiệu trong mọi phiên phỏng vấn.

### 4. Trạng thái
- **DONE** — Đã triển khai và đồng bộ toàn bộ bảng màu, bố cục 2 cột và kịch bản hiển thị cả 2 huy hiệu.
