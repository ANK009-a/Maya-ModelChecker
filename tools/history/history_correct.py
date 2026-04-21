# -*- coding: utf-8 -*-
"""
history_correct.py
選択オブジェクトのヒストリーを削除する。
- deformer（skinCluster, blendShape 等）がある場合 → bakePartialHistory でデフォーマを保持したまま削除
- deformer がない場合 → delete -ch で全削除
"""
import maya.cmds as cmds

DEFORMER_TYPES = frozenset([
    "skinCluster", "blendShape", "cluster", "wire", "ffd",
    "nonLinear", "deltaMush", "tension", "proximityWrap",
    "shrinkWrap", "softMod",
])


def _short_name(dag_path):
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _is_intermediate(shape):
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
    except Exception:
        return False


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
        shapes = cmds.listRelatives(
            tr, shapes=True, type="mesh", noIntermediate=True, fullPath=True
        ) or []
        for shape in shapes:
            history = cmds.listHistory(shape, pruneDagObjects=True) or []
            history = [
                h for h in history
                if h != shape
                and cmds.objExists(h)
                and cmds.nodeType(h) not in ("time", "mesh")
            ]
            if not history:
                continue

            has_deformers = any(cmds.nodeType(h) in DEFORMER_TYPES for h in history)
            try:
                if has_deformers:
                    cmds.bakePartialHistory(tr, prePostDeformers=True)
                    results.append({
                        "transform": _short_name(tr),
                        "message": "ヒストリー削除 (デフォーマ保持): bakePartialHistory",
                    })
                else:
                    cmds.delete(tr, ch=True)
                    results.append({
                        "transform": _short_name(tr),
                        "message": "ヒストリー全削除: delete -ch",
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
