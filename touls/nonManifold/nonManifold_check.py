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

        nm_edges = cmds.polyInfo(shape, nonManifoldEdges=True) or []
        nm_verts = cmds.polyInfo(shape, nonManifoldVertices=True) or []

        if nm_edges or nm_verts:
            details = []
            if nm_edges:
                details.append(f"非マニフォールドエッジ: {len(nm_edges)} 件")
                for line in nm_edges[:10]:
                    details.append(f"  {line.strip()}")
            if nm_verts:
                details.append(f"非マニフォールド頂点: {len(nm_verts)} 件")
                for line in nm_verts[:10]:
                    details.append(f"  {line.strip()}")
            results.append({
                "transform": parent_short,
                "message": f"非マニフォールド検出: {parent_short} (edge:{len(nm_edges)}, vtx:{len(nm_verts)})",
                "details": details,
            })
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[nonManifold] 非マニフォールドジオメトリは見つかりませんでした。")
    else:
        for r in res:
            print(r["message"])
