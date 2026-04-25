# -*- coding: utf-8 -*-
"""
animLayer_check.py

check処理:
シーン内の animLayer ノード（BaseAnimation 含む）を検出します。

対象:
- シーン全体（選択に関係なく常に全件）

旧 animationKey ツールから animLayer 検出のみを分離。
animCurve は別ツール `animCurve` として分割。
"""
import maya.cmds as cmds
from _results import CheckResult, Severity


def _anim_layers():
    """シーン内の animLayer ノード（BaseAnimation 含む）を返す。"""
    return cmds.ls(type="animLayer") or []


def get_results():
    results = []

    for n in sorted(_anim_layers()):
        details = ["Type: animLayer"]
        if n == "BaseAnimation":
            details.append("⚠ BaseAnimation を削除すると配下の animLayer も全削除されます")
        results.append(CheckResult(
            target=n,
            message=f"animLayer: {n}",
            details=details,
            severity=Severity.ERROR,
        ))

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[animLayer] animLayer ノードは見つかりませんでした。")
    else:
        print(f"[animLayer] {len(res)} 件")
        for r in res:
            print(r.message)
