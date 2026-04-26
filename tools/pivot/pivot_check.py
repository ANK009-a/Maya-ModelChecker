# -*- coding: utf-8 -*-
"""
pivot_check.py

- mesh の親 transform の rotatePivot / scalePivot がローカル原点(0,0,0)からズレているものを返す
- ローカル空間で判定するため、ロケーター下の eye など意図的に配置されたメッシュは誤検知しない
- 常にシーン内の mesh shape を全件対象
"""

import maya.cmds as cmds
from _util import iter_unique_mesh_parents as _iter_unique_mesh_parents
from _results import CheckResult, Severity

TOLERANCE = 1e-6


def _is_not_origin(pos, tol=TOLERANCE):
    return (abs(pos[0]) > tol) or (abs(pos[1]) > tol) or (abs(pos[2]) > tol)


def get_results():
    results = []

    transforms = _iter_unique_mesh_parents()
    if not transforms:
        return results

    for tr in transforms:
        try:
            # ws=True を外してローカル空間で取得する
            rp = cmds.xform(tr, q=True, rp=True)
            sp = cmds.xform(tr, q=True, sp=True)

            bad_rp = _is_not_origin(rp)
            bad_sp = _is_not_origin(sp)

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
