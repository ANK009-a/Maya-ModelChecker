# -*- coding: utf-8 -*-
"""
scriptNode_check.py

check処理:
シーンに含まれる scriptNode と expression を検出します。

scriptNode はファイル open / close 時に任意のスクリプトを実行できるため、
不審な scriptNode は Maya 経由で広まるマルウェアの典型的な感染経路となる。
本ツールでは検出のみ行い、内容を確認の上で手動削除することを推奨。

scriptType:
  0=Demand / 1=Open/Close / 2=GUI / 3=GUI Open/Close /
  4=Internal / 5=Open / 6=Close / 7=Software
"""
import maya.cmds as cmds
from _results import CheckResult, Severity


_SCRIPT_TYPE_LABELS = {
    0: "Demand",
    1: "Open/Close",
    2: "GUI",
    3: "GUI Open/Close",
    4: "Internal",
    5: "Open",
    6: "Close",
    7: "Software",
}

# Open / Close 系（ファイル開閉時に自動実行されるため要注意）
_DANGEROUS_TYPES = {1, 5, 6}


def _get_attr_safe(node, attr, default=""):
    try:
        v = cmds.getAttr(f"{node}.{attr}")
        return v if v is not None else default
    except Exception:
        return default


def _preview(text, n=80):
    line = (text or "").strip().splitlines()
    if not line:
        return ""
    s = line[0]
    return s if len(s) <= n else s[: n - 1] + "…"


def get_results():
    results = []

    for n in sorted(cmds.ls(type="script") or []):
        st = _get_attr_safe(n, "scriptType", default=None)
        label = _SCRIPT_TYPE_LABELS.get(st, f"Unknown({st})")
        before = _get_attr_safe(n, "before")
        after = _get_attr_safe(n, "after")

        details = [
            "Type: scriptNode",
            f"scriptType: {label}",
        ]
        if st in _DANGEROUS_TYPES:
            details.append("⚠ ファイル open / close 時に自動実行されます")
        if before.strip():
            details.append(f"  before: {_preview(before)}")
        if after.strip():
            details.append(f"  after: {_preview(after)}")
        if not before.strip() and not after.strip():
            details.append("  （スクリプト本体は空）")

        results.append(CheckResult(
            target=n,
            message=f"scriptNode: {n} [{label}]",
            details=details,
            severity=Severity.WARNING,
        ))

    for n in sorted(cmds.ls(type="expression") or []):
        expr = _get_attr_safe(n, "expression")
        details = ["Type: expression"]
        if expr.strip():
            details.append(f"  expression: {_preview(expr)}")
        else:
            details.append("  （式は空）")
        results.append(CheckResult(
            target=n,
            message=f"expression: {n}",
            details=details,
            severity=Severity.WARNING,
        ))

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[scriptNode] scriptNode / expression は見つかりませんでした。")
    else:
        print(f"[scriptNode] {len(res)} 件")
        for r in res:
            print(r.message)
