# lockNormal_fix.py
# 選択中オブジェクトの mesh に対して
# 「ロックされている法線（freeze normals / locked normals）」を解除する。
# OpenMaya API を優先し、失敗時は cmds フォールバック。

import maya.cmds as cmds

try:
    import maya.api.OpenMaya as om2
except Exception:
    om2 = None


def _to_transforms(selection):
    """shape が選ばれても transform に正規化（重複除去・順序維持）"""
    transforms = []
    for n in selection:
        if not cmds.objExists(n):
            continue
        if cmds.nodeType(n) == "transform":
            transforms.append(n)
        else:
            parents = cmds.listRelatives(n, parent=True, fullPath=True) or []
            transforms.extend([p for p in parents if cmds.nodeType(p) == "transform"])
    seen = set()
    uniq = []
    for t in transforms:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def _iter_mesh_shapes(transform):
    """transform 配下の mesh shape（中間オブジェクト除外）"""
    shapes = cmds.listRelatives(transform, shapes=True, fullPath=True) or []
    return [
        s for s in shapes
        if cmds.nodeType(s) == "mesh"
        and not cmds.getAttr(s + ".intermediateObject")
    ]


def _has_locked_normals(shape):
    """ロック法線が存在するか。API 優先 → cmds フォールバック"""
    if om2:
        try:
            sel = om2.MSelectionList()
            sel.add(shape)
            fn = om2.MFnMesh(sel.getDagPath(0))
            for i in range(fn.numNormals):
                if fn.isNormalLocked(i):
                    return True
            return False
        except Exception:
            pass
    # cmds フォールバック
    try:
        vals = cmds.polyNormalPerVertex(shape + ".vtx[*]", q=True, freezeNormal=True) or []
        return any(bool(v) for v in vals)
    except Exception:
        return False


def _unfreeze_normals(shape):
    """法線ロック解除: API 優先 → cmds フォールバック。エラー文字列 or None を返す"""
    if om2:
        try:
            sel = om2.MSelectionList()
            sel.add(shape)
            fn = om2.MFnMesh(sel.getDagPath(0))
            fn.unlockVertexNormals(om2.MIntArray(range(fn.numVertices)))
            return None
        except Exception:
            pass
    try:
        cmds.polyNormalPerVertex(shape + ".vtx[*]", unFreezeNormal=True)
        return None
    except Exception as e:
        return str(e)


def get_results():
    sel = cmds.ls(sl=True, long=True) or []
    transforms = _to_transforms(sel)
    if not transforms:
        return []

    results = []
    for tr in transforms:
        for shape in _iter_mesh_shapes(tr):
            if not _has_locked_normals(shape):
                continue
            err = _unfreeze_normals(shape)
            if err:
                results.append({
                    "transform": tr,
                    "message": f"[ERROR] {shape}: ロック解除に失敗 ({err})",
                })
            else:
                results.append({
                    "transform": tr,
                    "message": f"{shape}: ロック解除を実行",
                })
    return results


if __name__ == "__main__":
    for r in get_results():
        print(r.get("message", ""))
