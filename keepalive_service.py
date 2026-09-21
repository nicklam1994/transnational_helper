"""
Teamwork Token Keepalive Service
策略：Flutter 只在剩餘<=60秒且有API請求時自動刷新。
     用戶閒置時自動切tab觸發請求讓 Flutter 自己刷新，同步到 token.json。
輸出：只在關鍵事件時顯示，安靜輪詢不刷屏。
"""

import json
import os
import time
from playwright.sync_api import sync_playwright

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'token.json')

playwright = None
browser = None
teamwork_page = None

def fmt_time(ts):
    return time.strftime('%H:%M:%S', time.localtime(ts))

def connect_to_edge():
    global playwright, browser, teamwork_page
    try:
        if playwright is None:
            playwright = sync_playwright().start()
        browser = playwright.chromium.connect_over_cdp("http://127.0.0.1:9222")
        for context in browser.contexts:
            for page in context.pages:
                if "transnational-grp.com" in page.url:
                    teamwork_page = page
                    print("✓ 已找到 teamwork 頁面")
                    return True
        return False
    except Exception as e:
        print(f"✗ 連接 Edge 失敗: {e}")
        reset_connection()
        return False

def reset_connection():
    global playwright, browser, teamwork_page
    try:
        if playwright:
            playwright.stop()
    except:
        pass
    playwright = None
    browser = None
    teamwork_page = None

def read_browser_token():
    global teamwork_page
    if teamwork_page is None:
        return None
    try:
        if teamwork_page.is_closed():
            print("⚠ 頁面已關閉")
            reset_connection()
            return None
        token_data = teamwork_page.evaluate("""() => {
            const access = localStorage.getItem('flutter.access_token');
            const refresh = localStorage.getItem('flutter.refreshTokens');
            const exp = localStorage.getItem('flutter.accessTokenExp');
            const login = localStorage.getItem('flutter.loginToken');
            return {
                access_token: access ? access.replace(/^"|"$/g, '') : null,
                refresh_token: refresh ? refresh.replace(/^"|"$/g, '') : null,
                expires_at: exp ? parseInt(exp) : 0,
                login_token: login
            };
        }""")
        if token_data and token_data.get('access_token') and token_data.get('login_token') == 'true':
            token_data['last_updated'] = time.time()
            return token_data
        return None
    except Exception as e:
        print(f"✗ 讀取 token 失敗: {e}")
        reset_connection()
        return None

def get_user_idle_seconds():
    global teamwork_page
    if teamwork_page is None:
        return 9999
    try:
        teamwork_page.evaluate("""() => {
            if (!window.__lastUserActivity) {
                window.__lastUserActivity = Date.now();
                const update = () => { window.__lastUserActivity = Date.now(); };
                ['mousemove', 'mousedown', 'keydown', 'touchstart', 'wheel'].forEach(
                    evt => window.addEventListener(evt, update, { passive: true })
                );
            }
        }""")
        return teamwork_page.evaluate("(Date.now() - (window.__lastUserActivity || 0)) / 1000")
    except:
        return 9999

def get_tab_buttons():
    global teamwork_page
    if teamwork_page is None:
        return []
    try:
        return teamwork_page.evaluate("""() => {
            const all = document.querySelectorAll('flt-semantics[role="button"]');
            const result = [];
            for (const el of all) {
                const text = el.textContent || '';
                const rect = el.getBoundingClientRect();
                const lines = text.split(String.fromCharCode(10));
                const firstLine = (lines[0] || '').trim();
                if (rect.y > window.innerHeight * 0.8 && (firstLine === 'Home' || firstLine === 'My Orders')) {
                    if (rect.width > 0) {
                        result.push({
                            name: firstLine,
                            x: Math.round(rect.x + rect.width/2),
                            y: Math.round(rect.y + rect.height/2)
                        });
                    }
                }
            }
            return result;
        }""")
    except Exception as e:
        print(f"  查 tab 出錯: {e}")
        return []

def ensure_accessibility():
    global teamwork_page
    if teamwork_page is None:
        return False
    try:
        result = teamwork_page.evaluate("""() => {
            const p = document.querySelector('flt-semantics-placeholder');
            if (p) { p.click(); return 'clicked'; }
            return document.querySelectorAll('flt-semantics').length > 0 ? 'ready' : 'none';
        }""")
        if result == 'clicked':
            time.sleep(1.5)
        return True
    except Exception as e:
        print(f"✗ 啟用語義樹失敗: {e}")
        return False

def switch_tab():
    """切 tab 觸發 Flutter 刷新（先切去另一個 tab，再切回）"""
    global teamwork_page
    if teamwork_page is None:
        return False
    try:
        tabs = get_tab_buttons()
        if len(tabs) < 2:
            time.sleep(3)
            tabs = get_tab_buttons()
        if len(tabs) < 2:
            ensure_accessibility()
            time.sleep(2)
            tabs = get_tab_buttons()
        if len(tabs) < 2:
            print("  ⚠ 找不到 tab 按鈕")
            return False

        home = next((t for t in tabs if t['name'] == 'Home'), None)
        orders = next((t for t in tabs if t['name'] == 'My Orders'), None)
        if not home or not orders:
            print(f"  ⚠ tab 不完整: {[t['name'] for t in tabs]}")
            return False

        # 先點 My Orders 觸發請求，再點回 Home
        teamwork_page.mouse.click(orders['x'], orders['y'])
        time.sleep(2.5)
        teamwork_page.mouse.click(home['x'], home['y'])
        time.sleep(1.5)
        return True
    except Exception as e:
        print(f"✗ 切換 tab 失敗: {e}")
        return False

def save_token(token_data):
    try:
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump(token_data, f, indent=2)
    except Exception as e:
        print(f"✗ 保存 token 失敗: {e}")

def main():
    print("=" * 60)
    print("Teamwork Token Keepalive Service")
    print("輪詢: 5秒一次 (讀本地 localStorage，零網路請求)")
    print("顯示: 關鍵事件才顯示")
    print("按 Ctrl+C 停止")
    print("=" * 60)

    last_access = None
    last_exp = 0
    fail_count = 0
    last_refresh_attempt = 0
    notified_low = False

    while True:
        if teamwork_page is None:
            if not connect_to_edge():
                fail_count += 1
                print(f"✗ 無法連接 Edge ({fail_count})，10 秒後重試...")
                time.sleep(10)
                continue

        token = read_browser_token()

        if token:
            fail_count = 0
            exp_in = int(token['expires_at'] - time.time())

            # Token 有變化 → 同步並顯示
            if token['access_token'] != last_access or token['expires_at'] != last_exp:
                save_token(token)
                last_access = token['access_token']
                last_exp = token['expires_at']
                print(f"✓ Token 已同步，過期時間: {fmt_time(token['expires_at'])}")

            # 快過期時處理：強制切 tab 觸發刷新（帶 60 秒防抖）
            # 注意：不依賴「用戶活躍」判斷——用戶只是看頁面/移滑鼠不會觸發
            # Flutter 發請求，所以必須由我們主動切 tab
            if exp_in < 55 and exp_in > 0:
                notified_low = True
                if time.time() - last_refresh_attempt > 60:
                    print(f"⏳ Token 剩餘 {exp_in} 秒，自動切 tab 觸發刷新...")
                    last_refresh_attempt = time.time()
                    switch_tab()
                    time.sleep(2)
                    new_token = read_browser_token()
                    if new_token and new_token['expires_at'] > token['expires_at']:
                        save_token(new_token)
                        last_access = new_token['access_token']
                        last_exp = new_token['expires_at']
                        print(f"✓✓ 刷新成功! 新 token 剩餘 {int(new_token['expires_at'] - time.time())} 秒")
                        notified_low = False
                    else:
                        print("✗ 切 tab 後 token 未更新，60 秒後重試")
            elif exp_in <= 0:
                # token 已過期：安靜等待重新登入，每 2 分鐘提示一次
                if time.time() - last_refresh_attempt > 120:
                    print("⚠ Token 已過期，請在 Edge 中重新登入 teamwork")
                    last_refresh_attempt = time.time()
            else:
                notified_low = False

        else:
            fail_count += 1
            # 安靜模式：只在每 8 次（約 2 分鐘）提示一次，避免刷屏
            if fail_count % 24 == 1:
                print(f"⚠ 未讀取到登入 token，請重新登入 teamwork（每 2 分鐘提示一次）")
            if fail_count >= 30:
                reset_connection()
                fail_count = 0

        time.sleep(5)

if __name__ == '__main__':
    main()
