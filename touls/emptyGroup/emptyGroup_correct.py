# -*- coding: utf-8 -*-
"""
emptyGroup_correct.py
選択した空グループ（子なし transform）を削除する。
接続がある場合や子がある場合はスキップして警告を出す。
"""
import maya.cmds as cmds


def _short_name(dag_path):
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def get_results():
    results = []
    sel = cmds.ls(sl=True, long=True) or []
    transforms = [n for n in sel if cmds.nodeType(n) == "transform"]

    for tr in transforms:
        if not cmds.objExists(tr):
            continue

        children = cmds.listRelatives(tr, children=True, fullPath=True) or []
        if children:
            results.append({
                "transform": _short_name(tr),
                "message": "スキップ（子ノードあり）",
            })
            continue

        incoming = cmds.listConnections(tr, s=True, d=False) or []
        outgoing = cmds.listConnections(tr, s=False, d=True) or []
        if incoming or outgoing:
            results.append({
                "transform": _short_name(tr),
                "message": f"スキップ（接続あり: in={len(incoming)}, out={len(outgoing)}）",
            })
            continue

        try:
            cmds.delete(tr)
            results.append({
                "transform": _short_name(tr),
                "message": f"削除: {_short_name(tr)}",
            })
        except Exception as e:
            results.append({
                "transform": _short_name(tr),
                "message": f"削除失敗: {e}",
            })
    return results


if __name__ == "__main__":
    for r in get_results():
        print(f'{r["transform"]}: {r["message"]}')
