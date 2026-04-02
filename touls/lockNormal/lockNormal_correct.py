# lockNormal_correct.py
# 選択中オブジェクトの mesh に対して
# 「ロックされている法線（freeze normals / locked normals）」を解除し、
# UI（checkList）向けに get_results() で構造化結果を返す

import maya.cmds as cmds


# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------
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


def _locked_count(mesh_shape):
    """
    返り値: (locked_count:int, err:str|None)
    lockNormal_check.py と同じく freezeNormal query で数える
    """
    try:
        vals = cmds.polyNormalPerVertex(mesh_shape + ".vtx[*]", q=True, freezeNormal=True)
        if not vals:
            return 0, None

        locked = 0
        for v in vals:
            try:
                if bool(v):
                    locked += 1
            except Exception:
                pass

        return locked, None
    except Exception as e:
        return 0, str(e)


def _unfreeze(mesh_shape):
    """返り値: err:str|None"""
    try:
        cmds.polyNormalPerVertex(mesh_shape + ".vtx[*]", unFreezeNormal=True)
        return None
    except Exception as e:
        return str(e)


# ------------------------------------------------------------
# Entry points
# ------------------------------------------------------------
def get_results():
    """
    UI（checkList）から呼ばれる想定。
    解除を実行し、list[dict] を返す。
    - transform: グルーピング用
    - message: 右側詳細用
    """
    sel = cmds.ls(sl=True, long=True) or []
    transforms = _to_transforms(sel)

    if not transforms:
        return []

    results = []
    total_unfrozen = 0
    touched = 0

    for tr in transforms:
        shapes = _iter_mesh_shapes(tr)
        for shape in shapes:
            before, err = _locked_count(shape)
            if err:
                results.append({
                    "transform": tr,
                    "shape": shape,
                    "unfrozen_count": 0,
                    "message": f"[ERROR] {shape} : ロック状態の取得に失敗しました ({err})"
                })
                continue

            if before <= 0:
                continue  # ロックなしは表示しない（“解除した shape / 件数”に絞る）

            touched += 1

            err2 = _unfreeze(shape)
            if err2:
                results.append({
                    "transform": tr,
                    "shape": shape,
                    "unfrozen_count": 0,
                    "message": f"[ERROR] {shape} : 解除処理に失敗しました ({err2})"
                })
                continue

            after, err3 = _locked_count(shape)
            if err3:
                # 再確認できない場合は「解除を実行した」ことだけ返す
                total_unfrozen += before
                results.append({
                    "transform": tr,
                    "shape": shape,
                    "unfrozen_count": before,
                    "message": f"{shape} : ロック解除を実行（解除前 {before} / 解除後の再確認は失敗）"
                })
                continue

            unfrozen = max(0, before - after)
            total_unfrozen += unfrozen

            if after == 0:
                results.append({
                    "transform": tr,
                    "shape": shape,
                    "unfrozen_count": unfrozen,
                    "message": f"{shape} : ロック解除 {unfrozen}（解除前 {before}）"
                })
            else:
                results.append({
                    "transform": tr,
                    "shape": shape,
                    "unfrozen_count": unfrozen,
                    "message": f"{shape} : 部分的に解除 {unfrozen}（解除前 {before} → 解除後 {after}）"
                })

    return results


def correct():
    """互換用：従来の correct() でも動くようにしておく"""
    return get_results()


if __name__ == "__main__":
    # Script Editor から直接実行した場合はメッセージを出す
    for r in get_results():
        print(r.get("message", ""))
