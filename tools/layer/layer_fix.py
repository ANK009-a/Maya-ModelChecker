# -*- coding: utf-8 -*-
"""
layer_fix.py
選択されたレイヤーノードを削除する。

- animLayer: そのまま削除。BaseAnimation 削除で配下も連鎖削除されるため、
  既に存在しないノードはスキップ。
- displayLayer: ロックされている場合は解除してから削除。defaultLayer はスキップ。
- renderLayer: FIX 対象外。renderSetup が renderLayer への参照を持つため
  cmds.delete で直接削除するとエラーになる。Render Setup ウィンドウから削除すること。

assetChecker から呼ばれる際は _run_fix() が事前にチェック結果のノードを選択しているため、
ここでは current selection をそのまま削除対象として扱う。
"""
import maya.cmds as cmds


_DEFAULTS = {"defaultLayer", "defaultRenderLayer"}


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
            results.append({
                "transform": n,
                "message": f"スキップ: {n} は既に削除済み（連鎖削除）",
            })
            continue

        try:
            t = cmds.nodeType(n)
        except Exception:
            continue

        if t == "renderLayer":
            results.append({
                "transform": n,
                "message": f"スキップ: {n} は renderLayer のため FIX 対象外（Render Setup ウィンドウから削除してください）",
            })
            continue

        if t not in ("animLayer", "displayLayer"):
            continue

        if n in _DEFAULTS:
            results.append({
                "transform": n,
                "message": f"スキップ: {n} はデフォルトレイヤーです",
            })
            continue

        try:
            if t == "displayLayer" and _is_locked(n):
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
