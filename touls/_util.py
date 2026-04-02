# -*- coding: utf-8 -*-
"""
_util.py  ─  assetChecker touls 共通ユーティリティ

assetChecker.py が TARGET_DIR（= このファイルのあるディレクトリ）を
sys.path に追加するため、各スクリプトから直接 import できる:

    from _util import iter_scene_mesh_shapes
"""
import maya.cmds as cmds


def _is_intermediate(shape):
    try:
        return bool(cmds.getAttr(f"{shape}.intermediateObject"))
    except Exception:
        return False


def iter_scene_mesh_shapes():
    """
    シーン内の non-intermediate mesh shape を全件取得する。
    ni / noIntermediate フラグを優先試行し、使えない環境はフォールバック。
    """
    for kwargs in ({"ni": True}, {"noIntermediate": True}):
        try:
            return cmds.ls(type="mesh", long=True, **kwargs) or []
        except TypeError:
            pass
        except Exception:
            pass

    meshes = cmds.ls(type="mesh", long=True) or []
    return [m for m in meshes if cmds.objExists(m) and not _is_intermediate(m)]
