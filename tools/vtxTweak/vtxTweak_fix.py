# vtxTweak_fix.py
# Lattice を一度かけてから Delete History で焼く（見た目を維持したまま pnts を 0 系に寄せる意図）
# ※ lattice を動かさなければ見た目は変わりません（作って即焼くので当然）
# ※ 既に変形（skin/cluster等）がある場合は「焼く」= その変形を破壊する可能性があります

import maya.cmds as cmds


def lattice_apply_auto(selected_only=True, divisions=(2, 2, 2), object_centered=True):
    """
    Returns:
        list[dict]: checkList.py 側で扱いやすい構造化結果
    """
    results = []

    # 対象取得
    targets = cmds.ls(sl=True, type="transform") if selected_only else cmds.ls(type="transform")
    if not targets:
        cmds.warning("transform が選択されていません。")
        return results

    # mesh shape を持つ transform に絞る
    mesh_transforms = []
    for t in targets:
        if not cmds.objExists(t):
            continue
        shapes = cmds.listRelatives(t, s=True, ni=True, type="mesh") or []
        if shapes:
            mesh_transforms.append(t)

    if not mesh_transforms:
        cmds.warning("mesh を持つ transform が選択されていません。")
        return results

    # 選択退避
    prev_sel = cmds.ls(sl=True, long=True) or []

    ffd_nodes = []
    lattice_nodes = []
    base_lattice_nodes = []

    try:
        # まとめてラティス作成（ffd#, lattice#, baseLattice#）
        cmds.select(mesh_transforms, r=True)
        created = cmds.lattice(divisions=divisions, objectCentered=object_centered) or []
        # created 例: ['ffd1', 'lattice1', 'baseLattice1']
        if len(created) >= 1:
            ffd_nodes.append(created[0])
        if len(created) >= 2:
            lattice_nodes.append(created[1])
        if len(created) >= 3:
            base_lattice_nodes.append(created[2])

        # ここで lattice のポイントを動かす処理を入れるならここ
        # （現状は何もしない = 見た目変化なし）

        # “Apply” 相当：履歴を焼く
        # ※ delete(ch=True) はその transform の履歴を全部消します
        for t in mesh_transforms:
            try:
                cmds.delete(t, ch=True)
                results.append({
                    "transform": t,
                    "message": "Delete History を実行しました（ラティス適用/焼き込み）",
                    "ok": True,
                })
            except Exception as e:
                results.append({
                    "transform": t,
                    "message": f"Delete History に失敗: {e}",
                    "ok": False,
                })

    except Exception as e:
        # ラティス作成自体が失敗した場合
        for t in mesh_transforms:
            results.append({
                "transform": t,
                "message": f"ラティス作成/適用の処理が失敗: {e}",
                "ok": False,
            })
    finally:
        # 選択を戻す
        try:
            if prev_sel:
                cmds.select(prev_sel, r=True)
            else:
                cmds.select(clear=True)
        except Exception:
            pass

    # UI で参照したいならノード名も返す（必要なければ消してOK）
    if results:
        results.append({
            "transform": "(info)",
            "message": f"created: ffd={ffd_nodes}, lattice={lattice_nodes}, base={base_lattice_nodes}",
            "ok": True,
        })

    return results


def get_results():
    """
    checkList.py の run_py_get_structured_or_text() が優先的に呼ぶ入口
    """
    return lattice_apply_auto(selected_only=True)
