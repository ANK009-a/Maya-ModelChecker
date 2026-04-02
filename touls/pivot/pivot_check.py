# -*- coding: utf-8 -*-
"""
pivot_check_allScene_shortName_nodup.py

- 選択判定なし：常にシーン内の mesh shape を全件対象
- mesh の親 transform の rotatePivot / scalePivot がワールド原点(0,0,0)からズレているものを返す
- 一覧（中央）は transform 短名に統一
- ★assetChecker側で message が details に混ざるため、details を付けず重複表示を防止
"""

import maya.cmds as cmds
from _util import iter_scene_mesh_shapes as _iter_scene_mesh_shapes

TOLERANCE = 1e-6  # 許容誤差（必要なら 1e-4 などに）


def _is_not_origin(pos, tol=TOLERANCE):
    return (abs(pos[0]) > tol) or (abs(pos[1]) > tol) or (abs(pos[2]) > tol)


def _short_name(dag_path: str) -> str:
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _mesh_parent_transforms():
    """シーン内 mesh shape の親 transform を重複なしで返す（順序保持）"""
    transforms = []
    for shape in _iter_scene_mesh_shapes():
        if not cmds.objExists(shape):
            continue
        try:
            p = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            if p and cmds.nodeType(p[0]) == "transform":
                transforms.append(p[0])
        except Exception:
            pass

    seen = set()
    uniq = []
    for t in transforms:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def get_results():
    results = []

    transforms = _mesh_parent_transforms()
    if not transforms:
        return results

    for tr in transforms:
        tr_short = _short_name(tr)
        try:
            rp = cmds.xform(tr, q=True, ws=True, rp=True)  # [x, y, z]
            sp = cmds.xform(tr, q=True, ws=True, sp=True)

            bad_rp = _is_not_origin(rp)
            bad_sp = _is_not_origin(sp)

            if not (bad_rp or bad_sp):
                continue

            msg_parts = []
            if bad_rp:
                msg_parts.append(f"RotatePivot: ({rp[0]:.6f}, {rp[1]:.6f}, {rp[2]:.6f})")
            if bad_sp:
                msg_parts.append(f"ScalePivot: ({sp[0]:.6f}, {sp[1]:.6f}, {sp[2]:.6f})")

            results.append({
                "transform": tr_short,
                "message": " / ".join(msg_parts),
                # details は付けない（重複表示防止）
            })

        except Exception as e:
            results.append({
                "transform": tr_short,
                "message": f"Pivot取得エラー: {e}"
            })

    return results


if __name__ == "__main__":
    for item in get_results():
        print(f'{item.get("transform")} : {item.get("message")}')
