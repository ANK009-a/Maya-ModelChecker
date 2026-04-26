# -*- coding: utf-8 -*-
"""
assetChecker の再利用可能ウィジェット群。
assetChecker.py から bootstrap でロードされ、`import _widgets` で参照される。
"""

import re
from PySide2 import QtWidgets, QtCore, QtGui


# Maya コンポーネント検出用の正規表現
# vtx[..], f[..], e[..], map[..], uv[..], cv[..], ep[..], pt[..]
# プレフィックス（オブジェクト名）の有無どちらにもマッチ
COMPONENT_PATTERN = re.compile(
    r'(?:\|?[A-Za-z_][A-Za-z0-9_:\|]*\.)?'
    r'(?:vtx|f|e|map|uv|cv|ep|pt)\[[0-9:,\-\s]+\]'
)


# ============================================================
# ダブルクリック対応ボタン
# ============================================================
class DoubleClickButton(QtWidgets.QPushButton):
    """QTimer でシングル/ダブルクリックを明確に分離したボタン。
    - singleClicked : 短時間内にダブルクリックが来なかった場合にのみ発火
    - doubleClicked : ダブルクリック時に発火（singleClicked は発火しない）
    """
    singleClicked = QtCore.Signal()
    doubleClicked = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # シングル/ダブル判定待ち時間（短めにしてシングルクリックの反応を良くする）
        _interval = min(180, QtWidgets.QApplication.doubleClickInterval())
        self._click_timer = QtCore.QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(_interval)
        self._click_timer.timeout.connect(self.singleClicked.emit)
        self._cancel_next_release = False

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() != QtCore.Qt.LeftButton:
            return
        if self._cancel_next_release:
            self._cancel_next_release = False
            return
        self._click_timer.start()

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._click_timer.stop()
            self._cancel_next_release = True
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)


# ============================================================
# カスタムツールチップ + 即時表示フィルター
# ============================================================
class CustomTooltip(QtWidgets.QFrame):
    """Design System 仕様のカスタムツールチップ。
    タイトル / 説明 / 区切り線 / カテゴリ・バージョンバッジを構造化表示する。"""

    _SS = """
QFrame#customTooltip {
    background-color: #0b1628;
    border: 1px solid #1a3050;
    border-radius: 7px;
}
QLabel#ttTitle {
    color: #88b8f0;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}
QLabel#ttDesc {
    color: #7a9ab8;
    font-size: 11px;
    background: transparent;
}
QLabel#ttCat {
    color: #3a6888;
    background-color: #0f1e34;
    border: 1px solid #1a2e4a;
    border-radius: 3px;
    padding: 1px 6px;
    font-size: 10px;
}
QLabel#ttVer {
    color: #2a5070;
    background-color: #0f1e34;
    border: 1px solid #1a2e4a;
    border-radius: 3px;
    padding: 1px 6px;
    font-size: 10px;
}
QFrame#ttDivider {
    background-color: #1a3050;
    border: none;
}
"""

    def __init__(self, parent=None):
        # ToolTip フラグでフォーカスを奪わずに最前面表示
        super().__init__(parent, QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint)
        self.setObjectName("customTooltip")
        self.setStyleSheet(self._SS)
        self.setMaximumWidth(260)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        self.title_lbl = QtWidgets.QLabel()
        self.title_lbl.setObjectName("ttTitle")
        self.title_lbl.setWordWrap(True)

        self.divider = QtWidgets.QFrame()
        self.divider.setObjectName("ttDivider")
        self.divider.setFixedHeight(1)

        self.desc_lbl = QtWidgets.QLabel()
        self.desc_lbl.setObjectName("ttDesc")
        self.desc_lbl.setWordWrap(True)

        meta_w = QtWidgets.QWidget()
        meta_w.setStyleSheet("background: transparent;")
        meta_lay = QtWidgets.QHBoxLayout(meta_w)
        meta_lay.setContentsMargins(0, 0, 0, 0)
        meta_lay.setSpacing(8)

        self.cat_lbl = QtWidgets.QLabel()
        self.cat_lbl.setObjectName("ttCat")
        self.ver_lbl = QtWidgets.QLabel()
        self.ver_lbl.setObjectName("ttVer")

        meta_lay.addWidget(self.cat_lbl)
        meta_lay.addWidget(self.ver_lbl)
        meta_lay.addStretch(1)

        lay.addWidget(self.title_lbl)
        lay.addWidget(self.divider)
        lay.addWidget(self.desc_lbl)
        lay.addWidget(meta_w)

    def set_data(self, title, desc, category, version):
        self.title_lbl.setText(title or "")
        self.desc_lbl.setText(desc or "")
        self.desc_lbl.setVisible(bool(desc))
        self.divider.setVisible(bool(desc))
        self.cat_lbl.setText(category or "")
        self.cat_lbl.setVisible(bool(category))
        self.ver_lbl.setText(f"v{version}" if version else "")
        self.ver_lbl.setVisible(bool(version))
        self.adjustSize()

    def show_near_cursor(self, cursor_global_pos, offset=14):
        """カーソル位置 + offset の右下に表示。画面端では反対側へ回り込み"""
        self.adjustSize()
        try:
            screen = QtWidgets.QApplication.desktop().availableGeometry(cursor_global_pos)
        except Exception:
            screen = QtWidgets.QApplication.desktop().availableGeometry()
        cx, cy = cursor_global_pos.x(), cursor_global_pos.y()
        x = cx + offset
        y = cy + offset
        if x + self.width() > screen.right() - 8:
            x = cx - self.width() - 8
        if y + self.height() > screen.bottom() - 8:
            y = cy - self.height() - 8
        x = max(screen.left() + 8, x)
        y = max(screen.top() + 8, y)
        self.move(x, y)
        if not self.isVisible():
            self.show()


class InstantTooltipFilter(QtCore.QObject):
    """ホバー後 _interval ms（既定 400ms）でカスタムツールチップを表示し、
    マウス移動に追従させる。"""
    _interval = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._show_for_target)
        self._target = None
        self._tip = CustomTooltip()
        self._data_map = {}

    def register(self, widget, title, desc, category, version):
        """ウィジェットにツールチップ情報を登録し、イベントフィルターを取り付ける"""
        self._data_map[widget] = (title, desc, category, version)
        try:
            widget.setMouseTracking(True)
        except Exception:
            pass
        widget.installEventFilter(self)

    def _show_for_target(self):
        obj = self._target
        if not obj:
            return
        data = self._data_map.get(obj)
        if not data:
            return
        self._tip.set_data(*data)
        self._tip.show_near_cursor(QtGui.QCursor.pos())

    def eventFilter(self, obj, event):
        et = event.type()
        if et == QtCore.QEvent.Enter:
            self._target = obj
            self._timer.start(self._interval)
        elif et == QtCore.QEvent.Leave:
            self._timer.stop()
            self._target = None
            self._tip.hide()
        elif et == QtCore.QEvent.MouseMove and self._target is obj and self._tip.isVisible():
            self._tip.show_near_cursor(QtGui.QCursor.pos())
        return False


# ============================================================
# 詳細ビュー（コンポーネントクリック対応 QTextEdit）
# ============================================================
class ComponentTextEdit(QtWidgets.QTextEdit):
    """クリックされた位置の Maya コンポーネント文字列を検出して
    componentClicked シグナルを emit する。
    - ホバー時にポインターカーソル表示
    - ドラッグでテキスト選択した場合は emit しない"""
    componentClicked = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

    def _component_at(self, pos):
        cursor = self.cursorForPosition(pos)
        block_text = cursor.block().text()
        col = cursor.positionInBlock()
        for m in COMPONENT_PATTERN.finditer(block_text):
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
        if self.textCursor().hasSelection():
            return
        comp = self._component_at(event.pos())
        if comp:
            self.componentClicked.emit(comp)


# ============================================================
# ツールボタン（名前ラベル内包）
# ============================================================
class ToolButton(DoubleClickButton):
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
class CategoryHeader(QtWidgets.QWidget):
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
# 省略対応ラベル（幅超過時に末尾を "..." に置換）
# ============================================================
class ElidedLabel(QtWidgets.QLabel):
    """幅に収まらないテキストを末尾 '...' で省略する QLabel。
    setSizePolicy を Ignored にしているため親レイアウトを押し広げない。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._full_text = self.text()
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.setMinimumWidth(0)

    def setText(self, text):
        self._full_text = text
        self._apply_elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self):
        elided = self.fontMetrics().elidedText(
            self._full_text, QtCore.Qt.ElideRight, max(self.width(), 1)
        )
        super().setText(elided)
