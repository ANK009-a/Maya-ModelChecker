# -*- coding: utf-8 -*-
"""
animationKey_check.py

check処理:
シーン内のアニメーションカーブノード（animCurve*）をリストします（選択不要）

対象:
- animCurveTA / animCurveTL / animCurveTT
- animCurveUA / animCurveUL / animCurveUT
- animCurveTU
（= nodeType が "animCurve" で始まるもの全て）

checkList.py 連携想定:
- get_results() が list[dict] を返す（無ければ []）
"""

import maya.cmds as cmds
from _util import checker_selection as _checker_selection


_ANIM_TYPES = [
    "animCurveTA", "animCurveTL", "animCurveTT",
    "animCurveUA", "animCurveUL", "animCurveUT",
    "animCurveTU", "animCurveUU",
]


def _anim_curves_for_selection(sel):
    """選択ノード配下に接続された animCurve をユニーク化して返す。"""
    targets = cmds.ls(sel, dag=True, long=True) or []
    if not targets:
        return []
    # animCurve は DG ノードなのでノード名がシーン内で一意（long=True 正規化は不要）
    connected = cmds.listConnections(targets, type=_ANIM_TYPES, source=True, destination=False) or []
    seen = set()
    uniq = []
    for n in connected:
        if n in seen:
            continue
        seen.add(n)
        uniq.append(n)
    return uniq


def get_results():
    results = []

    sel = _checker_selection()
    if sel:
        raw = _anim_curves_for_selection(sel)
    else:
        # animCurve の各型を直接指定して取得（全ノード走査を避ける）
        raw = cmds.ls(type=_ANIM_TYPES, long=True) or []
    anim_curves = [(n, cmds.nodeType(n)) for n in raw if cmds.objExists(n)]

    if not anim_curves:
        return []

    # 見やすいよう type -> name でソート
    anim_curves.sort(key=lambda x: (x[1], x[0]))

    for n, t in anim_curves:
        results.append({
            "transform": n,  # 左一覧でノード名がそのまま見えるように
            "message": f"animCurve: {n} ({t})",
            "details": [
                f"Type: {t}",
            ],
        })

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[animationKey] animCurve ノードは見つかりませんでした。")
    else:
        print(f"[animationKey] animCurve ノード: {len(res)} 件")
        for r in res:
            print(r["message"])
