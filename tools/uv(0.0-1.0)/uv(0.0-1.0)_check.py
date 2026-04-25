# -*- coding: utf-8 -*-
"""
UVSpace(0.0-1.0)_check_fast.py

高速化ポイント:
- intermediate mesh を cmds.ls(..., ni/noIntermediate) で列挙段階から除外（getAttr連打を減らす）
- UVSet名取得を cmds.polyUVSet から maya.api.OpenMaya(MFnMesh) に変更（cmds呼び出し削減）
- U/V の min/max と 範囲外数(out_count) を 1パスで計算（配列の走査回数を削減）
- 参照ノード判定は親transformだけで行う（referenceQuery回数を削減）

仕様:
- 選択不要（常にシーン内の non-intermediate mesh を全件対象）
- 全UVセットを対象に、UVが0.0〜1.0範囲外のセットがある mesh を返す
- PencilSelectedEdge* は Pencil+ プラグインが内部で利用する UVSet のため判定対象外
- OpenMaya(maya.api.OpenMaya) が使えない環境では何もしない（元スクリプトと同じ方針）
"""

from __future__ import annotations

import maya.cmds as cmds
from _util import (
    iter_scene_mesh_shapes as _iter_scene_mesh_shapes_no_intermediate,
    short_name as _short_name,
    parent_transform as _parent_transform,
    is_referenced as _is_referenced,
)
from _results import CheckResult, Severity

try:
    import maya.api.OpenMaya as om2
except Exception:
    om2 = None

EPS = 1e-9  # 端の誤差許容

# 判定対象外の UVSet 名プレフィックス（Pencil+ プラグイン由来）
EXCLUDE_UVSET_PREFIXES = (
    "PencilSelectedEdge",
)


def _get_mfnmesh(shape: str):
    if om2 is None:
        return None
    try:
        sel = om2.MSelectionList()
        sel.add(shape)
        dag = sel.getDagPath(0)
        return om2.MFnMesh(dag)
    except Exception:
        return None


def _get_uv_set_names(mfn) -> list[str]:
    """MFnMesh から UVSet名一覧を取得（cmds.polyUVSet を使わない）"""
    try:
        names = mfn.getUVSetNames()
        return [str(n) for n in names] if names else []
    except Exception:
        return []


def _uv_out_of_range_info_onepass(mfn, uv_set_name: str):
    """
    Returns:
      (has_error: bool, info: dict|None)
      info keys: u_min,u_max,v_min,v_max,out_count,total
    """
    try:
        u_arr, v_arr = mfn.getUVs(uvSet=uv_set_name)
    except Exception:
        # UV取得不可は「判定不能」扱い（エラー扱いにしない）
        return False, None

    total = len(u_arr)
    if total == 0:
        return False, {"u_min": None, "u_max": None, "v_min": None, "v_max": None, "out_count": 0, "total": 0}

    # 1パスで min/max と out_count を計算
    u0 = float(u_arr[0])
    v0 = float(v_arr[0])
    u_min = u_max = u0
    v_min = v_max = v0

    out_count = 0
    # 先頭も判定に含める
    if (u0 < 0.0 - EPS) or (u0 > 1.0 + EPS) or (v0 < 0.0 - EPS) or (v0 > 1.0 + EPS):
        out_count = 1

    for i in range(1, total):
        u = float(u_arr[i])
        v = float(v_arr[i])

        if u < u_min:
            u_min = u
        elif u > u_max:
            u_max = u

        if v < v_min:
            v_min = v
        elif v > v_max:
            v_max = v

        if (u < 0.0 - EPS) or (u > 1.0 + EPS) or (v < 0.0 - EPS) or (v > 1.0 + EPS):
            out_count += 1

    has_err = (u_min < 0.0 - EPS) or (u_max > 1.0 + EPS) or (v_min < 0.0 - EPS) or (v_max > 1.0 + EPS)
    if not has_err:
        # out_count は 0 であるはずだが、EPS判定で揺れた場合でも 0 に丸める
        return False, {"u_min": u_min, "u_max": u_max, "v_min": v_min, "v_max": v_max, "out_count": 0, "total": total}

    return True, {"u_min": u_min, "u_max": u_max, "v_min": v_min, "v_max": v_max, "out_count": out_count, "total": total}


def get_results():
    results = []

    # OpenMaya が使えない環境では判定しない（元スクリプト方針）
    if om2 is None:
        return results

    shapes = _iter_scene_mesh_shapes_no_intermediate()

    for shape in shapes:
        parent = _parent_transform(shape)

        # 参照ノードはスキップ（親transformだけで判定して呼び出し回数削減）
        if _is_referenced(parent):
            continue

        mfn = _get_mfnmesh(shape)
        if mfn is None:
            continue

        uv_sets = _get_uv_set_names(mfn)
        if not uv_sets:
            continue

        bad_sets = []  # (uvSetName, info)
        for uv_set in uv_sets:
            if uv_set.startswith(EXCLUDE_UVSET_PREFIXES):
                continue
            has_err, info = _uv_out_of_range_info_onepass(mfn, uv_set)
            if has_err and info:
                bad_sets.append((uv_set, info))

        if not bad_sets:
            continue

        parent_short = _short_name(parent)
        shape_short = _short_name(shape)

        details = [
            "Out of 0-1 UV sets:",
        ]
        for uv_set, info in bad_sets:
            details.append(
                f"  - {uv_set}: "
                f"U[{info['u_min']:.6f} .. {info['u_max']:.6f}] "
                f"V[{info['v_min']:.6f} .. {info['v_max']:.6f}] "
                f"out={info['out_count']}/{info['total']}"
            )

        results.append(CheckResult(
            target=parent,
            message=f"UV範囲外(0-1): {shape_short}（{len(bad_sets)} uvSets）",
            details=details,
            severity=Severity.WARNING,
        ))

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[UVSpace 0-1] 範囲外UVを持つ mesh は見つかりませんでした。")
    else:
        print(f"[UVSpace 0-1] 範囲外UVを持つ mesh: {len(res)} 件")
        for r in res:
            print(r.message)
            for line in r.details:
                print("  - " + line)
