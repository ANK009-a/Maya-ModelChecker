# -*- coding: utf-8 -*-
"""
laminaFace_correct.py
選択オブジェクトのラミナフェース（完全重複面）を削除する。
polyInfo で面インデックスを特定し、該当フェースを delete する。
"""
import re
import maya.cmds as cmds


def _short_name(dag_path):
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _is_intermediate(shape):
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
    except Exception:
        return False


def _parse_face_indices(info_lines):
    """polyInfo の結果行からフェースインデックスを抽出"""
    indices = []
    for line in info_lines:
        m = re.search(r':\s*(\d+)', line)
        if m:
            indices.append(int(m.group(1)))
    return indices


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
        shapes = cmds.listRelatives(tr, shapes=True, type="mesh", noIntermediate=True, fullPath=True) or []
        for shape in shapes:
            lamina = cmds.polyInfo(shape, laminaFaces=True) or []
            if not lamina:
                continue
            indices = _parse_face_indices(lamina)
            if not indices:
                continue
            face_comps = [f"{shape}.f[{i}]" for i in indices]
            try:
                cmds.select(face_comps, r=True)
                cmds.delete()
                results.append({
                    "transform": _short_name(tr),
                    "message": f"ラミナフェース削除: {len(indices)} 面",
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
