# -*- coding: utf-8 -*-
"""
namespace_fix.py

デフォルト以外・非リファレンスの namespace を root に merge して削除する。

namespace は Maya ノードではないため selection には乗らない。よって selection を
参照せず、シーン内の全 namespace を再列挙して処理する。

深い namespace から先に処理する（親より子を先に削除しないと removeNamespace が失敗する）。
"""
import maya.cmds as cmds


_DEFAULT_NS = {":", "UI", "shared", ":UI", ":shared"}


def _is_referenced_ns(ns):
    try:
        return bool(cmds.namespaceInfo(ns, isRootNamespace=False, isReferenced=True))
    except Exception:
        return False


def _list_namespaces():
    try:
        all_ns = cmds.namespaceInfo(":", listOnlyNamespaces=True, recurse=True, absoluteName=True) or []
    except Exception:
        all_ns = []
    return [ns for ns in all_ns if ns not in _DEFAULT_NS]


def get_results():
    results = []

    # 深い順（コロンが多い順）に処理
    targets = sorted(_list_namespaces(), key=lambda x: x.count(":"), reverse=True)

    for ns in targets:
        if _is_referenced_ns(ns):
            results.append({
                "transform": ns,
                "message": f"スキップ: {ns} はリファレンス由来",
            })
            continue
        try:
            cmds.namespace(setNamespace=":")
        except Exception:
            pass
        try:
            cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
            results.append({
                "transform": ns,
                "message": f"merge & 削除: {ns}",
            })
        except Exception as e:
            results.append({
                "transform": ns,
                "message": f"merge 失敗 ({ns}): {e}",
            })

    return results


if __name__ == "__main__":
    for r in get_results():
        print(f'{r["transform"]}: {r["message"]}')
