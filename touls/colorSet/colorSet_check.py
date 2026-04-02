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


def _is_intermediate(shape: str) -> bool:
    """中間オブジェクト判定"""
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
    except Exception:
        return False


def _parent_transform_short(shape: str) -> str:
    """shape の親transform短名（なければ shape の短名）"""
    try:
        p = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        parent = p[0] if p else shape
    except Exception:
        parent = shape

    return parent.rsplit("|", 1)[-1] if "|" in parent else parent


def _get_color_sets(shape: str) -> list[str]:
    """カラーセット一覧を取得（無ければ []）"""
    try:
        sets_ = cmds.polyColorSet(shape, query=True, allColorSets=True) or []
    except Exception:
        return []
    return [str(s) for s in sets_]


def get_results() -> list[dict]:
    results: list[dict] = []

    # mesh shape を全件対象
    shapes = cmds.ls(type="mesh", long=True) or []

    for shape in shapes:
        if _is_intermediate(shape):
            continue

        color_sets = _get_color_sets(shape)
        if not color_sets:
            continue

        results.append({
            "transform": _parent_transform_short(shape),
            "message": f"カラーセット {len(color_sets)} 件: {_parent_transform_short(shape)}",
            "details": color_sets,
        })

    return results


if __name__ == "__main__":
    # スタンドアロン実行用（UI連携では未使用）
    res = get_results()
    if not res:
        print("[ColorSet] カラーセットを持つ shape は見つかりませんでした。")
    else:
        print(f"[ColorSet] カラーセットを持つ shape が {len(res)} 件見つかりました。")
        for r in res:
            for line in r.get("details", []):
                print(str(line))
