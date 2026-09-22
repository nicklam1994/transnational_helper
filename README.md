# 德安物流小助手 (Transnational Helper)

Teamwork 訂單管理系統 - 本地 Flask Web 應用，提供訂單查看、報表統計、地址管理、運單列印等功能。

## 功能特性

### 📦 訂單管理
- **全部訂單**：查看所有訂單，支持多條件篩選（狀態、日期、AM/PM），**自動刷新**（預設 30 秒，可調整）
- **訂單報表**：日報表/月報表/年報表，Cancelled 以刪除線顯示，**自動刷新**
- **物流查詢**：追蹤訂單物流狀態

### 🖨️ 運單列印（完全靜默、不需任何 PDF 程式）
- **原單 (A4)**：Teamwork 收據 PDF 以印表機原生 DPI 等比縮放，經 Windows 印表機驅動 **GDI 直印** → 指定 A4 印表機，1 張
- **標籤機**：A4 兩聯自動切開、旋轉縮放成 102×210mm → **GDI 直印** → 指定標籤機，2 張
- **標簽機 (ZPL)**：程式自行點陣化成 ZPL，**直送印表機 raw 埠 9100**（不經 Windows 驅動）
- 三種模式都 **無對話框、無彈窗**，且 **不需要** Adobe Reader / Foxit / 任何 PDF 閱讀程式
- 列印前請先在左下 ⚙️ **設定** 選好「原始運單打印機 (A4)」「標籤運單打印機 (Label)」與標籤機 IP
- **新單監聽自動列印**：開啟後自動偵測新訂單並列印（預設原單 A4，可切換標籤機/ZPL），每 20 秒檢查一次
- 驗證送印：A4／標籤走 Windows 佇列（`Get-PrintJob -PrinterName "<印表機>"`）；
  ZPL 直送不進佇列，用印表機查詢（`~HI` / `~HS`）

### 📍 地址管理
- 完整的地址 CRUD（新增/編輯/刪除/搜尋）
- 國家 → 城市 → 地區 → 區域 下拉連動
- 新增地址預設：郵編留空，聯絡人/電話/分機/手機/電郵填 `-`
- 自訂樣式的刪除確認彈窗 + 右上角 Toast 提示

### 🔐 自動保活
- 透過 Edge CDP 保持 Teamwork 登入狀態
- 5 秒輪詢 localStorage（零網路請求）
- Token 即將過期時自動觸發刷新（模擬用戶點擊）
- 寫入 `token.json` 供後端使用

### 🔧 依賴檢查與修復
- **自動檢查**：`setup.bat` 與 `apply_update.bat` 會自動檢查所有依賴是否完整
- **一鍵修復**：`repair_deps.bat` 自動修復損壞的依賴（如 PyMuPDF 的 DLL 缺失）
- **系統 runtime**：`install_vcruntime.bat` 自動下載並安裝 VC++ 2015-2022 Redistributable（全新 Windows 常缺）

## 安裝步驟

### 1. 環境準備
- Windows 10/11
- Python 3.10+（需加入 PATH，推薦 3.12）
- Microsoft Edge
- **VC++ 2015-2022 Redistributable (x64)**（全新 Windows 常缺，見下方說明）

### 2. 安裝 VC++ Runtime（如需要）
若系統缺少 VC++ runtime（`ImportError: DLL load failed while importing _extra`），執行：
```bash
# 右鍵以系統管理員身分執行
install_vcruntime.bat
```
或手動下載安裝：https://aka.ms/vs/17/release/vc_redist.x64.exe

### 3. 安裝依賴
雙擊 `setup.bat`，會自動：
- 停止正在運行的服務（避免檔案被鎖）
- 檢測 Python 環境（優選 3.12/3.13）
- 創建虛擬環境 `.venv`
- 安裝依賴套件（flask, flask-cors, requests, playwright, PyPDF2, PyMuPDF, pywin32, pillow）
- **自動檢查依賴完整性**

### 4. 啟動 Edge Debug 模式
雙擊 `start_server.bat` 會自動啟動 Edge（帶 `--remote-debugging-port=9222`）

### 5. 啟動服務
```bash
# 啟動 Flask 伺服器（端口 5000）+ Keepalive 服務
start_server.bat

# 或分開啟動
restart_server.bat        # 只啟動 Flask
restart_keepalive.bat     # 只啟動 Keepalive
```

### 6. 登入 Teamwork
瀏覽器會自動開啟 `http://localhost:5000`，點擊「登入」按鈕：
1. 輸入 Teamwork 帳號（例如：hase.gts.mail@hangseng.com）
2. 輸入收到的 OTP 驗證碼
3. 登入成功後會自動跳轉到訂單頁面

## 使用說明

### 訂單篩選
- **狀態篩選**：多選下拉框，可同時選擇多個狀態
- **日期篩選**：支持 yyyy/mm/dd 格式自動格式化
- **清除篩選**：一鍵清除所有篩選條件
- **自動刷新**：預設每 30 秒自動更新（可在設定頁調整或關閉）

### 運單列印
1. 點擊左側選單「🖨️ 運單列印」
2. 選擇列印方式：原單 (A4) / 標籤機 / 標簽機 (ZPL)
3. 搜尋訂單（支持逗號分隔多個訂單號）
4. 勾選要列印的訂單
5. 點擊「🖨️ 列印選中」

**新單監聽自動列印**：
1. 在運單列印頁開啟「🔔 新單監聽自動列印」開關
2. 選擇列印方式（預設原單 A4）
3. 系統會自動偵測新訂單並列印（每 20 秒檢查一次）

### 地址管理
1. 點擊左側選單「📍地址管理」
2. 點擊「+ 新增地址」按鈕
3. 填寫表單（地址欄位各佔整行，其餘收進「選填」折疊區）
4. 點擊「保存」

### 報表查看
- **今日統計**：頂部 3 張卡片顯示今日 AM/PM/總計
- **報表類型**：日報表/月報表/年報表
- **Cancelled 顯示**：刪除線 + 扣除後數字（例：~~20~~19）
- **自動刷新**：預設每 30 秒自動更新

## 技術架構

```
┌─────────────────────────────────────────┐
│         瀏覽器 (localhost:5000)          │
│              app.html                   │
│  - 自動刷新（全部訂單/運單列印/訂單報表） │
│  - 新單監聽自動列印                      │
└──────────────┬──────────────────────────┘
               │ HTTP API
┌──────────────▼──────────────────────────┐
│         Flask Server (server.py)        │
│  - /api/orders                          │
│  - /api/addresses (CRUD)                │
│  - /api/geo/* (國家/城市/地區/區域)      │
│  - /api/print-waybill (GDI/ZPL)         │
│  - /api/printers                        │
└──────────────┬──────────────────────────┘
               │ 讀取 token.json
┌──────────────▼──────────────────────────┐
│    Keepalive Service (keepalive.py)     │
│  - 5s 輪詢 localStorage                 │
│  - <55s 自動切 tab 觸發刷新              │
│  - 寫入 token.json                      │
└──────────────┬──────────────────────────┘
               │ Edge CDP (9222)
┌──────────────▼──────────────────────────┐
│     Edge Browser (Teamwork 頁面)        │
│  - Flutter App                          │
│  - localStorage (token)                 │
└─────────────────────────────────────────┘
```

## 檔案說明

| 檔案 | 說明 |
|------|------|
| `app.html` | 前端單頁應用（訂單/報表/地址管理/運單列印） |
| `server.py` | Flask 後端（API 路由、GDI/ZPL 列印） |
| `keepalive_service.py` | 自動保活服務 |
| `check_deps.py` | 依賴檢查與自動修復工具 |
| `setup.bat` | 安裝依賴（含依賴檢查） |
| `start_server.bat` | 啟動 Flask + Edge + Keepalive |
| `restart_server.bat` | 重啟 Flask |
| `restart_keepalive.bat` | 重啟 Keepalive |
| `apply_update.bat` | 應用更新（含依賴檢查 + 重啟服務） |
| `repair_deps.bat` | 一鍵修復損壞的依賴 |
| `install_vcruntime.bat` | 安裝 VC++ 2015-2022 Redistributable |
| `.gitignore` | Git 忽略規則 |

## 更新流程

### 本機更新
1. 修改程式碼
2. 雙擊 `apply_update.bat`（自動檢查依賴 + 重啟服務）
3. 瀏覽器按 `Ctrl+F5` 強制重新整理

### 另一台電腦更新
1. 下載「更新包.zip」（包含 `app.html`、`server.py`、`check_deps.py`、`repair_deps.bat`、`install_vcruntime.bat`、`apply_update.bat`、`setup.bat`、`更新說明.txt`）
2. 解壓到小助手資料夾（覆蓋舊檔案）
3. 雙擊 `apply_update.bat`（會自動檢查依賴，缺則提示修復）
4. 瀏覽器按 `Ctrl+F5`

## 故障排查

### 列印功能失效
- **症狀**：`ImportError: DLL load failed while importing _extra`
- **原因 1**：系統缺少 VC++ runtime（全新 Windows 常見）
  - **解決**：執行 `install_vcruntime.bat`（管理員）或手動安裝 https://aka.ms/vs/17/release/vc_redist.x64.exe
- **原因 2**：PyMuPDF 安裝不完整（`mupdfcpp64.dll` 缺失或截斷）
  - **解決**：先關閉所有服務，再執行 `repair_deps.bat`
- **診斷**：執行 `.venv\Scripts\python.exe check_deps.py --verify`

### Token 失效
- **症狀**：API 回傳 401 或「無法獲取 token」
- **解決**：
  1. 確認 Edge 仍在運行（`start_server.bat` 會自動啟動）
  2. 確認 Keepalive 服務在運行（`restart_keepalive.bat`）
  3. 瀏覽器重新登入 Teamwork

### 自動刷新不工作
- **檢查**：設定頁「🔄 自動刷新」是否開啟
- **調整**：可修改刷新間隔（5-600 秒）或關閉
- **注意**：正在輸入、彈窗開啟、列印中會自動跳過

## 注意事項

### Token 管理
- `token.json` 包含登入憑證，**不要上傳到 GitHub**
- 每次登入會重新生成
- Keepalive 服務會自動刷新 token

### API 端點
Teamwork API 基址：`https://hk-teamwork-api-rp.transnational-grp.com`

主要端點：
- 訂單列表：`POST /api/Order/GetAllOrders`
- 地址列表：`POST /api/Contact/GetContactAddressByContactId`
- 地址新增：`POST /api/Contact/SavecontactAddress`（INSERT ONLY，無去重）
- 地址更新：`PUT /api/Contact/UpdateContactAddress`
- 地址刪除：`DELETE /api/Contact/DeleteContactAddressBook`

### 地址遷移
如需從 DHL 遷移地址到 Teamwork：
1. 匯出 DHL 地址簿（JSON）
2. 使用 `batch_import.py` 腳本批量導入
3. 每批 100 筆，間隔 60 秒（避免觸發限流）

## 開發者

- **GitHub**: [nicklam1994](https://github.com/nicklam1994)
- **項目**: 德安物流小助手
- **用途**: Hang Seng GTS 快遞 operation

## License

Private - 僅供內部使用
