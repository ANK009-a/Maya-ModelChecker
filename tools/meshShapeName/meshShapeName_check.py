# -*- coding: utf-8 -*-
"""
meshShapeName_check.py

check:
シーン内の non-intermediate mesh shape で、
「親 transform の短名 + 'Shape'」になっていない shape をリストします。

例:
transform: body_geo
expected shape short name: body_geoShape
"""

from _util import (
    iter_scene_mesh_shapes as _iter_shapes,
    short_name as _short_name,
    parent_transform as _parent_transform,
    is_referenced as _is_referenced,
)

SUFFIX = "Shape"


def get_results():
    results = []

    shapes = _iter_shapes()
    for shape in shapes:
        parent = _parent_transform(shape)
        if _is_referenced(shape) or _is_referenced(parent):
            continue

        parent_short = _short_name(parent)
        shape_short = _short_name(shape)
        expected = f"{parent_short}{SUFFIX}"

        if shape_short == expected:
            continue

        results.append({
            "transform": parent_short,
            "message": f"Shape名不一致: {parent_short} / {shape_short}（expected: {expected}）",
            "details": [
                f"Transform: {parent}",
                f"Shape: {shape}",
                f"Expected(short): {expected}",
            ],
        })

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[meshShapeName] 問題なし（全shapeが <transform>Shape です）")
    else:
        print(f"[meshShapeName] 不一致 {len(res)} 件")
        for r in res:
            print(r["message"])
            for line in r.get("details", []):
                print("  - " + line)
