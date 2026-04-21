# -*- coding: utf-8 -*-
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

        lamina = cmds.polyInfo(shape, laminaFaces=True) or []
        if lamina:
            details = [f"ラミナフェース数: {len(lamina)} 件"]
            for line in lamina[:15]:
                details.append(f"  {line.strip()}")
            results.append({
                "transform": parent_short,
                "message": f"ラミナフェース: {parent_short} ({len(lamina)} 面)",
                "details": details,
            })
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[laminaFace] ラミナフェースは見つかりませんでした。")
    else:
        for r in res:
            print(r["message"])
