# -*- coding: utf-8 -*-
"""
colorSet_correct.py
シーン内（または選択範囲）の mesh shape が持つ「カラーセット」を削除します。

- 選択がある場合: 選択 transform 配下の mesh を対象
- 選択がない場合: シーン内の全 mesh を対象
- intermediateObject は除外
- 参照ノード（reference）は基本スキップ（削除できない/事故防止）

checkList.py のUI連携想定:
- get_results() が list[dict] を返す
- dict には transform / message / details を入れる
"""

import maya.cmds as cmds


def _is_intermediate(shape: str) -> bool:
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
    except Exception:
        return False


def _parent_transform(shape: str) -> str:
    try:
        p = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        return p[0] if p else shape
    except Exception:
        return shape


def _short_name(dag_path: str) -> str:
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _is_referenced(node: str) -> bool:
    try:
        return bool(cmds.referenceQuery(node, isNodeReferenced=True))
    except Exception:
        return False


def _iter_target_meshes():
    """
    選択があれば選択配下、なければシーン全体の mesh を返す（fullPath）
    """
    sel = cmds.ls(sl=True, long=True) or []
    if sel:
        # 選択が shape の場合は親transformに寄せる
        transforms = []
        for n in sel:
            if cmds.nodeType(n) in ("mesh", "nurbsSurface", "nurbsCurve", "subdiv"):
                p = cmds.listRelatives(n, parent=True, fullPath=True) or []
                if p:
                    transforms.append(p[0])
            else:
                transforms.append(n)

        # 選択 transform 配下の mesh を全部
        meshes = []
        for t in transforms:
            if not cmds.objExists(t):
                continue
            shapes = cmds.listRelatives(t, ad=True, fullPath=True, type="mesh") or []
            meshes.extend(shapes)
        # 重複排除
        return sorted(set(meshes))

    # 選択が無ければシーン全体
    return cmds.ls(type="mesh", long=True) or []


def _get_color_sets(shape: str):
    try:
        return cmds.polyColorSet(shape, query=True, allColorSets=True) or []
    except Exception:
        return []


def _get_current_color_set(shape: str):
    try:
        cur = cmds.polyColorSet(shape, query=True, currentColorSet=True)
        if isinstance(cur, (list, tuple)) and cur:
            return cur[0]
        return cur
    except Exception:
        return None


def _set_current_color_set(shape: str, set_name: str) -> bool:
    try:
        cmds.polyColorSet(shape, currentColorSet=True, colorSet=set_name)
        return True
    except Exception:
        return False


def _delete_color_set(shape: str, set_name: str) -> bool:
    """
    polyColorSet の削除。環境差が出た時のため2パターン試す。
    """
    try:
        cmds.polyColorSet(shape, delete=True, colorSet=set_name)
        return True
    except Exception:
        # まれにフラグ名の解釈差で通らない環境向け
        try:
            cmds.polyColorSet(shape, delete=True, cs=set_name)  # type: ignore
            return True
        except Exception:
            return False


def get_results():
    results = []
    shapes = _iter_target_meshes()

    for shape in shapes:
        if not cmds.objExists(shape):
            continue
        if _is_intermediate(shape):
            continue

        # 参照ノードは基本スキップ
        if _is_referenced(shape) or _is_referenced(_parent_transform(shape)):
            results.append({
                "transform": _short_name(_parent_transform(shape)),
                "message": f"スキップ(参照): {_short_name(_parent_transform(shape))} / {_short_name(shape)}",
                "details": [f"Shape: {shape}", "Reason: referenced node"],
            })
            continue

        color_sets = _get_color_sets(shape)
        if not color_sets:
            continue

        parent = _parent_transform(shape)
        parent_short = _short_name(parent)
        shape_short = _short_name(shape)

        removed = []
        failed = []

        # current を見て、消す直前に別セットへ切り替える（必要な場合）
        cur = _get_current_color_set(shape)

        # 削除は「一覧にあるもの全部」
        # ただし current を消すときは、残る候補があるなら先に切り替える
        for cs_name in list(color_sets):
            # まだ存在するセット一覧を更新（途中で消えるので）
            now_sets = _get_color_sets(shape)

            if cs_name not in now_sets:
                continue

            now_cur = _get_current_color_set(shape)

            if now_cur == cs_name:
                # 消す対象が current の場合、他があれば一旦切り替え
                alt = None
                for cand in now_sets:
                    if cand != cs_name:
                        alt = cand
                        break
                if alt:
                    _set_current_color_set(shape, alt)

            ok = _delete_color_set(shape, cs_name)
            if ok:
                removed.append(cs_name)
            else:
                failed.append(cs_name)

        # まとめて結果を返す（削除できた/できなかったが分かるように）
        detail_lines = [f"Shape: {shape}"]
        if removed:
            detail_lines.append("Removed: " + ", ".join(removed))
        if failed:
            detail_lines.append("Failed: " + ", ".join(failed))

        if removed and not failed:
            msg = f"カラーセット削除: {parent_short} / {shape_short}（{len(removed)} sets）"
        elif removed and failed:
            msg = f"カラーセット一部削除: {parent_short} / {shape_short}（removed {len(removed)} / failed {len(failed)}）"
        else:
            msg = f"カラーセット削除失敗: {parent_short} / {shape_short}"

        results.append({
            "transform": parent_short,
            "message": msg,
            "details": detail_lines,
        })

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[ColorSet Correct] 対象なし（カラーセット所持meshが見つからない、または全てスキップ）")
    else:
        print(f"[ColorSet Correct] レポート {len(res)} 件")
        for r in res:
            print(r["message"])
            for line in r.get("details", []):
                print("  - " + line)
