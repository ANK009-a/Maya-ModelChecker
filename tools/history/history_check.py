# -*- coding: utf-8 -*-
"""
history_check.py
mesh のコンストラクションヒストリー（入力ノード）を検出する。
デフォーマー（skinCluster, blendShape 等）とポリゴン操作ヒストリーを区別して表示する。
"""
import maya.cmds as cmds

DEFORMER_TYPES = frozenset([
    "skinCluster", "blendShape", "cluster", "wire", "ffd",
    "nonLinear", "deltaMush", "tension", "proximityWrap",
    "shrinkWrap", "softMod",
])

# Maya が正常運用のため自動生成する補助ノード（ヒストリー残留ではない）
IGNORE_TYPES = frozenset([
    "time",
    "mesh",
    "shadingEngine",   # マテリアル割り当て SG（全 mesh 必須）
    "groupId",         # 複数マテリアル割当時の補助ノード
    "groupParts",      # groupId と対の接続ノード
    "creaseSet",       # サブディビジョンクリース
    "objectSet",       # ユーザー作成セット等
])


from _util import iter_scene_mesh_shapes as _iter_shapes


def get_results():
    results = []
    shapes = _iter_shapes()
    seen_parents = set()

    for shape in shapes:
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        if not parents:
            continue
        parent = parents[0]
        if parent in seen_parents:
            continue
        seen_parents.add(parent)

        history = cmds.listHistory(shape, pruneDagObjects=True) or []
        history = [
            h for h in history
            if h != shape
            and cmds.objExists(h)
            and cmds.nodeType(h) not in IGNORE_TYPES
        ]
        if not history:
            continue

        deformers = [h for h in history if cmds.nodeType(h) in DEFORMER_TYPES]
        poly_ops = [h for h in history if cmds.nodeType(h) not in DEFORMER_TYPES]

        details = []
        if poly_ops:
            details.append(f"ポリゴン操作ヒストリー: {len(poly_ops)} ノード")
            for h in poly_ops[:10]:
                details.append(f"  [{cmds.nodeType(h)}] {h}")
        if deformers:
            details.append(f"デフォーマー: {len(deformers)} ノード（削除に注意）")
            for h in deformers[:5]:
                details.append(f"  [{cmds.nodeType(h)}] {h}")

        results.append({
            "transform": parent,
            "message": f"ヒストリー残留 (poly:{len(poly_ops)}, deformer:{len(deformers)})",
            "details": details,
        })
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[history] ヒストリーは見つかりませんでした。")
    else:
        for r in res:
            print(r["message"])
