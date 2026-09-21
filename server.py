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
    print("=" * 60)
    print("德安物流小助手 (Flask Server)")
    print("=" * 60)
    print("\n功能:")
    print("  ✓ 訂單詳情（搜索、過濾、統計）")
    print("  ✓ 物流查詢")
    print("  ✓ Token 從 token.json 自動讀取")
    print("\n注意：請先啟動 keepalive_service.py 維護 token")
    print("\n服務器啟動中...")
    print("請在瀏覽器中打開: http://localhost:5000")
    print("按 Ctrl+C 停止")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
