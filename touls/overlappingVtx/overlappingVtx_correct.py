# -*- coding: utf-8 -*-
"""
overlappingVtx_correct.py
選択オブジェクトの重複頂点を polyMergeVertex でマージする。
"""
import maya.cmds as cmds

THRESHOLD = 0.0001


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
            v_before = cmds.polyEvaluate(tr, v=True) or 0
            cmds.polyMergeVertex(tr, d=THRESHOLD, am=True, ch=False)
            v_after = cmds.polyEvaluate(tr, v=True) or 0
            merged = v_before - v_after
            if merged > 0:
                results.append({
                    "transform": _short_name(tr),
                    "message": f"頂点マージ: {merged} 個 ({v_before} → {v_after})",
                })
            else:
                results.append({
                    "transform": _short_name(tr),
                    "message": f"マージ対象なし (閾値: {THRESHOLD})",
                })
        except Exception as e:
            results.append({
                "transform": _short_name(tr),
                "message": f"マージ失敗: {e}",
            })
    return results


if __name__ == "__main__":
    for r in get_results():
        print(f'{r["transform"]}: {r["message"]}')
