"""
德安物流小助手 (Flask 服務器)
- 從 token.json 讀取 token（由 keepalive_service.py 維護）
- 提供網頁界面和 API
- 修改此文件後只需重啟此服務，不影響瀏覽器和保活
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import json
import os
import time
import threading

# 列印功能需要 PyPDF2（缺少時給出明確提示，而不是原始 500）
try:
    from PyPDF2 import PdfReader, PdfWriter, Transformation
    from PyPDF2.generic import RectangleObject
    PDF_LIB_OK = True
    PDF_LIB_ERR = ''
except Exception as _e:
    PDF_LIB_OK = False
    PDF_LIB_ERR = str(_e)

# 標籤機直送需要 PyMuPDF（把 PDF 點陣化成 ZPL）；缺少時退回系統列印路徑
try:
    import fitz  # PyMuPDF
    ZPL_OK = True
    ZPL_ERR = ''
except Exception as _e:
    ZPL_OK = False
    ZPL_ERR = str(_e)

# 本機印表機直印需要 pywin32 + Pillow（PyMuPDF 點陣化 → GDI 直接列印）
#   → 不需要 Adobe / Foxit / SumatraPDF，無對話框、無「假成功」
try:
    import win32print, win32ui, win32con
    from PIL import Image, ImageWin
    GDI_OK = True
    GDI_ERR = ''
except Exception as _e:
    GDI_OK = False
    GDI_ERR = str(_e)

app = Flask(__name__)
CORS(app)

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'token.json')

def get_token():
    """從 token.json 讀取有效的 token"""
    try:
        if not os.path.exists(TOKEN_FILE):
            return None
        
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            token_data = json.load(f)
        
        access_token = token_data.get('access_token')
        expires_at = token_data.get('expires_at', 0)
        
        if not access_token:
            return None
        
        # 檢查是否過期
        if expires_at < time.time():
            # 嘗試用 refresh_token 刷新
            refresh_token = token_data.get('refresh_token')
            if refresh_token:
                new_token = refresh_token_api(refresh_token)
                if new_token:
                    return new_token.get('access_token')
            return None
        
        return access_token
    except Exception as e:
        print(f"讀取 token 失敗: {e}")
        return None

def refresh_token_api(refresh_token):
    """調用刷新 token API"""
    try:
        url = "https://hk-teamwork-api-rp.transnational-grp.com/api/Auth/RefreshToken"
        
        headers = {
            "accept": "*/*",
            "apikey": "5567GGH67225HYVGG",
            "content-type": "application/json",
            "origin": "https://hk-teamwork.transnational-grp.com",
            "referer": "https://hk-teamwork.transnational-grp.com/"
        }
        
        response = requests.post(url, json={"refreshToken": refresh_token}, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('IsSuccess') and data.get('Result'):
                result = data['Result']
                new_token = {
                    'access_token': result.get('AccessToken', ''),
                    'refresh_token': result.get('RefreshToken', refresh_token),
                    'expires_at': int(time.time()) + 300,
                    'last_updated': time.time()
                }
                # 更新 token.json
                with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
                    json.dump(new_token, f)
                print("✓ 已自動刷新 token")
                return new_token
        return None
    except Exception as e:
        print(f"刷新 token 失敗: {e}")
        return None

def api_headers():
    """構建 API headers"""
    token = get_token()
    if not token:
        return None
    
    return {
        "accept": "*/*",
        "apikey": "5567GGH67225HYVGG",
        "authorization": f"Bearer {token}",
        "content-type": "application/json",
        "origin": "https://hk-teamwork.transnational-grp.com",
        "referer": "https://hk-teamwork.transnational-grp.com/"
    }

@app.route('/')
def index():
    return send_from_directory('.', 'app.html')

@app.route('/api/orders', methods=['GET'])
def get_orders():
    """獲取所有訂單"""
    try:
        headers = api_headers()
        if not headers:
            return jsonify({"error": "無法獲取 token，請先啟動 keepalive_service.py"}), 500
        
        payload = {
            "CreatedBy": 4323,
            "CreatedByType": "CO",
            "cd": "HKTeamwork",
            "OrderStatusObjList": []
        }
        
        response = requests.post(
            "https://hk-teamwork-api-rp.transnational-grp.com/api/Order/GetAllOrders",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            return jsonify({"error": f"API 錯誤: {response.status_code}"}), 500
        
        result = response.json()
        
        if not result.get('IsSuccess'):
            return jsonify({"error": result.get('Message', 'API 返回失敗')}), 500
        
        orders = result.get('Result', [])
        
        return jsonify({
            "success": True,
            "total": len(orders),
            "orders": orders
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/printers', methods=['GET'])
def get_printers():
    """獲取所有可用打印機列表"""
    import subprocess
    try:
        # 使用 PowerShell 獲取打印機列表
        result = subprocess.run(
            ['powershell', '-Command', 'Get-Printer | Select-Object Name, PortName | ConvertTo-Json'],
            capture_output=True, text=True, check=True
        )
        printers = json.loads(result.stdout)
        if isinstance(printers, dict):
            printers = [printers]
        
        # 返回所有打印機，前端會根據名稱判斷類型
        all_printers = [{"name": p.get('Name'), "port": p.get('PortName')} for p in printers]
        
        return jsonify({
            "success": True,
            "printers": all_printers
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/print-waybill', methods=['POST'])
def print_waybill():
    """列印運單 - 根據打印機類型自動選擇處理方式"""
    import tempfile
    import subprocess
    
    data = request.json or {}
    invoice_id = data.get('InvoiceId')
    printer_name = (data.get('printer') or '').strip()
    # channel: auto（先 PDF 再 ZPL）| pdf（只走 PDF 處理程式）| zpl（只用 ZPL 直送，不需印表機名）
    channel = str(data.get('channel') or 'auto').lower()
    zpl_ip_req = (data.get('zpl_ip') or '').strip()
    try:
        zpl_port_req = int(data.get('zpl_port') or 9100)
    except Exception:
        zpl_port_req = 9100

    if not invoice_id:
        return jsonify({"success": False, "error": "缺少 InvoiceId"}), 400
    if not printer_name and channel != 'zpl':
        return jsonify({"success": False, "error": "缺少 printer 參數（列印機）"}), 400
    
    if not PDF_LIB_OK:
        return jsonify({
            "success": False,
            "error": "伺服器缺少 PyPDF2，無法處理列印。請執行 pip install PyPDF2 後重啟（詳情：" + PDF_LIB_ERR + "）"
        }), 500
    
    # 判斷是否為標籤打印機（channel=zpl 時一律視為標籤模式）
    is_label_printer = ('ZD' in printer_name.upper()
                        or 'LABEL' in printer_name.upper()
                        or channel == 'zpl')
    
    try:
        # 1. 獲取訂單詳情
        headers = api_headers()
        if not headers:
            return jsonify({"success": False, "error": "無法獲取 token"}), 500
        
        response = requests.post(
            "https://hk-teamwork-api-rp.transnational-grp.com/api/Order/GetOrderByOrderId",
            json={"InvoiceId": invoice_id, "CD": "HKTeamwork"},
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            return jsonify({"success": False, "error": f"API 錯誤: {response.status_code}"}), 500
        
        result = response.json()
        if not result.get('IsSuccess'):
            return jsonify({"success": False, "error": result.get('Message', 'API 返回失敗')}), 500
        
        # receiptFile 位於 Result[0].Order.Table[0]（不是 Result[0] 直層）
        order_detail = result.get('Result', [{}])[0]
        receipt_url = order_detail.get('receiptFile')
        order_row = {}
        if not receipt_url:
            order_table = ((order_detail.get('Order') or {}).get('Table') or [])
            if order_table:
                order_row = order_table[0]
                receipt_url = order_row.get('receiptFile')
        if not order_row:
            order_table = ((order_detail.get('Order') or {}).get('Table') or [])
            order_row = order_table[0] if order_table else {}
        
        if not receipt_url:
            return jsonify({"success": False, "error": "沒有收據文件"}), 400
        
        # 2. 下載 PDF 到內存
        pdf_response = requests.get(receipt_url, headers=headers, timeout=30)
        if pdf_response.status_code != 200:
            return jsonify({"success": False, "error": f"下載 PDF 失敗: {pdf_response.status_code}"}), 500
        
        import io
        
        label_build = ''
        if is_label_printer:
            # 標籤機：切成兩張 102x210mm
            #   優先用 PyMuPDF 重建標準 2 頁 PDF（GDI 點陣化的來源），
            #   PyMuPDF 不可用時才退回 PyPDF2 舊法
            if ZPL_OK:
                try:
                    merged_pdf = build_label_pdf_clean(pdf_response.content)
                    label_build = 'PyMuPDF 重建（標準 2 頁）'
                except Exception as e:
                    merged_pdf = build_label_pdf_legacy(pdf_response.content)
                    label_build = 'PyPDF2 舊法（PyMuPDF 重建失敗: %s）' % e
            else:
                merged_pdf = build_label_pdf_legacy(pdf_response.content)
                label_build = 'PyPDF2 舊法（PyMuPDF 不可用）'
            page_count = 2
            print_mode = "標籤模式（2張）"
        else:
            # 普通打印機：原檔 1:1 直出，不改寫 PDF（GDI 點陣化最忠實）
            merged_pdf = pdf_response.content
            try:
                page_count = len(PdfReader(io.BytesIO(merged_pdf)).pages)
            except Exception:
                page_count = 1
            print_mode = "A4 整張模式"
        
        # 乾跑模式：只驗證 PDF/ZPL 產生結果，不送印（測試用）
        try:
            _pg0 = PdfReader(io.BytesIO(merged_pdf)).pages[0]
            _dims = '%.0fx%.0fpt' % (float(_pg0.mediabox.width), float(_pg0.mediabox.height))
        except Exception:
            _dims = '?'
        print("[print] order=%s printer=%r channel=%s mode=%s pages=%s build=%s pdf=%s pagesize=%s dry=%s"
              % (invoice_id, printer_name, channel, print_mode, page_count, label_build or '-',
                 len(merged_pdf), _dims, bool(data.get('dry_run'))), flush=True)

        if data.get('dry_run'):
            info = {
                "success": True,
                "dry_run": True,
                "mode": print_mode,
                "pages": page_count,
                "pdf_bytes": len(merged_pdf),
                "build": label_build,
                "printer": printer_name,
                "order_no": order_row.get('OrderNo') or order_detail.get('OrderNo')
            }
            if is_label_printer:
                ip = zpl_ip_req or _printer_ip(printer_name)
                info['zpl_target'] = (ip + ':' + str(zpl_port_req)) if ip else None
                if ip and ZPL_OK:
                    try:
                        info['zpl_bytes'] = len(build_zpl_from_pdf(merged_pdf))
                    except Exception as e:
                        info['zpl_error'] = str(e)
                elif not ZPL_OK:
                    info['zpl_error'] = 'PyMuPDF 不可用'
            return jsonify(info)
        
        # 送印方式（2026-09-21 改為原生路徑，完全移除 Adobe / Foxit / ShellExecute）：
        #   channel='zpl'  → ZPL 直送印表機 raw 埠（標籤機，不經 Windows 驅動）
        #   channel='pdf'  → pywin32 GDI 直接列印（A4 與標籤機皆可，無對話框）
        #   channel='auto' → 標籤機走 ZPL，其餘走 GDI
        use_zpl = (channel == 'zpl') or (channel == 'auto' and is_label_printer)
        order_no = order_row.get('OrderNo') or order_detail.get('OrderNo') or str(invoice_id)

        if use_zpl:
            ip = zpl_ip_req or _printer_ip(printer_name)
            if not ip:
                return jsonify({"success": False, "error":
                                "ZPL 直送需要印表機 IP：請在「設定 → 網絡 (IP)」填寫，或選含 IP 的印表機名稱"}), 400
            if not ZPL_OK:
                return jsonify({"success": False, "error": "ZPL 直送需要 PyMuPDF：" + ZPL_ERR}), 500
            try:
                zpl = build_zpl_from_pdf(merged_pdf)
                send_zpl_via_tcp(zpl, ip, zpl_port_req)
            except Exception as e:
                return jsonify({"success": False, "error": "ZPL 直送失敗：" + str(e)}), 500
            print("[print] → ZPL 直送 %s:%s (%d bytes)" % (ip, zpl_port_req, len(zpl)), flush=True)
            return jsonify({
                "success": True,
                "message": "已直送 %s (%s)" % (printer_name or ip, print_mode),
                "order_no": order_no,
                "mode": print_mode,
                "build": label_build,
                "send_method": "ZPL 直送 %s:%s (%d bytes)" % (ip, zpl_port_req, len(zpl))
            })

        # GDI 直接列印（不需任何 PDF 閱讀程式）
        if not GDI_OK:
            return jsonify({"success": False, "error":
                            "本機直印需要 pywin32 與 Pillow，請執行 pip install pywin32 pillow（詳情：" + GDI_ERR + "）"}), 500
        try:
            with _PRINT_LOCK:
                sent_pages, gdi_info = print_pdf_via_gdi(
                    merged_pdf, printer_name, doc_name='Waybill ' + str(order_no))
        except Exception as e:
            return jsonify({"success": False, "error": "GDI 送印失敗：" + str(e)}), 500
        print("[print] → GDI 直印 %r %d 頁 %s" % (printer_name, sent_pages, gdi_info), flush=True)

        return jsonify({
            "success": True,
            "message": "已發送到 %s (%s)" % (printer_name, print_mode),
            "order_no": order_no,
            "mode": print_mode,
            "build": label_build,
            "send_method": "GDI 直印 %s（%d 頁 / %s）" % (printer_name, sent_pages, gdi_info)
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500



def _printer_ip(printer_name):
    """取得印表機 IP：先從名稱抓（例 'ZD420 (192.168.168.251)'），否則查 Windows 印表機埠。"""
    import re
    m = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', printer_name or '')
    if m:
        return m.group(1)
    try:
        ps = ('$p=(Get-Printer -Name "%s" -ErrorAction SilentlyContinue).PortName;'
              'if($p){(Get-PrinterPort -Name $p -ErrorAction SilentlyContinue).PrinterHostAddress}') % printer_name
        out = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                             capture_output=True, text=True, timeout=30).stdout
        m = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', out or '')
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


# 黑白二值化門檻（GDI 直印與 ZPL 直送共用同一個值，兩條路徑輸出一致）
#   2026-09-21 實測定案：舊值 128 會把標籤上「非純黑」的內容全部刪掉 ——
#     · Transnational logo：灰階 96~249（平均 169）→ 整塊消失
#     · 灰色分區色帶（灰階 165）：整條消失，連帶其上「COLLECT FROM」反白字也不見
#     · 全頁墨點被砍掉 55.3%
#   門檻 200 的實測結果：
#     · logo 完整回來、灰帶變成「實心黑底 + 白色反白字」（符合原設計意圖，且熱感機不會有灰階抖動）
#     · 孤立雜點由 41 個降到 4 個（門檻越高，文字邊緣的灰階反而與字身連成一片，不會散成點）
#     · 只砍掉 10.5% 墨點，細小文字不會被填糊（235 會過度加粗，不採用）
INK_THRESHOLD = 200


def build_zpl_from_pdf(pdf_bytes, width_mm=102, height_mm=210, dpmm=8, threshold=INK_THRESHOLD):
    """把 PDF 每一頁點陣化成 1-bit 並轉成 ZPL（^GFA 點陣圖）。

    完全不依賴任何 PDF 閱讀程式或 Windows 驅動，任何電腦都能用。
    dpmm=8 對應 ZD420 的 203dpi（8 dots/mm）。
    """
    import fitz  # PyMuPDF
    w = int(round(width_mm * dpmm))
    h = int(round(height_mm * dpmm))
    bpr = (w + 7) // 8                     # 每列位元組數
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')

    # 灰階 → 0/1（1 = 黑點）的查表；再轉成 ASCII '0'/'1' 供 int(.., 2) 打包
    to_bit = bytes(1 if i < threshold else 0 for i in range(256))
    to_ascii = bytes(48 + (1 if i < threshold else 0) for i in range(256))

    pages = []
    for page in doc:
        mat = fitz.Matrix(w / page.rect.width, h / page.rect.height)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY, alpha=False)
        bits = pix.samples.translate(to_ascii)          # 每像素一個 '0'/'1'
        stride = pix.stride
        rows = []
        for y in range(h):
            row_bytes = bits[y * stride: y * stride + w]
            if len(row_bytes) < w:
                row_bytes = row_bytes + b'0' * (w - len(row_bytes))
            packed = int(row_bytes, 2).to_bytes(bpr, 'big')
            rows.append(packed)
        data = b''.join(rows)
        pages.append(
            '^XA\n^PW{}\n^LL{}\n^FO0,0\n^GFA,{},{},{},{}\n^FS\n^XZ\n'.format(
                w, h, len(data), len(data), bpr, data.hex().upper())
        )
    return ''.join(pages).encode('ascii')


def send_zpl_via_tcp(zpl_bytes, ip, port=9100, timeout=120):
    """直接把 ZPL 位元組送到印表機的 9100 埠（Zebra 標準 raw 埠）。"""
    import socket
    with socket.create_connection((ip, port), timeout=timeout) as s:
        s.sendall(zpl_bytes)


# 標籤裁切範圍（PDF 座標，原點左下）：上聯 / 下聯
#   上聯去掉 "Order created By" 那行；下聯去掉底部殘行
LABEL_CROPS = [(20, 441.8, 575, 802.0), (0, 42.1, 575, 402.3)]
LABEL_W_MM, LABEL_H_MM = 102, 210


def build_label_pdf_clean(pdf_bytes, width_mm=LABEL_W_MM, height_mm=LABEL_H_MM):
    """用 PyMuPDF 重建 2 頁 102x210mm 標籤 PDF（標準構造）。

    show_pdf_page 產生標準 page/XObject 引用，裁切框與縮放完全一致；
    print_pdf_via_gdi 的點陣化直接吃這個輸出。
    （PyPDF2「設 mediabox + transformation」的舊構造已不再採用。）
    """
    import fitz  # PyMuPDF
    src = fitz.open(stream=pdf_bytes, filetype='pdf')
    H = src[0].rect.height                 # PDF→PyMuPDF 是上下翻轉，y 要換算
    w_pt = width_mm * 72 / 25.4
    h_pt = height_mm * 72 / 25.4
    out = fitz.open()
    for (x0, y0, x1, y1) in LABEL_CROPS:
        clip = fitz.Rect(x0, H - y1, x1, H - y0)
        page = out.new_page(width=w_pt, height=h_pt)
        rw, rh = clip.height, clip.width   # 旋轉 90° 後的寬高
        s = min(w_pt / rw, h_pt / rh)
        tw, th = rw * s, rh * s
        target = fitz.Rect((w_pt - tw) / 2, (h_pt - th) / 2,
                           (w_pt + tw) / 2, (h_pt + th) / 2)
        page.show_pdf_page(target, src, 0, clip=clip, rotate=90)
    return out.tobytes()


def build_label_pdf_legacy(pdf_bytes, width_mm=LABEL_W_MM, height_mm=LABEL_H_MM):
    """舊法（PyPDF2 設 mediabox + transformation）。只在 PyMuPDF 不可用時使用。

    注意：PyMuPDF 同時是 GDI 點陣化的來源，缺少它時整條列印路都不通，
    所以此路徑實務上只是防呆，不會真的走到。
    """
    mm = 72 / 25.4
    label_w = width_mm * mm
    label_h = height_mm * mm
    out = io.BytesIO()
    writer = PdfWriter()

    def one(crop, fresh_bytes):
        reader = PdfReader(io.BytesIO(fresh_bytes))
        page = reader.pages[0]
        page.mediabox = RectangleObject((crop[0], crop[1], crop[2], crop[3]))
        rw = crop[3] - crop[1]                 # 旋轉 90° 後寬度 = 原高度
        rh = crop[2] - crop[0]
        s = min(label_w / rw, label_h / rh)
        xo = (label_w - rw * s) / 2
        yo = (label_h - rh * s) / 2
        a, b, c, d = 0, -s, s, 0
        e = -crop[1] * s + xo
        f = crop[2] * s + yo
        page.add_transformation(Transformation((a, b, c, d, e, f)))
        page.mediabox = RectangleObject((0, 0, label_w, label_h))
        page.cropbox = RectangleObject((0, 0, label_w, label_h))
        writer.add_page(page)

    for crop in LABEL_CROPS:
        one(crop, pdf_bytes)
    writer.write(out)
    return out.getvalue()




_PRINT_LOCK = threading.Lock()


def print_pdf_via_gdi(pdf_bytes, printer_name, doc_name='Waybill', threshold=INK_THRESHOLD):
    """PyMuPDF 點陣化 → pywin32 GDI 直接列印。回傳 (頁數, 說明字串)。

    為何用這條路（2026-09-21 實測定案，已完全取代 PDF 閱讀程式路徑）：
      - GDI：無外部程式、無對話框、1 頁約 0.4 秒，批量連送全部進佇列（實測零遺失）。
      - 舊路徑已廢棄（勿回頭用）：Adobe `/t` 會短暫彈窗、returncode 不可靠（成功也可能回 1），
        曾害程式誤判失敗又送一次（快速列印印出 4 張）；ShellExecute `-Verb PrintTo`
        不會把印表機名傳進 PDF 程式，會彈窗且掉工作。
    EndDoc 會等 spooler 收下工作，所以回傳成功 = 真的進佇列。

    ★ 熱感標籤機「印出一堆點點點」的修正（2026-09-21）：
      ZD420 的驅動 DC 實測是 1-bit 單色、原生 203dpi、畫布 815x1678。
      舊寫法用 300dpi「彩色 RGB」點陣圖再 StretchBlt 縮到 815x1678，兩個問題同時發生：
        ① 300→203dpi 最近鄰降採樣，把細線與文字邊緣打散成散點
        ② GDI 把彩色轉 1bpp 時會做抖動（dithering）→ 整片點點點
      現在改成「依 DC 實測規格送圖」：
        ① 以印表機原生解析度點陣化，尺寸與畫布 1:1 → 完全不做二次縮放
        ② DC 是 1-bit 就先硬門檻二值化再送 → 沒有灰階，驅動無從抖動
      另外門檻值本身也曾出錯（128 會刪掉 logo 與灰色色帶）：見 INK_THRESHOLD 說明。
      （A4 的 HP 驅動 DC 是 8-bit 灰階 / 600dpi，維持灰階直送即可，不二值化。）

    呼叫端需以 _PRINT_LOCK 序列化（GDI 對同一印表機非執行緒安全）。
    """
    import io
    import fitz
    import win32ui, win32con
    from PIL import Image, ImageWin

    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)
    try:
        pw = hdc.GetDeviceCaps(win32con.HORZRES)      # 可列印區寬（裝置像素）
        ph = hdc.GetDeviceCaps(win32con.VERTRES)      # 可列印區高
        nat_dpi = hdc.GetDeviceCaps(win32con.LOGPIXELSX) or 300
        mono = hdc.GetDeviceCaps(win32con.BITSPIXEL) == 1
        hdc.StartDoc(doc_name)
        pages = 0
        for page in doc:
            rect = page.rect
            # 整頁對映到恰好 pw x ph 個裝置像素 → 就是原生解析度，之後不再縮放
            mat = fitz.Matrix(pw / rect.width, ph / rect.height)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY, alpha=False)
            im = Image.frombytes('L', (pix.width, pix.height), pix.samples)
            if im.size != (pw, ph):
                im = im.resize((pw, ph), Image.LANCZOS)
            if mono:
                # 硬門檻二值化（明確關閉抖動）→ 送出的就是最終黑點，驅動無從加噪
                im = im.point(lambda v: 255 if v >= threshold else 0)
                im = im.convert('1', dither=getattr(getattr(Image, 'Dither', Image), 'NONE', 0))
            hdc.StartPage()
            ImageWin.Dib(im).draw(hdc.GetHandleOutput(), (0, 0, pw, ph))
            hdc.EndPage()
            pages += 1
        hdc.EndDoc()
        return pages, '原生 %ddpi %s' % (nat_dpi, '1-bit 二值化' if mono else '8-bit 灰階')
    finally:
        hdc.DeleteDC()

@app.route('/api/order-detail', methods=['POST'])
def order_detail():
    """獲取訂單詳情"""
    data = request.json
    invoice_id = data.get('InvoiceId')
    
    if not invoice_id:
        return jsonify({"error": "缺少 InvoiceId"}), 400
    
    try:
        headers = api_headers()
        if not headers:
            return jsonify({"error": "無法獲取 token，請先啟動 keepalive_service.py"}), 500
        
        # 獲取訂單詳情
        response = requests.post(
            "https://hk-teamwork-api-rp.transnational-grp.com/api/Order/GetOrderByOrderId",
            json={"InvoiceId": invoice_id, "CD": "HKTeamwork"},
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            return jsonify({"error": f"API 錯誤: {response.status_code}"}), 500
        
        result = response.json()
        
        if not result.get('IsSuccess'):
            return jsonify({"error": result.get('Message', 'API 返回失敗')}), 500
        
        # 獲取訂單狀態追蹤
        status_response = requests.post(
            "https://hk-teamwork-api-rp.transnational-grp.com/api/Order/GetOrderStatusByOrderId",
            json={"InvoiceId": invoice_id, "CD": "HKTeamwork"},
            headers=headers,
            timeout=30
        )
        
        status_result = []
        if status_response.status_code == 200:
            status_data = status_response.json()
            if status_data.get('IsSuccess'):
                status_result = status_data.get('Result', [])
        
        order_detail_result = result.get('Result', [])
        if isinstance(order_detail_result, list) and len(order_detail_result) > 0:
            order_detail = order_detail_result[0]
        else:
            order_detail = order_detail_result
        
        return jsonify({
            "success": True,
            "orderDetail": order_detail,
            "orderStatus": status_result
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/track', methods=['POST'])
def track_order():
    data = request.json
    order_number = data.get('orderNumber')
    
    if not order_number:
        return jsonify({"error": "缺少訂單號"}), 400
    
    try:
        headers = api_headers()
        if not headers:
            return jsonify({"error": "無法獲取 token，請先啟動 keepalive_service.py"}), 500
        
        payload = {
            "CreatedBy": 4323,
            "CreatedByType": "CO",
            "cd": "HKTeamwork",
            "OrderStatusObjList": []
        }
        
        response = requests.post(
            "https://hk-teamwork-api-rp.transnational-grp.com/api/Order/GetAllOrders",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            return jsonify({"error": f"API 錯誤: {response.status_code}"}), 500
        
        result = response.json()
        
        if not result.get('IsSuccess'):
            return jsonify({"error": result.get('Message', 'API 返回失敗')}), 500
        
        orders = result.get('Result', [])
        
        # 支持逗號分隔的多個訂單
        order_numbers = [n.strip() for n in order_number.split(',') if n.strip()]
        results = []
        
        for num in order_numbers:
            order_data = None
            for order in orders:
                if str(order.get('OrderNo', '')) == num or str(order.get('InvoiceId', '')) == num:
                    order_data = order
                    break
            
            if order_data:
                results.append({
                    "orderNumber": num,
                    "found": True,
                    "order": order_data
                })
            else:
                results.append({
                    "orderNumber": num,
                    "found": False
                })
        
        return jsonify({
            "success": True,
            "results": results
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/token-status', methods=['GET'])
def token_status():
    """獲取 token 狀態"""
    token_file_exists = os.path.exists(TOKEN_FILE)
    token = get_token()
    
    expires_in = 0
    if token_file_exists:
        try:
            with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
            expires_in = int(token_data.get('expires_at', 0) - time.time())
        except:
            pass
    
    return jsonify({
        'token_file_exists': token_file_exists,
        'token_valid': token is not None,
        'expires_in': expires_in
    })

# ==================== 地址管理 API ====================

@app.route('/api/addresses', methods=['GET'])
def get_addresses():
    """獲取地址列表"""
    token = get_token()
    if not token:
        return jsonify({'success': False, 'message': 'Token 無效或已過期'}), 401
    
    try:
        # 調用 Teamwork API 獲取地址列表
        url = 'https://hk-teamwork-api-rp.transnational-grp.com/api/Contact/GetContactAddressByContactId'
        headers = {
            'Authorization': f'Bearer {token}',
            'APIKey': '5567GGH67225HYVGG',
            'Content-Type': 'application/json',
            'Origin': 'https://hk-teamwork.transnational-grp.com',
            'Referer': 'https://hk-teamwork.transnational-grp.com/'
        }
        payload = {
            'ContactId': 4323,
            'CD': 'HKTeamwork'
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        
        if data.get('IsSuccess'):
            return jsonify({
                'success': True,
                'addresses': data.get('Result', [])
            })
        else:
            return jsonify({
                'success': False,
                'message': data.get('Message', '獲取地址失敗')
            }), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


def _address_payload(addr_data, cab_id=None, is_new=False):
    """建立地址 payload（與 Flutter App 一致）

    is_new=True（新增）時：PostalCode 留空，聯絡人/電話/分機/手機/電郵一律填 "-"
    """
    def pick(key):
        """新增時一律 '-', 編輯時用表單值（空則 '-'）"""
        if is_new:
            return '-'
        return addr_data.get(key) or '-'
    
    p = {
        'AddressName': addr_data.get('AddressName', ''),
        'CostCenterName': addr_data.get('CostCenterName') or addr_data.get('AddressName', ''),
        'ContactName': pick('ContactName'),
        'Countryid': str(addr_data.get('Countryid') or '1'),
        'CityId': str(addr_data.get('CityId') or ''),
        'Districtid': str(addr_data.get('Districtid') or ''),
        'Zoneid': str(addr_data.get('Zoneid') or ''),
        'Stateid': str(addr_data.get('Stateid') or '2'),
        'Regionid': addr_data.get('Regionid', ''),
        'PostalCode': '' if is_new else (addr_data.get('PostalCode') or ''),
        'Address1': addr_data.get('Address1', ''),
        'Address2': addr_data.get('Address2', ''),
        'Address3': addr_data.get('Address3', ''),
        'Address4': addr_data.get('Address4', ''),
        'Phone1': pick('Phone1'),
        'Ext1': pick('Ext1'),
        'Phone2': pick('Phone2'),
        'Ext2': pick('Ext2'),
        'Mobile': pick('Mobile'),
        'Email': pick('Email'),
        'Collection': 'True',
        'Delivery': 'True',
        'Collection_Instruction': '',
        'DefaultAddress': 'false',
        'DefaultShipping': 'no',
        'DefaultBilling': 'no',
        'ALatitude': addr_data.get('ALatitude', ''),
        'ALongitude': addr_data.get('ALongitude', ''),
        'BranchName': '',
        'Department': '',
        'CBranchId': '',
        'Contactid': 4323,
        'CustomerId': 148551,
        'CD': 'HKTeamwork'
    }
    if cab_id is not None:
        p['CABid'] = cab_id
    return p


@app.route('/api/addresses', methods=['POST'])
def add_address():
    """新增地址"""
    token = get_token()
    if not token:
        return jsonify({'success': False, 'message': 'Token 無效或已過期'}), 401
    
    try:
        addr_data = request.json
        
        # 調用 Teamwork API 新增地址
        url = 'https://hk-teamwork-api-rp.transnational-grp.com/api/Contact/SavecontactAddress'
        headers = {
            'Authorization': f'Bearer {token}',
            'APIKey': '5567GGH67225HYVGG',
            'Content-Type': 'application/json',
            'Origin': 'https://hk-teamwork.transnational-grp.com',
            'Referer': 'https://hk-teamwork.transnational-grp.com/'
        }
        
        # 構建 Teamwork API 需要的 payload
        payload = _address_payload(addr_data, is_new=True)
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        
        if data.get('IsSuccess'):
            return jsonify({
                'success': True,
                'message': '地址新增成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': data.get('Message', '新增地址失敗')
            }), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/addresses/<int:cab_id>', methods=['PUT'])
def update_address(cab_id):
    """編輯地址"""
    token = get_token()
    if not token:
        return jsonify({'success': False, 'message': 'Token 無效或已過期'}), 401
    
    try:
        addr_data = request.json
        
        # 調用 Teamwork API 更新地址
        # 依 Flutter App 實作：PUT /api/Contact/UpdateContactAddress + form-urlencoded
        # （用 SavecontactAddress 帶 CABid 不會更新，只會新增副本）
        url = 'https://hk-teamwork-api-rp.transnational-grp.com/api/Contact/UpdateContactAddress'
        headers = {
            'Authorization': f'Bearer {token}',
            'APIKey': '5567GGH67225HYVGG',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://hk-teamwork.transnational-grp.com',
            'Referer': 'https://hk-teamwork.transnational-grp.com/'
        }
        
        payload = _address_payload(addr_data, cab_id)
        form = {k: ('' if v is None else str(v)) for k, v in payload.items()}
        
        response = requests.put(url, headers=headers, data=form, timeout=30)
        data = response.json()
        
        if data.get('IsSuccess'):
            return jsonify({
                'success': True,
                'message': '地址更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': data.get('Message', '更新地址失敗')
            }), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/addresses/<int:cab_id>', methods=['DELETE'])
def delete_address(cab_id):
    """刪除地址 (DELETE /api/Contact/DeleteContactAddressBook, form body) """
    token = get_token()
    if not token:
        return jsonify({'success': False, 'message': 'Token 無效或已過期'}), 401
    
    try:
        # 調用 Teamwork API 刪除地址（依 Flutter 實作：DELETE + form-urlencoded body）
        url = 'https://hk-teamwork-api-rp.transnational-grp.com/api/Contact/DeleteContactAddressBook'
        headers = {
            'Authorization': f'Bearer {token}',
            'APIKey': '5567GGH67225HYVGG',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://hk-teamwork.transnational-grp.com',
            'Referer': 'https://hk-teamwork.transnational-grp.com/'
        }
        
        # Flutter 原始請求：body = "CABid=7814&CD=HKTeamwork"
        body = f'CABid={cab_id}&CD=HKTeamwork'
        
        response = requests.delete(url, headers=headers, data=body, timeout=30)
        data = response.json()
        
        if data.get('IsSuccess'):
            return jsonify({
                'success': True,
                'message': '地址刪除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': data.get('Message', '刪除地址失敗')
            }), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500



# ==================== 地理資料 API（國家/城市/地區/區域）====================

def _tapi_post(path, payload):
    """通用 Teamwork API POST 代理，回傳 (json, error)"""
    token = get_token()
    if not token:
        return None, ('Token 無效或已過期', 401)
    headers = {
        'Authorization': f'Bearer {token}',
        'APIKey': '5567GGH67225HYVGG',
        'Content-Type': 'application/json',
        'Origin': 'https://hk-teamwork.transnational-grp.com',
        'Referer': 'https://hk-teamwork.transnational-grp.com/'
    }
    try:
        r = requests.post('https://hk-teamwork-api-rp.transnational-grp.com' + path,
                          headers=headers, json=payload, timeout=30)
        return r.json(), None
    except Exception as e:
        return None, (str(e), 500)


@app.route('/api/geo/countries', methods=['GET'])
def geo_countries():
    """國家清單"""
    data, err = _tapi_post('/api/Country/GetAllCountries',
                           {'LanguageId': '1', 'CD': 'HKTeamwork'})
    if err:
        return jsonify({'success': False, 'message': err[0]}), err[1]
    return jsonify({'success': bool(data.get('IsSuccess')), 'items': data.get('Result', [])})


@app.route('/api/geo/cities', methods=['GET'])
def geo_cities():
    """城市清單（依 CountryId）"""
    country_id = request.args.get('countryId', '-1')
    data, err = _tapi_post('/api/City/GetCityByCountryId',
                           {'LanguageId': '1', 'CountryId': str(country_id), 'CD': 'HKTeamwork'})
    if err:
        return jsonify({'success': False, 'message': err[0]}), err[1]
    return jsonify({'success': bool(data.get('IsSuccess')), 'items': data.get('Result', [])})


@app.route('/api/geo/districts', methods=['GET'])
def geo_districts():
    """地區清單（依 CityId）"""
    city_id = request.args.get('cityId', '-1')
    data, err = _tapi_post('/api/Country/GetDistrict',
                           {'CityId': str(city_id), 'CD': 'HKTeamwork'})
    if err:
        return jsonify({'success': False, 'message': err[0]}), err[1]
    return jsonify({'success': bool(data.get('IsSuccess')), 'items': data.get('Result', [])})


@app.route('/api/geo/zones', methods=['GET'])
def geo_zones():
    """區域清單（依 DistrictId；注意參數名為 DistinctId）"""
    district_id = request.args.get('districtId', '-1')
    data, err = _tapi_post('/api/Country/GetZone',
                           {'DistinctId': str(district_id), 'CD': 'HKTeamwork'})
    if err:
        return jsonify({'success': False, 'message': err[0]}), err[1]
    return jsonify({'success': bool(data.get('IsSuccess')), 'items': data.get('Result', [])})


if __name__ == '__main__':
    import sys
    print("=" * 60)
    print("德安物流小助手 (Flask Server)")
    print("=" * 60)
    print("\n功能:")
    print("  ✓ 訂單詳情（搜索、過濾、統計）")
    print("  ✓ 運單列印（A4 / 標籤機：GDI 直印；標簽機 ZPL：直送 IP:埠）")
    print("  ✓ 物流查詢")
    print("  ✓ Token 從 token.json 自動讀取")
    print("\n環境:")
    print(f"  Python: {sys.version.split()[0]}  ({sys.executable})")
    print(f"  列印模組 PyPDF2: {'✓ 可用' if PDF_LIB_OK else '✗ 缺少 - ' + PDF_LIB_ERR}")
    print(f"  標籤直送 PyMuPDF: {'✓ 可用（ZPL 直送 IP:埠）' if ZPL_OK else '✗ 缺少 - ' + ZPL_ERR}")
    print(f"  本機直印 GDI: {'✓ 可用（pywin32，無對話框）' if GDI_OK else '✗ 缺少 - ' + GDI_ERR}")
    print("\n注意：請先啟動 keepalive_service.py 維護 token")
    print("\n服務器啟動中...")
    print("請在瀏覽器中打開: http://localhost:5000")
    print("按 Ctrl+C 停止")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
