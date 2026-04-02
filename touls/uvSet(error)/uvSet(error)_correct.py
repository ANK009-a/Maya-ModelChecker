# -*- coding: utf-8 -*-
"""
uvSet(error)_correct.py

内容:
シーン内の mesh について、
「polyUVSet -q -allUVSets（=UV Set Editor想定の一覧）には出ないのに、
shape.uvSet[*].uvSetPoints を保持している uvSet」
を “エラーUVset” とみなし、すべて除去します（選択不要）。

方式:
- meshShape.uvSet の multiIndices を走査
- uvSetName が “見えるUVset一覧” に含まれない かつ uvSetPoints size>0 を対象
- cmds.removeMultiInstance("shape.uvSet[i]", b=True) で uvSet エントリ自体を削除

注意:
- 参照ノード（reference）は基本スキップ（削除できない/事故防止）
- intermediateObject は除外
- Mayaの内部状態によっては removeMultiInstance が失敗する場合があります（レポートに残します）

checkList.py のUI連携想定:
- get_results() が list[dict] を返す（何も処理しなければ [] でもOKだが、ここはレポートを返す）
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


def _get_visible_uv_sets(shape: str):
    """UV Set Editorに出る想定のUVセット一覧"""
    try:
        uv_sets = cmds.polyUVSet(shape, query=True, allUVSets=True)
    except Exception:
        uv_sets = None

    if not uv_sets:
        return []
    if isinstance(uv_sets, (list, tuple)):
        return list(uv_sets)
    return [str(uv_sets)]


def _get_uvset_indices(shape: str):
    """meshShape.uvSet[*] の配列インデックス"""
    try:
        idx = cmds.getAttr(f"{shape}.uvSet", multiIndices=True) or []
        return list(idx)
    except Exception:
        return []


def _get_uvset_name(shape: str, i: int):
    try:
        return cmds.getAttr(f"{shape}.uvSet[{i}].uvSetName")
    except Exception:
        return None


def _get_uvset_points_size(shape: str, i: int):
    try:
        return int(cmds.getAttr(f"{shape}.uvSet[{i}].uvSetPoints", size=True))
    except Exception:
        return None


def _unlock_attr(attr: str):
    """ロックされていたら解除を試みる（失敗しても無視）"""
    try:
        if cmds.getAttr(attr, lock=True):
            cmds.setAttr(attr, lock=False)
    except Exception:
        pass


def _remove_uvset_instance(shape: str, i: int):
    """
    uvSet[i] を removeMultiInstance で削除
    Returns: (ok: bool, reason: str|None)
    """
    plug = f"{shape}.uvSet[{i}]"

    # 念のため、関連プラグのロック解除を試す
    _unlock_attr(plug)
    _unlock_attr(f"{plug}.uvSetName")
    _unlock_attr(f"{plug}.uvSetPoints")

    try:
        cmds.removeMultiInstance(plug, b=True)  # b=True で接続も切る
        return True, None
    except Exception as e:
        return False, str(e)


def get_results():
    results = []

    shapes = cmds.ls(type="mesh", long=True) or []

    for shape in shapes:
        if not cmds.objExists(shape):
            continue
        if _is_intermediate(shape):
            continue

        parent = _parent_transform(shape)

        # 参照ノードはスキップ
        if _is_referenced(shape) or _is_referenced(parent):
            continue

        visible = _get_visible_uv_sets(shape)
        visible_set = set(visible)

        idx_list = _get_uvset_indices(shape)
        if not idx_list:
            continue

        targets = []  # (i, name, size)
        unknown = []  # (i, name) size取得失敗

        for i in idx_list:
            name = _get_uvset_name(shape, i)
            name_str = name if name else "<unnamed>"

            size = _get_uvset_points_size(shape, i)
            if size is None:
                unknown.append((i, name_str))
                continue
            if size <= 0:
                continue

            # “見えない”判定：polyUVSetの一覧に含まれない
            if name_str not in visible_set:
                targets.append((i, name_str, size))

        if not targets:
            continue

        removed = []
        failed = []

        for i, n, s in targets:
            ok, reason = _remove_uvset_instance(shape, i)
            if ok:
                removed.append((i, n, s))
            else:
                failed.append((i, n, s, reason))

        # 削除後の再チェック（残ってるか確認）
        remain = []
        idx_list2 = _get_uvset_indices(shape)
        for i in idx_list2:
            name = _get_uvset_name(shape, i)
            name_str = name if name else "<unnamed>"
            size = _get_uvset_points_size(shape, i)
            if size and size > 0 and name_str not in visible_set:
                remain.append((i, name_str, size))

        parent_short = _short_name(parent)
        shape_short = _short_name(shape)

        details = [
            f"Shape: {shape}",
            "Visible(UV Set Editor): " + (", ".join(visible) if visible else "(none)"),
            "Removed:",
        ]
        for i, n, s in removed:
            details.append(f"  - [{i}] {n} / uvSetPoints size={s}")

        if failed:
            details.append("Failed:")
            for i, n, s, reason in failed:
                details.append(f"  - [{i}] {n} / size={s} / reason={reason}")

        if unknown:
            details.append("Unknown(size取得失敗):")
            for i, n in unknown:
                details.append(f"  - [{i}] {n}")

        if remain:
            details.append("Remain(after):")
            for i, n, s in remain:
                details.append(f"  - [{i}] {n} / uvSetPoints size={s}")

        if removed and not failed and not remain:
            msg = f"UVSet(error)除去: {parent_short} / {shape_short}（{len(removed)} sets）"
        elif removed and (failed or remain):
            msg = f"UVSet(error)一部除去: {parent_short} / {shape_short}（removed {len(removed)} / failed {len(failed)} / remain {len(remain)}）"
        else:
            msg = f"UVSet(error)除去失敗: {parent_short} / {shape_short}"

        results.append({
            "transform": parent_short,
            "message": msg,
            "details": details,
        })

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[UVSet(Error) Correct] 対象なし")
    else:
        print(f"[UVSet(Error) Correct] レポート {len(res)} 件")
        for r in res:
            print(r["message"])
            for line in r.get("details", []):
                print("  - " + line)
