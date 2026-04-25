# -*- coding: utf-8 -*-
"""
displayLayer_fix.py
選択された displayLayer を削除する。
defaultLayer は安全のためスキップ。
ロックされている場合は事前に lockNode -l 0 で解除する。

renderLayer は Render Setup の管理下にあり、cmds.delete でも UI 上に残ることが
あるため FIX 対象外。手動で Render Setup ウィンドウから削除する必要がある。

assetChecker から呼ばれる際は _run_fix() が事前にチェック結果のノードを選択しているため、
ここでは current selection をそのまま削除対象として扱う。
"""
import maya.cmds as cmds


_DEFAULTS = {"defaultLayer", "defaultRenderLayer"}
# renderLayer は Render Setup との整合性が取れない（cmds.delete でも UI 上に残る）ため
# FIX 対象は displayLayer のみとする。renderLayer は手動削除を促す。
_VALID_TYPES = {"displayLayer"}


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
        if t == "renderLayer":
            results.append({
                "transform": n,
                "message": f"スキップ: {n} は renderLayer のため FIX 対象外（Render Setup ウィンドウから手動削除してください）",
            })
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
