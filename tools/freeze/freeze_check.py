# -*- coding: utf-8 -*-
"""
freeze_check_allScene.py

目的（checkList / assetChecker 用）:
- 選択判定は行わず、常に「シーン内の mesh shape を全件」対象にします。
- mesh の親 transform について、以下を検出して返します:
  - translate が (0,0,0) ではない
  - rotate が (0,0,0) ではない
  - scale が (1,1,1) ではない

返却形式:
- get_results() -> list[dict]
  dict keys: "transform", "message"
"""

import maya.cmds as cmds
from _util import iter_scene_mesh_shapes as _iter_scene_mesh_shapes

TOL = 1e-6  # 許容誤差（必要なら 1e-4 などに）


def _short_name(dag_path: str) -> str:
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _neq(a, b, tol=TOL):
    return abs(a - b) > tol


def _vec_not_equal(v, target, tol=TOL):
    return any(_neq(v[i], target[i], tol) for i in range(3))


def _mesh_parent_transforms():
    """
    シーン内の mesh shape の親 transform を重複なしで返す（順序保持）
    """
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
    transforms = _mesh_parent_transforms()
    results = []

    # シーンに mesh が無ければ空（問題なし）
    if not transforms:
        return results

    for tr in transforms:
        tr_short = _short_name(tr)
        try:
            # ローカル値で判定（必要なら ws=True の xform に切り替え可）
            t = cmds.getAttr(tr + ".translate")[0]  # (x,y,z)
            r = cmds.getAttr(tr + ".rotate")[0]
            s = cmds.getAttr(tr + ".scale")[0]

            bad_t = _vec_not_equal(t, (0.0, 0.0, 0.0))
            bad_r = _vec_not_equal(r, (0.0, 0.0, 0.0))
            bad_s = _vec_not_equal(s, (1.0, 1.0, 1.0))

            if bad_t or bad_r or bad_s:
                parts = []
                if bad_t:
                    parts.append(f"移動: ({t[0]:.3f}, {t[1]:.3f}, {t[2]:.3f})")
                if bad_r:
                    parts.append(f"回転: ({r[0]:.3f}, {r[1]:.3f}, {r[2]:.3f})")
                if bad_s:
                    parts.append(f"スケール: ({s[0]:.3f}, {s[1]:.3f}, {s[2]:.3f})")

                results.append({
                    "transform": tr_short,
                    "message": " / ".join(parts)
                })

        except Exception as e:
            results.append({
                "transform": tr_short,
                "message": f"TRS取得エラー: {e}"
            })

    return results


if __name__ == "__main__":
    for item in get_results():
        print(f'{item.get("transform")} : {item.get("message")}')
