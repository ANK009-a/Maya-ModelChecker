# -*- coding: utf-8 -*-
"""
lockNormal_check_allScene_fast.py

速度改善版（大規模シーン向け）
- 選択判定なし：常にシーン内の mesh shape を全件対象
- intermediate shape は除外
- 可能なら maya.api.OpenMaya 側のAPIで「法線ロック」を軽く判定（環境差があるため存在チェック付き）
- APIが使えない場合は従来どおり polyNormalPerVertex(freezeNormal=True) で判定（これが最も重い）

返却形式（checkList / assetChecker想定）:
- get_results() -> list[dict]
  dict keys: "transform", "message"
"""

from __future__ import annotations

import maya.cmds as cmds
from _util import iter_scene_mesh_shapes as _iter_scene_mesh_shapes


# ----------------------------
# Utils
# ----------------------------
def _short_name(dag_path: str) -> str:
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def _is_intermediate(shape: str) -> bool:
    try:
        return bool(cmds.getAttr(shape + ".intermediateObject"))
    except Exception:
        return False


def _shape_parent_transform(shape: str) -> str:
    """shape の親 transform（fullPath）を返す。無い場合は shape を返す。"""
    try:
        p = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        return p[0] if p else shape
    except Exception:
        return shape


# ----------------------------
# Locked normals check
# ----------------------------
def _has_locked_normals_api(mesh_shape: str):
    """
    maya.api.OpenMaya を使えれば軽く判定できる可能性があるため試す。
    ただし Maya のビルド/環境でメソッド有無が違う可能性があるので、存在チェックしてダメなら None を返す。

    return:
      - (has_locked: bool, locked_count: int|None)  … 判定成功
      - None                                      … API未対応/失敗
    """
    try:
        import maya.api.OpenMaya as om2
    except Exception:
        return None

    try:
        sel = om2.MSelectionList()
        sel.add(mesh_shape)
        dag = sel.getDagPath(0)
        fn = om2.MFnMesh(dag)

        # 1) 代表的なAPI名がある場合はそれを優先（無ければフォールバック）
        if hasattr(fn, "getLockedNormals"):
            locked = fn.getLockedNormals()
            # locked が iterable(bool) を返す想定だが、型が違う可能性があるので頑健に数える
            cnt = 0
            try:
                for v in locked:
                    if bool(v):
                        cnt += 1
            except Exception:
                # 形式が想定外なら「ある/ない」だけ返す
                return (True, None) if locked else (False, 0)
            return (cnt > 0, cnt)

        # 2) isNormalLocked + numNormals がある場合は早期終了で「ある/ない」だけ判定
        if hasattr(fn, "isNormalLocked") and hasattr(fn, "numNormals"):
            n = int(fn.numNormals)
            for i in range(n):
                try:
                    if fn.isNormalLocked(i):
                        return (True, None)
                except Exception:
                    break
            return (False, 0)

        return None

    except Exception:
        return None


def _has_locked_normals_cmds(mesh_shape: str):
    """
    従来方式（重い）:
    polyNormalPerVertex(..., q=True, freezeNormal=True) で全頂点分の状態を受け取り、locked数を数える。
    """
    try:
        vals = cmds.polyNormalPerVertex(mesh_shape + ".vtx[*]", q=True, freezeNormal=True)
        if not vals:
            return (False, 0, None)

        # Python側のループは最小限に（sum(map(bool, ...)) が速め）
        try:
            locked = sum(1 for v in vals if bool(v))
        except Exception:
            locked = 0
            for v in vals:
                try:
                    if bool(v):
                        locked += 1
                except Exception:
                    pass

        return (locked > 0, locked, None)

    except Exception as e:
        return (False, 0, str(e))


def _has_locked_normals(mesh_shape: str):
    """
    まずAPIで軽く判定できないか試し、ダメなら cmds 方式へ。
    return: (has_locked: bool, locked_count: int|None, err: str|None, used: str)
    """
    api_res = _has_locked_normals_api(mesh_shape)
    if api_res is not None:
        has_locked, locked_count = api_res
        return (has_locked, locked_count, None, "api")

    has_locked, locked_count, err = _has_locked_normals_cmds(mesh_shape)
    return (has_locked, locked_count, err, "cmds")


# ----------------------------
# Public API
# ----------------------------
def get_results():
    shapes = _iter_scene_mesh_shapes()

    # transform -> [mesh_shapes]
    tr_to_shapes = {}
    for shape in shapes:
        tr = _shape_parent_transform(shape)
        tr_to_shapes.setdefault(tr, []).append(shape)

    results = []

    for tr, mesh_shapes in tr_to_shapes.items():
        tr_short = _short_name(tr)
        locked_infos = []
        last_err = None
        err_count = 0

        for shape in mesh_shapes:
            has_locked, locked_count, err, used = _has_locked_normals(shape)
            if err:
                last_err = err
                err_count += 1
                continue

            if has_locked:
                sname = _short_name(shape)
                if locked_count is None:
                    locked_infos.append(f"{sname} : locked")
                else:
                    locked_infos.append(f"{sname} : locked({locked_count})")

        if locked_infos:
            results.append({
                "transform": tr_short,
                "message": " / ".join(locked_infos)
            })
        else:
            # すべて失敗した場合のみエラーとして返す（不要ならこのブロックを削除）
            if last_err and err_count == len(mesh_shapes):
                results.append({
                    "transform": tr_short,
                    "message": f"法線ロック判定エラー: {last_err}"
                })

    return results


if __name__ == "__main__":
    for item in get_results():
        print(f'{item.get("transform")} : {item.get("message")}')
