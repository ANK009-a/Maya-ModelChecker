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
| `LEFT_PANEL_W` | 204 | 左パネル全体の幅 px（CHECK/ALL CHECK ボタンとツール一覧を内包） |
| `BTN_H`        | 28  | ツールボタン / トップバーボタンの高さ px |
| `FIX_W`        | 38  | FIX ボタンの幅 px |

## ランチャーバージョン
```python
LAUNCHER_VERSION = "1.3.1"  # assetChecker.py 上部
```
ステータスバー右下に `v1.3.1` として表示される。assetChecker.py 本体を編集したらこの値をバンプする。

## 詳細表示の HTML 整形
右パネルの詳細ビュー（`detail_view`）は `_format_details_html()` で HTML 化される：
- 1 行目（`message`）: 太字見出し（カテゴリ色 `#7aa3d0`、13px）
- `⚠` で始まる行: 警告色（アンバー `#e0b060`）
- 先頭スペース 2 文字以上のインデント行: モノスペース（座標・サンプル整列用）
- `key: value` 形式: ラベルと値を色分け
- その他: 通常テキスト

check / fix スクリプト側で details に `⚠` プレフィックス・インデント・`key: value` 形式を使うと
自動で整形される。

## ウィンドウサイズ
```python
self.resize(600, 700)  # __init__ 内
```
カテゴリ折り畳みデフォルトとの相性のため、コンテンツ高さに合わせる自動リサイズ
（旧 `_adjust_height`）は廃止。固定の初期サイズのみで運用。

## レイアウト構造（v1.2.0 〜）
```
QDialog (bg #060c18)
└── body (margin 10, spacing 10)
    ├── 左パネル QFrame#leftPanel (rounded 8px, bg #0b1628, border #1a2e4a, fixedW 204)
    │   ├── 上部ボタン QHBoxLayout (margin 7,7,7,0, spacing 6)
    │   │   ├── CHECK (BTN_H=28)
    │   │   └── ALL CHECK (BTN_H=28)
    │   └── ツール一覧 QScrollArea (transparent, no border)
    │       └── rows_layout QVBoxLayout (margin 7, spacing 3)
    │           ├── _CategoryHeader (Transform 系)
    │           ├── tool row (QWidget) × N
    │           ├── _CategoryHeader (Mesh 形状系)
    │           ├── ...
    │           └── stretch
    └── 右パネル QHBoxLayout (spacing 8)
        ├── object_list (rounded 8px) - stretch 37
        └── detail_view  (rounded 8px) - stretch 63
└── ステータスバー QFrame#statusBar (h 30, bg #0b1628, top border)
    [✗ N件エラー] [✓ N件 OK] [○ N件 未チェック] ... [v1.2.0]
```

トップバー（タイトル / CHECK / ALL CHECK）は廃止。CHECK/ALL CHECK は左パネル上部に移動。

## カテゴリ折り畳み
- `_CategoryHeader` クリックでそのカテゴリの全ツール行を表示/非表示切替
- 矢印 `▾`（展開）/ `▸`（折り畳み）
- 起動時は全カテゴリ折り畳み状態
- ヘッダー右端のステータス表示（`setStatus(err_tool_count, all_ok)`）:
  - 1 つでもエラーツールがあれば **エラーツール数**（件数ではなく「エラー状態のツールの数」）を赤 pill で表示
  - 全ツールが OK 状態なら **✓**（緑）を表示
  - それ以外（未チェック含む）は非表示

## ツールボタン構造
`_ToolButton`（`_DoubleClickButton` を継承）：
- 内部 QHBoxLayout で `名前 QLabel` のみを配置（件数バッジは v1.3.0 で削除）
- エラー件数はカテゴリヘッダー側に集約
- 子ラベルは `Qt.WA_TransparentForMouseEvents` でクリック透過
- `setName(text, color)` で更新
- 状態に応じた背景は `setStyleSheet(_SS_BTN_*)` で切替
- `setMinimumWidth(1)` でテキスト伸長による FIX 押し出し防止

## 詳細ビューのコンポーネントクリック選択
`_ComponentTextEdit`（`QTextEdit` を継承）：
- `mouseReleaseEvent` で `vtx[..]` / `f[..]` / `e[..]` / `map[..]` / `uv[..]` / `cv[..]` / `ep[..]` / `pt[..]` パターンを検出
- `setMouseTracking(True)` + `mouseMoveEvent` でコンポーネント上にホバー時だけカーソルを `PointingHandCursor` に変更（その他は `IBeamCursor`）
- ドラッグでテキスト選択した場合は emit しない（通常のテキストコピーを阻害しない）
- `componentClicked` シグナル → `_on_detail_component_clicked`:
  - フル形式（`xxx.vtx[..]`）→ そのまま `cmds.select`
  - コンポーネントのみ（`vtx[..]`）→ object_list で選択中のオブジェクト key と結合して select
- 見た目: `_format_details_html` 内の `_wrap_components` でコンポーネント文字列を `<span>` で囲み、pill 状（bg `#14243c` / border `#1e3554` / text `#88b8f0` / radius 3px / padding 0 4px）に装飾
- 正規表現は module-level `_COMPONENT_PATTERN` に集約（検出とスタイリングで同一パターンを共用）

## ボタン操作
- **シングルクリック**：直近のチェック結果を右パネルに再表示（再チェックしない）
- **ダブルクリック**：チェック実行
- `_DoubleClickButton` クラスでクリック判定間隔を 180ms に短縮

## ツールチップ方針
- manifest_index.json の `title` / `description` / `version` / `category` から動的生成
- ツールチップ右下に `カテゴリ名  v1.0.1` を右寄せ表示（`<table>` で右寄せ）
- HTML タグ（`<b>`, `<br>` など）使用可
- 即時表示：`_InstantTooltipFilter`（`QEvent.Enter` で `QToolTip.showText()` 直呼び）

## テーマカラー（v1.2.0 〜）
| 用途 | カラーコード |
|------|------------|
| ダイアログ背景 | `#060c18` |
| パネル背景 | `#0b1628` |
| パネル枠線 | `#1a2e4a` |
| ツールボタン bg / 枠 / 文字 | `#0f1e34` / `#1a2e4a` / `#4878a0` |
| ツール OK bg / 枠 / 文字 | `#061c14` / `#0a3020` / `#28c880` |
| ツール ERROR bg / 枠 / 文字 | `#200c0c` / `#3a1010` / `#e05858` |
| FIX ボタン bg / hover | `#1e6ac0` / `#2878d0` |
| CHECK ボタン bg / 枠 / 文字 | `#0d2e2a` / `#3ecfbe` / `#3ecfbe` |
| ALL CHECK bg / 枠 / 文字 | `#0a1e38` / `#2878d0` / `#88b8f0` |
| object_list 選択 bg / 枠 / 文字 | `#142440` / `#3ecfbe` / `#3ecfbe` |
| カテゴリ見出し 文字 / hover | `#3a6888` / `#5a98c0` |
| バッジ bg / 文字 | `#3a1010` / `#e05858` |
| ツールチップ bg / 枠 / 文字 | `#0b1628` / `#1a3050` / `#b8d4ee` |
| ステータスバー version 文字 | `#263c58`（10px） |

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
