# -*- coding: utf-8 -*-
"""
isolateVtx_check.py

check処理:
シーン内の mesh で「どこの edge にも属していない vertex（孤立頂点）」を持つものをリストします（選択不要）

定義:
- edge が 1 本も接続していない vertex
  (Maya API の MItMeshVertex.getConnectedEdges() が空)

checkList.py 連携想定:
- get_results() が list[dict] を返す（問題なければ []）
"""

import maya.cmds as cmds

try:
    import maya.api.OpenMaya as om2
except Exception:
    om2 = None

MAX_SHOW = 50


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


def _get_dag_path(node: str):
    sel = om2.MSelectionList()
    sel.add(node)
    return sel.getDagPath(0)


def get_results():
    results = []

    # OpenMaya が使えないなら、この判定は確実にできないので何もしない
    if om2 is None:
        return results

    shapes = cmds.ls(type="mesh", long=True) or []
    for shape in shapes:
        if not cmds.objExists(shape):
            continue
        if _is_intermediate(shape):
            continue

        parent = _parent_transform(shape)
        if _is_referenced(shape) or _is_referenced(parent):
            continue

        try:
            dag = _get_dag_path(shape)
            fn = om2.MFnMesh(dag)
            # フェースに属する全頂点インデックスを一括取得し、接続済み頂点の set を構築
            _, face_connects = fn.getVertices()
            connected = set(face_connects)
            isolated = [i for i in range(fn.numVertices) if i not in connected]
        except Exception:
            continue

        if not isolated:
            continue

        parent_short = _short_name(parent)
        shape_short = _short_name(shape)

        details = [
            f"Shape: {shape}",
            f"Isolated vertex count: {len(isolated)}",
            "Samples:",
            "  - " + ", ".join(f"vtx[{i}]" for i in isolated[:MAX_SHOW]),
        ]
        if len(isolated) > MAX_SHOW:
            details.append(f"  ... (+{len(isolated) - MAX_SHOW})")

        results.append({
            "transform": parent_short,
            "message": f"孤立頂点あり: {parent_short} / {shape_short}（{len(isolated)} vtx）",
            "details": details,
        })

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[isolateVtx] 孤立頂点を持つ mesh は見つかりませんでした。")
    else:
        print(f"[isolateVtx] 孤立頂点あり: {len(res)} 件")
        for r in res:
            print(r["message"])
            for line in r.get("details", []):
                print("  - " + line)
