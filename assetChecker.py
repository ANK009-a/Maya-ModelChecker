# -*- coding: utf-8 -*-
import re
import html
import threading
import time
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
# 設定
# ============================================================
GITHUB_RAW          = "https://raw.githubusercontent.com/ANK009-a/Maya-ModelChecker/main"
WINDOW_OBJECT_NAME  = "assetChecker"
LAUNCHER_VERSION    = "1.19.0"
LEFT_PANEL_W = 204  # 左パネル全体の幅
BTN_H        = 28   # ツールボタンの高さ
TOP_BAR_H    = 26   # 枠外トップバーの高さ（CHECK/ALL CHECK / object_list_title / Info）
FIX_W        = 38   # FIX ボタンの幅

# bootstrap でリモートロードするヘルパーモジュール
_BOOTSTRAP_MODULES = ("_styles", "_widgets", "_loader", "_formatter", "_results")


# ============================================================
# Maya メインウィンドウ取得
# ============================================================
def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


# ============================================================
# ヘルパーモジュールの bootstrap
#   _util.py と同じ仕組み（fetch → exec → sys.modules 登録）で
#   _styles / _widgets / _loader / _formatter を読み込む。
#   assetChecker.py 再 exec のたびに最新版を取り直す。
# ============================================================
def _bootstrap_fetch(rel_path):
    url = f"{GITHUB_RAW}/{rel_path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"[assetChecker] 取得失敗: {url}\n{e}")
        return None


def _bootstrap_modules():
    # 旧モジュール登録を除去（再起動時に最新版を取り直すため）
    for name in _BOOTSTRAP_MODULES:
        sys.modules.pop(name, None)
    sys.modules.pop("_util", None)

    for name in _BOOTSTRAP_MODULES:
        code = _bootstrap_fetch(f"tools/{name}.py")
        if code is None:
            raise RuntimeError(f"{name}.py の取得に失敗しました")
        mod = types.ModuleType(name)
        exec(compile(code, f"{name}.py", "exec"), mod.__dict__)
        sys.modules[name] = mod


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
# bootstrap 実行 → import
# ============================================================
_bootstrap_modules()

import _styles
import _widgets
import _loader
import _formatter
import _results  # noqa: F401  ← check スクリプトが `from _results import CheckResult` で参照

_loader.configure(GITHUB_RAW)


# ============================================================
# 入力ブロック用イベントフィルタ
#   ALL CHECK / CHECK 実行中、assetChecker ダイアログ以外の入力を全部吸収する
#   （Maya のシーン操作を防いで cmds スレッド衝突を回避）
# ============================================================
class _MayaInputBlocker(QtCore.QObject):
    _BLOCKED = (
        QtCore.QEvent.MouseButtonPress,
        QtCore.QEvent.MouseButtonRelease,
        QtCore.QEvent.MouseButtonDblClick,
        QtCore.QEvent.KeyPress,
        QtCore.QEvent.KeyRelease,
        QtCore.QEvent.Wheel,
        QtCore.QEvent.ShortcutOverride,
    )

    def __init__(self, allow_widget):
        super().__init__(allow_widget)
        self._allow = allow_widget

    def eventFilter(self, obj, event):
        et = event.type()
        # ESC はフォーカス位置によらず確実に拾うため、フィルタ層で直接キャンセル要求にする
        if et == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
            if getattr(self._allow, "_all_check_running", False):
                self._allow._cancel_requested = True
                return True   # ESC を消費してこれ以上伝播させない
        if et not in self._BLOCKED:
            return False
        # obj が allow_widget またはその子孫なら通す、それ以外はブロック
        target = obj
        while target is not None:
            if target is self._allow:
                return False
            try:
                target = target.parent()
            except Exception:
                break
        return True


# ============================================================
# UI クラス
# ============================================================
class assetChecker(QtWidgets.QDialog):

    # Maya 選択をスキップする疑似キー
    _SKIP_SELECT_KEYS = frozenset({
        "stdout", "ALL_CHECK",
        "(summary)", "(result)", "(none)", "(info)",
    })

    # 起動時の先読みキャッシュ進捗（done, failed, total）
    _prefetch_progress = QtCore.Signal(int, int, int)

    # ----------------------------------------------------------
    def __init__(self, parent=maya_main_window()):
        super().__init__(parent)
        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle("assetChecker")
        self.resize(600, 650)
        self.setStyleSheet(_styles.SS_DIALOG)

        # 状態管理
        self._folder_states = {}   # folder -> _styles.S_*
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
        self._tooltip_filter = _widgets.InstantTooltipFilter(self)

        # ALL CHECK / CHECK 実行フラグ
        self._all_check_running    = False
        self._all_check_index      = 0
        self._all_check_summary    = []
        self._all_check_selection  = []   # [] = 全体, [...] = 選択範囲
        self._active_check_folders = []   # 現在実行中のフォルダ列（カテゴリ単位 CHECK 用）
        self._active_check_label   = ""   # 表示用ラベル（"ALL CHECK" / "Transform 系 CHECK" 等）
        self._cancel_requested     = False
        self._input_blocker        = None

        # Maya ↔ object_list 双方向選択同期
        self._maya_selection_job          = None
        self._syncing_selection           = False  # 同期処理中の再入防止
        self._suppress_maya_selection_sync = False  # Qt → Maya 直後の Maya 側イベント抑制

        self._prefetch_progress.connect(self._on_prefetch_progress)

        self._build_ui()
        self._load_folders()
        self._prefetch_scripts()
        self._install_maya_selection_job()

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
        left_container = QtWidgets.QWidget()
        left_container.setStyleSheet("background: transparent;")
        left_container.setFixedWidth(LEFT_PANEL_W)
        left_container_lay = QtWidgets.QVBoxLayout(left_container)
        left_container_lay.setContentsMargins(0, 0, 0, 0)
        left_container_lay.setSpacing(6)

        # 上部: "Tools" タイトル + キャッシュ状況（右パネルの "Objects" と同じ枠外配置）
        tools_title_w = QtWidgets.QWidget()
        tools_title_w.setStyleSheet("background: transparent;")
        tools_title_w.setFixedHeight(TOP_BAR_H)
        tools_title_lay = QtWidgets.QHBoxLayout(tools_title_w)
        tools_title_lay.setContentsMargins(8, 0, 8, 0)
        tools_title_lay.setSpacing(6)

        tools_title_main = QtWidgets.QLabel("Tools")
        tools_title_main.setStyleSheet(_styles.SS_PANEL_TITLE_MAIN)

        self._cache_status_label = QtWidgets.QLabel("")
        self._cache_status_label.setStyleSheet("background: transparent;")
        self._cache_status_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        tools_title_lay.addWidget(tools_title_main)
        tools_title_lay.addWidget(self._cache_status_label, 1)

        # 下部: CHECK / ALL CHECK ボタン
        bottom_btn_w = QtWidgets.QWidget()
        bottom_btn_w.setStyleSheet("background: transparent;")
        bottom_btn_lay = QtWidgets.QHBoxLayout(bottom_btn_w)
        bottom_btn_lay.setContentsMargins(0, 0, 0, 0)
        bottom_btn_lay.setSpacing(6)

        self.check_btn = QtWidgets.QPushButton("CHECK")
        self.check_btn.setFixedHeight(TOP_BAR_H)
        self.check_btn.setStyleSheet(_styles.SS_BTN_CHECK)
        self.check_btn.clicked.connect(self.start_check)
        self.check_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.check_btn.setMinimumWidth(1)

        self.all_check_btn = QtWidgets.QPushButton("ALL CHECK")
        self.all_check_btn.setFixedHeight(TOP_BAR_H)
        self.all_check_btn.setStyleSheet(_styles.SS_BTN_ALL)
        self.all_check_btn.clicked.connect(self.start_all_check)
        self.all_check_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.all_check_btn.setMinimumWidth(1)

        bottom_btn_lay.addWidget(self.check_btn)
        bottom_btn_lay.addWidget(self.all_check_btn)

        # 左パネル本体（角丸枠 + ツール一覧）
        left_panel = QtWidgets.QFrame()
        left_panel.setObjectName("leftPanel")
        left_panel.setStyleSheet(_styles.SS_LEFT_PANEL)
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

        left_container_lay.addWidget(tools_title_w)
        left_container_lay.addWidget(left_panel, 1)
        left_container_lay.addWidget(bottom_btn_w)

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
        obj_title_main.setStyleSheet(_styles.SS_PANEL_TITLE_MAIN)
        self.object_list_title_sub = _widgets.ElidedLabel("")
        self.object_list_title_sub.setStyleSheet(_styles.SS_PANEL_TITLE_SUB)
        self.object_list_title_sub.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        obj_title_lay.addWidget(obj_title_main)
        obj_title_lay.addWidget(self.object_list_title_sub, 1)
        self.object_list_title = obj_title_w

        self.object_list = QtWidgets.QListWidget()
        self.object_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.object_list.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.object_list.setStyleSheet(_styles.SS_OBJECT_LIST)

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
        info_title_main.setStyleSheet(_styles.SS_PANEL_TITLE_MAIN)
        info_title_lay.addWidget(info_title_main)
        info_title_lay.addStretch(1)

        self.detail_view = _widgets.ComponentTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.detail_view.setStyleSheet(_styles.SS_DETAIL_VIEW)
        self.detail_view.componentClicked.connect(self._on_detail_component_clicked)

        detail_lay.addWidget(info_title_w)
        detail_lay.addWidget(self.detail_view, 1)

        # HTML mockup の比率: 37% / 63%
        right_lay.addWidget(list_container, 37)
        right_lay.addWidget(detail_container, 63)

        self.object_list.itemSelectionChanged.connect(self.on_object_selection_changed)

        body_lay.addWidget(right_w, 1)
        root.addWidget(body, 1)

        # ---- ステータスバー ----
        status = QtWidgets.QFrame()
        status.setObjectName("statusBar")
        status.setStyleSheet(_styles.SS_STATUS_BAR)
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
        manifest = _loader.fetch_manifest_index()
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

            self._folder_states[folder]     = _styles.S_UNCHECKED
            self._folder_counts[folder]     = 0
            self.has_fix_script[folder]     = entry.get("has_fix", False)
            self._folder_titles[folder]     = title
            self._folder_categories[folder] = cat

            # カテゴリヘッダー（カテゴリが変わったタイミングで挿入）
            if cat != last_cat:
                last_cat = cat
                header = _widgets.CategoryHeader(cat)
                header.clicked.connect(lambda c=cat: self._toggle_category(c))
                header.refreshClicked.connect(lambda c=cat: self.start_category_check(c))
                self.rows_layout.addWidget(header)
                self._category_widgets[cat] = {"header": header, "rows": [], "folders": []}

            # ツール 1 行（ボタン + FIX）を QWidget で包む（折り畳み制御のため）
            row_w = QtWidgets.QWidget()
            row_w.setStyleSheet("background: transparent;")
            row_w.setFixedHeight(BTN_H)
            row_lay = QtWidgets.QHBoxLayout(row_w)
            row_lay.setSpacing(4)
            row_lay.setContentsMargins(0, 0, 0, 0)

            btn = _widgets.ToolButton()
            btn.setFixedHeight(BTN_H)
            btn.setStyleSheet(_styles.SS_BTN_UNCHECKED)
            btn.setName(f"○  {title}", "#4878a0")
            btn.singleClicked.connect(lambda f=folder: self._show_last_results(f))
            btn.doubleClicked.connect(lambda f=folder: self.run_check(f, show_details=True))

            if title or desc:
                self._tooltip_filter.register(btn, title, desc, cat, ver)
            row_lay.addWidget(btn)
            self._check_btns[folder] = btn

            # FIX ボタン（has_fix=true のツール・エラー時のみ表示）
            fix_btn = QtWidgets.QPushButton("FIX")
            fix_btn.setFixedSize(FIX_W, BTN_H)
            fix_btn.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
            fix_btn.setStyleSheet(_styles.SS_BTN_FIX)
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
    # 起動時の先読みキャッシュ
    #   バックグラウンドで全 check / fix スクリプトを取得して
    #   _loader._script_cache に乗せておく。初回 ALL CHECK のネットワーク
    #   待ちを無くし、cmds 表示が最初から見えるようにする。
    # ----------------------------------------------------------
    def _prefetch_scripts(self):
        fetch = getattr(_loader, "fetch_script", None)
        if fetch is None or not self.folders:
            return
        folders = list(self.folders)
        has_fix = dict(self.has_fix_script)
        total = len(folders)

        # 初期状態を即時反映
        self._prefetch_progress.emit(0, 0, total)

        def _do_prefetch():
            done = 0
            failed = 0
            for folder in folders:
                try:
                    fetch(folder, f"{folder}_check.py")
                except Exception:
                    failed += 1
                done += 1
                # シグナル経由でメインスレッドの UI を更新
                self._prefetch_progress.emit(done, failed, total)

                # fix スクリプトは進捗カウント対象外（ベストエフォート）
                if has_fix.get(folder, False):
                    try:
                        fetch(folder, f"{folder}_fix.py")
                    except Exception:
                        pass

        threading.Thread(target=_do_prefetch, daemon=True).start()

    def _on_prefetch_progress(self, done, failed, total):
        """キャッシュ取得進捗をステータスバーに反映"""
        if not hasattr(self, "_cache_status_label"):
            return
        if done < total:
            # 取得中：オレンジ系で進捗テキスト
            self._cache_status_label.setStyleSheet(
                "color: #e0b060; font-size: 10px; background: transparent;"
            )
            self._cache_status_label.setText(f"⟳ 取得中 {done}/{total}")
        elif failed == 0:
            # 完了：緑のドットだけ
            self._cache_status_label.setStyleSheet(
                "color: #28c880; font-size: 13px; background: transparent;"
            )
            self._cache_status_label.setText("●")
            self._cache_status_label.setToolTip(f"Cache ready ({total} scripts)")
        else:
            # 取得失敗あり：赤＋件数
            self._cache_status_label.setStyleSheet(
                "color: #e05858; font-size: 10px; background: transparent;"
            )
            self._cache_status_label.setText(f"● {failed}件失敗")
            self._cache_status_label.setToolTip(
                f"Cache: {total - failed}/{total} loaded ({failed} failed)"
            )

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
            1 for f in folders if self._folder_states.get(f) == _styles.S_ERROR
        )
        all_ok = (
            len(folders) > 0
            and all(self._folder_states.get(f) == _styles.S_OK for f in folders)
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
        if state == _styles.S_UNCHECKED:
            btn.setStyleSheet(_styles.SS_BTN_UNCHECKED)
            btn.setName(f"○  {title}", "#4878a0")
        elif state == _styles.S_OK:
            btn.setStyleSheet(_styles.SS_BTN_OK)
            btn.setName(f"✓  {title}", "#28c880")
        else:
            btn.setStyleSheet(_styles.SS_BTN_ERROR)
            btn.setName(f"✗  {title}", "#e05858")

        if fix:
            show = state == _styles.S_ERROR and self.has_fix_script.get(folder, False)
            fix.setVisible(show)
            fix.setEnabled(show)

        cat = self._folder_categories.get(folder)
        if cat:
            self._update_category_badge(cat)

    def _update_status_bar(self):
        n_err = sum(1 for s in self._folder_states.values() if s == _styles.S_ERROR)
        n_ok  = sum(1 for s in self._folder_states.values() if s == _styles.S_OK)
        n_unc = sum(1 for s in self._folder_states.values() if s == _styles.S_UNCHECKED)

        self._lbl_error.setText(f"✗  {n_err}件エラー")
        self._lbl_ok.setText(f"✓  {n_ok}件 OK")
        self._lbl_unchecked.setText(f"○  {n_unc}件 未チェック")

    # ----------------------------------------------------------
    # Maya 選択ユーティリティ（複数選択対応・双方向同期）
    # ----------------------------------------------------------
    def _selection_targets_for_node(self, node):
        """ノードキー(transform/shape/コンポーネント) → Maya 選択対象 transform 列。
        shape ならその親 transform を返す。同名衝突時は long path を全て返す。"""
        if not cmds:
            return []
        base = str(node).split(".", 1)[0] if node else ""
        if not base:
            return []

        paths = []
        try:
            paths.extend(cmds.ls(base, long=True) or [])
        except Exception:
            pass
        if cmds.objExists(base):
            paths.append(base)

        seen = set()
        result = []
        for path in paths:
            if path in seen or not cmds.objExists(path):
                continue
            seen.add(path)
            try:
                node_type = cmds.nodeType(path)
            except Exception:
                node_type = ""
            if node_type == "transform":
                if path not in result:
                    result.append(path)
                continue
            try:
                parents = cmds.listRelatives(path, parent=True, fullPath=True) or []
            except Exception:
                parents = []
            target = parents[0] if parents else path
            if target not in result:
                result.append(target)
        return result

    def _apply_maya_selection_for_items(self, items):
        """object_list で選択中のアイテム群を Maya 選択に反映"""
        if not cmds or not items:
            return
        targets = []
        seen = set()
        for item in items:
            key = item.data(QtCore.Qt.UserRole)
            if not key or key in self._SKIP_SELECT_KEYS:
                continue
            for target in self._selection_targets_for_node(str(key)):
                if target not in seen:
                    seen.add(target)
                    targets.append(target)
        if not targets:
            return
        try:
            cmds.select(clear=True)
            for target in targets:
                try:
                    cmds.select(target, add=True)
                except Exception:
                    pass
        except Exception:
            pass

    def _matching_object_items_for_maya_selection(self, selection):
        """Maya の選択ノード列 → 対応する object_list のアイテム列"""
        selected_targets = set()
        for node in selection:
            selected_targets.update(self._selection_targets_for_node(node))
        if not selected_targets:
            return []

        matches = []
        for row in range(self.object_list.count()):
            item = self.object_list.item(row)
            key = item.data(QtCore.Qt.UserRole)
            if not key or key in self._SKIP_SELECT_KEYS:
                continue
            if set(self._selection_targets_for_node(key)) & selected_targets:
                matches.append(item)
        return matches

    def _set_object_items_selected_from_maya(self, items):
        """Maya 由来の選択を object_list に反映する（重複除去・最初の項目を current に）"""
        unique_items = []
        seen_keys = set()
        for item in sorted(items, key=lambda x: self.object_list.row(x)):
            key = item.data(QtCore.Qt.UserRole)
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            unique_items.append(item)

        self._syncing_selection = True
        try:
            self.object_list.clearSelection()
            model = self.object_list.selectionModel()
            for item in unique_items:
                index = self.object_list.indexFromItem(item)
                if index.isValid():
                    model.select(index, QtCore.QItemSelectionModel.Select)
            if unique_items:
                first_index = self.object_list.indexFromItem(unique_items[0])
                if first_index.isValid():
                    model.setCurrentIndex(first_index, QtCore.QItemSelectionModel.NoUpdate)
        finally:
            self._syncing_selection = False

        self.object_list.viewport().update()
        self.detail_view.clear()
        details_html = self._format_selected_object_details(unique_items)
        if details_html:
            self.detail_view.setHtml(details_html)

    def _install_maya_selection_job(self):
        if not cmds or self._maya_selection_job is not None:
            return
        try:
            self._maya_selection_job = cmds.scriptJob(
                event=["SelectionChanged", self._on_maya_selection_changed]
            )
        except Exception:
            self._maya_selection_job = None

    def _remove_maya_selection_job(self):
        if not cmds or self._maya_selection_job is None:
            return
        job = self._maya_selection_job
        self._maya_selection_job = None
        try:
            if cmds.scriptJob(exists=job):
                cmds.scriptJob(kill=job, force=True)
        except Exception:
            pass

    def _on_maya_selection_changed(self):
        # 自分自身の同期処理中・ALL CHECK 中・ダイアログ未構築なら何もしない
        if (
            self._syncing_selection
            or self._suppress_maya_selection_sync
            or self._all_check_running
            or not hasattr(self, "object_list")
        ):
            return
        try:
            sel = cmds.ls(sl=True, long=True) or []
        except Exception:
            return
        if sel:
            self._set_object_items_selected_from_maya(
                self._matching_object_items_for_maya_selection(sel)
            )
        elif self.object_list.selectedItems():
            self._set_object_items_selected_from_maya([])

    def _release_maya_selection_sync_suppression(self):
        self._suppress_maya_selection_sync = False

    def _format_selected_object_details(self, items):
        """選択数に応じた詳細 HTML を生成。複数選択時はオブジェクトごとに区切り表示。"""
        if not items:
            return ""
        if len(items) == 1:
            key = items[0].data(QtCore.Qt.UserRole)
            details = self.object_to_details.get(key, [])
            return _formatter.format_details_html(details) if details else ""

        parts = [
            f"<div style='font-family:Consolas,monospace; font-size:11px;"
            f" color:#3ecfbe; margin-bottom:6px;'>"
            f"{len(items)} OBJECTS SELECTED</div>",
            "<div style='font-family:Consolas,monospace; font-size:10px;"
            " color:#1a3050; margin-bottom:8px;'>────────────────────────────</div>",
        ]
        for i, item in enumerate(items):
            key = item.data(QtCore.Qt.UserRole)
            display = item.text()
            details = self.object_to_details.get(key, [])
            if i > 0:
                parts.append(
                    "<div style='font-family:Consolas,monospace; font-size:10px;"
                    " color:#1a3050; margin:10px 0 8px;'>────────────────────────────</div>"
                )
            parts.append(
                f"<div style='font-weight:bold; color:#3ecfbe;"
                f" font-size:12px; margin-bottom:6px;'>{html.escape(display)}</div>"
            )
            if details:
                parts.append(_formatter.format_details_html(details))
        return "".join(parts)

    # ----------------------------------------------------------
    # 右パネル
    # ----------------------------------------------------------
    def _on_detail_component_clicked(self, comp):
        """詳細ビュー内のコンポーネント文字列がクリックされたら Maya で選択する"""
        if not cmds:
            return
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

    def on_object_selection_changed(self):
        """object_list の選択が変わったら Maya 選択と詳細表示を更新する"""
        if self._syncing_selection:
            return
        self.detail_view.clear()
        items = self.object_list.selectedItems()
        if not items:
            return
        details_html = self._format_selected_object_details(items)
        if details_html:
            self.detail_view.setHtml(details_html)

        # Qt → Maya 反映の前後でフラグ管理（直後の Maya イベントを抑制）
        self._suppress_maya_selection_sync = True
        self._syncing_selection = True
        try:
            self._apply_maya_selection_for_items(items)
        finally:
            self._syncing_selection = False
        # SelectionChanged が遅延して飛んでくることがあるので 150ms 抑制
        QtCore.QTimer.singleShot(150, self._release_maya_selection_sync_suppression)

    def _set_object_list_title(self, text):
        """Objects タイトル右側のサブラベル（ツール名 / 進捗）を更新"""
        if hasattr(self, "object_list_title_sub"):
            self.object_list_title_sub.setText(text or "")

    def set_object_results(self, obj_to_details):
        self.object_to_details = obj_to_details or {}
        self.object_list.clear()
        keys = list(self.object_to_details.keys())
        display_map = _formatter.disambiguate_keys(keys)
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

    # ----------------------------------------------------------
    # チェック実行
    # ----------------------------------------------------------
    def run_check(self, folder, show_details=True, selection=None):
        structured, text = _loader.load_and_run(folder, f"{folder}_check.py", selection=selection)
        return self._apply_check_result(folder, structured, text, show_details)

    def _apply_check_result(self, folder, structured, text, show_details):
        """check 結果（structured, text）を UI に反映する。メインスレッドから呼ぶこと。"""
        if structured is not None:
            obj_to_details = _formatter.normalize_structured(structured)
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

        self._set_folder_state(folder, _styles.S_ERROR if has_issue else _styles.S_OK, count)
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
        structured, text = _loader.load_and_run(folder, f"{folder}_fix.py", selection=[])
        if structured is not None:
            self.set_object_results(_formatter.normalize_structured(structured))
        else:
            self.set_object_results({"stdout": [text]} if text.strip() else {})
        # fix 後に自動 re-check
        QtCore.QTimer.singleShot(0, lambda: self.run_check(folder, show_details=True))

    # ----------------------------------------------------------
    # 入力ブロック / キャンセル
    # ----------------------------------------------------------
    def _install_input_block(self):
        if self._input_blocker is None:
            self._input_blocker = _MayaInputBlocker(self)
        try:
            QtWidgets.QApplication.instance().installEventFilter(self._input_blocker)
        except Exception:
            pass

    def _remove_input_block(self):
        if self._input_blocker is not None:
            try:
                QtWidgets.QApplication.instance().removeEventFilter(self._input_blocker)
            except Exception:
                pass

    def keyPressEvent(self, event):
        # ESC は常に吸収する（QDialog の標準 reject() でダイアログが閉じるのを防ぐ）
        # ALL CHECK 中ならキャンセル要求として記録、それ以外は無効キーとして握り潰す
        if event.key() == QtCore.Qt.Key_Escape:
            if self._all_check_running and not self._cancel_requested:
                self._cancel_requested = True
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        # ダイアログ消滅時は確実にブロック解除（ALL CHECK 中なら停止フラグも立てる）
        self._cancel_requested = True
        self._remove_input_block()
        self._remove_maya_selection_job()
        super().closeEvent(event)

    # ----------------------------------------------------------
    # ALL CHECK / CHECK
    # ----------------------------------------------------------
    def _begin_check_sequence(self, folders, selection, label):
        """CHECK / ALL CHECK / カテゴリ CHECK の共通起動処理"""
        if self._all_check_running:
            return False
        folders = list(folders)
        if not folders:
            return False
        self._all_check_running    = True
        self._all_check_index      = 0
        self._all_check_summary    = []
        self._all_check_selection  = selection
        self._active_check_folders = folders
        self._active_check_label   = label
        self._cancel_requested     = False
        self._set_busy(True)
        self._install_input_block()
        self._set_object_list_title(label)
        self.set_object_results({})
        self.detail_view.setPlainText(f"{label} 実行中...")
        QtCore.QTimer.singleShot(0, self._step_all_check)
        return True

    def start_check(self):
        """選択オブジェクトのみを対象に全ツールをチェック"""
        if self._all_check_running:
            return
        sel = (cmds.ls(sl=True, long=True) or []) if cmds else []
        if not sel:
            self.detail_view.setPlainText("オブジェクトを選択してください")
            return
        self._begin_check_sequence(self.folders, sel, "CHECK")

    def start_all_check(self):
        if self._all_check_running:
            return
        self._begin_check_sequence(self.folders, [], "ALL CHECK")

    def start_category_check(self, cat):
        """カテゴリ内ツールだけを対象にチェック。選択があれば選択範囲、なければ全体。"""
        if self._all_check_running:
            return
        info = self._category_widgets.get(cat)
        if not info:
            return
        sel = (cmds.ls(sl=True, long=True) or []) if cmds else []
        label = f"{cat} CHECK" if sel else f"{cat} ALL CHECK"
        self._begin_check_sequence(info.get("folders", []), sel if sel else [], label)

    def _step_all_check(self):
        # ダイアログ消滅後に singleShot が遅れて発火した場合は何もしない
        if not self.isVisible():
            return
        active_folders = self._active_check_folders or self.folders
        if self._cancel_requested or self._all_check_index >= len(active_folders):
            self._finish_all_check()
            return
        folder  = active_folders[self._all_check_index]
        title   = self._folder_titles.get(folder, folder)
        total   = len(active_folders)
        current = self._all_check_index + 1
        header_label = (
            self._active_check_label
            or ("CHECK" if self._all_check_selection else "ALL CHECK")
        )

        # チェック結果と完了フラグを共有する箱
        result_holder = {
            "structured": None,
            "text": "",
            "done": False,
            "error": None,
            "last_cmd": None,            # 直近に整形した cmds 呼び出し
            "last_format_time": 0.0,     # 整形のスロットル管理
        }
        FORMAT_INTERVAL = 0.030  # 30ms 以内の連続呼び出しは整形をスキップ

        def _make_wrapper(name, original, worker_thread):
            # cmds.{name} の呼び出しをワーカースレッド限定で記録するラッパ
            def wrapper(*args, **kwargs):
                try:
                    if threading.current_thread() is worker_thread:
                        now = time.monotonic()
                        if now - result_holder["last_format_time"] >= FORMAT_INTERVAL:
                            result_holder["last_format_time"] = now

                            def _truncate(s):
                                # 長すぎる引数は「先頭...末尾」形式で短縮
                                return s if len(s) <= 40 else s[:15] + "..." + s[-22:]

                            parts = []
                            for a in args:
                                try:
                                    parts.append(_truncate(repr(a)))
                                except Exception:
                                    parts.append("?")
                            for k, v in kwargs.items():
                                try:
                                    parts.append(f"{k}={_truncate(repr(v))}")
                                except Exception:
                                    parts.append(f"{k}=?")
                            result_holder["last_cmd"] = f"cmds.{name}({', '.join(parts)})"
                except Exception:
                    pass
                return original(*args, **kwargs)
            return wrapper

        def _run_check_in_thread():
            worker_thread = threading.current_thread()
            originals = {}
            try:
                # cmds の callable 属性を一時的にラップ
                if cmds is not None:
                    for attr_name in dir(cmds):
                        if attr_name.startswith("_"):
                            continue
                        try:
                            attr = getattr(cmds, attr_name)
                            if callable(attr):
                                originals[attr_name] = attr
                                setattr(cmds, attr_name, _make_wrapper(attr_name, attr, worker_thread))
                        except Exception:
                            pass
                try:
                    structured, text = _loader.load_and_run(
                        folder, f"{folder}_check.py", selection=self._all_check_selection
                    )
                    result_holder["structured"] = structured
                    result_holder["text"] = text
                finally:
                    # cmds を元に戻す
                    for n, orig in originals.items():
                        try:
                            setattr(cmds, n, orig)
                        except Exception:
                            pass
            except Exception as e:
                result_holder["error"] = e
            finally:
                result_holder["done"] = True

        self._all_check_index += 1
        thread = threading.Thread(target=_run_check_in_thread, daemon=True)
        thread.start()

        # メインスレッド: チェックが終わるまでスクランブルを回す
        self._animate_until_done(header_label, current, total, title, result_holder)
        thread.join()

        # メインスレッドで UI 反映
        if result_holder["error"] is not None:
            print(f"[assetChecker] {folder} check failed: {result_holder['error']}")
            has_issue = False
        else:
            has_issue = self._apply_check_result(
                folder,
                result_holder["structured"],
                result_holder["text"],
                show_details=False,
            )

        self._all_check_summary.append(("ERROR" if has_issue else "OK", folder))
        QtCore.QTimer.singleShot(0, self._step_all_check)

    def _animate_until_done(self, header_label, current, total, title, result_holder):
        """チェック完了まで実行中の cmds（無ければツール名）を表示しつつ UI を生かす"""

        def _build_html(scan_line):
            hint = "  キャンセル中..." if self._cancel_requested else "  (ESC でキャンセル)"
            parts = [
                f"<div style='font-family:Consolas,monospace; font-size:11px;"
                f" color:#3ecfbe; margin-bottom:6px;'>"
                f"{html.escape(header_label)}  [{current}/{total}]"
                f"<span style='color:#88b8f0; font-size:10px;'>{html.escape(hint)}</span>"
                f"</div>",
                "<div style='font-family:Consolas,monospace; font-size:10px;"
                " color:#1a3050; margin-bottom:4px;'>────────────────────────────</div>",
            ]
            for status, f in self._all_check_summary:
                color = "#28c880" if status == "OK" else "#e05858"
                mark  = "✓" if status == "OK" else "✗"
                t     = self._folder_titles.get(f, f)
                cnt   = self._folder_counts.get(f, 0)
                badge = (
                    f"  <span style='color:#e05858;'>[{cnt}件]</span>"
                    if status == "ERROR" else ""
                )
                parts.append(
                    f"<div style='font-family:Consolas,monospace; font-size:11px;"
                    f" color:{color};'>{mark}  {html.escape(t)}{badge}</div>"
                )
            parts.append(
                f"<div style='font-family:Consolas,monospace; font-size:11px;"
                f" color:#88b8f0; margin-top:3px;'>▶  {html.escape(scan_line)}</div>"
            )
            return "".join(parts)

        # チェック完了まで「実行中の cmds」を表示し続ける（無ければツール名を静的に）
        while not result_holder["done"]:
            last_cmd = result_holder.get("last_cmd")
            display = last_cmd if last_cmd else f"{title}..."
            self.detail_view.setHtml(_build_html(display + "█"))
            QtWidgets.QApplication.processEvents()
            QtCore.QThread.msleep(35)

        # 完了 → 確定状態を即表示
        self.detail_view.setHtml(_build_html(title + "..."))
        QtWidgets.QApplication.processEvents()

    def _finish_all_check(self):
        self._all_check_running = False
        self._remove_input_block()
        cancelled = self._cancel_requested
        self._cancel_requested = False
        active_label = self._active_check_label
        self._active_check_folders = []
        self._active_check_label = ""
        self._set_busy(False)
        if not self.isVisible():
            return
        header_label = active_label or (
            "CHECK" if self._all_check_selection else "ALL CHECK"
        )
        if cancelled:
            header_label += " (CANCELLED)"

        n_err = sum(1 for s, _ in self._all_check_summary if s == "ERROR")
        n_ok  = sum(1 for s, _ in self._all_check_summary if s == "OK")

        # オブジェクトリスト用プレーンテキスト
        lines = [f"{header_label} 結果", ""]
        for status, folder in self._all_check_summary:
            lines.append(f"  {status} : {folder}")
        self.set_object_results({"ALL_CHECK": lines})
        self._set_object_list_title(header_label)

        # 完了後の詳細ビュー：スタイル付き HTML で上書き
        parts = [
            f"<div style='font-family:Consolas,monospace; font-size:11px;"
            f" color:#3ecfbe; margin-bottom:6px;'>{html.escape(header_label)} COMPLETE</div>",
            "<div style='font-family:Consolas,monospace; font-size:10px;"
            " color:#1a3050; margin-bottom:4px;'>────────────────────────────</div>",
        ]
        for status, folder in self._all_check_summary:
            color = "#28c880" if status == "OK" else "#e05858"
            mark  = "✓" if status == "OK" else "✗"
            t     = self._folder_titles.get(folder, folder)
            cnt   = self._folder_counts.get(folder, 0)
            badge = (
                f"  <span style='color:#e05858;'>[{cnt}件]</span>"
                if status == "ERROR" else ""
            )
            parts.append(
                f"<div style='font-family:Consolas,monospace; font-size:11px;"
                f" color:{color};'>{mark}  {html.escape(t)}{badge}</div>"
            )
        err_color = "#e05858" if n_err > 0 else "#1a3050"
        parts += [
            "<div style='font-family:Consolas,monospace; font-size:10px;"
            " color:#1a3050; margin:6px 0 4px;'>────────────────────────────</div>",
            f"<div style='font-family:Consolas,monospace; font-size:11px;'>"
            f"<span style='color:{err_color};'>✗ {n_err}件エラー</span>"
            f"  <span style='color:#28c880;'>✓ {n_ok}件 OK</span></div>",
        ]
        self.detail_view.setHtml("".join(parts))

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
        # カテゴリ単位 CHECK ボタン（↻）も一緒に制御
        for info in getattr(self, "_category_widgets", {}).values():
            header = info.get("header")
            if hasattr(header, "setRefreshEnabled"):
                header.setRefreshEnabled(not busy)
        for f, fix_btn in self._fix_btns.items():
            if busy:
                fix_btn.setEnabled(False)
            else:
                show = (
                    self._folder_states.get(f) == _styles.S_ERROR
                    and self.has_fix_script.get(f, False)
                )
                fix_btn.setVisible(show)
                fix_btn.setEnabled(show)

        if not busy:
            self._update_status_bar()


# ============================================================
# 起動
# ============================================================
def show_asset_checker():
    close_existing_ui()
    new_ui = assetChecker()
    new_ui.show()
    return new_ui


ui = show_asset_checker()
