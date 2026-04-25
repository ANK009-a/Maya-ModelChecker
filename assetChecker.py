# -*- coding: utf-8 -*-
import io
import contextlib
import re
import json
import html
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
LAUNCHER_VERSION    = "1.4.0"
LEFT_PANEL_W = 204  # 左パネル全体の幅
BTN_H        = 28   # ツールボタンの高さ
TOP_BAR_H    = 26   # 枠外トップバーの高さ（CHECK/ALL CHECK / object_list_title / Info）
FIX_W        = 38   # FIX ボタンの幅

_script_cache = {}  # { "folder/script.py": "コード文字列" }

# 毎回最新の _util をロードするためにキャッシュをクリア
sys.modules.pop("_util", None)


# ============================================================
# ダブルクリック対応ボタン
# ============================================================
class _DoubleClickButton(QtWidgets.QPushButton):
    """QTimer でシングル/ダブルクリックを明確に分離したボタン。
    - singleClicked : 短時間内にダブルクリックが来なかった場合にのみ発火
    - doubleClicked : ダブルクリック時に発火（singleClicked は発火しない）
    """
    singleClicked = QtCore.Signal()
    doubleClicked = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # シングル/ダブル判定待ち時間（短めにしてシングルクリックの反応を良くする）
        # Qt 既定の doubleClickInterval(通常500ms) より短い値の小さい方を採用
        _interval = min(180, QtWidgets.QApplication.doubleClickInterval())
        self._click_timer = QtCore.QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(_interval)
        self._click_timer.timeout.connect(self.singleClicked.emit)
        self._cancel_next_release = False

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)  # ボタン内部状態を正常にリセット
        if event.button() != QtCore.Qt.LeftButton:
            return
        # ダブルクリックの2回目 release はタイマー起動を抑制
        if self._cancel_next_release:
            self._cancel_next_release = False
            return
        # シングルクリックかもしれない → タイマーで遅延発火
        self._click_timer.start()

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._click_timer.stop()       # シングル候補を破棄
            self._cancel_next_release = True
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)


# ============================================================
# ツールチップ即時表示フィルター
# ============================================================
class _InstantTooltipFilter(QtCore.QObject):
    """ホバー後 _interval ms（既定 400ms）でツールチップを表示するイベントフィルター"""
    _interval = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._show_for_target)
        self._target = None

    def _show_for_target(self):
        obj = self._target
        if not obj:
            return
        tip = obj.toolTip()
        if tip:
            pos = obj.mapToGlobal(QtCore.QPoint(0, obj.height() + 4))
            QtWidgets.QToolTip.showText(pos, tip, obj)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Enter:
            self._target = obj
            self._timer.start(self._interval)
        elif event.type() == QtCore.QEvent.Leave:
            self._timer.stop()
            self._target = None
            QtWidgets.QToolTip.hideText()
        return False


# ============================================================
# 詳細ビュー（コンポーネントクリック選択対応 QTextEdit）
# ============================================================
_COMPONENT_PATTERN = re.compile(
    r'(?:\|?[A-Za-z_][A-Za-z0-9_:\|]*\.)?'
    r'(?:vtx|f|e|map|uv|cv|ep|pt)\[[0-9:,\-\s]+\]'
)


class _ComponentTextEdit(QtWidgets.QTextEdit):
    """クリックされた位置の Maya コンポーネント（vtx[], f[], e[], map[] 等）を
    検出して componentClicked シグナルを emit する。
    - ホバー時にポインターカーソル表示
    - テキスト選択（ドラッグ）時は emit しない"""
    componentClicked = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)  # ボタン無しでも mouseMoveEvent を受信

    def _component_at(self, pos):
        cursor = self.cursorForPosition(pos)
        block_text = cursor.block().text()
        col = cursor.positionInBlock()
        for m in _COMPONENT_PATTERN.finditer(block_text):
            if m.start() <= col <= m.end():
                return m.group(0)
        return None

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        vp = self.viewport()
        if self._component_at(event.pos()):
            vp.setCursor(QtCore.Qt.PointingHandCursor)
        else:
            vp.setCursor(QtCore.Qt.IBeamCursor)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() != QtCore.Qt.LeftButton:
            return
        # ドラッグでテキスト選択された場合は Maya 選択を発火しない
        if self.textCursor().hasSelection():
            return
        comp = self._component_at(event.pos())
        if comp:
            self.componentClicked.emit(comp)


# ============================================================
# ツールボタン（名前ラベルを内包）
# ============================================================
class _ToolButton(_DoubleClickButton):
    """名前ラベルを内包するダブルクリック対応ボタン。
    QPushButton 自体の text は使わず、子 QLabel をマウス透過で配置する。"""
    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setMinimumWidth(1)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(0)

        self._name_lbl = QtWidgets.QLabel("")
        self._name_lbl.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self._name_lbl.setStyleSheet("background: transparent; color: #4878a0; font-size: 11px;")
        lay.addWidget(self._name_lbl, 1)

    def setName(self, text, color=None):
        self._name_lbl.setText(text)
        if color:
            self._name_lbl.setStyleSheet(
                f"background: transparent; color: {color}; font-size: 11px;"
            )


# ============================================================
# カテゴリーヘッダー（折り畳み可能 + 件数バッジ）
# ============================================================
class _CategoryHeader(QtWidgets.QWidget):
    """カテゴリ名・矢印・件数バッジを表示するクリック可能ヘッダー"""
    clicked = QtCore.Signal()

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setObjectName("catHeader")
        self.setStyleSheet(
            "QWidget#catHeader { border-bottom: 1px solid #142030; background: transparent; }"
        )
        self.setFixedHeight(26)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 3)
        lay.setSpacing(5)

        self._arrow_lbl = QtWidgets.QLabel("▾")
        self._arrow_lbl.setStyleSheet(
            "color: #2a5070; font-size: 9px; background: transparent;"
        )
        self._arrow_lbl.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        self._name_lbl = QtWidgets.QLabel(name.upper())
        self._name_lbl.setStyleSheet(
            "color: #3a6888; font-size: 10px; background: transparent;"
            " letter-spacing: 1px; font-weight: 600;"
        )
        self._name_lbl.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        self._badge_lbl = QtWidgets.QLabel("")
        self._badge_lbl.setStyleSheet(
            "background: #3a1010; color: #e05858; border-radius: 3px;"
            " padding: 1px 6px; font-size: 10px;"
        )
        self._badge_lbl.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self._badge_lbl.setVisible(False)

        lay.addWidget(self._arrow_lbl, 0)
        lay.addWidget(self._name_lbl, 1)
        lay.addWidget(self._badge_lbl, 0)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self._name_lbl.setStyleSheet(
            "color: #5a98c0; font-size: 10px; background: transparent;"
            " letter-spacing: 1px; font-weight: 600;"
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._name_lbl.setStyleSheet(
            "color: #3a6888; font-size: 10px; background: transparent;"
            " letter-spacing: 1px; font-weight: 600;"
        )
        super().leaveEvent(event)

    def setCollapsed(self, collapsed):
        self._collapsed = collapsed
        self._arrow_lbl.setText("▸" if collapsed else "▾")

    def isCollapsed(self):
        return self._collapsed

    def setStatus(self, err_tool_count, all_ok):
        """err_tool_count: エラー状態のツール数（件数ではなくツール数）
        all_ok: カテゴリ内の全ツールが OK 状態なら True → ✓ 表示"""
        if err_tool_count > 0:
            self._badge_lbl.setText(str(err_tool_count))
            self._badge_lbl.setStyleSheet(
                "background: #3a1010; color: #e05858; border-radius: 3px;"
                " padding: 1px 6px; font-size: 10px;"
            )
            self._badge_lbl.setVisible(True)
        elif all_ok:
            self._badge_lbl.setText("✓")
            self._badge_lbl.setStyleSheet(
                "background: transparent; color: #28c880;"
                " padding: 1px 2px; font-size: 11px;"
            )
            self._badge_lbl.setVisible(True)
        else:
            self._badge_lbl.setVisible(False)


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


def load_and_run(folder, script_name, selection=None):
    """スクリプトを取得して exec し、構造化結果または stdout テキストを返す。
    selection=None  : 呼び出し時点の Maya 選択を使用
    selection=[]    : シーン全体を対象（強制全チェック）
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
    background: qlineargradient(x1:0, y1:0, x2:0.4, y2:1, stop:0 #080f1e, stop:1 #04080f);
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #1a3050;
    min-height: 20px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover { background: #244068; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #1a3050;
    min-width: 20px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover { background: #244068; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
QToolTip {
    background-color: #0b1628;
    color: #b8d4ee;
    border: 1px solid #1a3050;
    border-radius: 5px;
    padding: 6px 10px;
    font-size: 12px;
}
"""

    # ツールボタン: 未チェック
    _SS_BTN_UNCHECKED = """
QPushButton {
    background-color: #0f1e34;
    border: 1px solid #1a2e4a;
    border-radius: 6px;
    text-align: left;
}
QPushButton:hover {
    background-color: #122030;
    border: 1px solid #243c58;
}
QPushButton:disabled { background-color: #0a1424; border-color: #14253a; }
"""

    # ツールボタン: OK
    _SS_BTN_OK = """
QPushButton {
    background-color: #061c14;
    border: 1px solid #0a3020;
    border-radius: 6px;
    text-align: left;
}
QPushButton:hover { background-color: #081e16; }
QPushButton:disabled { background-color: #04140e; }
"""

    # ツールボタン: エラー
    _SS_BTN_ERROR = """
QPushButton {
    background-color: #200c0c;
    border: 1px solid #3a1010;
    border-radius: 6px;
    text-align: left;
}
QPushButton:hover { background-color: #240e0e; }
QPushButton:disabled { background-color: #170808; }
"""

    # FIX ボタン
    _SS_BTN_FIX = """
QPushButton {
    background-color: #1e6ac0;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
}
QPushButton:hover    { background-color: #2878d0; }
QPushButton:pressed  { background-color: #1858a8; }
QPushButton:disabled { background-color: #2a3a50; color: #506070; }
"""

    # ALL CHECK ボタン
    _SS_BTN_ALL = """
QPushButton {
    background-color: #0a1e38;
    border: 1px solid rgba(40, 120, 208, 0.53);
    color: #88b8f0;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    padding: 0 10px;
}
QPushButton:hover {
    background-color: #0e2444;
    border: 1px solid rgba(40, 120, 208, 0.8);
}
QPushButton:pressed  { background-color: #08182e; }
QPushButton:disabled {
    background-color: #07172a;
    color: #2a4868;
    border-color: #14283d;
}
"""

    # CHECK ボタン
    _SS_BTN_CHECK = """
QPushButton {
    background-color: #0d2e2a;
    border: 1px solid rgba(62, 207, 190, 0.4);
    color: #3ecfbe;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 500;
    padding: 0 10px;
}
QPushButton:hover {
    background-color: #112e2a;
    border: 1px solid rgba(62, 207, 190, 0.7);
}
QPushButton:pressed  { background-color: #0a2420; }
QPushButton:disabled {
    background-color: #08201d;
    color: #1a4540;
    border-color: #14302c;
}
"""

    # オブジェクトリスト
    _SS_OBJECT_LIST = """
QListWidget {
    background-color: #0b1628;
    color: #b8d4ee;
    border: 1px solid #1a2e4a;
    border-radius: 8px;
    outline: none;
    padding: 4px 0;
    font-size: 12px;
}
QListWidget::item {
    padding: 7px 14px;
    border-left: 3px solid transparent;
}
QListWidget::item:hover { background-color: #0f1e34; }
QListWidget::item:selected {
    background-color: #142440;
    color: #3ecfbe;
    border-left: 3px solid #3ecfbe;
}
"""

    # 詳細ビュー
    _SS_DETAIL_VIEW = """
QTextEdit {
    background-color: #0b1628;
    color: #b8d4ee;
    border: 1px solid #1a2e4a;
    border-radius: 8px;
    padding: 12px 14px;
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
    selection-background-color: #142440;
    selection-color: #3ecfbe;
}
"""

    # パネル上部のタイトル（Objects / Info）メインラベル
    _SS_PANEL_TITLE_MAIN = """
QLabel {
    color: #88b8f0;
    font-size: 12px;
    font-weight: bold;
    background: transparent;
}
"""

    # パネル上部タイトルのサブラベル（Objects 右下のツール名や進捗）
    _SS_PANEL_TITLE_SUB = """
QLabel {
    color: #3a6888;
    font-size: 10px;
    font-weight: normal;
    background: transparent;
}
"""

    # 左パネル外枠
    _SS_LEFT_PANEL = """
QFrame#leftPanel {
    background-color: #0b1628;
    border: 1px solid #1a2e4a;
    border-radius: 8px;
}
"""

    # ステータスバー
    _SS_STATUS_BAR = """
QFrame#statusBar {
    background-color: #0b1628;
    border-top: 1px solid #1a2e4a;
}
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
        self.resize(600, 650)
        self.setStyleSheet(self._SS_DIALOG)

        # 状態管理
        self._folder_states = {}   # folder -> _S_*
        self._folder_counts = {}   # folder -> int

        # ウィジェット参照
        self._check_btns = {}
        self._fix_btns   = {}
        self.has_fix_script = {}

        # 右パネル
        self.object_to_details = {}
        self._last_check_results = {}  # folder -> obj_to_details（FIX 前の自動選択に使用）

        # フォルダ一覧
        self.folders = []

        # ツールチップ即時表示フィルター（全ボタン共有）
        self._tooltip_filter = _InstantTooltipFilter(self)

        # ALL CHECK / CHECK 実行フラグ
        self._all_check_running   = False
        self._all_check_index     = 0
        self._all_check_summary   = []
        self._all_check_selection = []   # [] = 全体, [...] = 選択範囲

        self._build_ui()
        self._load_folders()

    # ----------------------------------------------------------
    # UI 構築
    # ----------------------------------------------------------
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- ボディ（左パネル + 右パネル）----
        body = QtWidgets.QWidget()
        body.setStyleSheet("background: transparent;")
        body_lay = QtWidgets.QHBoxLayout(body)
        body_lay.setContentsMargins(10, 6, 10, 10)
        body_lay.setSpacing(6)

        # ---- 左カラム（CHECK/ALL CHECK + 左パネル）----
        # 右パネルの list_container（タイトル + object_list）と同じ構造で、
        # ボタンは枠（leftPanel）の外側に配置する
        left_container = QtWidgets.QWidget()
        left_container.setStyleSheet("background: transparent;")
        left_container.setFixedWidth(LEFT_PANEL_W)
        left_container_lay = QtWidgets.QVBoxLayout(left_container)
        left_container_lay.setContentsMargins(0, 0, 0, 0)
        left_container_lay.setSpacing(6)

        # 上部: CHECK / ALL CHECK ボタン（枠外）
        top_btn_w = QtWidgets.QWidget()
        top_btn_w.setStyleSheet("background: transparent;")
        top_btn_lay = QtWidgets.QHBoxLayout(top_btn_w)
        top_btn_lay.setContentsMargins(0, 0, 0, 0)
        top_btn_lay.setSpacing(6)

        # ボタンの縦幅は object_list_title と同じ高さに合わせる
        self.check_btn = QtWidgets.QPushButton("CHECK")
        self.check_btn.setFixedHeight(TOP_BAR_H)
        self.check_btn.setStyleSheet(self._SS_BTN_CHECK)
        self.check_btn.clicked.connect(self.start_check)
        self.check_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.check_btn.setMinimumWidth(1)

        self.all_check_btn = QtWidgets.QPushButton("ALL CHECK")
        self.all_check_btn.setFixedHeight(TOP_BAR_H)
        self.all_check_btn.setStyleSheet(self._SS_BTN_ALL)
        self.all_check_btn.clicked.connect(self.start_all_check)
        self.all_check_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.all_check_btn.setMinimumWidth(1)

        top_btn_lay.addWidget(self.check_btn)
        top_btn_lay.addWidget(self.all_check_btn)

        # 左パネル本体（角丸枠 + ツール一覧）
        left_panel = QtWidgets.QFrame()
        left_panel.setObjectName("leftPanel")
        left_panel.setStyleSheet(self._SS_LEFT_PANEL)
        left_lay = QtWidgets.QVBoxLayout(left_panel)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(0)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            " QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        left_inner = QtWidgets.QWidget()
        left_inner.setStyleSheet("background: transparent;")
        self.rows_layout = QtWidgets.QVBoxLayout(left_inner)
        self.rows_layout.setContentsMargins(7, 0, 7, 7)
        self.rows_layout.setSpacing(3)
        scroll.setWidget(left_inner)
        self.left_scroll = scroll
        self.left_inner  = left_inner
        left_lay.addWidget(scroll, 1)

        left_container_lay.addWidget(top_btn_w)
        left_container_lay.addWidget(left_panel, 1)

        body_lay.addWidget(left_container)

        # ---- 右パネル（オブジェクトリスト + 詳細ビュー）----
        right_w = QtWidgets.QWidget()
        right_w.setStyleSheet("background: transparent;")
        right_lay = QtWidgets.QHBoxLayout(right_w)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(6)

        # オブジェクトリスト + 上部の "Objects" タイトル（メイン + サブラベル）
        list_container = QtWidgets.QWidget()
        list_container.setStyleSheet("background: transparent;")
        list_lay = QtWidgets.QVBoxLayout(list_container)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(6)

        obj_title_w = QtWidgets.QWidget()
        obj_title_w.setStyleSheet("background: transparent;")
        obj_title_w.setFixedHeight(TOP_BAR_H)
        obj_title_lay = QtWidgets.QHBoxLayout(obj_title_w)
        obj_title_lay.setContentsMargins(8, 0, 8, 0)
        obj_title_lay.setSpacing(6)

        obj_title_main = QtWidgets.QLabel("Objects")
        obj_title_main.setStyleSheet(self._SS_PANEL_TITLE_MAIN)
        self.object_list_title_sub = QtWidgets.QLabel("")
        self.object_list_title_sub.setStyleSheet(self._SS_PANEL_TITLE_SUB)
        self.object_list_title_sub.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        obj_title_lay.addWidget(obj_title_main)
        obj_title_lay.addStretch(1)
        obj_title_lay.addWidget(self.object_list_title_sub)
        # 既存呼び出しとの互換のため container も保持
        self.object_list_title = obj_title_w

        self.object_list = QtWidgets.QListWidget()
        self.object_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.object_list.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.object_list.setStyleSheet(self._SS_OBJECT_LIST)

        list_lay.addWidget(obj_title_w)
        list_lay.addWidget(self.object_list, 1)

        # 詳細ビュー + 上部の "Info" タイトル
        detail_container = QtWidgets.QWidget()
        detail_container.setStyleSheet("background: transparent;")
        detail_lay = QtWidgets.QVBoxLayout(detail_container)
        detail_lay.setContentsMargins(0, 0, 0, 0)
        detail_lay.setSpacing(6)

        info_title_w = QtWidgets.QWidget()
        info_title_w.setStyleSheet("background: transparent;")
        info_title_w.setFixedHeight(TOP_BAR_H)
        info_title_lay = QtWidgets.QHBoxLayout(info_title_w)
        info_title_lay.setContentsMargins(8, 0, 8, 0)
        info_title_lay.setSpacing(6)
        info_title_main = QtWidgets.QLabel("Info")
        info_title_main.setStyleSheet(self._SS_PANEL_TITLE_MAIN)
        info_title_lay.addWidget(info_title_main)
        info_title_lay.addStretch(1)

        self.detail_view = _ComponentTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.detail_view.setStyleSheet(self._SS_DETAIL_VIEW)
        self.detail_view.componentClicked.connect(self._on_detail_component_clicked)

        detail_lay.addWidget(info_title_w)
        detail_lay.addWidget(self.detail_view, 1)

        # HTML mockup の比率: 37% / 63%
        right_lay.addWidget(list_container, 37)
        right_lay.addWidget(detail_container, 63)

        self.object_list.currentItemChanged.connect(self.on_object_selected)
        self.object_list.itemClicked.connect(self.on_object_clicked)

        body_lay.addWidget(right_w, 1)
        root.addWidget(body, 1)

        # ---- ステータスバー ----
        status = QtWidgets.QFrame()
        status.setObjectName("statusBar")
        status.setStyleSheet(self._SS_STATUS_BAR)
        status.setFixedHeight(30)
        status_lay = QtWidgets.QHBoxLayout(status)
        status_lay.setContentsMargins(16, 5, 16, 5)
        status_lay.setSpacing(20)

        _lbl_ss = "font-size: 11px; background: transparent;"
        self._lbl_error     = QtWidgets.QLabel("✗  0件エラー")
        self._lbl_ok        = QtWidgets.QLabel("✓  0件 OK")
        self._lbl_unchecked = QtWidgets.QLabel("○  0件 未チェック")
        self._lbl_error.setStyleSheet(f"color: #e05858; {_lbl_ss}")
        self._lbl_ok.setStyleSheet(f"color: #28c880; {_lbl_ss}")
        self._lbl_unchecked.setStyleSheet(f"color: #4878a0; {_lbl_ss}")
        for lbl in (self._lbl_error, self._lbl_ok, self._lbl_unchecked):
            lbl.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
            status_lay.addWidget(lbl)
        status_lay.addStretch()

        ver_lbl = QtWidgets.QLabel(f"v{LAUNCHER_VERSION}")
        ver_lbl.setStyleSheet("color: #263c58; font-size: 10px; background: transparent;")
        ver_lbl.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
        status_lay.addWidget(ver_lbl)
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
        self._folder_titles     = {}
        self._folder_categories = {}
        self._category_widgets  = {}   # cat_name -> {"header", "rows": [...], "folders": [...]}

        last_cat = None
        for entry in manifest:
            folder = entry["folder"]
            title  = entry.get("title", folder)
            desc   = entry.get("description", "")
            ver    = entry.get("version", "")
            cat    = entry.get("category", "Other")

            self._folder_states[folder]     = _S_UNCHECKED
            self._folder_counts[folder]     = 0
            self.has_fix_script[folder]     = entry.get("has_fix", False)
            self._folder_titles[folder]     = title
            self._folder_categories[folder] = cat

            # カテゴリヘッダー（カテゴリが変わったタイミングで挿入）
            if cat != last_cat:
                last_cat = cat
                header = _CategoryHeader(cat)
                header.clicked.connect(lambda c=cat: self._toggle_category(c))
                self.rows_layout.addWidget(header)
                self._category_widgets[cat] = {"header": header, "rows": [], "folders": []}

            # ツール 1 行（ボタン + FIX）を QWidget で包む（折り畳み制御のため）
            row_w = QtWidgets.QWidget()
            row_w.setStyleSheet("background: transparent;")
            row_lay = QtWidgets.QHBoxLayout(row_w)
            row_lay.setSpacing(4)
            row_lay.setContentsMargins(0, 0, 0, 0)

            btn = _ToolButton()
            btn.setFixedHeight(BTN_H)
            btn.setStyleSheet(self._SS_BTN_UNCHECKED)
            btn.setName(f"○  {title}", "#4878a0")
            btn.singleClicked.connect(lambda f=folder: self._show_last_results(f))
            btn.doubleClicked.connect(lambda f=folder: self.run_check(f, show_details=True))

            if title or desc:
                meta_parts = []
                if cat:
                    meta_parts.append(f"<span style='color:#7aa3d0;'>{cat}</span>")
                if ver:
                    meta_parts.append(f"<span style='color:#6a89a8;'>v{ver}</span>")
                meta_html = (
                    f"<td align='right' valign='bottom'>"
                    f"<span style='font-size:9px;'>{'  '.join(meta_parts)}</span></td>"
                    if meta_parts else ""
                )
                btn.setToolTip(
                    f"<table width='100%' cellspacing='0' cellpadding='0'><tr>"
                    f"<td><b style='font-size:13px;'>{title}</b></td>"
                    f"{meta_html}"
                    f"</tr></table>"
                    f"<hr style='border:1px solid #1a3050; margin:4px 0;'>"
                    f"<span style='line-height:1.6;'>{desc}</span>"
                )
                btn.installEventFilter(self._tooltip_filter)
            row_lay.addWidget(btn)
            self._check_btns[folder] = btn

            # FIX ボタン（has_fix=true のツール・エラー時のみ表示）
            fix_btn = QtWidgets.QPushButton("FIX")
            fix_btn.setFixedWidth(FIX_W)
            fix_btn.setFixedHeight(BTN_H)
            fix_btn.setStyleSheet(self._SS_BTN_FIX)
            fix_btn.setVisible(False)
            fix_btn.clicked.connect(lambda *_, f=folder: self._run_fix(f))
            row_lay.addWidget(fix_btn)
            self._fix_btns[folder] = fix_btn

            self.rows_layout.addWidget(row_w)
            self._category_widgets[cat]["rows"].append(row_w)
            self._category_widgets[cat]["folders"].append(folder)

        self.rows_layout.addStretch()

        # 起動時は全カテゴリ折り畳み状態
        for info in self._category_widgets.values():
            info["header"].setCollapsed(True)
            for row in info["rows"]:
                row.setVisible(False)

        self._update_status_bar()

    # ----------------------------------------------------------
    # カテゴリ折り畳み / バッジ
    # ----------------------------------------------------------
    def _toggle_category(self, cat):
        info = self._category_widgets.get(cat)
        if not info:
            return
        new_collapsed = not info["header"].isCollapsed()
        info["header"].setCollapsed(new_collapsed)
        for row in info["rows"]:
            row.setVisible(not new_collapsed)

    def _update_category_badge(self, cat):
        info = self._category_widgets.get(cat)
        if not info:
            return
        folders = info["folders"]
        err_tool_count = sum(
            1 for f in folders if self._folder_states.get(f) == _S_ERROR
        )
        all_ok = (
            len(folders) > 0
            and all(self._folder_states.get(f) == _S_OK for f in folders)
        )
        info["header"].setStatus(err_tool_count, all_ok)

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

        title = self._folder_titles.get(folder, folder)
        if state == _S_UNCHECKED:
            btn.setStyleSheet(self._SS_BTN_UNCHECKED)
            btn.setName(f"○  {title}", "#4878a0")
        elif state == _S_OK:
            btn.setStyleSheet(self._SS_BTN_OK)
            btn.setName(f"✓  {title}", "#28c880")
        else:
            btn.setStyleSheet(self._SS_BTN_ERROR)
            btn.setName(f"✗  {title}", "#e05858")

        if fix:
            show = state == _S_ERROR and self.has_fix_script.get(folder, False)
            fix.setVisible(show)
            fix.setEnabled(show)

        # カテゴリヘッダーのバッジを更新
        cat = self._folder_categories.get(folder)
        if cat:
            self._update_category_badge(cat)

    def _update_status_bar(self):
        n_err = sum(1 for s in self._folder_states.values() if s == _S_ERROR)
        n_ok  = sum(1 for s in self._folder_states.values() if s == _S_OK)
        n_unc = sum(1 for s in self._folder_states.values() if s == _S_UNCHECKED)

        self._lbl_error.setText(f"✗  {n_err}件エラー")
        self._lbl_ok.setText(f"✓  {n_ok}件 OK")
        self._lbl_unchecked.setText(f"○  {n_unc}件 未チェック")

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

    def _on_detail_component_clicked(self, comp):
        """詳細ビュー内のコンポーネント文字列がクリックされたら Maya で選択する"""
        if not cmds:
            return
        # フル形式 (xxx.vtx[...]) ならそのまま、コンポーネント指定のみなら現在選択オブジェクトと結合
        if "." in comp:
            target = comp
        else:
            current = self.object_list.currentItem()
            if not current:
                return
            key = current.data(QtCore.Qt.UserRole)
            if not key or key in self._SKIP_SELECT_KEYS:
                return
            target = f"{key}.{comp}"
        try:
            if cmds.objExists(target):
                cmds.select(target, r=True)
        except Exception:
            pass

    def on_object_selected(self, current, previous):
        self.detail_view.clear()
        if not current:
            return
        key = current.data(QtCore.Qt.UserRole)
        if not key:
            return
        details = self.object_to_details.get(key, [])
        if details:
            self.detail_view.setHtml(self._format_details_html(details))
        self._apply_maya_selection_for_key(key, details)

    @staticmethod
    def _wrap_components(escaped_text):
        """エスケープ済みテキスト内の Maya コンポーネント文字列をボタン風 span で包む"""
        return _COMPONENT_PATTERN.sub(
            lambda m: (
                f"<span style='background:#14243c; color:#88b8f0;"
                f" border: 1px solid #1e3554;"
                f" border-radius:3px; padding:0 4px;'>{m.group(0)}</span>"
            ),
            escaped_text,
        )

    @classmethod
    def _format_details_html(cls, details):
        """details リストを見やすい HTML に整形する。
        - 1 行目（message）: 強調見出し
        - ⚠ で始まる行: 警告色（アンバー）
        - インデント行（先頭スペース2文字以上）: モノスペースでサンプル/座標を整列表示
        - "key: value" 形式: ラベルと値を色分け
        - その他: 通常テキスト
        - Maya コンポーネント（vtx[..] / f[..] 等）は pill 状にスタイリング → クリックで Maya 選択
        """
        if not details:
            return ""
        wrap = cls._wrap_components
        out = []
        for i, raw in enumerate(details):
            text = html.escape(str(raw))
            if i == 0:
                out.append(
                    f"<div style='font-weight:bold; color:#7aa3d0;"
                    f" font-size:13px; margin-bottom:8px;'>{wrap(text)}</div>"
                )
                continue
            stripped = str(raw).lstrip()
            leading = len(str(raw)) - len(stripped)
            if stripped.startswith("⚠"):
                out.append(
                    f"<div style='color:#e0b060; padding:1px 0;'>{wrap(text)}</div>"
                )
                continue
            if leading >= 2:
                indent_px = leading * 4
                out.append(
                    f"<div style='font-family:Consolas,monospace; color:#a0c4e0;"
                    f" padding:1px 0 1px {indent_px}px; white-space:pre;'>"
                    f"{wrap(html.escape(stripped))}</div>"
                )
                continue
            if ": " in text:
                k, _, v = text.partition(": ")
                out.append(
                    f"<div style='padding:1px 0;'>"
                    f"<span style='color:#7a9aae;'>{k}:</span> "
                    f"<span style='color:#ccddef; font-family:Consolas,monospace;'>{wrap(v)}</span>"
                    f"</div>"
                )
                continue
            out.append(
                f"<div style='padding:1px 0; color:#ccddef;'>{wrap(text)}</div>"
            )
        return "".join(out)

    @staticmethod
    def _disambiguate_keys(keys):
        """
        long path のリストから「最小限で一意になる表示名」へのマップを返す。
        例:
          ["|grp_A|pCube1", "|grp_B|pCube1", "animCurveTA1"]
          → {"|grp_A|pCube1": "grp_A | pCube1",
              "|grp_B|pCube1": "grp_B | pCube1",
              "animCurveTA1":   "animCurveTA1"}
        """
        result = {}
        for path in keys:
            parts = path.lstrip("|").split("|")
            for n in range(1, len(parts) + 1):
                suffix = "|" + "|".join(parts[-n:])
                # 他のパスがこの suffix で終わるなら衝突 → 階層を増やす
                collide = any(
                    other != path and other.endswith(suffix)
                    for other in keys
                )
                if not collide:
                    result[path] = " | ".join(parts[-n:])
                    break
            else:
                result[path] = path
        return result

    def _set_object_list_title(self, text):
        """Objects タイトル右側のサブラベル（ツール名 / 進捗）を更新"""
        if hasattr(self, "object_list_title_sub"):
            self.object_list_title_sub.setText(text or "")

    def set_object_results(self, obj_to_details):
        self.object_to_details = obj_to_details or {}
        self.object_list.clear()
        keys = list(self.object_to_details.keys())
        display_map = self._disambiguate_keys(keys)
        # 表示名でソート（同名衝突時は階層名が頭に付くので自然な並び）
        keys.sort(key=lambda k: display_map.get(k, k))
        for key in keys:
            display = display_map.get(key, key)
            item = QtWidgets.QListWidgetItem(display)
            item.setData(QtCore.Qt.UserRole, key)  # 内部キーは long path のまま
            self.object_list.addItem(item)
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
    def run_check(self, folder, show_details=True, selection=None):
        structured, text = load_and_run(folder, f"{folder}_check.py", selection=selection)

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
            self._set_object_list_title(self._folder_titles.get(folder, folder))
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

    def _show_last_results(self, folder):
        """シングルクリック時：直近のチェック結果を右パネルに表示する（再チェックは行わない）"""
        cached = self._last_check_results.get(folder)
        self._set_object_list_title(self._folder_titles.get(folder, folder))
        self.set_object_results(cached if cached is not None else {})

    # ----------------------------------------------------------
    # FIX 実行
    # ----------------------------------------------------------
    def _run_fix(self, folder):
        self._select_check_results(folder)  # チェック結果オブジェクトを事前に Maya 選択
        self._set_object_list_title(self._folder_titles.get(folder, folder))
        structured, text = load_and_run(folder, f"{folder}_fix.py", selection=[])
        if structured is not None:
            self.set_object_results(self.normalize_structured(structured))
        else:
            self.set_object_results({"stdout": [text]} if text.strip() else {})
        # fix 後に自動 re-check
        QtCore.QTimer.singleShot(0, lambda: self.run_check(folder, show_details=True))

    # ----------------------------------------------------------
    # ALL CHECK
    # ----------------------------------------------------------
    def start_check(self):
        """選択オブジェクトのみを対象に全ツールをチェック"""
        if self._all_check_running:
            return
        sel = (cmds.ls(sl=True, long=True) or []) if cmds else []
        if not sel:
            self.detail_view.setPlainText("オブジェクトを選択してください")
            return
        self._all_check_running   = True
        self._all_check_index     = 0
        self._all_check_summary   = []
        self._all_check_selection = sel
        self._set_busy(True)
        self._set_object_list_title("CHECK")
        self.set_object_results({})
        self.detail_view.setPlainText("CHECK 実行中...")
        QtCore.QTimer.singleShot(0, self._step_all_check)

    def start_all_check(self):
        if self._all_check_running:
            return
        self._all_check_running   = True
        self._all_check_index     = 0
        self._all_check_summary   = []
        self._all_check_selection = []   # 空リスト = シーン全体
        self._set_busy(True)
        self._set_object_list_title("ALL CHECK")
        self.set_object_results({})
        self.detail_view.setPlainText("ALL CHECK 実行中...")
        QtCore.QTimer.singleShot(0, self._step_all_check)

    def _step_all_check(self):
        if self._all_check_index >= len(self.folders):
            self._finish_all_check()
            return
        folder = self.folders[self._all_check_index]
        title  = self._folder_titles.get(folder, folder)
        total  = len(self.folders)
        current = self._all_check_index + 1

        # 進捗を可視化（実行直前に表示更新）
        header_label = "CHECK" if self._all_check_selection else "ALL CHECK"
        self._set_object_list_title(f"{header_label} [{current}/{total}]")
        lines = [f"{header_label} 実行中...  [{current}/{total}]", ""]
        for status, f in self._all_check_summary:
            mark = "✓" if status == "OK" else "✗"
            lines.append(f"  {mark}  {self._folder_titles.get(f, f)}")
        lines.append(f"  →  {title}")
        self.detail_view.setPlainText("\n".join(lines))
        QtWidgets.QApplication.processEvents()

        self._all_check_index += 1
        has_issue = self.run_check(folder, show_details=False, selection=self._all_check_selection)
        self._all_check_summary.append(("ERROR" if has_issue else "OK", folder))
        QtCore.QTimer.singleShot(0, self._step_all_check)

    def _finish_all_check(self):
        self._all_check_running = False
        self._set_busy(False)
        header_label = "CHECK" if self._all_check_selection else "ALL CHECK"
        header = f"{header_label} 結果"
        lines = [header, ""]
        for status, folder in self._all_check_summary:
            lines.append(f"  {status} : {folder}")
        self.set_object_results({"ALL_CHECK": lines})
        self._set_object_list_title(header_label)
        self.detail_view.setPlainText("\n".join(lines))

    # ----------------------------------------------------------
    # ビジー状態の一括制御
    # ----------------------------------------------------------
    def _set_busy(self, busy):
        """ALL CHECK / CHECK 実行中のボタン一括制御"""
        self.check_btn.setEnabled(not busy)
        self.check_btn.setText("…" if busy else "CHECK")
        self.all_check_btn.setEnabled(not busy)
        self.all_check_btn.setText("…" if busy else "ALL CHECK")

        for btn in self._check_btns.values():
            btn.setEnabled(not busy)
        for f, fix_btn in self._fix_btns.items():
            if busy:
                fix_btn.setEnabled(False)
            else:
                show = (
                    self._folder_states.get(f) == _S_ERROR
                    and self.has_fix_script.get(f, False)
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
