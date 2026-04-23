# -*- coding: utf-8 -*-
"""
animationKey_fix.py
選択されたアニメーション系ノード（animCurve* / animLayer）を削除する。

assetChecker から呼ばれる際は _run_fix() が事前にチェック結果のノードを選択しているため、
ここでは current selection をそのまま削除対象として扱う。
"""
import maya.cmds as cmds


_ANIM_CURVE_PREFIX = "animCurve"


def _is_anim_target(node):
    """animCurve* もしくは animLayer であれば True。"""
    try:
        t = cmds.nodeType(node)
    except Exception:
        return False
    return t == "animLayer" or t.startswith(_ANIM_CURVE_PREFIX)


def get_results():
    results = []
    sel = cmds.ls(sl=True) or []

    # animLayer の削除は配下 animLayer を巻き込むので、先に animCurve → 後に animLayer の順に処理する
    curves = []
    layers = []
    for n in sel:
        if not cmds.objExists(n):
            continue
        if not _is_anim_target(n):
            continue
        if cmds.nodeType(n) == "animLayer":
            layers.append(n)
        else:
            curves.append(n)

    # animCurve を先に削除
    for n in curves:
        try:
            cmds.delete(n)
            results.append({
                "transform": n,
                "message": f"削除: {n} (animCurve)",
            })
        except Exception as e:
            results.append({
                "transform": n,
                "message": f"削除失敗: {e}",
            })

    # animLayer を削除（BaseAnimation を含む）
    # BaseAnimation を削除すると配下も消えるので、削除後に存在しないものはスキップ
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
