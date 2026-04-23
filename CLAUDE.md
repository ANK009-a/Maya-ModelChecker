# assetChecker — プロジェクト仕様

## 概要
Maya 用アセットチェックツール。PySide2 で実装されたダークテーマの QDialog。
チェックスクリプト群（`tools/` 配下）を GitHub からリモートロードし、
左パネルのボタンで各チェックの実行・修正ができる。

## アーキテクチャ

### 配布構成
```
GitHub (raw.githubusercontent.com/ANK009-a/Maya-ModelChecker/main)
└── tools/
    ├── manifest_index.json     ← 全ツールのメタ情報（一覧＋バージョン）
    ├── _util.py                ← 共通ユーティリティ
    ├── animationKey/
    │   ├── animationKey_check.py
    │   └── animationKey_fix.py
    ├── colorSet/
    │   ├── colorSet_check.py
    │   └── colorSet_fix.py
    └── ...

ローカル (Maya)
└── assetChecker.py             ← これだけ配布すれば動く（リモートローダー）
```

### ローディングの流れ
1. 起動時 `fetch_manifest_index()` で `tools/manifest_index.json` を取得 → UI 構築
2. チェックボタン押下時に `{folder}/{folder}_check.py` を取得して `exec()`
3. FIX ボタン押下時に `{folder}/{folder}_fix.py` を取得して `exec()`
4. `_util.py` は最初の `_ensure_util_module()` で取得し `sys.modules["_util"]` に登録

### キャッシュ
- メモリのみ：`_script_cache = {}`（ファイル単位 dict）
- assetChecker.py を再 exec すると `_script_cache` が空の新しい dict になるためリセットされる
  → Maya を閉じる必要なし、ランチャー再実行だけで最新化
- ディスクには一切残さない方針（PC にゴミファイルを作らない）

### スクリプト実行の選択伝達
- `load_and_run(folder, script_name, selection)`
  - `selection=None`: 呼び出し時点の Maya 選択を使用
  - `selection=[]`  : シーン全体（強制全チェック）
  - `selection=[...]`: 指定オブジェクトのみ
- `_util._checker_selection` にセットされ、各 check スクリプトが `iter_scene_mesh_shapes()` 経由で参照

## manifest_index.json
配列形式。各要素 1 ツール。
```json
{
  "folder": "colorSet",
  "title": "Color Set",
  "description": "カラーセットを持つ mesh を検出します。",
  "has_fix": true,
  "version": "1.0.1"
}
```

| フィールド | 型 | 説明 |
|------------|-----|------|
| `folder` | string | tools/ 配下フォルダ名（スクリプトファイル名のプレフィックスにもなる） |
| `category` | string | カテゴリ名（例: `"Transform 系"`）。ツールチップ右下に表示 |
| `title` | string | UI ツールチップタイトル |
| `description` | string | ツールチップ本文（HTML 可） |
| `has_fix` | bool | FIX ボタンを出すか（`_fix.py` の存在） |
| `version` | string | semver。ツールチップ右下に `v1.0.1` 表示（カテゴリの右隣） |

### ツール並び順ルール
作業フローに沿った **カテゴリ順** で配置する。各カテゴリ間は JSON 上に空行を入れて視認性を上げる
（パーサーは空行を無視するため動作には影響しない）。

| 順 | カテゴリ | 含まれるツール |
|----|---------|---------------|
| 1 | **Transform 系** | emptyGroup → hiddenObject → freeze → pivot → negativeScale |
| 2 | **Mesh 形状系** | nonManifold → laminaFace → reversedNormal → isolateVtx → overlappingVtx |
| 3 | **Mesh 属性系** | history → vtxTweak → lockNormal → colorSet → meshShapeName |
| 4 | **UV 系** | uv(0.0-1.0) → uvSet(extra) → uvSet(error) |
| 5 | **テクスチャ系** | texturePath |
| 6 | **シーン系** | nameCollision → animationKey |

新ツールを追加する際は適切なカテゴリの末尾に追加する。カテゴリ自体を新設する場合は
作業フロー上の位置を判断して挿入し、CLAUDE.md のこの表も更新する。

並び替えのみの編集でも全ツールの version をバンプする（バージョン管理ルール参照）。

## check.py / fix.py インターフェース規約

### 命名（**重要：correct ではなく fix で統一**）
- `{folder}/{folder}_check.py` … チェック本体
- `{folder}/{folder}_fix.py`   … 修正本体（任意。`has_fix: true` の場合に必要）

### 戻り値（`get_results()` 関数 or `RESULTS` 変数）
推奨は `list[dict]`：
```python
def get_results():
    return [
        {
            "transform": "|grp|Sphere",   # ★ long path（フルパス）必須
            "message":   "RotatePivot: (1.0, 0.0, 0.0)",
            "details":   ["details行1", "details行2"],   # 任意
        },
    ]
```
- `transform` は **long path（`|` 始まり）** を入れる
  - 同名オブジェクトが別グループに居る場合、short name だと `cmds.select()` が曖昧で失敗する
  - UI 側で短い表示に自動圧縮する（`_disambiguate_keys`）
- `message` に短い結果概要、`details` に詳細リスト
- 旧形式 `dict[str, list[str]]` も `normalize_structured()` で吸収される

### UI 側の同名衝突解決
`_disambiguate_keys(keys)` がオブジェクト一覧の表示名を最小階層で生成：
- 衝突なし → `"Sphere"`
- 別グループに同名あり → `"grp1 | Sphere"` のように必要分だけ親をたどる
- 内部キーは long path のまま保持（`Qt.UserRole`）→ 選択時の曖昧さなし

## 共通ユーティリティ（`tools/_util.py`）
| 関数 | 用途 |
|------|------|
| `iter_scene_mesh_shapes()` | 選択 or シーン全体の non-intermediate mesh shape |
| `iter_unique_mesh_parents()` | 上記の親 transform（重複なし、順序保持） |
| `short_name(dag_path)` | leaf 名のみ |
| `parent_transform(shape)` | shape の親 transform full path |
| `is_referenced(node)` | リファレンス由来か |
| `checker_selection()` | `_checker_selection` を返す（`[]` = シーン全体） |

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

## ボタン操作
- **シングルクリック**：直近のチェック結果を右パネルに再表示（再チェックしない）
- **ダブルクリック**：チェック実行
- `_DoubleClickButton` クラスでクリック判定間隔を 180ms に短縮

## ツールチップ方針
- manifest_index.json の `title` / `description` / `version` から動的生成
- ツールチップ右下に `v1.0.1` のようにバージョン表示（`<table>` で右寄せ）
- HTML タグ（`<b>`, `<br>` など）使用可
- 即時表示：`_InstantTooltipFilter`（`QEvent.Enter` で `QToolTip.showText()` 直呼び）

## テーマカラー（_SS_DIALOG より）
| 用途 | カラーコード |
|------|------------|
| ダイアログ背景 | `#1c2b3a` |
| ツールチップ背景 | `#1a3050` |
| ツールチップ文字 | `#ccddef` |
| ツールチップ枠 | `#3a6488` |
| バージョン文字 | `#6a89a8`（小さめ 9px） |

## 命名規約（重要）
- **修正スクリプトは `_fix.py`**。旧 `_correct.py` は全廃。
- ユーザー向け文言も `fix` で統一（`correct` という単語は使わない）
- 関数名も `def fix():` を推奨（旧 `def correct():` は廃止）

## バージョン管理ルール（必須）
ファイルを編集したら **必ず** `tools/manifest_index.json` の対応 `version` をバンプする。
| 編集内容 | バンプ幅 |
|---------|---------|
| 内部リネーム・docstring・コメント整理 | PATCH（1.0.0 → 1.0.1） |
| 検出仕様の変更・機能追加削除・description 変更 | MINOR（1.0.0 → 1.1.0） |
| 互換性破壊（インターフェース変更など） | MAJOR（1.0.0 → 2.0.0） |

**例外なし**: manifest_index.json の並び替え・整形のみの編集でも全ツールを PATCH バンプする
（ランチャーのツールチップ version 表示でしか最新かどうか判別できないため）。

## コメント規約
- コード内コメントは **日本語** で記述する
- 不要なコメントは書かない（WHAT は識別子から読み取れる。WHY が非自明な場合のみ）
