# -*- coding: utf-8 -*-
"""
unknownNode_fix.py

選択された unknown ノードを削除し、シーンに残っている未ロードプラグイン参照を一括削除する。

unknown ノードはロックされている場合があるため、削除前に lockNode -l 0 で解除する。
プラグイン参照は Maya ノードではないため selection には乗らない。よって
cmds.unknownPlugin(query=True, list=True) で取得し、すべて remove する。
"""
import maya.cmds as cmds


_UNKNOWN_TYPES = {"unknown", "unknownDag", "unknownTransform"}


def _is_locked(node):
    try:
        v = cmds.lockNode(node, query=True, lock=True)
        return bool(v[0]) if v else False
    except Exception:
        return False


def get_results():
    results = []

    sel = cmds.ls(sl=True, long=True) or []
    for n in sel:
        if not cmds.objExists(n):
            continue
        try:
            t = cmds.nodeType(n)
        except Exception:
            continue
        if t not in _UNKNOWN_TYPES:
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

    plugins = cmds.unknownPlugin(query=True, list=True) or []
    for p in plugins:
        try:
            cmds.unknownPlugin(p, remove=True)
            results.append({
                "transform": p,
                "message": f"プラグイン参照を削除: {p}",
            })
        except Exception as e:
            results.append({
                "transform": p,
                "message": f"プラグイン参照の削除失敗 ({p}): {e}",
            })

    return results


if __name__ == "__main__":
    for r in get_results():
        print(f'{r["transform"]}: {r["message"]}')
