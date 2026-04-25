# -*- coding: utf-8 -*-
"""
nonPlanarFace_check.py

check処理:
非平面 face（4 頂点以上で頂点が同一平面に乗っていない face）を検出します。

Maya 標準の polySelectConstraint(mode=3, type=face, nonplanar=1) を利用。
現在の選択と polySelectConstraint state は処理後に解除する。
FIX は付けない（修正には face の三角形化や頂点位置調整が必要で破壊的なため、手動推奨）。
"""
import maya.cmds as cmds
from _util import iter_unique_mesh_parents
from _results import CheckResult, Severity


_FACE_TYPE_BIT = 0x0008


def _collect_face_indices(face_strs):
    """'.f[N]' / '.f[A:B]' 形式のリストから face index リストを展開して返す。"""
    indices = []
    for s in face_strs:
        if ".f[" not in s:
            continue
        body = s.rsplit(".f[", 1)[1].rstrip("]")
        if ":" in body:
            a, b = body.split(":", 1)
            try:
                indices.extend(range(int(a), int(b) + 1))
            except ValueError:
                continue
        else:
            try:
                indices.append(int(body))
            except ValueError:
                continue
    return indices


def _eval_shape(shape):
    """単一 shape の非平面 face index リストを返す。"""
    try:
        fc = cmds.polyEvaluate(shape, face=True)
    except Exception:
        return []
    if not isinstance(fc, int) or fc <= 0:
        return []

    try:
        cmds.select(f"{shape}.f[0:{fc - 1}]", r=True)
        cmds.polySelectConstraint(mode=3, type=_FACE_TYPE_BIT, nonplanar=1)
        bad = cmds.ls(sl=True, long=True) or []
    finally:
        try:
            cmds.polySelectConstraint(disable=True)
            cmds.polySelectConstraint(nonplanar=0)
        except Exception:
            pass

    return sorted(set(_collect_face_indices(bad)))


def get_results():
    results = []

    transforms = list(iter_unique_mesh_parents())
    if not transforms:
        return results

    original_sel = cmds.ls(sl=True, long=True) or []

    try:
        for tr in transforms:
            shapes = cmds.listRelatives(tr, shapes=True, type="mesh", noIntermediate=True, fullPath=True) or []
            collected = []
            for shape in shapes:
                collected.extend(_eval_shape(shape))

            if not collected:
                continue

            collected.sort()
            preview_n = 30
            preview = ", ".join(f"f[{i}]" for i in collected[:preview_n])
            details = [
                f"Mesh: {tr}",
                f"Face count: {len(collected)}",
                f"  {preview}",
            ]
            if len(collected) > preview_n:
                details.append(f"  ... 他 {len(collected) - preview_n} 件")

            results.append(CheckResult(
                target=tr,
                message=f"non-planar face: {len(collected)} 件",
                details=details,
                severity=Severity.WARNING,
            ))
    finally:
        try:
            cmds.polySelectConstraint(disable=True)
        except Exception:
            pass
        try:
            if original_sel:
                cmds.select(original_sel, r=True)
            else:
                cmds.select(clear=True)
        except Exception:
            pass

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[nonPlanarFace] non-planar face は見つかりませんでした。")
    else:
        print(f"[nonPlanarFace] {len(res)} mesh")
        for r in res:
            print(r.message)
