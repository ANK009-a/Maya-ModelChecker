# -*- coding: utf-8 -*-
"""
displayLayer_fix.py
選択された displayLayer / renderLayer を削除する。
defaultLayer / defaultRenderLayer は安全のためスキップ。
ロックされている場合は事前に lockNode -l 0 で解除する。

assetChecker から呼ばれる際は _run_fix() が事前にチェック結果のノードを選択しているため、
ここでは current selection をそのまま削除対象として扱う。
"""
import maya.cmds as cmds


_DEFAULTS = {"defaultLayer", "defaultRenderLayer"}
_VALID_TYPES = {"displayLayer", "renderLayer"}


def _is_locked(node):
    try:
        v = cmds.lockNode(node, query=True, lock=True)
        return bool(v[0]) if v else False
    except Exception:
        return False


def get_results():
    results = []
    sel = cmds.ls(sl=True) or []

    for n in sel:
        if not cmds.objExists(n):
            continue
        try:
            t = cmds.nodeType(n)
        except Exception:
            continue
        if t not in _VALID_TYPES:
            continue
        if n in _DEFAULTS:
            results.append({
                "transform": n,
                "message": f"スキップ: {n} はデフォルトレイヤーです",
            })
            continue
        try:
            if _is_locked(n):
                cmds.lockNode(n, lock=False)
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
