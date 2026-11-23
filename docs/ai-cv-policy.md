# Chinh sach xu ly du lieu CV/JD khi gui cho AI

**Ngay tao:** 2026-11-14 · **Pham vi:** nhánh `AI` (assistant-team06) · **Trang thai:** CHO DUYET

Tai lieu nay quy dinh du lieu gi duoc phep gui toi LLM (NVIDIA host) trong tinh nang
phong van thử, va phai duoc thong nhat TRUOC KHI bien `INTERVIEW_ALLOW_CV_TO_AI`
duoc dat thanh `1`. Co che che PII da duoc cai dat va co test, va nguoi quan tri
da thong nhat huong bat; moi moi truong trien khai van phai lam day du cac buoc
o muc 6 truoc khi bat.

## 1. Muc dich

- Cho phep AI doc JD (Job Profile) va CV de sinh cau hoi sat hon voi tung ung vien
  va tung vi tri, thay vi cau hoi chung chung.
- Khong dat du lieu ca nhan cua ung vien vao rui ro: chi gui nhung gi thuc su can
  cho cau hoi, che thong tin nhan dang, va khong giua lau.

## 2. Pham vi du lieu gui di

| Du lieu | Khi nao gui | Ghi chu |
| --- | --- | --- |
| Job Profile | Luon luon gui | La yeu cau cong viec, khong phai du lieu ca nhan cua ung vien. |
| CV cua ung vien | Chi khi `INTERVIEW_ALLOW_CV_TO_AI=1` | Neu co bang 0, CV KHONG duoc vao prompt. |
| Summary/research notes | Du lieu danh cho LLM | Ket qua nghien cuu web (TinyFish) va phan tong hop, dung de nen tang cho cau hoi. |
| Hoc ba, diem so, giai thuoc chi tiet | Khong gui | Nam ngoai pham vi cua tai lieu nay. |

## 3. Quy tac che du lieu (bat buoc)

Ham `mask_cv_pii()` trong `src/assistant/aiworker.py` phai thay the email bang
`[email]` va so dien thoai bang `[phone]` TRUOC KHI CV duoc dat vao prompt. Day la
buoc bat buoc, khong tuy chon.

Vi du truoc/sau khi che:

```text
Truoc khi che:
"Ung vien: Nguyen Van A. Lien he: nguyenvana@gmail.com, sdt 0912 345 678.

Sau khi che (vao prompt):
"Ung vien: Nguyen Van A. Lien he: [email], sdt [phone].
```

Quy tac bo sung:

- Chi giu lai phan CV lien quan den ky nang, kinh nghiem, hoc van lien quan den vi
  tri; bo phan thong tin nhan dang khong can thiet.
- Neu chua co co che che, hoac chua chac no chay dung, thi CV khong duoc gui di.

## 4. Nhung dieu cam

- In hoac ghi log CV tho (noi dung CV nguyen ban).
- Ghi CV tho hoac noi dung tra loi ca nhan cua ung vien vao report/bao cao.
- Gui API key ra ngoai server (key chi ton tai trong bien moi truong cua Render).
- Commit file `.env` that chua key that vao repo (`.env` nam trong `.gitignore`).
- Gui CV di khi chua bat co che che (xem muc 3).

## 5. Luu tru va bao mat

- CV chi nam trong prompt gui toi NVIDIA API trong mot lan goi; khong luu lau phia
  server sau khi cau hoi duoc sinh ra.
- Key chi dat tren Render dashboard, khong bao gio nam trong repo hay trong code.
- Log chi ghi latency va ma loi (vi du `AiTimeoutError`, `HTTP 429`); khong ghi noi
  dung prompt, khong ghi CV, khong ghi key.
- Module `src/assistant/ai.py` chi dung key lam request header (`Authorization`
  / `X-API-Key`); no khong log, khong tra va va khong ghi key ra dia.

## 6. Quy trinh bat co `INTERVIEW_ALLOW_CV_TO_AI=1`

1. Duyet tai lieu policy nay.
2. Test local voi CV gia lap (khong dung CV that).
3. Phe duyet cua nguoi quan tri du an.
4. Dat bien tren Render dashboard.
5. Ghi nhan thoi diem bat (them vao muc "Trang thai hien tai" ben duoi).

## 7. Kiem tra va rollback

- Dat lai `INTERVIEW_ALLOW_CV_TO_AI=0` ngay khi phat hien bat thuong (vi du: CV tho
  hien trong log, bao cao, hoac loi bat ngo o buon sinh cau hoi).
- Doi key neu nghi lo key; luu y key cu phai bi thu hoi phia NVIDIA/TinyFish.
- Review dinh ky chinh sach nay va cac muc log lien quan.

## 8. Trang thai hien tai

- Nguoi quan tri da thong nhat huong bat (2026-11-16) sau khi `mask_cv_pii()` co
  test. Vi vay `.env.example` ship `INTERVIEW_ALLOW_CV_TO_AI=1` va
  `INTERVIEW_AI_PROVIDER=mock`; chi khi bien doi sang `nvidia` va co that
  `NVIDIA_API_KEY` thi cau hoi moi thuc su co CV trong prompt.
- Moi moi truong trien khai van tu dat bien cua rieng theo muc 6: duyet policy,
  test local voi CV gia lap, phe duyet quan tri, dat bien tren dashboard, roi
  ghi nhan thoi diem bat. Dat `0` de quay lai hanh dong ngay lap tuc.

## 9. Lien ket voi code (tham chieu)

- Mui noi phong van `src/assistant/interview_ai.py` chi chuyen tiep CV
  (`{"raw": cv}`) cho module cua nhom (`TeamInterviewAI.generate_questions`) KHI
  VA CHI KHI co `allow_cv=True`, tuc la `INTERVIEW_ALLOW_CV_TO_AI=1`
  (xem `configured_ai()`). Khi co o gia tri khac `1`, CV khong bao gio toi
  `aiworker.py`/`ai.py`.
- Cac ten bien moi truong cua lop AI (`AI_MAX_TOKENS`, `AI_TIMEOUT_S`,
  `AI_TEMPERATURE`, `AI_RESEARCH_TURNS`, `AI_MAX_TOOL_CALLS`, `NVIDIA_*`,
  `TINYFISH_*`, `AI_RETRY_DELAY_S`) nam o `.env.example` va duoc doc boi
  `src/assistant/ai.py` (`FETCH_*` va `AI_RETRIES` chi duoc code doc voi
  gia tri mac dinh, khong nam trong `.env.example`). Bien `INTERVIEW_*`
  thuoc ve lop phong van, khong su dung
  cho muc dich gui CV trong tai lieu nay ngoai `INTERVIEW_ALLOW_CV_TO_AI`.