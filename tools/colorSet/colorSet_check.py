# -*- coding: utf-8 -*-
"""
colorSet_check_simple.py

目的:
- シーン内の mesh shape を全件走査し、カラーセット（Color Set）を持つものを検出する。

UI連携（assetChecker想定）:
- get_results() が list[dict] を返す（問題が無ければ []）
- dict は "transform" / "message" / "details" を持つ
  - details: 右側欄に表示される文字列リスト
  - message: assetChecker側で details に混ざる実装があるため、空文字にして表示を抑制
本スクリプトでは details に「ColorSet名だけ（1行1set）」を入れる。
"""

from __future__ import annotations

import maya.cmds as cmds
from _util import (
    iter_scene_mesh_shapes as _iter_shapes,
    short_name as _short_name,
    parent_transform as _parent_transform,
)
from _results import CheckResult, Severity


def _get_color_sets(shape: str) -> list[str]:
    """カラーセット一覧を取得（無ければ []）"""
    try:
        sets_ = cmds.polyColorSet(shape, query=True, allColorSets=True) or []
    except Exception:
        return []
    return [str(s) for s in sets_]


def get_results():
    results = []

    shapes = _iter_shapes()

    for shape in shapes:
        color_sets = _get_color_sets(shape)
        if not color_sets:
            continue

        parent = _parent_transform(shape)
        results.append(CheckResult(
            target=parent,
            message=f"カラーセット {len(color_sets)} 件",
            details=color_sets,
            severity=Severity.ERROR,
        ))

    return results


if __name__ == "__main__":
    # スタンドアロン実行用（UI連携では未使用）
    res = get_results()
    if not res:
        print("[ColorSet] カラーセットを持つ shape は見つかりませんでした。")
    else:
        print(f"[ColorSet] カラーセットを持つ shape が {len(res)} 件見つかりました。")
        for r in res:
            for line in r.details:
                print(str(line))
