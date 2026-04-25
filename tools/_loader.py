# -*- coding: utf-8 -*-
"""
GitHub raw からツールスクリプトを動的にロードする機構。
- メモリのみキャッシュ（ディスクには残さない）
- assetChecker.py 再 exec 時に新しい _loader が読み込まれてキャッシュリセット
"""

import io
import contextlib
import json
import urllib.request
import types
import sys

try:
    import maya.cmds as cmds
except Exception:
    cmds = None


# ホスト（assetChecker.py）から configure() で設定される
GITHUB_RAW = None

# { "folder/script.py": "ソース文字列" }
_script_cache = {}


def configure(github_raw):
    """assetChecker.py から呼ばれてベース URL を設定"""
    global GITHUB_RAW
    GITHUB_RAW = github_raw


def fetch_manifest_index():
    """manifest_index.json を取得してリストを返す"""
    if GITHUB_RAW is None:
        print("[assetChecker] _loader.configure() が未呼び出しです")
        return []
    url = f"{GITHUB_RAW}/tools/manifest_index.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8-sig"))
    except Exception as e:
        print(f"[assetChecker] manifest_index.json の取得に失敗しました: {e}")
        return []


def fetch_script(folder, script_name):
    """GitHub raw からスクリプトを取得（メモリキャッシュ付き）"""
    key = f"{folder}/{script_name}" if folder else script_name
    if key in _script_cache:
        return _script_cache[key]
    path = f"tools/{folder}/{script_name}" if folder else f"tools/{script_name}"
    url = f"{GITHUB_RAW}/{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            code = resp.read().decode("utf-8")
            _script_cache[key] = code
            return code
    except Exception as e:
        print(f"[assetChecker] スクリプトの取得に失敗しました: {url}\n{e}")
        return None


def _ensure_util_module():
    """_util.py を sys.modules に登録（import _util を可能にする）"""
    if "_util" not in sys.modules:
        code = fetch_script("", "_util.py")
        if code:
            mod = types.ModuleType("_util")
            exec(compile(code, "_util.py", "exec"), mod.__dict__)
            sys.modules["_util"] = mod


def load_and_run(folder, script_name, selection=None):
    """スクリプトを取得して exec し、構造化結果または stdout テキストを返す。
    selection=None  : 呼び出し時点の Maya 選択を使用
    selection=[]    : シーン全体を対象
    selection=[...] : 指定オブジェクトのみを対象
    """
    _ensure_util_module()
    util_mod = sys.modules.get("_util")
    if util_mod:
        if selection is None:
            util_mod._checker_selection = (cmds.ls(sl=True, long=True) or []) if cmds else []
        else:
            util_mod._checker_selection = selection

    code = fetch_script(folder, script_name)
    if code is None:
        return None, ""

    ns = {}
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(code, script_name, "exec"), ns)
        get_results = ns.get("get_results", None)
        if callable(get_results):
            return get_results(), ""
        if "RESULTS" in ns:
            return ns["RESULTS"], ""
    except Exception as e:
        print(f"[assetChecker] 実行エラー: {script_name}\n{e}")

    return None, buf.getvalue().strip()
