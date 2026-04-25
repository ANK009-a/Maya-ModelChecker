# vtxTweak_fix.py
# tweak（pnts オフセット）のみを焼き込み、skinCluster / blendShape / cluster などの
# デフォーマーはそのまま残す。
# 内部的には Maya の "Edit > Delete by Type > Non-Deformer History" 相当
# （cmds.bakePartialHistory(prePostDeformers=True)）を使う。

import maya.cmds as cmds


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


def fix(selected_only=True):
    """
    tweak（pnts）だけを焼き込み、デフォーマーは保持する。
    Returns:
        list[dict]: 構造化結果
    """
    results = []

    mesh_transforms = _collect_mesh_transforms(selected_only=selected_only)
    if not mesh_transforms:
        cmds.warning("mesh を持つ transform が選択されていません。")
        return results

    prev_sel = cmds.ls(sl=True, long=True) or []

    try:
        for t in mesh_transforms:
            try:
                # prePostDeformers=True で tweak / polyTweak など
                # デフォーマー前後の履歴のみを焼き込む（skinCluster 等は保持）
                cmds.bakePartialHistory(t, prePostDeformers=True)
                results.append({
                    "transform": t,
                    "message": "tweak を焼き込みました（デフォーマー保持）",
                    "ok": True,
                })
            except Exception as e:
                results.append({
                    "transform": t,
                    "message": f"bakePartialHistory に失敗: {e}",
                    "ok": False,
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
