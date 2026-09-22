#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""德安物流小助手 - 依賴檢查／修復工具

用法（在本資料夾下）:
    .venv\\Scripts\\python.exe check_deps.py            檢查，有問題自動修復（預設）
    .venv\\Scripts\\python.exe check_deps.py --verify   只檢查不修復（更新前確認用）
    .venv\\Scripts\\python.exe check_deps.py --repair   強制重裝所有依賴

為何需要它:
  1. 更新包只替換 app.html / server.py，不會裝新依賴。若目標機缺少新依賴
     （例如 pywin32 / pillow），程式不會壞但列印功能會靜默失效 —— 所以要主動檢查。
  2. PyMuPDF 的 _extra.pyd 依賴同目錄下的 _mupdf.pyd 與 mupdfcpp64.dll（約 25MB）。
     安裝時若有檔案被鎖（舊服務仍在跑）／中斷／被防毒攔截／磁碟不足，就會出現
     「ImportError: DLL load failed while importing _extra: The specified module
     could not be found.」—— 這種情況清乾淨重裝即可修好（已實測可重現及修復）。

注意：所有檢查都在「新的子行程」內進行 —— pywin32 靠 pywin32.pth 加 sys.path，
      只在直譯器啟動時載入，在同一行程內重驗會出現假失敗。
"""
import json
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

PY = sys.executable

# (import 名稱, pip 名稱, 用途)
REQUIRED = [
    ('flask',      'flask',      'Web 服務'),
    ('flask_cors', 'flask-cors', '跨網域請求'),
    ('requests',   'requests',   '呼叫 Teamwork API'),
    ('PyPDF2',     'PyPDF2',     'PDF 頁數／標籤重建'),
    ('pymupdf',    'pymupdf',    'PDF 點陣化（GDI 直印／ZPL 直送必要）'),
    ('win32print', 'pywin32',    'GDI 直接列印'),
    ('win32ui',    'pywin32',    'GDI 直接列印'),
    ('PIL',        'pillow',     '影像處理（GDI 列印必要）'),
    ('playwright', 'playwright', 'Edge 自動登入（Token 保活）'),
]

# PyMuPDF 的原生檔案：(檔名, 最小合理大小)。缺一不可 —— 這就是 DLL load failed 的根源。
PYMUPDF_FILES = [
    ('_extra.pyd', 100_000),
    ('_mupdf.pyd', 5_000_000),
    ('mupdfcpp64.dll', 10_000_000),
]

VCRUNTIME = ['msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']

# PyMuPDF 首選版本（Windows 只有 cp310-abi3 wheel，Python 3.10+ 通用；已於 3.12 / 3.14 實測）
PREFERRED_PYMUPDF = 'pymupdf==1.28.2'

# 子行程檢查程式（務必在新行程執行，見檔頭說明）
_CHECK_TPL = (
    "import importlib, importlib.metadata as md, json, sys\n"
    "mods = %s\n"
    "pkgs = %s\n"
    # 注意：這裡用 % 格式化，不會處理大括號，所以直接寫單大括號
    "out = {}\n"
    "for m, p in zip(mods, pkgs):\n"
    "    try:\n"
    "        importlib.import_module(m)\n"
    "        try:\n"
    "            ver = md.version(p)\n"
    "        except Exception:\n"
    "            ver = ''\n"
    "        out[m] = {'ok': True, 'ver': ver, 'err': ''}\n"
    "    except Exception as e:\n"
    "        out[m] = {'ok': False, 'ver': '', 'err': '%%s: %%s' %% (type(e).__name__, e)}\n"
    "sys.stdout.write('@@J@@' + json.dumps(out))\n"
)


def log(msg=''):
    print(msg, flush=True)


def check_all():
    """用新子行程檢查所有模組，回傳 {mod: {...}}"""
    mods = [r[0] for r in REQUIRED]
    pkgs = [r[1] for r in REQUIRED]
    code = _CHECK_TPL % (json.dumps(mods), json.dumps(pkgs))
    try:
        r = subprocess.run([PY, '-c', code], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=300)
        out = r.stdout or ''
        if '@@J@@' in out:
            return json.loads(out.split('@@J@@', 1)[1])
        return {m: {'ok': False, 'ver': '', 'err': '子行程檢查無回應: ' + (out + (r.stderr or ''))[-200:]}
                for m in mods}
    except Exception as e:
        return {m: {'ok': False, 'ver': '', 'err': '檢查失敗: %s' % e} for m in mods}


def pip(args):
    log('      $ ' + ' '.join(args))
    try:
        return subprocess.call([PY, '-m', 'pip'] + list(args)) == 0
    except Exception as e:
        log('      [pip 執行失敗] ' + str(e))
        return False


def pip_install(pkgs):
    """先要求純 wheel（客戶機不必裝編譯器），失敗才退回允許源碼包。"""
    base = ['install', '--no-cache-dir', '--upgrade', '--force-reinstall']
    if pip(base + ['--only-binary=:all:'] + pkgs):
        return True
    log('      （純 wheel 安裝失敗，改為允許源碼包再試一次）')
    return pip(base + pkgs)


def find_pymupdf_dir():
    try:
        import site
        cands = list(site.getsitepackages()) + [site.getusersitepackages()]
    except Exception:
        cands = []
    p = os.path.join(os.path.dirname(os.path.dirname(PY)), 'Lib', 'site-packages')
    cands.append(p)
    for sp in cands:
        d = os.path.join(sp, 'pymupdf')
        if os.path.isdir(d):
            return d
    return None


def check_pymupdf_files():
    d = find_pymupdf_dir()
    if not d:
        return False, ['找不到 pymupdf 套件目錄']
    problems, notes = [], []
    for fn, min_size in PYMUPDF_FILES:
        fp = os.path.join(d, fn)
        if not os.path.exists(fp):
            problems.append('缺少 %s' % fn)
        else:
            sz = os.path.getsize(fp)
            if sz < min_size:
                problems.append('%s 只有 %.1f MB（應 >= %.1f MB，下載／解壓不完整）'
                                % (fn, sz / 1048576.0, min_size / 1048576.0))
            else:
                notes.append('%s OK (%.1f MB)' % (fn, sz / 1048576.0))
    return (not problems), (problems if problems else notes)


def check_vcruntime():
    sys32 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
    missing = [d for d in VCRUNTIME if not os.path.exists(os.path.join(sys32, d))]
    return (not missing), missing


def print_results(results, pm_ok, pm_detail):
    log('-' * 62)
    log('  套件檢查結果')
    log('-' * 62)
    for mod, pkg, purpose in REQUIRED:
        r = results.get(mod, {})
        if r.get('ok'):
            log('  [OK]   %-11s %-22s %s' % (mod, purpose, r.get('ver', '')))
        else:
            log('  [缺失] %-11s %-22s %s' % (mod, purpose, (r.get('err') or '')[:70]))
    log('')
    log('  PyMuPDF 原生檔案（DLL load failed 的根源）:')
    for line in pm_detail:
        log('    %s %s' % ('[OK]  ' if pm_ok else '[問題]', line))


def main():
    args = [a.lower() for a in sys.argv[1:]]
    verify_only = '--verify' in args
    force_repair = '--repair' in args

    log('=' * 62)
    log('  德安物流小助手 - 依賴檢查')
    log('=' * 62)
    log('  Python  : %s' % sys.version.split()[0])
    log('  架構    : %s' % ('64-bit' if sys.maxsize > 2 ** 32 else '32-bit'))
    log('  位置    : %s' % PY)
    log('')

    if sys.version_info < (3, 10):
        log('  [警告] Python 低於 3.10，部分套件沒有對應 wheel。')
        log('         建議安裝 Python 3.12 後重新執行 setup.bat。')
        log('')
    if sys.maxsize <= 2 ** 32:
        log('  [警告] 這是 32-bit Python；建議改用 64-bit 版本。')
        log('')

    log('  檢查中…')
    results = check_all()
    pm_ok, pm_detail = check_pymupdf_files()
    vc_ok, vc_missing = check_vcruntime()

    log('')
    print_results(results, pm_ok, pm_detail)
    log('')
    log('  Visual C++ 執行檔 (System32): %s'
        % ('齊全' if vc_ok else '缺少 ' + ', '.join(vc_missing)))
    if not vc_ok:
        log('  → 這也可能是 _extra.pyd 載入失敗的原因。請安裝：')
        log('    "Microsoft Visual C++ 2015-2022 Redistributable (x64)"')
        log('    https://aka.ms/vs/17/release/vc_redist.x64.exe')

    broken = [r for r in REQUIRED if not results.get(r[0], {}).get('ok')]
    need_repair = bool(broken) or (not pm_ok) or force_repair

    log('')
    log('=' * 62)
    if not need_repair:
        log('  [OK] 全部依賴正常，列印與登入功能可用。')
        log('=' * 62)
        return 0

    log('  發現問題：')
    if broken:
        for r in broken:
            log('    - %s (%s)' % (r[0], r[1]))
    if not pm_ok:
        log('    - PyMuPDF 原生檔案不完整（＝DLL load failed while importing _extra 的原因）')
    log('=' * 62)

    if verify_only:
        log('')
        log('  [--verify 模式] 不進行修復，回傳 1。')
        log('  請執行 repair_deps.bat（或 setup.bat）來修復。')
        return 1

    log('')
    log('  開始修復…')
    log('  （若舊服務仍在跑，檔案會被鎖住 —— 請先關閉，或用 repair_deps.bat）')
    log('')

    log('  [a] 移除舊的 PyMuPDF / fitz')
    pip(['uninstall', '-y', 'pymupdf', 'fitz'])

    pkgs = []
    for r in broken:
        if r[1] not in pkgs:
            pkgs.append(r[1])
    if (not pm_ok) and ('pymupdf' not in pkgs):
        pkgs.append('pymupdf')
    if not pkgs:
        pkgs = ['pymupdf']

    log('')
    log('  [b] 重新安裝: %s' % ', '.join(pkgs))
    first = [PREFERRED_PYMUPDF if p == 'pymupdf' else p for p in pkgs]
    if not pip_install(first) and 'pymupdf' in pkgs:
        log('      （首選版本 %s 失敗，改裝最新版）' % PREFERRED_PYMUPDF)
        pip_install(['pymupdf' if p == 'pymupdf' else p for p in pkgs])

    log('')
    log('  [c] 重新檢查（新行程）…')
    results2 = check_all()
    pm_ok2, pm_detail2 = check_pymupdf_files()
    log('')
    print_results(results2, pm_ok2, pm_detail2)

    still = [r[0] for r in REQUIRED if not results2.get(r[0], {}).get('ok')]
    log('')
    log('=' * 62)
    if not still and pm_ok2:
        log('  [修復成功] 全部依賴正常，列印與登入功能可用。')
        log('=' * 62)
        return 0
    log('  [修復未完成] 仍有問題: %s' % (', '.join(still) if still else 'PyMuPDF 原生檔案'))
    log('  請依序嘗試：')
    log('    1. 關閉所有 python.exe / 服務，再執行 repair_deps.bat')
    log('    2. 確認防毒沒有隔離 mupdfcpp64.dll')
    log('    3. 確認磁碟剩餘空間 >= 1GB（PyMuPDF 解壓後約 40MB）')
    if not vc_ok:
        log('    4. 安裝 VC++ 2015-2022 Redistributable (x64)')
    log('  若仍失敗，請把以上整段輸出複製給開發者。')
    log('=' * 62)
    return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
