# -*- coding: utf-8 -*-
"""
unknownNode_check.py

check処理:
unknown ノード（型: unknown / unknownDag / unknownTransform）と、
シーンに残っている未ロードプラグイン参照を検出します。

対象（シーン全体・選択に関係なく常に全件）:
- unknown / unknownDag / unknownTransform 型のノード
- cmds.unknownPlugin(query=True, list=True) で返るプラグイン参照

unknown ノードはロックされている場合がある。FIX 時に lockNode -l 0 して削除する。
プラグイン参照は Maya ノードではないため list の選択対象にはならず、FIX では
全プラグイン参照を一括で削除する。
"""
import maya.cmds as cmds


_UNKNOWN_TYPES = ["unknown", "unknownDag", "unknownTransform"]


def _is_locked(node):
    try:
        v = cmds.lockNode(node, query=True, lock=True)
        return bool(v[0]) if v else False
    except Exception:
        return False


def get_results():
    results = []

    nodes = cmds.ls(type=_UNKNOWN_TYPES, long=True) or []
    for n in sorted(nodes):
        try:
            t = cmds.nodeType(n)
        except Exception:
            continue
        details = [f"Type: {t}"]
        if _is_locked(n):
            details.append("⚠ lockNode で保護されています（FIX 時に解除します）")
        results.append({
            "transform": n,
            "message": f"unknown node: {n} ({t})",
            "details": details,
        })

    plugins = cmds.unknownPlugin(query=True, list=True) or []
    for p in sorted(plugins):
        results.append({
            "transform": p,
            "message": f"unknown plugin: {p}",
            "details": [
                "Type: unknown plugin reference",
                "※ Maya ノードではないため Maya 上では選択されません",
                "※ FIX で参照を一括削除します",
            ],
        })

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[unknownNode] unknown ノード / プラグイン参照は見つかりませんでした。")
    else:
        print(f"[unknownNode] {len(res)} 件")
        for r in res:
            print(r["message"])
