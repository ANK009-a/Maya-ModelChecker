# -*- coding: utf-8 -*-
"""
reversedNormal_check.py
BFS flood-fill によりワインディングの一貫性をチェック。
各連結コンポーネントで「多数派と逆向き」のフェース群を反転フェースとして報告する。

アルゴリズム:
  隣接フェース間でエッジ方向を比較し、同じ向き = 反転と判定。
  各連結コンポーネントで少数派が「反転」。
"""
import collections
import maya.cmds as cmds
from _util import (
    iter_scene_mesh_shapes as _iter_shapes,
    short_name as _short_name,
)
from _results import CheckResult, Severity

MAX_FACES_PER_MESH = 50000  # これ以上の面数はスキップ
MAX_SHOW = 20


def _find_reversed_faces(shape):
    """BFS flood-fill で反転フェースのインデックスリストを返す"""
    try:
        import maya.api.OpenMaya as om2
    except ImportError:
        return []

    try:
        sel = om2.MSelectionList()
        sel.add(shape)
        dag = sel.getDagPath(0)
        fn = om2.MFnMesh(dag)
    except Exception:
        return []

    n_faces = fn.numPolygons
    if n_faces == 0 or n_faces > MAX_FACES_PER_MESH:
        return []

    # 全フェースの頂点インデックスを一括取得（per-face API 呼び出しを回避）
    face_counts, face_connects = fn.getVertices()
    face_verts_list = []
    offset = 0
    for cnt in face_counts:
        face_verts_list.append(list(face_connects[offset:offset + cnt]))
        offset += cnt

    # 有向エッジ (v1,v2) -> face_index のマップを構築
    edge_map = {}
    for fi, verts in enumerate(face_verts_list):
        n = len(verts)
        for j in range(n):
            edge_map[(verts[j], verts[(j + 1) % n])] = fi

    all_visited = set()
    total_reversed = set()

    for start_fi in range(n_faces):
        if start_fi in all_visited:
            continue

        consistent = {start_fi}
        reversed_set = set()
        visited = {start_fi}
        # deque を使い popleft() を O(1) に
        queue = collections.deque([start_fi])

        while queue:
            fi = queue.popleft()
            verts = face_verts_list[fi]
            fi_c = fi in consistent
            n = len(verts)

            for j in range(n):
                v1 = verts[j]
                v2 = verts[(j + 1) % n]

                # 逆エッジ (v2,v1) を持つ隣接フェース = ワインディング一致
                adj = edge_map.get((v2, v1))
                if adj is not None and adj not in visited:
                    (consistent if fi_c else reversed_set).add(adj)
                    visited.add(adj)
                    queue.append(adj)

                # 同エッジ (v1,v2) を持つ隣接フェース = ワインディング不一致 = 反転
                adj_r = edge_map.get((v1, v2))
                if adj_r is not None and adj_r != fi and adj_r not in visited:
                    (reversed_set if fi_c else consistent).add(adj_r)
                    visited.add(adj_r)
                    queue.append(adj_r)

        all_visited |= visited
        # 少数派が「反転」
        if len(reversed_set) <= len(consistent):
            total_reversed |= reversed_set
        else:
            total_reversed |= consistent

    return sorted(total_reversed)


def get_results():
    results = []
    shapes = _iter_shapes()
    for shape in shapes:
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        parent = parents[0] if parents else shape
        parent_short = _short_name(parent)

        n_faces = cmds.polyEvaluate(shape, f=True) or 0
        if n_faces > MAX_FACES_PER_MESH:
            results.append(CheckResult(
                target=parent,
                message=f"スキップ（フェース数 {n_faces} > {MAX_FACES_PER_MESH}）",
                details=["フェース数が多すぎます。Maya の Mesh > Cleanup を使用してください。"],
                severity=Severity.WARNING,
            ))
            continue

        reversed_faces = _find_reversed_faces(shape)
        if not reversed_faces:
            continue

        details = [
            f"反転フェース数: {len(reversed_faces)} / {n_faces}",
            f"サンプル (最大 {MAX_SHOW}):",
        ]
        for fi in reversed_faces[:MAX_SHOW]:
            details.append(f"  f[{fi}]")

        results.append(CheckResult(
            target=parent,
            message=f"法線反転フェース ({len(reversed_faces)} 面)",
            details=details,
            severity=Severity.ERROR,
        ))
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[reversedNormal] 反転フェースは見つかりませんでした。")
    else:
        for r in res:
            print(r.message)
