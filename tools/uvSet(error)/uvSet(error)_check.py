# -*- coding: utf-8 -*-
"""
uvSet(error)_check.py

目的:
シーン内の mesh で、
「UV Set Editor（= polyUVSet -q -allUVSets で取得できるUVセット一覧）には出てこないのに、
meshShape の uvSet 配列に “UV点(uvSetPoints)” を保持している UVset」
を検出してリスト化します。

※ “UV Set Editorに乗らない” は Maya 内部仕様/UI依存で厳密定義が難しいため、
このスクリプトでは下記をエラーUVsetの条件として扱います:
- shape.uvSet[*].uvSetName が、polyUVSet -q -allUVSets の戻りに含まれない
  かつ
- shape.uvSet[*].uvSetPoints の size が 1 以上（= UV情報を保持）

checkList.py のUI連携想定:
- get_results() が list[dict] を返す（問題なければ []）
"""

import maya.cmds as cmds

REQUIRED_UVSET = "map1"  # 使わないが、将来の表示用に残してもOK


from _util import (
    iter_scene_mesh_shapes as _iter_shapes,
    short_name as _short_name,
    parent_transform as _parent_transform,
    is_referenced as _is_referenced,
)


def _get_visible_uv_sets(shape: str):
    """
    UV Set Editorに出る想定のUVセット一覧（polyUVSetで取得）
    """
    try:
        uv_sets = cmds.polyUVSet(shape, query=True, allUVSets=True)
    except Exception:
        uv_sets = None

    if not uv_sets:
        return []
    if isinstance(uv_sets, (list, tuple)):
        return list(uv_sets)
    return [str(uv_sets)]


def _get_uvset_indices(shape: str):
    """
    meshShape.uvSet[*] の配列インデックスを取得
    """
    try:
        idx = cmds.getAttr(f"{shape}.uvSet", multiIndices=True) or []
        return list(idx)
    except Exception:
        return []


def _get_uvset_name(shape: str, i: int):
    try:
        return cmds.getAttr(f"{shape}.uvSet[{i}].uvSetName")
    except Exception:
        return None


def _get_uvset_points_size(shape: str, i: int):
    """
    uvSetPoints の要素数（重い配列取得は避けるため size=True を使用）
    """
    try:
        return int(cmds.getAttr(f"{shape}.uvSet[{i}].uvSetPoints", size=True))
    except Exception:
        return None


def get_results():
    results = []
    shapes = _iter_shapes()

    for shape in shapes:
        # 参照は基本スキップ（事故防止＆取得できても扱いが難しいため）
        parent = _parent_transform(shape)
        if _is_referenced(shape) or _is_referenced(parent):
            continue

        visible = _get_visible_uv_sets(shape)
        visible_set = set(visible)

        idx_list = _get_uvset_indices(shape)
        if not idx_list:
            continue

        hidden_with_uv = []
        unknown = []  # size取得に失敗など

        for i in idx_list:
            name = _get_uvset_name(shape, i)
            name_str = name if name else "<unnamed>"

            size = _get_uvset_points_size(shape, i)
            if size is None:
                unknown.append((i, name_str))
                continue

            if size <= 0:
                continue

            # 「見えていない」判定：polyUVSetの戻りに含まれない
            if name_str not in visible_set:
                hidden_with_uv.append((i, name_str, size))

        if not hidden_with_uv:
            # “見えない＋UV保持” が無ければ問題なし
            continue

        parent_short = _short_name(parent)
        shape_short = _short_name(shape)

        details = [
            "Visible(UV Set Editor): " + (", ".join(visible) if visible else "(none)"),
            "Hidden-with-UV (uvSet index / name / uvCount):",
        ]
        for i, n, s in hidden_with_uv:
            details.append(f"  - [{i}] {n} / uvSetPoints size={s}")

        if unknown:
            details.append("Note: uvSetPoints size が取得できない uvSet:")
            for i, n in unknown:
                details.append(f"  - [{i}] {n}")

        results.append({
            "transform": parent,
            "message": f"UVSet(非表示だがUV保持): {shape_short}（{len(hidden_with_uv)} sets）",
            "details": details,
        })

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[UVSet(Error)] 該当する mesh は見つかりませんでした。")
    else:
        print(f"[UVSet(Error)] 該当 {len(res)} 件")
        for r in res:
            print(r["message"])
            for line in r.get("details", []):
                print("  - " + line)
