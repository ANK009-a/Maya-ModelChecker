# -*- coding: utf-8 -*-
"""
unusedShadingNode_fix.py
選択された未使用シェーディングノードを削除する。
既定ノード（lambert1 等）は安全のためスキップ。

assetChecker から呼ばれる際は _run_fix() が事前にチェック結果のノードを選択しているため、
ここでは current selection をそのまま削除対象として扱う。
"""
import maya.cmds as cmds


_DEFAULT_NAMES = {"lambert1", "particleCloud1", "shaderGlow1"}


def get_results():
    results = []
    sel = cmds.ls(sl=True) or []

    for n in sel:
        if not cmds.objExists(n):
            continue
        if n in _DEFAULT_NAMES:
            results.append({
                "transform": n,
                "message": f"スキップ: {n} はデフォルトノードです",
            })
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
