# assetChecker リモートローディング設計仕様

## 概要

現状のローカルファイルベース構成を、GitHubをツール配布基盤とした  
**リモートローディング + マニフェスト駆動**のプラグインアーキテクチャに移行する。

---

## 現状の課題

| 課題 | 詳細 |
|------|------|
| ホスト依存 | ツールチップなどのメタ情報が `assetChecker.py` にハードコードされている |
| 配布コスト | ツールを更新するたびにファイルを手動で配布する必要がある |
| 拡張性 | 新ツール追加のたびにホスト側も編集が必要 |

---

## 新アーキテクチャ

### 全体像

```
GitHub (パブリックリポジトリ)
└── touls/
    ├── colorSet/
    │   ├── manifest.json        ← メタ情報
    │   ├── colorSet_check.py    ← チェックスクリプト
    │   └── colorSet_correct.py  ← 修正スクリプト（任意）
    ├── history/
    │   ├── manifest.json
    │   └── history_check.py
    └── ...

Maya ローカル
└── assetChecker.py              ← これだけ配布すればいい
```

### ローディングの流れ

```
起動
 │
 ├─① touls/ のフォルダ一覧を GitHub API で取得
 │
 ├─② 各フォルダの manifest.json を取得 → UIを構築
 │         （スクリプト本体はまだ取得しない）
 │
 └─③ チェックボタン押下時 → _check.py を取得して実行（遅延ローディング）
       FIXボタン押下時    → _correct.py を取得して実行
```

---

## manifest.json 仕様

各ツールフォルダに1つ配置する。

```json
{
  "title": "Color Set",
  "description": "カラーセットを持つ mesh を検出します。",
  "version": "1.0.0",
  "has_fix": true
}
```

| フィールド | 型 | 必須 | 説明 |
|------------|-----|------|------|
| `title` | string | ✅ | UI表示名 |
| `description` | string | ✅ | ツールチップ本文 |
| `version` | string | ✅ | バージョン管理用 |
| `has_fix` | bool | ✅ | FIXボタンを表示するか |

---

## _check.py / _correct.py インターフェース規約

現状と変わらず。`assetChecker.py` 側の `normalize_structured()` で吸収する。

```python
# パターンA：関数で返す（推奨）
def get_results():
    return { "meshName": ["エラー詳細"] }

# パターンB：変数で返す
RESULTS = { "meshName": ["エラー詳細"] }
```

---

## assetChecker.py の変更点

### 追加する定数

```python
GITHUB_RAW   = "https://raw.githubusercontent.com/ANK009-a/Maya-ModelChecker/main"
GITHUB_API   = "https://api.github.com/repos/ANK009-a/Maya-ModelChecker/contents/touls"
CACHE_DIR    = os.path.join(cmds.internalVar(usd=True), "assetChecker_cache")
```

### 追加する関数

```python
def fetch_tool_list()
    # GitHub API で touls/ のフォルダ一覧を取得
    # → [("colorSet", manifest_dict), ...]

def fetch_script(folder, script_name)
    # raw URL からスクリプトをキャッシュ付きで取得
    # → コード文字列

def load_and_run(folder, script_name)
    # fetch_script() → exec() → get_results() or RESULTS を返す
```

### 変更する関数

| 関数 | 変更内容 |
|------|----------|
| `_load_folders()` | `os.listdir()` → `fetch_tool_list()` に置き換え |
| `run_check()` | `runpy.run_path()` → `load_and_run()` に置き換え |
| `_run_fix()` | 同上 |
| `_TOOLTIPS` | 削除 → manifest.json から取得 |

---

## キャッシュ戦略

```
~/maya/scripts/assetChecker_cache/
├── colorSet_manifest.json
├── colorSet_check.py
└── colorSet_correct.py
```

| タイミング | 挙動 |
|------------|------|
| 初回起動 | GitHub から取得してキャッシュに保存 |
| 2回目以降 | キャッシュから読む（高速） |
| オフライン | キャッシュがあれば動作継続 |
| 手動リロード | UIに「Reload」ボタンを追加してキャッシュ削除+再取得 |

---

## 移行ステップ

```
Step 1  manifest.json を各ツールフォルダに追加
Step 2  assetChecker.py にリモートローディング関数を追加
Step 3  _load_folders() を新方式に切り替え（UIの見た目は変わらない）
Step 4  run_check() / _run_fix() を新方式に切り替え
Step 5  _TOOLTIPS を削除
Step 6  キャッシュ + Reloadボタンを追加
```

各Stepが独立しているため、1つずつ動作確認しながら進められる。

---

## 対応しないこと（スコープ外）

- プライベートリポジトリ対応（PAT認証）
- バージョン管理・ロールバック
- QThread による完全非同期化
- PySide6対応（別タスク）
