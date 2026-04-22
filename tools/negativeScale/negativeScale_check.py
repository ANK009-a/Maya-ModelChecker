# -*- coding: utf-8 -*-
"""
negativeScale_check.py
mesh を持つ transform のスケール値がマイナスのものを検出する。
ミラー操作後に残りやすく、Unity / VRChat でメッシュが裏返って見える原因になる。
"""
import maya.cmds as cmds
from _util import (
    iter_scene_mesh_shapes as _iter_shapes,
    short_name as _short_name,
)

TOL = 1e-6


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

        try:
            s = cmds.getAttr(f"{parent}.scale")[0]
        except Exception:
            continue

        neg = [axis for axis, val in zip("XYZ", s) if val < -TOL]
        if neg:
            results.append({
                "transform": parent,
                "message": (
                    f"マイナススケール: {parent_short} "
                    f"({s[0]:.3f}, {s[1]:.3f}, {s[2]:.3f}) 軸:{', '.join(neg)}"
                ),
                "details": [
                    f"scaleX: {s[0]:.6f}",
                    f"scaleY: {s[1]:.6f}",
                    f"scaleZ: {s[2]:.6f}",
                    f"マイナス軸: {', '.join(neg)}",
                    "修正: correct ボタンで makeIdentity(scale) + 法線反転を実行",
                ],
            })
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[negativeScale] マイナススケールは見つかりませんでした。")
    else:
        for r in res:
            print(r["message"])
