# -*- coding: utf-8 -*-
"""
assetChecker のスタイルシート / 状態定数を集約するヘルパーモジュール。
assetChecker.py から bootstrap でロードされ、`import _styles` で参照される。
"""

# ============================================================
# 状態定数
# ============================================================
S_UNCHECKED = 0
S_OK        = 1
S_ERROR     = 2


# ============================================================
# ダイアログ全体（背景 + スクロールバー + デフォルトツールチップ）
# ============================================================
SS_DIALOG = """
QDialog#assetChecker {
    background: qlineargradient(x1:0, y1:0, x2:0.4, y2:1, stop:0 #080f1e, stop:1 #04080f);
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 8px 3px 8px 0;
}
QScrollBar::handle:vertical {
    background: #1a3050;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover { background: #244068; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0 8px 3px 8px;
}
QScrollBar::handle:horizontal {
    background: #1a3050;
    min-width: 20px;
    border-radius: 4px;
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


# ============================================================
# スクロールバー: スクロール不要時に視覚的に隠す
# （setStyleSheet で動的に切り替えて、領域は維持しつつ手元だけ透明に）
# ============================================================
SS_OBJECT_SCROLLBAR_HIDDEN = """
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 8px 3px 8px 0;
}
QScrollBar::handle:vertical {
    background: transparent;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover { background: transparent; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""


# ============================================================
# ツールボタン: 状態別（未チェック / OK / エラー）
# ============================================================
SS_BTN_UNCHECKED = """
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

SS_BTN_OK = """
QPushButton {
    background-color: #061c14;
    border: 1px solid #0a3020;
    border-radius: 6px;
    text-align: left;
}
QPushButton:hover { background-color: #081e16; }
QPushButton:disabled { background-color: #04140e; }
"""

SS_BTN_ERROR = """
QPushButton {
    background-color: #200c0c;
    border: 1px solid #3a1010;
    border-radius: 6px;
    text-align: left;
}
QPushButton:hover { background-color: #240e0e; }
QPushButton:disabled { background-color: #170808; }
"""


# ============================================================
# トップバーボタン（FIX / ALL CHECK / CHECK）
# ============================================================
SS_BTN_FIX = """
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

SS_BTN_ALL = """
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

SS_BTN_CHECK = """
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


# ============================================================
# 右パネル（オブジェクトリスト + 詳細ビュー + タイトル）
# ============================================================
SS_OBJECT_LIST = """
QListWidget {
    background-color: #0b1628;
    color: #b8d4ee;
    border: 1px solid #1a2e4a;
    border-radius: 8px;
    outline: none;
    padding: 0;
    font-size: 12px;
}
QListWidget::item {
    margin: 4px 4px;
    padding: 7px 10px;
    border-radius: 4px;
}
QListWidget::item:hover { background-color: #0f1e34; }
QListWidget::item:selected {
    background-color: #142440;
    color: #3ecfbe;
}
"""

SS_DETAIL_VIEW = """
QTextEdit {
    background-color: #0b1628;
    color: #b8d4ee;
    border: 1px solid #1a2e4a;
    border-radius: 8px;
    padding: 0;
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
    selection-background-color: #142440;
    selection-color: #3ecfbe;
}
"""

SS_PANEL_TITLE_MAIN = """
QLabel {
    color: #88b8f0;
    font-size: 12px;
    font-weight: bold;
    background: transparent;
}
"""

SS_PANEL_TITLE_SUB = """
QLabel {
    color: #3a6888;
    font-size: 10px;
    font-weight: normal;
    background: transparent;
}
"""


# ============================================================
# 左パネル枠 + ステータスバー
# ============================================================
SS_LEFT_PANEL = """
QFrame#leftPanel {
    background-color: #0b1628;
    border: 1px solid #1a2e4a;
    border-radius: 8px;
}
"""

SS_STATUS_BAR = """
QFrame#statusBar {
    background-color: #0b1628;
    border-top: 1px solid #1a2e4a;
}
"""
