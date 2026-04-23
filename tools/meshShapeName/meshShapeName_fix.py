# -*- coding: utf-8 -*-
"""
meshShapeName_fix.py

fix:
シーン内の non-intermediate mesh shape を、
「親 transform の短名 + 'Shape'」に揃えるようにリネームします（選択不要）。

注意:
- 参照ノードはスキップ
- intermediateObject は除外
- 同一 transform 配下に shape が複数ある場合は
  xxxShape, xxxShape1, xxxShape2... のように連番でユニーク化します
"""

import maya.cmds as cmds


SUFFIX = "Shape"


def _short_name(dag_path: str) -> str:
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _parent_transform(shape: str) -> str:
    p = cmds.listRelatives(shape, parent=True, fullPath=True) or []
    return p[0] if p else shape


def _is_intermediate(shape: str) -> bool:
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
    except Exception:
        return False


def _is_referenced(node: str) -> bool:
    try:
        return bool(cmds.referenceQuery(node, isNodeReferenced=True))
    except Exception:
        return False


def get_results():
    results = []

    # 全mesh shape（non-intermediate）
    all_shapes = [s for s in (cmds.ls(type="mesh", long=True) or []) if cmds.objExists(s)]
    all_shapes = [s for s in all_shapes if not _is_intermediate(s)]

    # 親transformごとにまとめる
    by_parent = {}
    for shape in all_shapes:
        parent = _parent_transform(shape)
        if not cmds.objExists(parent):
            continue
        if _is_referenced(shape) or _is_referenced(parent):
            continue
        by_parent.setdefault(parent, []).append(shape)

    # 親ごとにリネーム
    for parent, shapes in sorted(by_parent.items(), key=lambda x: _short_name(x[0])):
        parent_short = _short_name(parent)
        base = f"{parent_short}{SUFFIX}"

        # 形状が複数ある場合も安定するよう、現在名でソートして順番固定
        shapes_sorted = sorted(shapes, key=_short_name)

        renamed = []
        skipped = []

        for idx, shape in enumerate(shapes_sorted):
            desired = base if idx == 0 else f"{base}{idx}"

            current_short = _short_name(shape)
            if current_short == desired:
                skipped.append(f"{shape} (already '{desired}')")
                continue

            try:
                new_name = cmds.rename(shape, desired)  # 衝突があれば Maya が自動で調整する場合あり
                renamed.append(f"{shape} -> {new_name}")
            except Exception as e:
                skipped.append(f"{shape} (failed: {e})")

        if not renamed:
            continue

        results.append({
            "transform": parent_short,
            "message": f"Shapeリネーム: {parent_short}（{len(renamed)} renamed）",
            "details": (
                [f"Transform: {parent}", f"Base: {base}"]
                + ["Renamed:"] + [f"  - {x}" for x in renamed]
                + (["Skipped:"] + [f"  - {x}" for x in skipped] if skipped else [])
            ),
        })

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[meshShapeName Fix] 対象なし（リネーム不要 or 参照/中間のみ）")
    else:
        print(f"[meshShapeName Fix] レポート {len(res)} 件")
        for r in res:
            print(r["message"])
            for line in r.get("details", []):
                print("  - " + line)
