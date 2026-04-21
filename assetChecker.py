# -*- coding: utf-8 -*-
import io
import contextlib
import re
import json
import urllib.request
import types
import sys

import maya.OpenMayaUI as omui
try:
    import maya.cmds as cmds
except Exception:
    cmds = None
from PySide2 import QtWidgets, QtCore
from shiboken2 import wrapInstance


# ============================================================
# Maya メインウィンドウ取得
# ============================================================
def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


# ============================================================
# 設定
# ============================================================
GITHUB_RAW          = "https://raw.githubusercontent.com/ANK009-a/Maya-ModelChecker/main"
GITHUB_API_INDEX    = f"{GITHUB_RAW}/tools/manifest_index.json"
WINDOW_OBJECT_NAME  = "assetChecker"
LEFT_W = 168   # 左パネル（チェックボタン列）の幅
BTN_H  = 26    # チェックボタンの高さ
FIX_W  = 40    # FIX ボタンの幅

_script_cache = {}  # { "folder/script.py": "コード文字列" }


# ============================================================
# ツールチップ即時表示フィルター
# ============================================================
class _InstantTooltipFilter(QtCore.QObject):
    """ホバー時に遅延なくツールチップを表示するイベントフィルター"""
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Enter:
            tip = obj.toolTip()
            if tip:
                pos = obj.mapToGlobal(QtCore.QPoint(0, obj.height() + 4))
                QtWidgets.QToolTip.showText(pos, tip, obj)
        elif event.type() == QtCore.QEvent.Leave:
            QtWidgets.QToolTip.hideText()
        return False


# ============================================================
# 既存UIの多重起動防止
# ============================================================
def close_existing_ui():
    ptr = omui.MQtUtil.findWindow(WINDOW_OBJECT_NAME)
    if ptr:
        widget = wrapInstance(int(ptr), QtWidgets.QWidget)
        try:
            widget.close()
            widget.deleteLater()
        except Exception:
            pass



# ============================================================
# リモートローディングユーティリティ
# ============================================================
def fetch_manifest_index():
    """GitHub から manifest_index.json を取得してリスト返す"""
    try:
        with urllib.request.urlopen(GITHUB_API_INDEX, timeout=10) as resp:
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
    """_util.py を sys.modules に登録（import _util が使えるようにする）"""
    if "_util" not in sys.modules:
        code = fetch_script("", "_util.py")
        if code:
            mod = types.ModuleType("_util")
            exec(compile(code, "_util.py", "exec"), mod.__dict__)
            sys.modules["_util"] = mod


def load_and_run(folder, script_name):
    """スクリプトを取得して exec し、構造化結果または stdout テキストを返す"""
    _ensure_util_module()
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


# ============================================================
# 状態定数
# ============================================================
_S_UNCHECKED = 0
_S_OK        = 1
_S_ERROR     = 2


# ============================================================
# UI クラス
# ============================================================
class assetChecker(QtWidgets.QDialog):

    # ----------------------------------------------------------
    # スタイルシート
    # ----------------------------------------------------------
    _SS_DIALOG = """
QDialog#assetChecker {
    background-color: #1c2b3a;
}
QScrollArea {
    background-color: #162030;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background-color: #162030;
}
QListWidget {
    background-color: #162030;
    color: #a0b4c8;
    border: 1px solid #1a2e40;
    outline: none;
}
QListWidget::item {
    padding: 4px 8px;
}
QListWidget::item:selected {
    background-color: #2d6cdf;
    color: #ffffff;
}
QTextEdit {
    background-color: #162030;
    color: #ccddef;
    border: 1px solid #1a2e40;
    selection-background-color: #2d6cdf;
    selection-color: #ffffff;
}
QSplitter::handle {
    background-color: #1c2b3a;
}
QSplitter::handle:hover {
    background-color: #4a6888;
}
QScrollBar:vertical {
    background: #0d1a28;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #4a6888;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QToolTip {
    background-color: #1a3050;
    color: #ccddef;
    border: 1px solid #3a6488;
    border-radius: 5px;
    padding: 6px 10px;
    font-size: 12px;
    opacity: 230;
}
"""

    _SS_BTN_UNCHECKED = """QPushButton {
    background-color: #243546;
    color: #7a90a8;
    border: 1px solid #1a2e40;
    border-radius: 6px;
    text-align: left;
    padding: 0 12px;
    font-size: 12px;
}
QPushButton:hover   { background-color: #2d3e52; }
QPushButton:pressed { background-color: #1a2737; }
"""

    _SS_BTN_OK = """QPushButton {
    background-color: #183328;
    color: #3ecb72;
    border: 1px solid #1e4a32;
    border-radius: 6px;
    text-align: left;
    padding: 0 12px;
    font-size: 12px;
}
QPushButton:hover { background-color: #1e3d2e; }
"""

    _SS_BTN_ERROR = """QPushButton {
    background-color: #3a1e1e;
    color: #e06060;
    border: 1px solid #5a2a2a;
    border-radius: 6px;
    text-align: left;
    padding: 0 12px;
    font-size: 12px;
}
QPushButton:hover { background-color: #462424; }
"""

    _SS_BTN_FIX = """QPushButton {
    background-color: #3a6ec0;
    color: white;
    border-radius: 6px;
    font-size: 11px;
}
QPushButton:hover    { background-color: #5a8ee0; }
QPushButton:pressed  { background-color: #2a5aa0; }
QPushButton:disabled { background-color: #2a3a50; color: #506070; }
"""

    _SS_BTN_ALL = """QPushButton {
    background-color: #3a6ec0;
    color: white;
    border-radius: 6px;
    height: 26px;
    padding: 0 14px;
    font-size: 12px;
}
QPushButton:hover    { background-color: #5a8ee0; }
QPushButton:pressed  { background-color: #2a5aa0; }
QPushButton:disabled { background-color: #2a3a50; color: #506070; }
"""

    _SS_BTN_ALL_FIX = """QPushButton {
    background-color: #8a2c2c;
    color: #ffbbbb;
    border-radius: 5px;
    height: 20px;
    padding: 0 10px;
    font-size: 11px;
}
QPushButton:hover    { background-color: #b03a3a; }
QPushButton:pressed  { background-color: #6a2020; }
QPushButton:disabled { background-color: #3a2424; color: #6a4848; }
"""

    # Maya 選択をスキップする疑似キー
    _SKIP_SELECT_KEYS = frozenset({
        "stdout", "ALL_CHECK",
        "(summary)", "(result)", "(none)", "(info)",
    })

    # ----------------------------------------------------------
    def __init__(self, parent=maya_main_window()):
        super().__init__(parent)
        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle("assetChecker")
        self.resize(600, 500)
        self.setStyleSheet(self._SS_DIALOG)

        # 状態管理
        self._folder_states = {}   # folder -> _S_*
        self._folder_counts = {}   # folder -> int

        # ウィジェット参照
        self._check_btns = {}
        self._fix_btns   = {}
        self.has_correct_script = {}

        # 右パネル
        self.object_to_details = {}
        self._last_check_results = {}  # folder -> obj_to_details（FIX 前の自動選択に使用）

        # フォルダ一覧
        self.folders = []

        # ツールチップ即時表示フィルター（全ボタン共有）
        self._tooltip_filter = _InstantTooltipFilter(self)

        # ALL CHECK / ALL FIX 実行フラグ
        self._all_check_running = False
        self._all_check_index   = 0
        self._all_check_summary = []
        self._all_fix_running   = False
        self._all_fix_queue     = []
        self._all_fix_index     = 0

        self._build_ui()
        self._load_folders()
        QtCore.QTimer.singleShot(0, self._adjust_height)

    # ----------------------------------------------------------
    # UI 構築
    # ----------------------------------------------------------
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- トップバー ----
        top = QtWidgets.QWidget()
        top.setStyleSheet("background-color: #111e2d; border-bottom: 1px solid #1a2e40;")
        top_lay = QtWidgets.QHBoxLayout(top)
        top_lay.setContentsMargins(14, 7, 14, 7)

        title = QtWidgets.QLabel("assetChecker")
        title.setStyleSheet(
            "color: #7aaccf; font-size: 13px; font-weight: bold; background: transparent;"
        )
        top_lay.addWidget(title)
        top_lay.addStretch()

        self.all_check_btn = QtWidgets.QPushButton("ALL CHECK")
        self.all_check_btn.setStyleSheet(self._SS_BTN_ALL)
        self.all_check_btn.clicked.connect(self.start_all_check)
        top_lay.addWidget(self.all_check_btn)
        root.addWidget(top)

        # ---- メインエリア ----
        main_w = QtWidgets.QWidget()
        main_lay = QtWidgets.QHBoxLayout(main_w)
        main_lay.setContentsMargins(8, 8, 8, 8)
        main_lay.setSpacing(8)

        # 左ペイン（スクロールエリア）
        sbw = QtWidgets.QApplication.style().pixelMetric(QtWidgets.QStyle.PM_ScrollBarExtent)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)        # フレームを除去してvpを正確に確保
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # LEFT_W + row間隔(4) + FIX_W + rows_layoutの左右余白(4+4) + スクロールバー
        scroll.setFixedWidth(LEFT_W + 4 + FIX_W + 8 + sbw)

        left_inner = QtWidgets.QWidget()
        self.rows_layout = QtWidgets.QVBoxLayout(left_inner)
        self.rows_layout.setContentsMargins(4, 4, 4, 4)
        self.rows_layout.setSpacing(4)
        scroll.setWidget(left_inner)
        self.left_scroll = scroll
        self.left_inner  = left_inner
        main_lay.addWidget(scroll)

        # 右ペイン（スプリッター）
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.object_list = QtWidgets.QListWidget()
        self.object_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.detail_view = QtWidgets.QTextEdit()
        self.detail_view.setReadOnly(True)
        splitter.addWidget(self.object_list)
        splitter.addWidget(self.detail_view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        main_lay.addWidget(splitter, 1)

        self.object_list.currentItemChanged.connect(self.on_object_selected)
        self.object_list.itemClicked.connect(self.on_object_clicked)
        root.addWidget(main_w, 1)

        # ---- ステータスバー ----
        status = QtWidgets.QFrame()
        status.setStyleSheet("QFrame { background-color: #0e1c2c; border-top: 1px solid #1a2e40; }")
        status_lay = QtWidgets.QHBoxLayout(status)
        status_lay.setContentsMargins(14, 5, 14, 5)
        status_lay.setSpacing(18)

        _lbl_ss = "font-size: 11px; background: transparent;"
        self._lbl_error     = QtWidgets.QLabel("✗  0件エラー")
        self._lbl_ok        = QtWidgets.QLabel("✓  0件 OK")
        self._lbl_unchecked = QtWidgets.QLabel("○  0件 未チェック")
        self._lbl_error.setStyleSheet(f"color: #c05050; {_lbl_ss}")
        self._lbl_ok.setStyleSheet(f"color: #3ecb72; {_lbl_ss}")
        self._lbl_unchecked.setStyleSheet(f"color: #6a8aaa; {_lbl_ss}")
        for lbl in (self._lbl_error, self._lbl_ok, self._lbl_unchecked):
            status_lay.addWidget(lbl)
        status_lay.addStretch()

        self.all_fix_btn = QtWidgets.QPushButton("ALL FIX")
        self.all_fix_btn.setStyleSheet(self._SS_BTN_ALL_FIX)
        self.all_fix_btn.setEnabled(False)
        self.all_fix_btn.clicked.connect(self.start_all_fix)
        status_lay.addWidget(self.all_fix_btn)
        root.addWidget(status)

    # ----------------------------------------------------------
    # フォルダ読み込み → 左ペイン生成
    # ----------------------------------------------------------
    def _load_folders(self):
        manifest = fetch_manifest_index()
        if not manifest:
            self.rows_layout.addWidget(QtWidgets.QLabel("ツール一覧の取得に失敗しました"))
            return

        self.folders = [entry["folder"] for entry in manifest]

        for entry in manifest:
            folder = entry["folder"]
            self._folder_states[folder] = _S_UNCHECKED
            self._folder_counts[folder] = 0
            self.has_correct_script[folder] = entry.get("has_fix", False)

            row = QtWidgets.QHBoxLayout()
            row.setSpacing(4)
            row.setContentsMargins(0, 0, 0, 0)

            # チェックボタン（メイン）
            btn = QtWidgets.QPushButton(f"  ○  {folder}")
            btn.setFixedHeight(BTN_H)
            btn.setMinimumWidth(1)   # テキストが長くても FIX を押し出さないよう最小幅を解除
            btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            btn.setStyleSheet(self._SS_BTN_UNCHECKED)
            btn.clicked.connect(lambda *_, f=folder: self.run_check(f, show_details=True))
            title = entry.get("title", folder)
            desc  = entry.get("description", "")
            if title or desc:
                btn.setToolTip(
                    f"<b style='font-size:13px;'>{title}</b>"
                    f"<hr style='border:1px solid #3a6488; margin:4px 0;'>"
                    f"<span style='line-height:1.6;'>{desc}</span>"
                )
                btn.installEventFilter(self._tooltip_filter)
            row.addWidget(btn)
            self._check_btns[folder] = btn

            # FIX ボタン（has_fix=true のツール・エラー時のみ表示）
            fix_btn = QtWidgets.QPushButton("FIX")
            fix_btn.setFixedWidth(FIX_W)
            fix_btn.setFixedHeight(BTN_H)
            fix_btn.setStyleSheet(self._SS_BTN_FIX)
            fix_btn.setVisible(False)
            fix_btn.clicked.connect(lambda *_, f=folder: self._run_fix(f))
            row.addWidget(fix_btn)
            self._fix_btns[folder] = fix_btn

            self.rows_layout.addLayout(row)

        self.rows_layout.addStretch()
        self._update_status_bar()

    # ----------------------------------------------------------
    # 高さ自動調整
    # ----------------------------------------------------------
    def _adjust_height(self):
        try:
            self.left_inner.adjustSize()
            content_h = self.left_inner.sizeHint().height()
            chrome_h  = max(0, self.height() - self.left_scroll.viewport().height())
            screen    = QtWidgets.QApplication.primaryScreen()
            max_h     = int(screen.availableGeometry().height() * 0.85) if screen else 900
            self.resize(self.width(), min(max_h, max(360, content_h + chrome_h)))
        except Exception:
            pass

    # ----------------------------------------------------------
    # ボタン状態更新
    # ----------------------------------------------------------
    def _set_folder_state(self, folder, state, count=0):
        self._folder_states[folder] = state
        self._folder_counts[folder] = count
        btn = self._check_btns.get(folder)
        fix = self._fix_btns.get(folder)
        if not btn:
            return

        if state == _S_UNCHECKED:
            btn.setText(f"  ○  {folder}")
            btn.setStyleSheet(self._SS_BTN_UNCHECKED)
        elif state == _S_OK:
            btn.setText(f"  ✓  {folder}")
            btn.setStyleSheet(self._SS_BTN_OK)
        else:
            suffix = f"   ·  {count}件" if count > 0 else ""
            btn.setText(f"  ✗  {folder}{suffix}")
            btn.setStyleSheet(self._SS_BTN_ERROR)

        if fix:
            show = state == _S_ERROR and self.has_correct_script.get(folder, False)
            fix.setVisible(show)
            fix.setEnabled(show)

    def _update_status_bar(self):
        n_err = sum(1 for s in self._folder_states.values() if s == _S_ERROR)
        n_ok  = sum(1 for s in self._folder_states.values() if s == _S_OK)
        n_unc = sum(1 for s in self._folder_states.values() if s == _S_UNCHECKED)

        self._lbl_error.setText(f"✗  {n_err}件エラー")
        self._lbl_ok.setText(f"✓  {n_ok}件 OK")
        self._lbl_unchecked.setText(f"○  {n_unc}件 未チェック")

        can_fix = any(
            self._folder_states.get(f) == _S_ERROR and self.has_correct_script.get(f)
            for f in self.folders
        )
        busy = self._all_check_running or self._all_fix_running
        self.all_fix_btn.setEnabled(can_fix and not busy)

    # ----------------------------------------------------------
    # Maya 選択ユーティリティ
    # ----------------------------------------------------------
    def _gather_select_targets(self, key, details):
        if not cmds:
            return []
        candidates = []
        if isinstance(key, str) and key:
            candidates.append(key)
        if details:
            pattern = re.compile(
                r'[\|]?[A-Za-z_][A-Za-z0-9_:\|]*?(?:\.[A-Za-z]+)?(?:\[[0-9:,\-]+\])?'
            )
            for line in details:
                for tok in pattern.findall(str(line)):
                    tok = tok.strip()
                    if not tok or tok in ("stdout", "ALL_CHECK"):
                        continue
                    if cmds.objExists(tok):
                        candidates.append(tok)
                        continue
                    base = tok.split(".", 1)[0] if "." in tok else tok
                    if base and cmds.objExists(base):
                        candidates.append(base)
        seen = set()
        uniq = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        final = []
        for c in uniq:
            if cmds.objExists(c):
                final.append(c)
            elif "." in c:
                base = c.split(".", 1)[0]
                if base and cmds.objExists(base):
                    final.append(base)
        return final

    def _apply_maya_selection_for_key(self, key, details):
        if not cmds or key in self._SKIP_SELECT_KEYS:
            return
        try:
            targets = self._gather_select_targets(str(key), details)
            if targets:
                cmds.select(targets, r=True)
        except Exception:
            pass

    # ----------------------------------------------------------
    # 右パネル
    # ----------------------------------------------------------
    def on_object_clicked(self, item):
        if not item:
            return
        key = item.data(QtCore.Qt.UserRole)
        if key:
            self._apply_maya_selection_for_key(key, self.object_to_details.get(key, []))

    def on_object_selected(self, current, previous):
        self.detail_view.clear()
        if not current:
            return
        key = current.data(QtCore.Qt.UserRole)
        if not key:
            return
        details = self.object_to_details.get(key, [])
        if details:
            self.detail_view.setPlainText("\n".join(details))
        self._apply_maya_selection_for_key(key, details)

    def set_object_results(self, obj_to_details):
        self.object_to_details = obj_to_details or {}
        self.object_list.blockSignals(True)
        self.object_list.clear()
        for key in sorted(self.object_to_details.keys()):
            item = QtWidgets.QListWidgetItem(key)
            item.setData(QtCore.Qt.UserRole, key)
            self.object_list.addItem(item)
        self.object_list.blockSignals(False)
        if self.object_list.count() > 0:
            self.object_list.setCurrentRow(0)
        else:
            self.detail_view.clear()

    def normalize_structured(self, structured):
        obj_to_details = {}
        if structured is None:
            return obj_to_details
        if isinstance(structured, dict):
            for k, v in structured.items():
                obj_to_details[str(k)] = [str(x) for x in v] if isinstance(v, list) else [str(v)]
            return obj_to_details
        if isinstance(structured, list):
            for entry in structured:
                if not isinstance(entry, dict):
                    continue
                key = entry.get("transform") or entry.get("name") or "Unknown"
                msg = entry.get("message", "")
                details = entry.get("details", [])
                lines = []
                if msg:
                    lines.append(str(msg))
                if isinstance(details, list):
                    lines.extend(str(x) for x in details)
                elif details:
                    lines.append(str(details))
                obj_to_details.setdefault(str(key), []).extend(lines)
        return obj_to_details

    # ----------------------------------------------------------
    # チェック実行
    # ----------------------------------------------------------
    def run_check(self, folder, show_details=True):
        structured, text = load_and_run(folder, f"{folder}_check.py")

        if structured is not None:
            obj_to_details = self.normalize_structured(structured)
            has_issue = bool(obj_to_details)
            count = len(obj_to_details)
        else:
            has_issue = bool(text.strip())
            count = 1 if has_issue else 0
            obj_to_details = {"stdout": [text]} if has_issue else {}

        # FIX 前の自動選択に使うため常にキャッシュ
        self._last_check_results[folder] = obj_to_details

        if show_details:
            self.set_object_results(obj_to_details)

        self._set_folder_state(folder, _S_ERROR if has_issue else _S_OK, count)
        self._update_status_bar()
        return has_issue

    # ----------------------------------------------------------
    # FIX 前の自動選択
    # ----------------------------------------------------------
    def _select_check_results(self, folder):
        """直近のチェック結果に含まれるオブジェクトを Maya で選択する"""
        if not cmds:
            return
        obj_to_details = self._last_check_results.get(folder, {})
        targets = [
            k for k in obj_to_details
            if k not in self._SKIP_SELECT_KEYS and cmds.objExists(k)
        ]
        if targets:
            try:
                cmds.select(targets, r=True)
            except Exception:
                pass

    # ----------------------------------------------------------
    # FIX 実行
    # ----------------------------------------------------------
    def _run_fix(self, folder):
        self._select_check_results(folder)  # チェック結果オブジェクトを事前に Maya 選択
        structured, text = load_and_run(folder, f"{folder}_correct.py")
        if structured is not None:
            self.set_object_results(self.normalize_structured(structured))
        else:
            self.set_object_results({"stdout": [text]} if text.strip() else {})
        # correct 後に自動 re-check
        QtCore.QTimer.singleShot(0, lambda: self.run_check(folder, show_details=True))

    # ----------------------------------------------------------
    # ALL CHECK
    # ----------------------------------------------------------
    def start_all_check(self):
        if self._all_check_running or self._all_fix_running:
            return
        self._all_check_running = True
        self._all_check_index   = 0
        self._all_check_summary = []
        self._set_busy(True)
        self.set_object_results({})
        self.detail_view.setPlainText("ALL CHECK 実行中...")
        QtCore.QTimer.singleShot(0, self._step_all_check)

    def _step_all_check(self):
        if self._all_check_index >= len(self.folders):
            self._finish_all_check()
            return
        folder = self.folders[self._all_check_index]
        self._all_check_index += 1
        has_issue = self.run_check(folder, show_details=False)
        self._all_check_summary.append(("ERROR" if has_issue else "OK", folder))
        QtWidgets.QApplication.processEvents()
        QtCore.QTimer.singleShot(0, self._step_all_check)

    def _finish_all_check(self):
        self._all_check_running = False
        self._set_busy(False)
        lines = ["ALL CHECK 結果", ""]
        for status, folder in self._all_check_summary:
            lines.append(f"  {status} : {folder}")
        self.set_object_results({"ALL_CHECK": lines})
        self.detail_view.setPlainText("\n".join(lines))

    # ----------------------------------------------------------
    # ALL FIX
    # ----------------------------------------------------------
    def start_all_fix(self):
        if self._all_check_running or self._all_fix_running:
            return
        queue = [
            f for f in self.folders
            if self._folder_states.get(f) == _S_ERROR and self.has_correct_script.get(f)
        ]
        if not queue:
            return
        self._all_fix_running = True
        self._all_fix_queue   = queue
        self._all_fix_index   = 0
        self._set_busy(True)
        self.detail_view.setPlainText("ALL FIX 実行中...")
        QtCore.QTimer.singleShot(0, self._step_all_fix)

    def _step_all_fix(self):
        if self._all_fix_index >= len(self._all_fix_queue):
            self._finish_all_fix()
            return
        folder = self._all_fix_queue[self._all_fix_index]
        self._all_fix_index += 1
        self._select_check_results(folder)  # チェック結果オブジェクトを事前に Maya 選択
        load_and_run(folder, f"{folder}_correct.py")
        self.run_check(folder, show_details=False)
        QtWidgets.QApplication.processEvents()
        QtCore.QTimer.singleShot(0, self._step_all_fix)

    def _finish_all_fix(self):
        self._all_fix_running = False
        self._set_busy(False)
        self.detail_view.setPlainText("ALL FIX 完了")

    # ----------------------------------------------------------
    # ビジー状態の一括制御
    # ----------------------------------------------------------
    def _set_busy(self, busy):
        """ALL CHECK / ALL FIX 実行中のボタン一括制御"""
        self.all_check_btn.setEnabled(not busy)
        self.all_check_btn.setText("…" if busy else "ALL CHECK")
        self.all_fix_btn.setText("…" if (busy and self._all_fix_running) else "ALL FIX")

        for btn in self._check_btns.values():
            btn.setEnabled(not busy)
        for f, fix_btn in self._fix_btns.items():
            if busy:
                fix_btn.setEnabled(False)
            else:
                show = (
                    self._folder_states.get(f) == _S_ERROR
                    and self.has_correct_script.get(f, False)
                )
                fix_btn.setVisible(show)
                fix_btn.setEnabled(show)

        if not busy:
            self._update_status_bar()


# ============================================================
# 起動
# ============================================================
close_existing_ui()
ui = assetChecker()
ui.show()
