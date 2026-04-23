# -*- coding: utf-8 -*-
"""
negativeScale_fix.py
選択オブジェクトのマイナススケールを makeIdentity(scale) でフリーズし、
見た目が裏返らないよう法線を全フェース反転する。

注意: スケールに奇数個のマイナスがある場合のみ法線反転が必要。
     偶数個（例: -1, -1, 1）の場合は法線方向は変わらないが、
     安全のため常に反転を行う（反転後に再 check で確認推奨）。
"""
import maya.cmds as cmds

TOL = 1e-6


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
            s = cmds.getAttr(f"{tr}.scale")[0]
        except Exception:
            continue
        if not any(val < -TOL for val in s):
            continue

        # 奇数個のマイナス軸 → 法線反転が必要
        neg_count = sum(1 for val in s if val < -TOL)
        need_flip = (neg_count % 2 == 1)

        try:
            cmds.makeIdentity(tr, apply=True, s=True, t=False, r=False, n=False, pn=True)

            msg_parts = [f"スケールフリーズ: {_short_name(tr)}"]
            if need_flip:
                shapes = cmds.listRelatives(tr, shapes=True, type="mesh", noIntermediate=True, fullPath=True) or []
                for shape in shapes:
                    n_faces = cmds.polyEvaluate(shape, f=True) or 0
                    if n_faces > 0:
                        cmds.select(f"{shape}.f[0:{n_faces - 1}]", r=True)
                        cmds.polyNormal(normalMode=0, userNormalMode=0, ch=True)
                cmds.select(tr, r=True)
                msg_parts.append("法線反転実行")

            results.append({
                "transform": _short_name(tr),
                "message": " + ".join(msg_parts),
            })
        except Exception as e:
            results.append({
                "transform": _short_name(tr),
                "message": f"修正失敗: {e}",
            })
    return results


if __name__ == "__main__":
    for r in get_results():
        print(f'{r["transform"]}: {r["message"]}')
