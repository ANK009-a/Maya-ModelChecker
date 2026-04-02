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

import maya.cmds as cmds


SUFFIX = "Shape"


def _short_name(dag_path: str) -> str:
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _parent_transform(shape: str) -> str:
    p = cmds.listRelatives(shape, parent=True, fullPath=True) or []
    return p[0] if p else shape


def _is_intermediate(shape: str) -> bool:
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
    except Exception:
        return False


def _is_referenced(node: str) -> bool:
    try:
        return bool(cmds.referenceQuery(node, isNodeReferenced=True))
    except Exception:
        return False


def get_results():
    results = []

    shapes = cmds.ls(type="mesh", long=True) or []
    for shape in shapes:
        if not cmds.objExists(shape):
            continue
        if _is_intermediate(shape):
            continue

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
