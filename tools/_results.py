# -*- coding: utf-8 -*-
"""
check / fix の戻り値型（v1.6.0〜）。

新 API（オプトイン）:
    from _results import CheckResult, Severity

    def get_results():
        return [
            CheckResult(
                target="|grp|pCube1",
                message="頂点トゥイークが残っています",
                details=["Tweaked vertex count: 5"],
                severity=Severity.ERROR,
            ),
        ]

旧 API（list[dict] / dict[str, list[str]]）も継続サポート。
旧形式は severity が指定されていない場合 "error" として扱われる。

Severity:
- ERROR を既定値として使う。
- WARNING / INFO 定数は API として残してあるが、launcher 側では区別しない（v1.7.0 で UI 撤廃）。
  すべての結果が ERROR と同じ赤系で表示される。将来 WARNING UI を再導入する場合は
  _styles / _widgets / assetChecker._set_folder_state を再拡張する必要がある。
"""

from dataclasses import dataclass, field


# ============================================================
# Severity 定数
# ============================================================
class Severity:
    """検出結果の重大度。
    ERROR   → ツールボタンが赤、要対応
    WARNING → ツールボタンが黄、要確認（誤検知の可能性も含む）
    INFO    → 参考情報（ツール状態には影響しない場合がある）
    """
    ERROR   = "error"
    WARNING = "warning"
    INFO    = "info"


# ============================================================
# CheckResult dataclass
# ============================================================
@dataclass
class CheckResult:
    """1 つの検出対象に対する結果。

    Args:
        target:   内部キー（DAG long path 推奨。一意性確保のため）
        message:  短い概要（HTML 整形時に見出しとして表示される）
        details:  詳細情報の文字列リスト（インデント / "key: value" / ⚠ で自動整形）
        severity: "error" / "warning" / "info"（既定: "error"）
        display:  表示名の上書き（指定なら _formatter.disambiguate_keys を使わず
                  この名前を使う）
    """
    target: str
    message: str = ""
    details: list = field(default_factory=list)
    severity: str = Severity.ERROR
    display: str = ""
