# -*- coding: utf-8 -*-
"""
pivot_check.py

- mesh の親 transform の rotatePivot / scalePivot がワールド原点(0,0,0)からズレているものを返す
- ただしピボットがメッシュの bounding box 内にある場合はスキップ（目など意図的なケース）
- 常にシーン内の mesh shape を全件対象
"""

import maya.cmds as cmds
from _util import iter_unique_mesh_parents as _iter_unique_mesh_parents
from _results import CheckResult, Severity

TOLERANCE = 1e-6
BBOX_PAD  = 1e-4  # bbox 境界の許容マージン


def _is_not_origin(pos, tol=TOLERANCE):
    return (abs(pos[0]) > tol) or (abs(pos[1]) > tol) or (abs(pos[2]) > tol)


def _is_inside_bbox(pos, bbox):
    xmin, ymin, zmin, xmax, ymax, zmax = bbox
    return (
        xmin - BBOX_PAD <= pos[0] <= xmax + BBOX_PAD and
        ymin - BBOX_PAD <= pos[1] <= ymax + BBOX_PAD and
        zmin - BBOX_PAD <= pos[2] <= zmax + BBOX_PAD
    )


def get_results():
    results = []

    transforms = _iter_unique_mesh_parents()
    if not transforms:
        return results

    for tr in transforms:
        try:
            rp = cmds.xform(tr, q=True, ws=True, rp=True)
            sp = cmds.xform(tr, q=True, ws=True, sp=True)

            bad_rp = _is_not_origin(rp)
            bad_sp = _is_not_origin(sp)

            if not (bad_rp or bad_sp):
                continue

            # ピボットが bbox 内なら意図的とみなしてスキップ
            bbox = cmds.exactWorldBoundingBox(tr)
            if bad_rp and _is_inside_bbox(rp, bbox):
                bad_rp = False
            if bad_sp and _is_inside_bbox(sp, bbox):
                bad_sp = False

            if not (bad_rp or bad_sp):
                continue

            msg_parts = []
            if bad_rp:
                msg_parts.append(f"RotatePivot: ({rp[0]:.6f}, {rp[1]:.6f}, {rp[2]:.6f})")
            if bad_sp:
                msg_parts.append(f"ScalePivot: ({sp[0]:.6f}, {sp[1]:.6f}, {sp[2]:.6f})")

            results.append(CheckResult(
                target=tr,
                message=" / ".join(msg_parts),
                severity=Severity.ERROR,
            ))

        except Exception as e:
            results.append(CheckResult(
                target=tr,
                message=f"Pivot取得エラー: {e}",
                severity=Severity.ERROR,
            ))

    return results


if __name__ == "__main__":
    for item in get_results():
        print(f'{item.target} : {item.message}')
