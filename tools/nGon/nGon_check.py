# -*- coding: utf-8 -*-
"""
nGon_check.py

check処理:
N-gon（5 角以上のフェース）を検出します。

Maya 標準の polySelectConstraint(mode=3, type=face, size=3) を利用。
size=3 は「5 角以上のフェース」を意味する。
現在の選択と polySelectConstraint state は処理後に解除する。
FIX は付けない（修正は手動でのクワッド化を推奨）。
"""
import maya.cmds as cmds
from _util import iter_unique_mesh_parents
from _results import CheckResult, Severity


_FACE_TYPE_BIT = 0x0008
_SIZE_NGON = 3  # 5 角以上


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
    """単一 shape の N-gon face index リストを返す。"""
    try:
        fc = cmds.polyEvaluate(shape, face=True)
    except Exception:
        return []
    if not isinstance(fc, int) or fc <= 0:
        return []

    try:
        cmds.select(f"{shape}.f[0:{fc - 1}]", r=True)
        cmds.polySelectConstraint(mode=3, type=_FACE_TYPE_BIT, size=_SIZE_NGON)
        bad = cmds.ls(sl=True, long=True) or []
    finally:
        try:
            cmds.polySelectConstraint(disable=True)
            cmds.polySelectConstraint(size=0)
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
                message=f"n-gon: {len(collected)} 件",
                details=details,
                severity=Severity.ERROR,
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
        print("[nGon] N-gon は見つかりませんでした。")
    else:
        print(f"[nGon] {len(res)} mesh")
        for r in res:
            print(r.message)
