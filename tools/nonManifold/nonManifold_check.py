# -*- coding: utf-8 -*-
import maya.cmds as cmds
from _util import (
    iter_scene_mesh_shapes as _iter_shapes,
    short_name as _short_name,
)
from _results import CheckResult, Severity


def get_results():
    results = []
    shapes = _iter_shapes()
    for shape in shapes:
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
            results.append(CheckResult(
                target=parent,
                message=f"非マニフォールド検出 (edge:{len(nm_edges)}, vtx:{len(nm_verts)})",
                details=details,
                severity=Severity.ERROR,
            ))
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[nonManifold] 非マニフォールドジオメトリは見つかりませんでした。")
    else:
        for r in res:
            print(r.message)
