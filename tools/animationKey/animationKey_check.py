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


_ANIM_TYPES = [
    "animCurveTA", "animCurveTL", "animCurveTT",
    "animCurveUA", "animCurveUL", "animCurveUT",
    "animCurveTU", "animCurveUU",
]


def get_results():
    results = []

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
                f"Node: {n}",
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
