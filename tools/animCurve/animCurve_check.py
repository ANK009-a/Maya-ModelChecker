# -*- coding: utf-8 -*-
"""
animCurve_check.py

check処理:
シーン内の animCurve ノード（animCurveTA / TL / TT / UA / UL / UT / TU / UU）を検出します。

対象:
- 選択がある場合: その配下に接続された animCurve のみ
- 選択がない場合: シーン全体の animCurve

旧 animationKey ツールから animCurve 検出のみを分離。
animLayer は別ツール `animLayer` として分割。
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
        raw = cmds.ls(type=_ANIM_TYPES, long=True) or []
    anim_curves = [(n, cmds.nodeType(n)) for n in raw if cmds.objExists(n)]

    # type -> name でソート
    anim_curves.sort(key=lambda x: (x[1], x[0]))

    for n, t in anim_curves:
        results.append({
            "transform": n,
            "message": f"animCurve: {n} ({t})",
            "details": [
                f"Type: {t}",
            ],
        })

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[animCurve] animCurve ノードは見つかりませんでした。")
    else:
        print(f"[animCurve] {len(res)} 件")
        for r in res:
            print(r["message"])
