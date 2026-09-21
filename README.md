# 德安物流小助手 (Transnational Helper)

Teamwork 訂單管理系統 - 本地 Flask Web 應用，提供訂單查看、報表統計、地址管理等功能。

## 功能特性

### 📦 訂單管理
- **訂單詳情**：查看所有訂單，支持多條件篩選（狀態、日期、AM/PM）
- **訂單報表**：日報表/月報表/年報表，Cancelled 以刪除線顯示
- **物流查詢**：追蹤訂單物流狀態

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

## 安裝步驟

### 1. 環境準備
- Windows 10/11
- Python 3.10+（需加入 PATH）
- Microsoft Edge

### 2. 安裝依賴
雙擊 `setup.bat`，會自動：
- 檢測 Python 環境
- 創建虛擬環境 `.venv`
- 安裝依賴套件（flask, flask-cors, requests, playwright）

### 3. 啟動 Edge Debug 模式
雙擊 `start_server.bat` 會自動啟動 Edge（帶 `--remote-debugging-port=9222`）

### 4. 啟動服務
```bash
# 啟動 Flask 伺服器（端口 5000）
start_server.bat

# 啟動 Keepalive 服務（保持登入）
restart_keepalive.bat
```

### 5. 登入 Teamwork
瀏覽器會自動開啟 `http://localhost:5000`，點擊「登入」按鈕：
1. 輸入 Teamwork 帳號（例如：hase.gts.mail@hangseng.com）
2. 輸入收到的 OTP 驗證碼
3. 登入成功後會自動跳轉到訂單頁面

## 使用說明

### 訂單篩選
- **狀態篩選**：多選下拉框，可同時選擇多個狀態
- **日期篩選**：支持 yyyy/mm/dd 格式自動格式化
- **清除篩選**：一鍵清除所有篩選條件

### 地址管理
1. 點擊左側選單「📍地址管理」
2. 點擊「+ 新增地址」按鈕
3. 填寫表單（地址欄位各佔整行，其餘收進「選填」折疊區）
4. 點擊「保存」

### 報表查看
- **今日統計**：頂部 3 張卡片顯示今日 AM/PM/總計
- **報表類型**：日報表/月報表/年報表
- **Cancelled 顯示**：刪除線 + 扣除後數字（例：~~20~~19）

## 技術架構

```
┌─────────────────────────────────────────┐
│         瀏覽器 (localhost:5000)          │
│              app.html                   │
└──────────────┬──────────────────────────┘
               │ HTTP API
┌──────────────▼──────────────────────────┐
│         Flask Server (server.py)        │
│  - /api/orders                          │
│  - /api/addresses (CRUD)                │
│  - /api/geo/* (國家/城市/地區/區域)      │
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
| `app.html` | 前端單頁應用（訂單/報表/地址管理） |
| `server.py` | Flask 後端（API 路由） |
| `keepalive_service.py` | 自動保活服務 |
| `setup.bat` | 安裝依賴 |
| `start_server.bat` | 啟動 Flask + Edge |
| `restart_server.bat` | 重啟 Flask |
| `restart_keepalive.bat` | 重啟 Keepalive |
| `apply_update.bat` | 應用更新（重啟服務） |
| `.gitignore` | Git 忽略規則 |

## 更新流程

### 本機更新
1. 修改程式碼
2. 雙擊 `apply_update.bat`（自動重啟服務）
3. 瀏覽器按 `Ctrl+F5` 強制重新整理

### 另一台電腦更新
1. 下載「更新包.zip」（包含 `app.html`、`server.py`、`apply_update.bat`）
2. 解壓到小助手資料夾（覆蓋舊檔案）
3. 雙擊 `apply_update.bat`
4. 瀏覽器按 `Ctrl+F5`

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
