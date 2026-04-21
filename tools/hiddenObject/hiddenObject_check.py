# -*- coding: utf-8 -*-
"""
hiddenObject_check.py
visibility=False になっている mesh の親 transform を検出する。
意図せず残った非表示メッシュはエクスポートやランタイムで問題になることがある。
"""
import maya.cmds as cmds
from _util import (
    iter_scene_mesh_shapes as _iter_shapes,
    short_name as _short_name,
)


def _is_hidden(transform):
    """直接の visibility または親チェーンに非表示があるか確認"""
    try:
        if not cmds.getAttr(f"{transform}.visibility"):
            return True
        # 1階層上の親まで確認（深い階層の追跡は過剰なため）
        parents = cmds.listRelatives(transform, parent=True, fullPath=True) or []
        for p in parents:
            if not cmds.getAttr(f"{p}.visibility"):
                return True
    except Exception:
        pass
    return False


def get_results():
    results = []
    shapes = _iter_shapes()
    seen = set()
    for shape in shapes:
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        if not parents:
            continue
        parent = parents[0]
        if parent in seen:
            continue
        seen.add(parent)
        parent_short = _short_name(parent)

        if _is_hidden(parent):
            try:
                vis = cmds.getAttr(f"{parent}.visibility")
            except Exception:
                vis = "不明"
            results.append({
                "transform": parent_short,
                "message": f"非表示オブジェクト: {parent_short}",
                "details": [
                    f"visibility: {vis}",
                    "correct で表示状態に戻す（削除はユーザーが判断してください）",
                ],
            })
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[hiddenObject] 非表示メッシュは見つかりませんでした。")
    else:
        for r in res:
            print(r["message"])
