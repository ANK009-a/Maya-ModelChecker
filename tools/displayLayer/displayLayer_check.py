# -*- coding: utf-8 -*-
"""
displayLayer_check.py

check処理:
defaultLayer / defaultRenderLayer 以外の displayLayer・renderLayer を検出します。

対象（シーン全体・選択に関係なく常に全件）:
- displayLayer: defaultLayer を除く
- renderLayer:  defaultRenderLayer を除く（レガシー render layer）
"""
import maya.cmds as cmds
from _results import CheckResult, Severity


_DEFAULT_DISPLAY = "defaultLayer"
_DEFAULT_RENDER = "defaultRenderLayer"


def _layers(node_type, default_name):
    nodes = cmds.ls(type=node_type) or []
    return [n for n in nodes if n != default_name]


def _is_locked(node):
    try:
        v = cmds.lockNode(node, query=True, lock=True)
        return bool(v[0]) if v else False
    except Exception:
        return False


def get_results():
    results = []

    for n in sorted(_layers("displayLayer", _DEFAULT_DISPLAY)):
        members = cmds.editDisplayLayerMembers(n, query=True, fullNames=True) or []
        details = ["Type: displayLayer", f"Members: {len(members)}"]
        if members:
            preview = members[:10]
            details.append("  " + ", ".join(preview))
            if len(members) > 10:
                details.append(f"  ... 他 {len(members) - 10} 件")
        if _is_locked(n):
            details.append("⚠ lockNode で保護されています（FIX 時に解除します）")
        results.append(CheckResult(
            target=n,
            message=f"displayLayer: {n}",
            details=details,
            severity=Severity.WARNING,
        ))

    for n in sorted(_layers("renderLayer", _DEFAULT_RENDER)):
        details = [
            "Type: renderLayer (legacy)",
            "⚠ FIX 対象外（Render Setup と整合しないため手動削除推奨）",
            "  Maya の Render Setup ウィンドウから削除してください",
        ]
        if _is_locked(n):
            details.append("⚠ lockNode で保護されています")
        results.append(CheckResult(
            target=n,
            message=f"renderLayer: {n} (FIX 不可)",
            details=details,
            severity=Severity.WARNING,
        ))

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[displayLayer] 該当ノードは見つかりませんでした。")
    else:
        print(f"[displayLayer] {len(res)} 件")
        for r in res:
            print(r.message)
