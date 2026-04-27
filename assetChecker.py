# -*- coding: utf-8 -*-
import re
import html
import random
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
LAUNCHER_VERSION    = "1.9.0"
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
# UI クラス
# ============================================================
class assetChecker(QtWidgets.QDialog):

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

        top_btn_lay.addWidget(self.check_btn)
        top_btn_lay.addWidget(self.all_check_btn)

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
        obj_title_main.setStyleSheet(_styles.SS_PANEL_TITLE_MAIN)
        self.object_list_title_sub = _widgets.ElidedLabel("")
        self.object_list_title_sub.setStyleSheet(_styles.SS_PANEL_TITLE_SUB)
        self.object_list_title_sub.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        obj_title_lay.addWidget(obj_title_main)
        obj_title_lay.addWidget(self.object_list_title_sub, 1)
        self.object_list_title = obj_title_w

        self.object_list = QtWidgets.QListWidget()
        self.object_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
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

        self.object_list.currentItemChanged.connect(self.on_object_selected)
        self.object_list.itemClicked.connect(self.on_object_clicked)

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
                self.rows_layout.addWidget(header)
                self._category_widgets[cat] = {"header": header, "rows": [], "folders": []}

            # ツール 1 行（ボタン + FIX）を QWidget で包む（折り畳み制御のため）
            row_w = QtWidgets.QWidget()
            row_w.setStyleSheet("background: transparent;")
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
            fix_btn.setFixedWidth(FIX_W)
            fix_btn.setFixedHeight(BTN_H)
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
            self.detail_view.setHtml(_formatter.format_details_html(details))
        self._apply_maya_selection_for_key(key, details)

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
    # ALL CHECK / CHECK
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
        folder  = self.folders[self._all_check_index]
        title   = self._folder_titles.get(folder, folder)
        total   = len(self.folders)
        current = self._all_check_index + 1

        header_label = "CHECK" if self._all_check_selection else "ALL CHECK"
        self._animate_tool_scan(header_label, current, total, title)

        self._all_check_index += 1
        has_issue = self.run_check(folder, show_details=False, selection=self._all_check_selection)
        self._all_check_summary.append(("ERROR" if has_issue else "OK", folder))
        QtCore.QTimer.singleShot(0, self._step_all_check)

    def _animate_tool_scan(self, header_label, current, total, title):
        """ツール名がランダム文字から確定していくスクランブルアニメーション"""
        _chars = "0123456789ABCDEF><|_-:?!#$%"

        def _build_html(scan_line):
            parts = [
                f"<div style='font-family:Consolas,monospace; font-size:11px;"
                f" color:#3ecfbe; margin-bottom:6px;'>"
                f"{html.escape(header_label)}  [{current}/{total}]</div>",
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

        frames = 2
        for frame in range(frames):
            ratio   = frame / frames
            n_fixed = int(len(title) * ratio)
            noise   = title[:n_fixed] + "".join(
                " " if c == " " else random.choice(_chars)
                for c in title[n_fixed:]
            )
            self.detail_view.setHtml(_build_html(noise + "█"))
            QtWidgets.QApplication.processEvents()
            QtCore.QThread.msleep(7)

        self.detail_view.setHtml(_build_html(title + "..."))
        QtWidgets.QApplication.processEvents()

    def _finish_all_check(self):
        self._all_check_running = False
        self._set_busy(False)
        header_label = "CHECK" if self._all_check_selection else "ALL CHECK"

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
close_existing_ui()
ui = assetChecker()
ui.show()
