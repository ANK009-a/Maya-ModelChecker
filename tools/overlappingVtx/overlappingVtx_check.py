# -*- coding: utf-8 -*-
"""
overlappingVtx_check.py
同じ位置（閾値以内）に存在する頂点を検出する。
グリッドハッシュを使い、効率的に近傍を検索する。
"""
import maya.cmds as cmds
from _util import (
    iter_scene_mesh_shapes as _iter_shapes,
    short_name as _short_name,
)
from _results import CheckResult, Severity

THRESHOLD = 0.0001   # 重複判定距離（ワールド単位）
MAX_SHOW = 30
MAX_VERTS = 100000   # これ以上の頂点数はスキップ


def _find_overlapping_verts(shape, threshold=THRESHOLD):
    try:
        import maya.api.OpenMaya as om2
        sel = om2.MSelectionList()
        sel.add(shape)
        dag = sel.getDagPath(0)
        fn = om2.MFnMesh(dag)
        points = fn.getPoints(om2.MSpace.kWorld)
    except Exception:
        return []

    n = len(points)
    if n == 0 or n > MAX_VERTS:
        return []

    # グリッドハッシュで近傍候補を絞り込む
    cell = threshold * 2.0
    grid = {}
    for i, p in enumerate(points):
        key = (int(p.x / cell), int(p.y / cell), int(p.z / cell))
        grid.setdefault(key, []).append(i)

    overlapping = set()
    thr2 = threshold * threshold
    for i, p in enumerate(points):
        if i in overlapping:
            continue
        cx = int(p.x / cell)
        cy = int(p.y / cell)
        cz = int(p.z / cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in grid.get((cx + dx, cy + dy, cz + dz), []):
                        if j <= i:
                            continue
                        q = points[j]
                        d2 = (p.x - q.x) ** 2 + (p.y - q.y) ** 2 + (p.z - q.z) ** 2
                        if d2 < thr2:
                            overlapping.add(i)
                            overlapping.add(j)
    return sorted(overlapping)


def get_results():
    results = []
    shapes = _iter_shapes()
    for shape in shapes:
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        parent = parents[0] if parents else shape
        parent_short = _short_name(parent)

        n_verts = cmds.polyEvaluate(shape, v=True) or 0
        if n_verts > MAX_VERTS:
            continue

        overlapping = _find_overlapping_verts(shape)
        if not overlapping:
            continue

        details = [
            f"重複頂点数: {len(overlapping)} 個",
            f"閾値: {THRESHOLD}",
            f"サンプル (最大 {MAX_SHOW}):",
        ]
        for vi in overlapping[:MAX_SHOW]:
            details.append(f"  vtx[{vi}]")

        results.append(CheckResult(
            target=parent,
            message=f"重複頂点 ({len(overlapping)} 個)",
            details=details,
            severity=Severity.ERROR,
        ))
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[overlappingVtx] 重複頂点は見つかりませんでした。")
    else:
        for r in res:
            print(r.message)
