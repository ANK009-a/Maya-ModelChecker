# assetChecker — プロジェクト仕様

## 概要
Maya 用アセットチェックツール。PySide2 で実装されたダークテーマの QDialog。
チェックスクリプト群（`tools/` 配下）を読み込み、左パネルのボタンで実行・修正できる。

## レイアウト定数（変更時は必ず関連箇所も合わせて更新）
| 定数 | 値 | 説明 |
|------|-----|------|
| `LEFT_W` | 168 | 左パネル（チェックボタン列）の幅 px |
| `BTN_H`  | 26  | チェックボタンの高さ px |
| `FIX_W`  | 40  | FIX ボタンの幅 px |

## ウィンドウサイズ
```python
self.resize(600, 500)  # __init__ 内
```

## スクロールエリアの幅計算
```python
sbw = QtWidgets.QApplication.style().pixelMetric(QtWidgets.QStyle.PM_ScrollBarExtent)
scroll.setFixedWidth(LEFT_W + 4 + FIX_W + 8 + sbw)
# 内訳: チェックボタン列 + 行間隔 + FIXボタン + rows_layout左右余白(4+4) + スクロールバー
```
`setFrameShape(QFrame.NoFrame)` でフレームを除去し、この計算式が正確に成立するようにしている。

## チェックボタンの最小幅
```python
btn.setMinimumWidth(1)  # _load_folders() 内
```
チェック後にボタンテキストが長くなっても FIX ボタンが押し出されないように、
Qt の minimumSizeHint を無効化している。

## ツールチップ方針
- `_TOOLTIPS` dict に `(title, description)` タプルで定義
- 説明文は**汎用的**に書く（VRC 専用の推奨文・`<i>` イタリック行は含めない）
- HTML タグ（`<b>`, `<br>` など）使用可
- 即時表示: `_InstantTooltipFilter`（`QEvent.Enter` で `QToolTip.showText()` 直呼び）

## テーマカラー（_SS_DIALOG より）
| 用途 | カラーコード |
|------|------------|
| ダイアログ背景 | `#1c2b3a` |
| ツールチップ背景 | `#1a3050` |
| ツールチップ文字 | `#ccddef` |
| ツールチップ枠 | `#3a6488` |

## コメント規約
- コード内コメントは**日本語**で記述する
