# AIP491 — Hướng dẫn chạy & chia sẻ (share localhost)

Tài liệu dành cho thành viên **không có sẵn `start.bat`** — hướng dẫn chạy thủ công từng bước
và cách chia sẻ demo qua **VS Code Dev Tunnels**.

---

## 1. Kiến trúc & cổng

| Service | Thư mục | Cổng | Ghi chú |
|---------|---------|------|---------|
| Backend (BE) | `be` | **8000** | FastAPI. Frontend gọi vào đây. |
| AI Service | `ai` | **8001** | Chỉ BE gọi nội bộ (không cần mở ra ngoài). |
| Frontend (FE) | `fe/my-react-app` | **5173** | React + Vite. Người dùng mở trang này. |

FE gọi BE qua biến `VITE_API_BASE_URL`. BE gọi AI qua `AI_SERVICE_URL` (mặc định `http://127.0.0.1:8001`).

---

## 2. Yêu cầu cài đặt (mỗi máy làm 1 lần)

- **Python 3.11+** (bắt buộc 3.11, code dùng `datetime.UTC` — Python 3.10 sẽ lỗi).
- **Node.js 18+** và npm.
- **Git**.
- (Khuyến nghị) **uv** để tạo venv nhanh: `pip install uv`. Không có uv vẫn chạy được bằng `venv` + `pip`.

---

## 3. Lấy mã nguồn

3 repo tách biệt, cùng nhánh `dev`. Đặt cạnh nhau trong 1 thư mục cha (ví dụ `AIP491/`):

```powershell
mkdir AIP491; cd AIP491
git clone -b dev https://github.com/AIP491-G05-Capstone-Project/be.git be
git clone -b dev https://github.com/AIP491-G05-Capstone-Project/ai.git ai
git clone -b dev https://github.com/AIP491-G05-Capstone-Project/fe.git fe
```

Cấu trúc mong đợi:
```
AIP491/
├── be/                 # backend
├── ai/                 # ai service
└── fe/my-react-app/    # frontend
```

---

## 4. Cấu hình biến môi trường (.env)

> File `.env` **không** được commit lên Git (đã nằm trong `.gitignore`). Mỗi người tự tạo từ `.env.example`.

**Backend** (`be`):
```powershell
cd be
copy .env.example .env
```
Mở `be\.env` và điền các giá trị thật: `DATABASE_URL`, `JWT_SECRET_KEY`, `SMTP_*`, `CLOUDINARY_*`,
`GOOGLE_CLIENT_ID`, và (nếu dùng tìm CV) `CAREERVIET_*`, `VIETNAMWORKS_*`.
Xin bộ giá trị này từ trưởng nhóm (không đăng công khai).

**AI Service** (`ai`):
```powershell
cd ai
copy .env.example .env
```

**Frontend** (`fe/my-react-app`):
```powershell
cd fe\my-react-app
copy .env.example .env.local
```
Chạy local thì để `VITE_API_BASE_URL=http://localhost:8000` là được.

---

## 5. Cài dependencies & chạy (thủ công, không cần start.bat)

Mở **3 cửa sổ terminal** riêng.

### Terminal 1 — Backend (:8000)
```powershell
cd be
uv venv .venv --python 3.11        # hoặc: python -m venv .venv
.venv\Scripts\activate
uv pip install -r requirements.txt # hoặc: pip install -r requirements.txt
uvicorn app.main:app --reload
```
Kiểm tra: mở http://127.0.0.1:8000/docs

### Terminal 2 — AI Service (:8001)
```powershell
cd ai
uv venv .venv --python 3.11        # hoặc: python -m venv .venv
.venv\Scripts\activate
uv pip install -r requirements.txt # hoặc: pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### Terminal 3 — Frontend (:5173)
```powershell
cd fe\my-react-app
npm install
npm run dev
```
Mở http://localhost:5173

> **Lưu ý:** đổi bất kỳ file `.env` nào thì phải **tắt và chạy lại** service tương ứng (env chỉ nạp lúc khởi động).

### (Tùy chọn) Chạy nhanh bằng start.bat trên Windows
Nếu muốn 1 lệnh khởi động cả 3, tạo file `start.bat` ở thư mục cha `AIP491/` với nội dung:
```bat
@echo off
set ROOT=%~dp0
start "Backend :8000"  cmd /k "cd /d %ROOT%be  && .venv\Scripts\uvicorn app.main:app --reload"
start "AI :8001"       cmd /k "cd /d %ROOT%ai  && .venv\Scripts\uvicorn app.main:app --reload --port 8001"
start "Frontend :5173" cmd /k "cd /d %ROOT%fe\my-react-app && npm run dev"
```
(Chạy được sau khi đã tạo venv + cài dependencies ở bước 5.)

---

## 6. Chia sẻ demo ra ngoài qua VS Code Dev Tunnels

Chỉ cần mở **2 cổng: 8000 (BE) và 5173 (FE)**. AI (8001) chạy nội bộ, không cần mở.

### 6.1. Cài & đăng nhập (một lần)
```powershell
winget install Microsoft.devtunnel
devtunnel user login
```

### 6.2. Tạo tunnel cố định cho 2 cổng
```powershell
devtunnel create aip491 --allow-anonymous
devtunnel port create aip491 -p 8000
devtunnel port create aip491 -p 5173
devtunnel host aip491
```
→ In ra 2 URL trong dòng `Connect via browser:` (giữ terminal này chạy, đóng là tắt tunnel).
Lưu ý: phần đầu URL là **host-id tự sinh ngẫu nhiên** (KHÔNG phải tên `aip491`), ví dụ:
- BE: `https://<host-id>-8000.<region>.devtunnels.ms`  (vd `https://ldpzj0h5-8000.asse.devtunnels.ms`)
- FE: `https://<host-id>-5173.<region>.devtunnels.ms`
Host-id này **cố định** theo tunnel `aip491` (dùng lại được các lần host sau, không đổi).

### 6.3. Trỏ cấu hình sang URL tunnel
1. `be\.env` → đặt:
   ```
   BACKEND_PUBLIC_URL=https://aip491-xxxx-8000.<region>.devtunnels.ms
   ```
   (Để link preview file trả về đúng URL tunnel, không phải localhost.)
2. `fe\my-react-app\.env.local` → đặt:
   ```
   VITE_API_BASE_URL=https://aip491-xxxx-8000.<region>.devtunnels.ms
   ```

### 6.4. Khởi động lại dịch vụ (bắt buộc, để nạp .env mới)
- BE: tắt rồi chạy lại `uvicorn app.main:app --reload`.
- FE: chạy ở **chế độ tunnel** để HMR hoạt động:
  ```powershell
  cd fe\my-react-app
  $env:VITE_TUNNEL=1; npm run dev
  ```

### 6.5. Gửi link
Gửi cho người xem **URL FE (-5173)**. Họ mở là dùng được, **đăng nhập bằng email/mật khẩu**.

### 6.6. Chuyển nhanh giữa chạy LOCAL và DEV TUNNEL

Chỉ khác nhau **3 chỗ**. BE và AI khởi động y hệt ở cả 2 chế độ (`uvicorn ... --port 8000` / `--port 8001`).

| Cần đổi | File / Nơi | Chạy LOCAL | Chạy DEV TUNNEL |
|---|---|---|---|
| 1. URL public của BE | `be/.env` → `BACKEND_PUBLIC_URL` | `http://localhost:8000` | `https://<host-id>-8000.<region>.devtunnels.ms` |
| 2. URL BE cho FE gọi | `fe/my-react-app/.env.local` → `VITE_API_BASE_URL` | `http://localhost:8000` | `https://<host-id>-8000.<region>.devtunnels.ms` |
| 3. Cách chạy FE + tunnel | Terminal | `npm run dev` | `$env:VITE_TUNNEL=1; npm run dev` **+** terminal khác chạy `devtunnel host aip491` |

**→ Đổi sang LOCAL:** sửa (1) và (2) về `http://localhost:8000` → chạy FE bằng `npm run dev` → **restart BE + FE**.

**→ Đổi sang DEV TUNNEL:** chạy `devtunnel host aip491` để lấy URL → điền URL `-8000` vào (1) và (2) → chạy FE bằng `$env:VITE_TUNNEL=1; npm run dev` → **restart BE + FE**.

> ⚠️ Bắt buộc **restart BE và FE** mỗi khi đổi 2 file env (env chỉ đọc lúc khởi động).
> `VITE_TUNNEL=1` chỉ để HMR (hot reload) chạy đúng qua tunnel; chạy local thì bỏ đi.

### Kiểm tra nhanh khi lỗi
- Mở `URL-8000/docs` trên máy/điện thoại khác → thấy Swagger ⇒ BE tunnel OK.
- FE báo *"Blocked request / host not allowed"* ⇒ thiếu `allowedHosts` trong `vite.config.ts` (đã cấu hình sẵn cho `.devtunnels.ms`).
- FE trắng / gọi API lỗi ⇒ `VITE_API_BASE_URL` sai hoặc chưa restart FE.
- Preview file trả localhost ⇒ chưa đặt `BACKEND_PUBLIC_URL` hoặc chưa restart BE.

### Cảnh báo bảo mật
- `--allow-anonymous` = **ai có link đều vào được**. `.env` chứa secret thật → **tắt tunnel (đóng terminal 6.2) ngay khi demo xong**.
- **Google login** không chạy trên domain tunnel (trừ khi thêm origin vào Google Cloud Console) → dùng email/mật khẩu.

---

## 7. Push code lên GitHub (an toàn)

3 repo tách biệt → push từng repo. **Tuyệt đối không commit `.env`.**

### 7.1. Kiểm tra trước khi commit
```powershell
cd be
git status                    # .env KHÔNG được xuất hiện trong danh sách
git check-ignore .env         # in ra ".env" nghĩa là đã bị ignore (đúng)
```

### 7.2. Commit & push (làm tương tự cho từng repo có thay đổi)
```powershell
cd be
git add -A
git commit -m "docs: them huong dan chay va chia se qua dev tunnels"
git push origin dev
```
```powershell
cd ..\fe
git add -A
git commit -m "chore: cau hinh vite cho dev tunnels + cap nhat .env.example"
git push origin dev
```

> Khuyến nghị: làm việc trên **nhánh feature** rồi tạo Pull Request thay vì push thẳng `dev`:
> ```powershell
> git checkout -b feature/dev-tunnels
> git push -u origin feature/dev-tunnels
> ```

### 7.3. Nếu lỡ commit .env
1. Xoá khỏi Git (giữ file local): `git rm --cached .env` → commit lại.
2. **Đổi toàn bộ secret** đã lộ (mật khẩu DB, SMTP, API key...) vì lịch sử Git vẫn còn.
