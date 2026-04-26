# -*- coding: utf-8 -*-
"""
autoNode_fix.py
選択された自動生成ノードを削除する。
ロックされている場合は解除してから削除。

assetChecker から呼ばれる際は _run_fix() が事前にチェック結果のノードを選択しているため、
ここでは current selection をそのまま削除対象として扱う。
"""
import maya.cmds as cmds


def get_results():
    results = []
    sel = cmds.ls(sl=True) or []

    for n in sel:
        if not cmds.objExists(n):
            results.append({
                "transform": n,
                "message": f"スキップ: {n} は既に削除済み",
            })
            continue
        try:
            locked = cmds.lockNode(n, query=True, lock=True)
            if locked and locked[0]:
                cmds.lockNode(n, lock=False)
            cmds.delete(n)
            results.append({
                "transform": n,
                "message": f"削除: {n}",
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
