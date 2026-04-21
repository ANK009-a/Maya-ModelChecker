# -*- coding: utf-8 -*-
"""
UV Set check (extra UV sets)

目的:
- シーン内の mesh shape を全件走査し、以下の mesh を検出する
  1) 必須UVセット "map1" が無い
  2) "map1" 以外のUVセットを持っている（= 余分なUVSetがある）

UI連携（assetChecker想定）:
- get_results() が list[dict] を返す（問題が無ければ []）
- dict は "transform" / "message" / "details" を持つ
  - details: 右側欄に表示される文字列リスト（本スクリプトではUVSet名のみを1行ずつ）
  - message: assetChecker側で details に混ざる実装があるため、空文字にして表示を抑制
"""

from __future__ import annotations

import maya.cmds as cmds
from _util import iter_scene_mesh_shapes as _iter_scene_mesh_shapes

REQUIRED_UVSET = "map1"


# ----------------------------------------------------------------------
# Utility
# ----------------------------------------------------------------------
def _short_name(dag_path: str) -> str:
    """Return the last component of a DAG path (e.g. '|a|b|c' -> 'c')."""
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _get_uv_sets(shape: str) -> list[str]:
    """Return UV set names for the given mesh shape."""
    try:
        uv_sets = cmds.polyUVSet(shape, query=True, allUVSets=True)
    except Exception:
        uv_sets = None

    if not uv_sets:
        return []
    if isinstance(uv_sets, (list, tuple)):
        return [str(x) for x in uv_sets]
    return [str(uv_sets)]


# ----------------------------------------------------------------------
# Public API (assetChecker calls this)
# ----------------------------------------------------------------------
def get_results() -> list[dict]:
    results: list[dict] = []

    for shape in _iter_scene_mesh_shapes():
        if not cmds.objExists(shape):
            continue

        uv_sets = _get_uv_sets(shape)
        has_required = REQUIRED_UVSET in uv_sets
        has_extra = any(u != REQUIRED_UVSET for u in uv_sets)

        # "map1" のみなら問題なし
        if has_required and not has_extra:
            continue

        # UI左側のグルーピングキー（Cは入れていない方針なので short 名）
        try:
            parent = (cmds.listRelatives(shape, parent=True, fullPath=True) or [shape])[0]
        except Exception:
            parent = shape
        transform_key = _short_name(parent)

        has_required = REQUIRED_UVSET in uv_sets
        issues = []
        if not has_required:
            issues.append(f"{REQUIRED_UVSET} なし")
        extra = [u for u in uv_sets if u != REQUIRED_UVSET]
        if extra:
            issues.append(f"余分な UVSet {len(extra)} 件")

        results.append({
            "transform": transform_key,
            "message": f"UVSet({', '.join(issues)}): {transform_key}",
            "details": uv_sets[:] if uv_sets else ["(none)"],
        })

    return results


# ----------------------------------------------------------------------
# Standalone run (optional)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[UVSet] OK: extra UV sets not found.")
    else:
        print(f"[UVSet] NG: {len(res)} mesh(es) have UV set issues.")
        for r in res:
            for line in r.get("details", []):
                print(line)
