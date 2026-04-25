# -*- coding: utf-8 -*-
"""
emptyGroup_check.py
子ノードを持たない transform（空グループ）を検出する。
接続がある場合は削除に注意が必要なため、その旨を詳細に表示する。
"""
import maya.cmds as cmds
from _util import (
    short_name as _short_name,
    checker_selection as _checker_selection,
)
from _results import CheckResult, Severity

DEFAULT_NODES = frozenset(["persp", "top", "front", "side", "left"])


def get_results():
    results = []
    sel = _checker_selection()
    if sel:
        transforms = cmds.ls(sel, dag=True, type="transform", long=True) or []
    else:
        transforms = cmds.ls(type="transform", long=True) or []

    for tr in transforms:
        short = _short_name(tr)
        if short in DEFAULT_NODES:
            continue

        # シェイプを持つノードは空グループではない
        shapes = cmds.listRelatives(tr, shapes=True, fullPath=True) or []
        if shapes:
            continue

        # 子ノードがなければ空グループ
        children = cmds.listRelatives(tr, children=True, fullPath=True) or []
        if children:
            continue

        incoming = cmds.listConnections(tr, s=True, d=False) or []
        outgoing = cmds.listConnections(tr, s=False, d=True) or []

        details = []
        if incoming or outgoing:
            details.append(
                f"⚠ 接続あり (in={len(incoming)}, out={len(outgoing)}) — 削除前に確認してください"
            )

        results.append(CheckResult(
            target=tr,
            message="空グループ",
            details=details,
            severity=Severity.ERROR,
        ))
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[emptyGroup] 空グループは見つかりませんでした。")
    else:
        for r in res:
            print(r.message)
