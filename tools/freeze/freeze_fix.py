# freeze_fix.py
# 選択中オブジェクトのうち
# - translate != (0,0,0)
# - rotate    != (0,0,0)
# - scale     != (1,1,1)
# の成分だけを Freeze Transform（makeIdentity）する
# checkList_v001.py 向けに get_results() で構造化結果を返す

import maya.cmds as cmds

TOL = 1e-6


def _neq(a, b, tol=TOL):
    return abs(a - b) > tol


def _vec_not_equal(v, target, tol=TOL):
    return any(_neq(v[i], target[i], tol) for i in range(3))


def _to_transforms(selection):
    """shape が選ばれても transform に正規化して返す（重複除去・順序維持）"""
    transforms = []
    for n in selection:
        if not cmds.objExists(n):
            continue
        if cmds.nodeType(n) == "transform":
            transforms.append(n)
        else:
            parents = cmds.listRelatives(n, parent=True, fullPath=True) or []
            transforms.extend([p for p in parents if cmds.nodeType(p) == "transform"])

    seen = set()
    uniq = []
    for t in transforms:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def _attr_locked_or_connected(node, attr):
    """ロック or 入力接続があるか（安全側に倒す）"""
    plug = f"{node}.{attr}"
    try:
        if cmds.getAttr(plug, lock=True):
            return True
        con = cmds.listConnections(plug, s=True, d=False, p=True) or []
        return len(con) > 0
    except Exception:
        return True


def fix():
    sel = cmds.ls(sl=True, long=True) or []
    transforms = _to_transforms(sel)

    results = []
    if not transforms:
        return results

    for tr in transforms:
        try:
            t = cmds.getAttr(tr + ".translate")[0]
            r = cmds.getAttr(tr + ".rotate")[0]
            s = cmds.getAttr(tr + ".scale")[0]

            bad_t = _vec_not_equal(t, (0.0, 0.0, 0.0))
            bad_r = _vec_not_equal(r, (0.0, 0.0, 0.0))
            bad_s = _vec_not_equal(s, (1.0, 1.0, 1.0))

            if not (bad_t or bad_r or bad_s):
                continue  # デフォルトなら触らない

            # 適用する成分だけブロック判定
            blocked = []
            if bad_t and any(_attr_locked_or_connected(tr, a) for a in ("translateX", "translateY", "translateZ")):
                blocked.append("T(locked/connected)")
            if bad_r and any(_attr_locked_or_connected(tr, a) for a in ("rotateX", "rotateY", "rotateZ")):
                blocked.append("R(locked/connected)")
            if bad_s and any(_attr_locked_or_connected(tr, a) for a in ("scaleX", "scaleY", "scaleZ")):
                blocked.append("S(locked/connected)")

            if blocked:
                results.append({
                    "transform": tr,
                    "message": "フリーズスキップ: " + ", ".join(blocked)
                })
                continue

            # Freeze Transform（必要な成分だけ）
            # pn=True で pivot を維持しやすい
            cmds.makeIdentity(
                tr,
                apply=True,
                t=bad_t,
                r=bad_r,
                s=bad_s,
                n=False,
                pn=True
            )

            done = []
            if bad_t: done.append("T")
            if bad_r: done.append("R")
            if bad_s: done.append("S")

            results.append({
                "transform": tr,
                "message": f"フリーズ実行: {''.join(done)}"
            })

        except Exception as e:
            results.append({
                "transform": tr,
                "message": f"フリーズ失敗: {e}"
            })

    return results


def get_results():
    # checkList_v001.py の structured ルートで拾わせる入口
    return fix()


if __name__ == "__main__":
    # 単体実行時は Script Editor に出す
    for item in fix():
        print(f'{item.get("transform")} : {item.get("message")}')
