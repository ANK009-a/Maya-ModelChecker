# -*- coding: utf-8 -*-
"""
UV Set check (extra UV sets)

目的:
- シーン内の mesh shape を全件走査し、以下の mesh を検出する
  1) 必須UVセット "map1" が無い
  2) "map1" 以外のUVセットが 2 個以上ある
  3) "map1" 以外のUVセットが 1 個だが、どこにも接続されていない（= 未使用で残存）

"map1" + 接続済みの余分 UV セット 1 個（Pencil 等の正常運用）は問題なしとして扱う。

UI連携（assetChecker想定）:
- get_results() が list[dict] を返す（問題が無ければ []）
"""

from __future__ import annotations

import maya.cmds as cmds
from _util import (
    iter_scene_mesh_shapes as _iter_scene_mesh_shapes,
    short_name as _short_name,
    parent_transform as _parent_transform,
)

REQUIRED_UVSET = "map1"


# ----------------------------------------------------------------------
# Utility
# ----------------------------------------------------------------------
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


def _uvset_has_downstream_connection(shape: str, uv_set_name: str) -> bool:
    """
    指定名の UVSet にダウンストリーム接続（uvChooser / texture 等）があるか判定。
    判定不能時は True を返す（= 安全側：検出しない）。
    """
    try:
        indices = cmds.getAttr(f"{shape}.uvSet", multiIndices=True) or []
    except Exception:
        return True

    for i in indices:
        try:
            if cmds.getAttr(f"{shape}.uvSet[{i}].uvSetName") != uv_set_name:
                continue
        except Exception:
            continue

        # uvSetName / uvSetPoints のダウンストリーム接続を確認
        for sub in ("uvSetName", "uvSetPoints"):
            try:
                conns = cmds.listConnections(
                    f"{shape}.uvSet[{i}].{sub}",
                    source=False, destination=True,
                ) or []
            except Exception:
                conns = []
            if conns:
                return True
        return False

    # uvSetName が見つからないケースは判定不能 → 安全側
    return True


# ----------------------------------------------------------------------
# Public API (assetChecker calls this)
# ----------------------------------------------------------------------
def get_results() -> list[dict]:
    results: list[dict] = []

    for shape in _iter_scene_mesh_shapes():
        uv_sets = _get_uv_sets(shape)
        has_required = REQUIRED_UVSET in uv_sets
        extra = [u for u in uv_sets if u != REQUIRED_UVSET]

        # map1 のみなら問題なし
        if has_required and not extra:
            continue

        # 余分 UVSet のうち「未接続」のものを抽出
        unconnected_extras = [
            n for n in extra
            if not _uvset_has_downstream_connection(shape, n)
        ]

        # map1 あり ＆ 余分 1 個 ＆ それが接続済み → 正常運用とみなしてスキップ
        if has_required and len(extra) == 1 and not unconnected_extras:
            continue

        issues = []
        if not has_required:
            issues.append(f"{REQUIRED_UVSET} なし")
        if len(extra) >= 2:
            issues.append(f"余分な UVSet {len(extra)} 件")
        if unconnected_extras:
            issues.append(f"未接続 UVSet {len(unconnected_extras)} 件")

        # 上記ケースのいずれにも該当しない（= map1 あり ＆ 余分 1 個 ＆ 接続あり）は continue 済み
        if not issues:
            continue

        # 詳細表示：各 UVSet に接続状態のアノテーションを付ける
        details = []
        for name in uv_sets:
            if name == REQUIRED_UVSET:
                details.append(f"{name} (required)")
            elif name in unconnected_extras:
                details.append(f"{name} [未接続]")
            else:
                details.append(f"{name} (extra, connected)")
        if not details:
            details = ["(none)"]

        transform_key = _short_name(_parent_transform(shape))
        results.append({
            "transform": transform_key,
            "message": f"UVSet({', '.join(issues)}): {transform_key}",
            "details": details,
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
