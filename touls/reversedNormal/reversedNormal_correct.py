# -*- coding: utf-8 -*-
"""
reversedNormal_correct.py
選択オブジェクトの反転フェースを検出し polyNormal(normalMode=0) でフリップする。
"""
import collections
import maya.cmds as cmds

MAX_FACES_PER_MESH = 50000


def _short_name(dag_path):
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _is_intermediate(shape):
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
    except Exception:
        return False


def _find_reversed_faces(shape):
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
                adj = edge_map.get((v2, v1))
                if adj is not None and adj not in visited:
                    (consistent if fi_c else reversed_set).add(adj)
                    visited.add(adj)
                    queue.append(adj)
                adj_r = edge_map.get((v1, v2))
                if adj_r is not None and adj_r != fi and adj_r not in visited:
                    (reversed_set if fi_c else consistent).add(adj_r)
                    visited.add(adj_r)
                    queue.append(adj_r)
        all_visited |= visited
        if len(reversed_set) <= len(consistent):
            total_reversed |= reversed_set
        else:
            total_reversed |= consistent

    return sorted(total_reversed)


def get_results():
    results = []
    sel = cmds.ls(sl=True, long=True) or []
    transforms = []
    for n in sel:
        if cmds.nodeType(n) == "transform":
            transforms.append(n)
        else:
            parents = cmds.listRelatives(n, parent=True, fullPath=True) or []
            transforms.extend(parents)
    seen = set()
    uniq = []
    for t in transforms:
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    for tr in uniq:
        shapes = cmds.listRelatives(tr, shapes=True, type="mesh", noIntermediate=True, fullPath=True) or []
        for shape in shapes:
            reversed_faces = _find_reversed_faces(shape)
            if not reversed_faces:
                results.append({"transform": _short_name(tr), "message": "反転フェースなし (スキップ)"})
                continue
            face_comps = [f"{shape}.f[{i}]" for i in reversed_faces]
            try:
                cmds.select(face_comps, r=True)
                cmds.polyNormal(normalMode=0, userNormalMode=0, ch=True)
                cmds.select(tr, r=True)
                results.append({
                    "transform": _short_name(tr),
                    "message": f"法線フリップ: {len(reversed_faces)} 面",
                })
            except Exception as e:
                results.append({
                    "transform": _short_name(tr),
                    "message": f"フリップ失敗: {e}",
                })
    return results


if __name__ == "__main__":
    for r in get_results():
        print(f'{r["transform"]}: {r["message"]}')
