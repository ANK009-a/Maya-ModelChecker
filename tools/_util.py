# -*- coding: utf-8 -*-
"""
_util.py  ─  assetChecker tools 共通ユーティリティ

assetChecker.py が GitHub からフェッチして sys.modules に登録するため、
各スクリプトから直接 import できる:

    from _util import iter_scene_mesh_shapes
"""
import maya.cmds as cmds

_checker_selection = None  # load_and_run() が実行前にセット（[] = 全体チェック）


def _is_intermediate(shape):
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
    except Exception:
        return False


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
