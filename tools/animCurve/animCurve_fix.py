# -*- coding: utf-8 -*-
"""
animCurve_fix.py
選択された animCurve ノードを削除する。

assetChecker から呼ばれる際は _run_fix() が事前にチェック結果のノードを選択しているため、
ここでは current selection をそのまま削除対象として扱う。
"""
import maya.cmds as cmds


_ANIM_CURVE_PREFIX = "animCurve"


def _is_anim_curve(node):
    try:
        t = cmds.nodeType(node)
    except Exception:
        return False
    return t.startswith(_ANIM_CURVE_PREFIX) and t != "animLayer"


def get_results():
    results = []
    sel = cmds.ls(sl=True) or []

    for n in sel:
        if not cmds.objExists(n):
            continue
        if not _is_anim_curve(n):
            continue
        try:
            t = cmds.nodeType(n)
            cmds.delete(n)
            results.append({
                "transform": n,
                "message": f"削除: {n} ({t})",
            })
        except Exception as e:
            results.append({
                "transform": n,
                "message": f"削除失敗: {e}",
            })

    return results


if __name__ == "__main__":
    for r in get_results():
        print(f'{r["transform"]}: {r["message"]}')
