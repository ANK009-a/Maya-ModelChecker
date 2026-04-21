# -*- coding: utf-8 -*-
"""
_util.py  ─  assetChecker tools 共通ユーティリティ

assetChecker.py が GitHub からフェッチして sys.modules に登録するため、
各スクリプトから直接 import できる:

    from _util import iter_scene_mesh_shapes, short_name, parent_transform, is_referenced
"""
import maya.cmds as cmds

_checker_selection = None  # load_and_run() が実行前にセット（[] = 全体チェック）


def checker_selection():
    """現在のチェッカー選択を返す。None/[] はシーン全体対象を意味する。"""
    return _checker_selection or []


# ----------------------------------------------------------------------
# 名前・階層ユーティリティ
# ----------------------------------------------------------------------
def short_name(dag_path):
    """DAG パスから末尾（leaf）名を返す。'|a|b|c' -> 'c'"""
    return dag_path.rsplit("|", 1)[-1] if "|" in dag_path else dag_path


def parent_transform(shape):
    """shape の親 transform の fullPath を返す。無い場合は shape を返す。"""
    try:
        p = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        return p[0] if p else shape
    except Exception:
        return shape


def is_referenced(node):
    """ノードがリファレンス由来かを判定。"""
    try:
        return bool(cmds.referenceQuery(node, isNodeReferenced=True))
    except Exception:
        return False


def _is_intermediate(shape):
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
    except Exception:
        return False


# ----------------------------------------------------------------------
# mesh 列挙（選択対応）
# ----------------------------------------------------------------------
def iter_scene_mesh_shapes():
    """
    選択がある場合は選択オブジェクト配下の mesh shape、
    ない場合はシーン内全件の non-intermediate mesh shape を返す。
    """
    sel = _checker_selection
    if sel:
        for kwargs in ({"ni": True}, {"noIntermediate": True}):
            try:
                meshes = cmds.ls(sel, dag=True, type="mesh", long=True, **kwargs) or []
                if meshes:
                    return meshes
            except TypeError:
                pass
            except Exception:
                pass
        meshes = cmds.ls(sel, dag=True, type="mesh", long=True) or []
        return [m for m in meshes if cmds.objExists(m) and not _is_intermediate(m)]

    for kwargs in ({"ni": True}, {"noIntermediate": True}):
        try:
            return cmds.ls(type="mesh", long=True, **kwargs) or []
        except TypeError:
            pass
        except Exception:
            pass
    meshes = cmds.ls(type="mesh", long=True) or []
    return [m for m in meshes if cmds.objExists(m) and not _is_intermediate(m)]


def iter_unique_mesh_parents():
    """
    シーン内 mesh shape の親 transform を重複なしで返す（順序保持）。
    選択対応（iter_scene_mesh_shapes に準じる）。
    """
    seen = set()
    parents = []
    for shape in iter_scene_mesh_shapes():
        p = parent_transform(shape)
        if p in seen:
            continue
        seen.add(p)
        parents.append(p)
    return parents
