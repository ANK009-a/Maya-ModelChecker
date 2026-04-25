# vtxTweak_fix.py
# pnts オフセットを mesh の vrts に直接加算して pnts を 0 化する。
# ヒストリー（コンストラクションヒストリー / デフォーマーチェーン）には一切触らないため、
# skinCluster / blendShape / cluster などのデフォーマーがまったく影響を受けない。
#
# 仕組み:
#   visible 頂点位置 = vrts[i] + pnts[i]
#   → vrts[i] := vrts[i] + pnts[i] ; pnts[i] := 0
#   とすれば見た目は変わらず pnts を消せる。
#
# 注意:
#   shape の inMesh が deformer 等で上書きされている場合、vrts への書き込みは
#   評価時に上書きされて反映されないことがある。その場合は別途
#   bakePartialHistory 等のヒストリー操作が必要。

import maya.cmds as cmds

TOL = 1e-9


def _collect_mesh_transforms(selected_only=True):
    targets = cmds.ls(sl=True, type="transform", long=True) if selected_only else cmds.ls(type="transform", long=True)
    if not targets:
        return []
    mesh_transforms = []
    for t in targets:
        if not cmds.objExists(t):
            continue
        shapes = cmds.listRelatives(t, s=True, ni=True, type="mesh", fullPath=True) or []
        if shapes:
            mesh_transforms.append(t)
    return mesh_transforms


def _bake_pnts_for_shape(shape):
    """
    shape の pnts を vrts に焼き込み、pnts を 0 化する。
    Returns:
        (baked_count, skipped_count)
        baked_count: 焼き込みに成功した頂点数
        skipped_count: 書き込みエラー等で焼けなかった頂点数
    """
    try:
        indices = cmds.getAttr(f"{shape}.pnts", multiIndices=True) or []
    except Exception:
        return 0, 0

    baked = 0
    skipped = 0
    for i in indices:
        try:
            pnts_val = cmds.getAttr(f"{shape}.pnts[{i}]")[0]
        except Exception:
            skipped += 1
            continue

        if not any(abs(v) > TOL for v in pnts_val):
            continue

        try:
            vrts_val = cmds.getAttr(f"{shape}.vrts[{i}]")[0]
            new_pos = (
                vrts_val[0] + pnts_val[0],
                vrts_val[1] + pnts_val[1],
                vrts_val[2] + pnts_val[2],
            )
            cmds.setAttr(f"{shape}.vrts[{i}]", *new_pos)
            cmds.setAttr(f"{shape}.pnts[{i}]", 0.0, 0.0, 0.0, type="double3")
            baked += 1
        except Exception:
            skipped += 1
            continue

    return baked, skipped


def fix(selected_only=True):
    results = []

    mesh_transforms = _collect_mesh_transforms(selected_only=selected_only)
    if not mesh_transforms:
        cmds.warning("mesh を持つ transform が選択されていません。")
        return results

    prev_sel = cmds.ls(sl=True, long=True) or []

    try:
        for t in mesh_transforms:
            shapes = cmds.listRelatives(t, s=True, ni=True, type="mesh", fullPath=True) or []
            total_baked = 0
            total_skipped = 0
            for shape in shapes:
                b, s = _bake_pnts_for_shape(shape)
                total_baked += b
                total_skipped += s

            if total_baked == 0 and total_skipped == 0:
                continue

            if total_skipped == 0:
                results.append({
                    "transform": t,
                    "message": f"{total_baked} 頂点の pnts を焼き込みました（ヒストリー保持）",
                    "ok": True,
                })
            else:
                results.append({
                    "transform": t,
                    "message": f"{total_baked} 頂点を焼き込み / {total_skipped} 頂点で書き込み失敗",
                    "ok": total_baked > 0,
                })
    finally:
        try:
            if prev_sel:
                cmds.select(prev_sel, r=True)
            else:
                cmds.select(clear=True)
        except Exception:
            pass

    return results


def get_results():
    """
    checkList.py の run_py_get_structured_or_text() が優先的に呼ぶ入口
    """
    return fix(selected_only=True)
