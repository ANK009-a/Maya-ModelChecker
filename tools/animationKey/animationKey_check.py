# -*- coding: utf-8 -*-
"""
animationKey_check.py

check処理:
シーン内のアニメーション系ノード（animCurve* / animLayer）をリストします。

対象:
- animCurve*: animCurveTA / TL / TT / UA / UL / UT / TU / UU
  （選択がある場合は、その配下に接続された animCurve のみ対象）
- animLayer: BaseAnimation を含む全 animLayer ノード
  （シーン全体状態のため選択に関係なく常に全件対象）

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


def _anim_layers():
    """シーン内の animLayer ノード（BaseAnimation 含む）を返す。"""
    return cmds.ls(type="animLayer") or []


def get_results():
    results = []

    # --- animCurve（選択に応じて絞り込み） ---
    sel = _checker_selection()
    if sel:
        raw = _anim_curves_for_selection(sel)
    else:
        # animCurve の各型を直接指定して取得（全ノード走査を避ける）
        raw = cmds.ls(type=_ANIM_TYPES, long=True) or []
    anim_curves = [(n, cmds.nodeType(n)) for n in raw if cmds.objExists(n)]

    # 見やすいよう type -> name でソート
    anim_curves.sort(key=lambda x: (x[1], x[0]))

    for n, t in anim_curves:
        results.append({
            "transform": n,
            "message": f"animCurve: {n} ({t})",
            "details": [
                f"Type: {t}",
            ],
        })

    # --- animLayer（常にシーン全体が対象） ---
    for n in sorted(_anim_layers()):
        details = [f"Type: animLayer"]
        if n == "BaseAnimation":
            details.append("※ BaseAnimation を削除すると配下の animLayer も全削除されます")
        results.append({
            "transform": n,
            "message": f"animLayer: {n}",
            "details": details,
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
