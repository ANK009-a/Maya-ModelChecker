# -*- coding: utf-8 -*-
"""
hiddenObject_fix.py
選択オブジェクトを visibility=True にして表示状態に戻す。
削除するかどうかはユーザーが判断するため、ここでは表示のみ行う。
"""
import maya.cmds as cmds


def _short_name(dag_path):
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def get_results():
    results = []
    sel = cmds.ls(sl=True, long=True) or []
    transforms = []
    for n in sel:
        if cmds.nodeType(n) == "transform":
            transforms.append(n)
        else:
            parents = cmds.listRelatives(n, parent=True, fullPath=True) or []
            transforms.extend(parents)
    seen = set()
    uniq = []
    for t in transforms:
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    for tr in uniq:
        try:
            was_hidden = not cmds.getAttr(f"{tr}.visibility")
            cmds.setAttr(f"{tr}.visibility", True)
            if was_hidden:
                results.append({
                    "transform": _short_name(tr),
                    "message": f"表示に変更: {_short_name(tr)}",
                })
            else:
                results.append({
                    "transform": _short_name(tr),
                    "message": f"既に表示済み: {_short_name(tr)}",
                })
        except Exception as e:
            results.append({
                "transform": _short_name(tr),
                "message": f"変更失敗: {e}",
            })
    return results


if __name__ == "__main__":
    for r in get_results():
        print(f'{r["transform"]}: {r["message"]}')
