# -*- coding: utf-8 -*-
"""
animLayer_fix.py
選択された animLayer ノードを削除する。

assetChecker から呼ばれる際は _run_fix() が事前にチェック結果のノードを選択しているため、
ここでは current selection をそのまま削除対象として扱う。

BaseAnimation を削除すると配下の animLayer も連鎖削除されるため、
削除後に存在しないノードはスキップする。
"""
import maya.cmds as cmds


def _is_anim_layer(node):
    try:
        return cmds.nodeType(node) == "animLayer"
    except Exception:
        return False


def get_results():
    results = []
    sel = cmds.ls(sl=True) or []

    layers = [n for n in sel if cmds.objExists(n) and _is_anim_layer(n)]

    for n in layers:
        if not cmds.objExists(n):
            results.append({
                "transform": n,
                "message": f"スキップ: {n} は既に削除済み（親 animLayer と連鎖削除）",
            })
            continue
        try:
            cmds.delete(n)
            results.append({
                "transform": n,
                "message": f"削除: {n} (animLayer)",
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
