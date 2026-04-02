# -*- coding: utf-8 -*-
"""
reversedNormal_check.py
BFS flood-fill によりワインディングの一貫性をチェック。
各連結コンポーネントで「多数派と逆向き」のフェース群を反転フェースとして報告する。

アルゴリズム:
  隣接フェース間でエッジ方向を比較し、同じ向き = 反転と判定。
  各連結コンポーネントで少数派が「反転」。
"""
import maya.cmds as cmds

MAX_FACES_PER_MESH = 50000  # これ以上の面数はスキップ
MAX_SHOW = 20


def _short_name(dag_path):
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _is_intermediate(shape):
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
    except Exception:
        return False


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

    # 有向エッジ (v1,v2) -> face_index のマップを構築
    edge_map = {}
    face_verts_list = []
    for fi in range(n_faces):
        verts = list(fn.getPolygonVertices(fi))
        face_verts_list.append(verts)
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
        queue = [start_fi]

        while queue:
            fi = queue.pop(0)
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
    shapes = cmds.ls(type="mesh", long=True) or []
    for shape in shapes:
        if not cmds.objExists(shape):
            continue
        if _is_intermediate(shape):
            continue
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        parent = parents[0] if parents else shape
        parent_short = _short_name(parent)

        n_faces = cmds.polyEvaluate(shape, f=True) or 0
        if n_faces > MAX_FACES_PER_MESH:
            results.append({
                "transform": parent_short,
                "message": f"スキップ（フェース数 {n_faces} > {MAX_FACES_PER_MESH}）: {parent_short}",
                "details": ["フェース数が多すぎます。Maya の Mesh > Cleanup を使用してください。"],
            })
            continue

        reversed_faces = _find_reversed_faces(shape)
        if not reversed_faces:
            continue

        details = [
            f"反転フェース数: {len(reversed_faces)} / {n_faces}",
            f"Shape: {shape}",
            f"サンプル (最大 {MAX_SHOW}):",
        ]
        for fi in reversed_faces[:MAX_SHOW]:
            details.append(f"  f[{fi}]")

        results.append({
            "transform": parent_short,
            "message": f"法線反転フェース: {parent_short} ({len(reversed_faces)} 面)",
            "details": details,
        })
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[reversedNormal] 反転フェースは見つかりませんでした。")
    else:
        for r in res:
            print(r["message"])
