# Handoff: assetChecker UI リデザイン

## Overview

MayaのモデルチェッカーツールUIのリデザインです。
現行の `assetChecker.py`（PySide2製）のスタイルシートを、今回設計した深海テーマのデザインに更新することが目的です。

## About the Design Files

`assetChecker UI.html` は **デザイン参照用のHTMLプロトタイプ** です。
このHTMLをそのまま使うのではなく、**`assetChecker.py` の PySide2 QSS（スタイルシート）およびレイアウトコードを、このHTMLデザインに合わせて書き換える**のがタスクです。

参照リポジトリ: `https://github.com/ANK009-a/Maya-ModelChecker`

## Fidelity

**High-fidelity（高精度）**：色・スペーシング・フォントサイズ・角丸・状態表現（OK/Error/未チェック）まで含めた最終デザインです。ピクセル精度での再現を目標としてください。

---

## デザイントークン（Design Tokens）

### カラー

| 用途 | 色 |
|---|---|
| ウィンドウ背景 | `linear-gradient(160deg, #080f1e, #04080f)` |
| パネル背景 | `#0b1628` |
| ツールボタン（未チェック）背景 | `#0f1e34` |
| ツールボタン（OK）背景 | `#061c14` |
| ツールボタン（エラー）背景 | `#200c0c` |
| ボーダー | `#1a2e4a` |
| テキスト（メイン） | `#b8d4ee` |
| テキスト（サブ） | `#4878a0` |
| アクセント（CHECK/ティール） | `#3ecfbe` |
| アクセント（ALL CHECK/ブルー） | `#88b8f0` |
| FIX ボタン | `#1e6ac0` |
| OK テキスト | `#28c880` |
| エラーテキスト | `#e05858` |
| ステータスバー背景 | `#0b1628` |

### スペーシング

| 用途 | 値 |
|---|---|
| ウィンドウ内padding（上） | `6px` |
| ウィンドウ内padding（左右下） | `10px` |
| 各パネル間のgap | `6px` |
| 左パネル内部padding | `0 7px 7px 7px` |
| ツールボタン間gap | `3px` |
| ツール行内gap（ボタン+FIXボタン） | `4px` |

### サイズ

| 用途 | 値 |
|---|---|
| ウィンドウ全体幅 | `600px`（Mayaでは可変） |
| 左パネル幅 | `204px`（固定） |
| CHECK/ALL CHECKボタン高さ | `26px` |
| ツールボタン高さ | `28px` |
| FIX ボタン幅 | `38px` |
| カテゴリヘッダー高さ | `26px` |
| ステータスバー高さ | `30px` |
| Objects/Infoタイトル高さ | `26px` |

### フォント

| 用途 | 値 |
|---|---|
| 基本フォント | `"Segoe UI", "Yu Gothic UI", sans-serif` |
| 基本フォントサイズ | `12.5px` |
| ツールボタンフォントサイズ | `11px` |
| CHECKボタンフォントサイズ | `11px` |
| カテゴリヘッダーフォントサイズ | `10px` |
| ステータスバーフォントサイズ | `11px` |
| バージョン表示フォントサイズ | `10px` |

### 角丸

| 用途 | 値 |
|---|---|
| ウィンドウ全体 | `6px` |
| 左パネル枠 | `8px` |
| ツールボタン | `6px` |
| FIX ボタン | `6px` |
| Objects/Infoパネル | `8px` |
| CHECKボタン | `6px` |

---

## レイアウト構造

```
┌─ window (620px × 500px) ──────────────────────────────────────┐
│ ┌─ body (padding: 6px 10px 10px, gap: 6px) ─────────────────┐ │
│ │ ┌─ left-col (204px) ──┐  ┌─ right-panel (flex:1) ───────┐ │ │
│ │ │ [CHECK] [ALL CHECK] │  │ ┌─list-col──┐ ┌─detail-col─┐ │ │ │
│ │ │ ┌─ left-panel ────┐ │  │ │  Objects  │ │    Info    │ │ │ │
│ │ │ │  カテゴリヘッダ │ │  │ │  obj-list │ │detail-view │ │ │ │
│ │ │ │  ツールボタン   │ │  │ └───────────┘ └────────────┘ │ │ │
│ │ │ │  ...            │ │  └──────────────────────────────┘ │ │
│ │ │ └─────────────────┘ │                                   │ │
│ │ └─────────────────────┘                                   │ │
│ └───────────────────────────────────────────────────────────┘ │
│ ┌─ statusbar ───────────────────────────────────────────────┐ │
│ │ ✗ N件エラー  ✓ N件OK  ○ N件未チェック         v1.x.x    │ │
│ └───────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

---

## 各コンポーネントの仕様

### CHECK / ALL CHECK ボタン

**PySide2対応箇所：** `_SS_BTN_CHECK` / `_SS_BTN_ALL` / `check_btn` / `all_check_btn`

- 左パネル枠の**外側上部**に配置（左パネルと同じ幅、gap: 6px）
- 高さ: `26px`（`TOP_BAR_H = 26` に変更）
- CHECK: 背景 `#0d2e2a`、ボーダー `rgba(62,207,190,0.4)`、テキスト `#3ecfbe`
- ALL CHECK: 背景 `#0a1e38`、ボーダー `rgba(40,120,208,0.53)`、テキスト `#88b8f0`
- 両ボタンともflex:1で均等幅

### 左パネル（ツール一覧）

**PySide2対応箇所：** `left_panel` / `_SS_LEFT_PANEL` / `scroll` / `rows_layout`

- 背景: `#0b1628`、ボーダー: `1px solid #1a2e4a`、角丸: `8px`
- 内部padding: `0 7px 7px 7px`（上は0）
- スクロールバーは常時表示（`ScrollBarAlwaysOn`）← すでに実装済み

### カテゴリヘッダー

**PySide2対応箇所：** `_CategoryHeader`

- 高さ: `26px`
- 構成: `▾矢印` + `カテゴリ名（大文字）` + `エラーバッジ（右端）`
- 矢印色: `#2a5070`
- カテゴリ名色: `#3a6888`（ホバー時: `#5a98c0`）
- エラーバッジ: 背景`#3a1010`、テキスト`#e05858`、角丸`3px`
- 全OKバッジ: テキスト`#28c880`、背景transparent
- **初期状態: 全カテゴリ折りたたみ済み**
- ボーダー下線: `1px solid #142030`

### ツールボタン

**PySide2対応箇所：** `_ToolButton` / `_SS_BTN_UNCHECKED` / `_SS_BTN_OK` / `_SS_BTN_ERROR`

- 高さ: `28px`（`BTN_H = 28`）← すでに実装済み
- フォントサイズ: `11px`
- 状態別スタイル:
  - 未チェック: 背景`#0f1e34`、ボーダー`#1a2e4a`、テキスト`#4878a0`、アイコン`○`
  - OK: 背景`#061c14`、ボーダー`#0a3020`、テキスト`#28c880`、アイコン`✓`
  - エラー: 背景`#200c0c`、ボーダー`#3a1010`、テキスト`#e05858`、アイコン`✗`

### FIX ボタン

**PySide2対応箇所：** `_SS_BTN_FIX` / `fix_btn`

- 幅: `38px`、高さ: `28px`
- 背景: `#1e6ac0`、テキスト: `white`
- ホバー: `#2878d0`
- エラー時かつhas_fix=trueの場合のみ表示

### Objectsリスト上部タイトル

**PySide2対応箇所：** `object_list_title` / `_SS_OBJECT_LIST_TITLE`

- テキスト: **「Objects」**（初期値）
- チェック実行時: 右下に小さくツール名を表示（`font-size: 10px`、色: `#3a6888`）
- ALL CHECK実行時: 「ALL CHECK [N/21]」形式で進捗表示
- 高さ: `26px`（CHECKボタンと同じ）

### Infoパネルタイトル

**PySide2対応箇所：** 新規追加が必要

- テキスト: **「Info」**（固定）
- 高さ: `26px`
- 色: `#88b8f0`、フォントサイズ: `12px`、フォントウェイト: `bold`
- `detail_view` の上に `QLabel` を追加し、縦レイアウトでラップする

### Objectsリスト

**PySide2対応箇所：** `object_list` / `_SS_OBJECT_LIST`

- 背景: `#0b1628`、ボーダー: `1px solid #1a2e4a`、角丸: `8px`
- 選択アイテム: 背景`#142440`、テキスト`#3ecfbe`、左ボーダー`3px solid #3ecfbe`
- アイテムpadding: `7px 14px`
- フォントサイズ: `12px`

### 詳細ビュー（Info）

**PySide2対応箇所：** `_ComponentTextEdit` / `_SS_DETAIL_VIEW`

- 背景: `#0b1628`、ボーダー: `1px solid #1a2e4a`、角丸: `8px`
- フォント: `Consolas, "Courier New", monospace`
- フォントサイズ: `12px`

### ステータスバー

**PySide2対応箇所：** `_SS_STATUS_BAR` / status frame

- 背景: `#0b1628`、上ボーダー: `1px solid #1a2e4a`
- 高さ: `30px`
- padding: `5px 16px`
- エラー色: `#e05858`、OK色: `#28c880`、未チェック色: `#4878a0`
- バージョン色: `#263c58`

### カスタムツールチップ

**PySide2対応箇所：** `_InstantTooltipFilter` / `btn.setToolTip()`

- 背景: `#0b1628`、ボーダー: `1px solid #1a3050`、角丸: `7px`
- padding: `10px 12px`
- タイトル: `13px`、`font-weight: 600`、色: `#88b8f0`
- 説明文: `11px`、色: `#7a9ab8`
- カテゴリ/バージョンバッジ: 背景`#0f1e34`、ボーダー`#1a2e4a`、角丸`3px`
- ホバー後約400ms（`_interval = 400`）で表示

---

## スクロールバー

```css
/* QSSで設定 */
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
```

---

## 実装で変更が必要な主なポイント

| 変更箇所 | 内容 |
|---|---|
| `TOP_BAR_H` | `20` → `26` に変更 |
| `_SS_BTN_CHECK` / `_SS_BTN_ALL` | 高さ`height: 26px`を反映 |
| `left_container_lay` | `gap` を `6px` に変更 |
| `body_lay` のcontentsMargins | `(6, 10, 10, 10)` に変更（上だけ6px） |
| `body_lay` のspacing | `6` に変更 |
| `right_lay` のspacing | `6` に変更 |
| `list_lay` のspacing | `6` に変更 |
| `object_list_title` | 初期テキストを `"Objects"` に変更、右下にサブラベル追加 |
| Info タイトル追加 | `detail_view` の上に `QLabel("Info")` を追加してラップ |
| ツールチップ遅延 | `QTimer` を `400ms` に設定 |

---

## Files

- `assetChecker UI.html` — HTMLプロトタイプ（デザイン参照用）
- 実装対象: `assetChecker.py`（GitHubリポジトリ `ANK009-a/Maya-ModelChecker`）

---

## 注意事項

- HTMLプロトタイプはブラウザ上での確認用です。Mayaでは`PySide2`で実装してください
- `assetChecker.py` はすでにv1.3.7まで更新されており、多くのデザインが反映済みです。**差分のみを適用**してください
- アイコン自動インストール機能（Base64埋め込み）は別途検討中です
