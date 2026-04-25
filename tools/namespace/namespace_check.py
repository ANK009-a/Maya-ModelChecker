# -*- coding: utf-8 -*-
"""
namespace_check.py

check処理:
デフォルト（UI / shared / :）以外の namespace を検出します。

対象（シーン全体・選択に関係なく常に全件）:
- ルート以下の全 namespace（再帰）
- リファレンス由来の namespace は merge できないため除外

namespace は Maya ノードではないため Maya 上では選択されない。FIX では
selection を参照せず、再度 namespace を列挙してすべて root に merge する。
"""
import maya.cmds as cmds
from _results import CheckResult, Severity


_DEFAULT_NS = {":", "UI", "shared", ":UI", ":shared"}


def _is_referenced_ns(ns):
    try:
        return bool(cmds.namespaceInfo(ns, isRootNamespace=False, isReferenced=True))
    except Exception:
        return False


def _list_namespaces():
    """ルート以下の全 namespace（再帰、絶対表記）を返す。"""
    try:
        all_ns = cmds.namespaceInfo(":", listOnlyNamespaces=True, recurse=True, absoluteName=True) or []
    except Exception:
        all_ns = []
    return [ns for ns in all_ns if ns not in _DEFAULT_NS]


def get_results():
    results = []
    for ns in sorted(_list_namespaces(), key=lambda x: (x.count(":"), x)):
        is_ref = _is_referenced_ns(ns)
        try:
            contents = cmds.namespaceInfo(ns, listNamespace=True) or []
        except Exception:
            contents = []
        details = [
            f"Namespace: {ns}",
            f"Contents: {len(contents)}",
        ]
        if is_ref:
            details.append("⚠ リファレンス由来のため FIX では merge されません")
        results.append(CheckResult(
            target=ns,
            message=f"namespace: {ns}" + ("  [referenced]" if is_ref else ""),
            details=details,
            severity=Severity.WARNING,
        ))
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[namespace] 該当 namespace は見つかりませんでした。")
    else:
        print(f"[namespace] {len(res)} 件")
        for r in res:
            print(r.message)
