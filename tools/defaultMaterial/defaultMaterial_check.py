# -*- coding: utf-8 -*-
"""
defaultMaterial_check.py
initialShadingGroup（デフォルトの lambert1）のみが割り当てられている mesh を検出する。
Unity / VRChat ではマテリアル未設定のメッシュが意図しない表示になる原因になる。
"""
import maya.cmds as cmds


def _short_name(dag_path):
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _is_intermediate(shape):
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
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
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        parent = parents[0] if parents else shape
        parent_short = _short_name(parent)

        sgs = cmds.listSets(object=shape, type=1) or []

        if not sgs:
            results.append({
                "transform": parent_short,
                "message": f"マテリアル未割り当て: {parent_short}",
                "details": ["シェーディンググループへの割り当てがありません"],
            })
        elif all(sg == "initialShadingGroup" for sg in sgs):
            results.append({
                "transform": parent_short,
                "message": f"デフォルトマテリアル (lambert1): {parent_short}",
                "details": [f"シェーディンググループ: {', '.join(sgs)}"],
            })
        elif "initialShadingGroup" in sgs:
            others = [sg for sg in sgs if sg != "initialShadingGroup"]
            results.append({
                "transform": parent_short,
                "message": f"一部デフォルトマテリアル: {parent_short}",
                "details": [
                    "一部フェースが initialShadingGroup に属しています",
                    f"カスタム SG: {', '.join(others)}",
                ],
            })
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[defaultMaterial] デフォルトマテリアルの問題は見つかりませんでした。")
    else:
        for r in res:
            print(r["message"])
