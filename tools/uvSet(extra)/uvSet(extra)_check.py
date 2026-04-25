# -*- coding: utf-8 -*-
"""
UV Set check (extra UV sets)

目的:
- シーン内の mesh shape を全件走査し、以下の mesh を検出する
  1) 必須UVセット "map1" が無い
  2) "map1" / ホワイトリスト 以外のUVセットが 2 個以上ある
  3) "map1" / ホワイトリスト 以外のUVセットが 1 個だが、どこにも接続されていない
  4) PencilSelectedEdgeUVSet（PencilSelectedEdge プレフィックス）が 3 個以上ある

ホワイトリスト（WHITELIST_UVSETS）に含まれる UVSet は、
Pencil+ 等のプラグインが独自に名前参照するため接続検出ができない。
これらは「正常運用」として通常はスキップするが、PencilSelectedEdge*
が 3 個以上ある場合は不正生成の可能性として検出対象とする。

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
from _results import CheckResult, Severity

REQUIRED_UVSET = "map1"

# 接続検出ができないが正常運用とみなす UVSet 名（Pencil+ 等のプラグイン）
# - WHITELIST_EXACT    : 完全一致
# - WHITELIST_PREFIXES : プレフィックス一致（Pencil+ が動的に生成する番号付き名に対応）
#   例: PencilSelectedEdge14UVSet1 / PencilSelectedEdge49UVSet2 など
WHITELIST_EXACT = frozenset([
    "Pencil",
])
WHITELIST_PREFIXES = (
    "PencilSelectedEdge",
)

# PencilSelectedEdge* がこの個数以上ある場合は異常として検出
PENCIL_MAX_OK = 2


def _is_whitelisted_uvset(name: str) -> bool:
    """UVSet 名がホワイトリスト（完全一致 or プレフィックス）に該当するか。"""
    if name in WHITELIST_EXACT:
        return True
    return name.startswith(WHITELIST_PREFIXES)


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
def get_results():
    results = []

    for shape in _iter_scene_mesh_shapes():
        uv_sets = _get_uv_sets(shape)
        has_required = REQUIRED_UVSET in uv_sets
        # ホワイトリスト（Pencil+ 等）と map1 は判定対象外
        extra = [
            u for u in uv_sets
            if u != REQUIRED_UVSET and not _is_whitelisted_uvset(u)
        ]

        # PencilSelectedEdge* は通常ホワイトリストだが、過剰生成は異常として検出
        pencil_uvsets = [u for u in uv_sets if u.startswith("PencilSelectedEdge")]
        pencil_too_many = len(pencil_uvsets) > PENCIL_MAX_OK

        # map1 あり ＆ 判定対象 extra が 0 ＆ Pencil 過剰なし → 問題なし
        if has_required and not extra and not pencil_too_many:
            continue

        # 余分 UVSet のうち「未接続」のものを抽出
        unconnected_extras = [
            n for n in extra
            if not _uvset_has_downstream_connection(shape, n)
        ]

        # map1 あり ＆ 余分 1 個 ＆ それが接続済み ＆ Pencil 過剰なし → 正常運用とみなしてスキップ
        if has_required and len(extra) == 1 and not unconnected_extras and not pencil_too_many:
            continue

        issues = []
        if not has_required:
            issues.append(f"{REQUIRED_UVSET} なし")
        if len(extra) >= 2:
            issues.append(f"余分な UVSet {len(extra)} 件")
        if unconnected_extras:
            issues.append(f"未接続 UVSet {len(unconnected_extras)} 件")
        if pencil_too_many:
            issues.append(f"PencilSelectedEdgeUVSet {len(pencil_uvsets)} 個（{PENCIL_MAX_OK} 個以下が正常）")

        if not issues:
            continue

        # 詳細表示：各 UVSet に状態のアノテーションを付ける
        details = []
        for name in uv_sets:
            if name == REQUIRED_UVSET:
                details.append(f"{name} (required)")
            elif name.startswith("PencilSelectedEdge"):
                if pencil_too_many:
                    details.append(f"⚠ {name} (Pencil: {len(pencil_uvsets)} 個)")
                else:
                    details.append(f"{name} (whitelisted)")
            elif _is_whitelisted_uvset(name):
                details.append(f"{name} (whitelisted)")
            elif name in unconnected_extras:
                details.append(f"⚠ {name} [未接続]")
            else:
                details.append(f"{name} (extra, connected)")
        if not details:
            details = ["(none)"]

        results.append(CheckResult(
            target=_parent_transform(shape),
            message=f"UVSet({', '.join(issues)})",
            details=details,
            severity=Severity.WARNING,
        ))

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
            for line in r.details:
                print(line)
