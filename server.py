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

# 列印功能需要 PyPDF2（缺少時給出明確提示，而不是原始 500）
try:
    from PyPDF2 import PdfReader, PdfWriter, Transformation
    from PyPDF2.generic import RectangleObject
    PDF_LIB_OK = True
    PDF_LIB_ERR = ''
except Exception as _e:
    PDF_LIB_OK = False
    PDF_LIB_ERR = str(_e)

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
    printer_name = data.get('printer', 'ZD420')
    
    if not invoice_id:
        return jsonify({"success": False, "error": "缺少 InvoiceId"}), 400
    
    if not PDF_LIB_OK:
        return jsonify({
            "success": False,
            "error": "伺服器缺少 PyPDF2，無法處理列印。請執行 pip install PyPDF2 後重啟（詳情：" + PDF_LIB_ERR + "）"
        }), 500
    
    # 判斷是否為標籤打印機
    is_label_printer = 'ZD' in printer_name.upper() or 'LABEL' in printer_name.upper()
    
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
        
        if is_label_printer:
            # 標籤打印機：切割處理，分兩張打印
            pdf_bytes = io.BytesIO(pdf_response.content)
            reader = PdfReader(pdf_bytes)
            
            mm = 72 / 25.4
            label_w = 102 * mm
            label_h = 210 * mm
            
            # 上半部分：表格 Y 441.8-802.0（去掉 Order created By）
            top_crop = {'x0': 20, 'y0': 441.8, 'x1': 575, 'y1': 802.0, 'h': 360.2}
            # 下半部分：表格 Y 42.1-402.3（去掉底部的自我）
            bottom_crop = {'x0': 0, 'y0': 42.1, 'x1': 575, 'y1': 402.3, 'h': 360.2}
            
            def calc(crop, label_w, label_h):
                rotated_w = crop['h']
                rotated_h = crop['x1'] - crop['x0']
                scale = min(label_w / rotated_w, label_h / rotated_h)
                scaled_w = rotated_w * scale
                scaled_h = rotated_h * scale
                x_off = (label_w - scaled_w) / 2
                y_off = (label_h - scaled_h) / 2
                return scale, x_off, y_off
            
            writer = PdfWriter()
            
            # 上半
            page1 = reader.pages[0]
            page1.mediabox = RectangleObject((top_crop['x0'], top_crop['y0'], top_crop['x1'], top_crop['y1']))
            top_scale, top_x_off, top_y_off = calc(top_crop, label_w, label_h)
            a, b, c, d = 0, -top_scale, top_scale, 0
            e = -top_crop['y0'] * top_scale + top_x_off
            f = top_crop['x1'] * top_scale + top_y_off
            page1.add_transformation(Transformation((a, b, c, d, e, f)))
            page1.mediabox = RectangleObject((0, 0, label_w, label_h))
            page1.cropbox = RectangleObject((0, 0, label_w, label_h))
            writer.add_page(page1)
            
            # 下半
            reader2 = PdfReader(io.BytesIO(pdf_response.content))
            page2 = reader2.pages[0]
            page2.mediabox = RectangleObject((bottom_crop['x0'], bottom_crop['y0'], bottom_crop['x1'], bottom_crop['y1']))
            bot_scale, bot_x_off, bot_y_off = calc(bottom_crop, label_w, label_h)
            a, b, c, d = 0, -bot_scale, bot_scale, 0
            e = -bottom_crop['y0'] * bot_scale + bot_x_off
            f = bottom_crop['x1'] * bot_scale + bot_y_off
            page2.add_transformation(Transformation((a, b, c, d, e, f)))
            page2.mediabox = RectangleObject((0, 0, label_w, label_h))
            page2.cropbox = RectangleObject((0, 0, label_w, label_h))
            writer.add_page(page2)
            
            print_mode = "標籤模式（2張）"
        else:
            # 普通打印機：直接打印 A4 整張
            writer = PdfWriter()
            reader = PdfReader(io.BytesIO(pdf_response.content))
            for page in reader.pages:
                writer.add_page(page)
            print_mode = "A4 整張模式"
        
        # 4. 保存到臨時文件（打印後刪除）
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            writer.write(tmp)
            tmp_path = tmp.name
        
        # 乾跑模式：只驗證 PDF 產生結果，不送印（測試用）
        if data.get('dry_run'):
            page_count = len(writer.pages)
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return jsonify({
                "success": True,
                "dry_run": True,
                "mode": print_mode,
                "pages": page_count,
                "printer": printer_name,
                "order_no": order_row.get('OrderNo') or order_detail.get('OrderNo')
            })
        
        # 5. 發送到打印機
        #    不能用 ShellExecute 的 PrintTo（印表機名不會進到 Foxit 的 /t），
        #    要用註冊表 printto 指令列 → 實測才會真的進標籤機佇列。
        ok, method = send_pdf_to_printer(tmp_path, printer_name)
        if not ok:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return jsonify({"success": False, "error": "送印失敗：" + method}), 500
        
        # 6. 刪除臨時文件（延遲 2 秒確保打印完成）
        import threading
        def cleanup():
            import time
            time.sleep(2)
            try:
                os.remove(tmp_path)
            except:
                pass
        
        threading.Thread(target=cleanup, daemon=True).start()
        
        return jsonify({
            "success": True,
            "message": f"已發送到 {printer_name} ({print_mode})",
            "order_no": order_row.get('OrderNo') or order_detail.get('OrderNo'),
            "mode": print_mode,
            "send_method": method
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def _pdf_handler_printto_template():
    """從註冊表取得 .pdf 處理程式的 printto 指令範本（例如 Foxit 的 /t "%1" "%2"）。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, '.pdf') as k:
            handler = winreg.QueryValueEx(k, None)[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, handler + r'\shell\printto\command') as k:
            return winreg.QueryValueEx(k, None)[0]
    except Exception:
        return None


def send_pdf_to_printer(file_path, printer_name):
    """把 PDF 送到指定印表機，回傳 (成功, 使用的方法說明)。

    重要：不能用 PowerShell 的 `Start-Process -Verb PrintTo -ArgumentList "<printer>"`。
    ShellExecute 不會把印表機名餵進 PDF 處理程式的 /t 參數（Foxit 會只把檔案打開，
    彈出列印對話框，標籤機佇列全程 0 個工作）。必須直接照註冊表 printto 範本組指令列。
    """
    import subprocess, re
    CREATE_NO_WINDOW = 0x08000000

    # 方法 1（首選）：PDF 處理程式的 printto 指令列，例如
    # "D:\\Foxit Software\\Foxit PDF Editor\\FoxitPDFEditor.exe" /t "%1" "%2" "%3" "%4"
    tpl = _pdf_handler_printto_template()
    if tpl:
        m = re.match(r'^\s*"([^"]+)"\s*(.*)$', tpl)
        if m:
            exe, rest = m.group(1), m.group(2)
        else:
            parts = tpl.split(None, 1)
            exe, rest = parts[0], (parts[1] if len(parts) > 1 else '')
        if exe and os.path.exists(exe):
            args = [exe]
            for tok in re.findall(r'"[^"]*"|\S+', rest):
                val = tok.strip('"')
                val = (val.replace('%1', file_path)
                          .replace('%2', printer_name)
                          .replace('%3', '')
                          .replace('%4', ''))
                if val:  # 空的佔位符不要傳
                    args.append(val)
            try:
                r = subprocess.run(args, timeout=180, capture_output=True, text=True,
                                   creationflags=CREATE_NO_WINDOW)
                if r.returncode == 0:
                    return True, 'PDF 處理程式指令列: ' + os.path.basename(exe)
                err = (r.stderr or r.stdout or '').strip()[:200]
            except Exception as e:
                err = str(e)
        else:
            err = '處理程式不存在: ' + str(exe)
    else:
        err = '找不到 printto 指令範本'

    # 方法 2（退回）：ShellExecute PrintTo
    try:
        ps = f'Start-Process -FilePath "{file_path}" -Verb PrintTo -ArgumentList "{printer_name}"'
        subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=True, timeout=120,
                       creationflags=CREATE_NO_WINDOW)
        return True, 'ShellExecute PrintTo（退回）'
    except Exception as e:
        err = err + ' / PrintTo 也失敗: ' + str(e)

    # 方法 3（最後）：送到系統預設印表機
    try:
        ps = f'Start-Process -FilePath "{file_path}" -Verb Print'
        subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=True, timeout=120,
                       creationflags=CREATE_NO_WINDOW)
        return True, '系統預設印表機（退回）'
    except Exception as e:
        return False, err + ' / 預設印表機也失敗: ' + str(e)


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
    print("  ✓ 運單列印（標籤 2 張 / A4 整張）")
    print("  ✓ 物流查詢")
    print("  ✓ Token 從 token.json 自動讀取")
    print("\n環境:")
    print(f"  Python: {sys.version.split()[0]}  ({sys.executable})")
    print(f"  列印模組 PyPDF2: {'✓ 可用' if PDF_LIB_OK else '✗ 缺少 - ' + PDF_LIB_ERR}")
    print("\n注意：請先啟動 keepalive_service.py 維護 token")
    print("\n服務器啟動中...")
    print("請在瀏覽器中打開: http://localhost:5000")
    print("按 Ctrl+C 停止")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
