# -*- coding: utf-8 -*-
"""
autoNode_check.py

check処理:
Maya が自動生成する不要ノードを検出します。
- SavedTabsInfo 系: Node Editor / Hypershade のタブ状態保存ノード
- mayaUsdLayerManager 系: USD プラグインが生成するレイヤーマネージャーノード
対象はシーン全体（選択に関係なく常に全件）。
"""
import maya.cmds as cmds
from _results import CheckResult, Severity


# 名前に含まれる文字列で検出するパターン
_NAME_CONTAINS = [
    ("SavedTabsInfo", "エディタのタブ情報保存ノード（Node Editor / Hypershade が自動生成）"),
]

# ノードタイプで検出するリスト
_TYPE_LIST = [
    ("mayaUsdLayerManager", "Maya USD プラグインが自動生成するレイヤーマネージャー"),
]


def get_results():
    results = []
    seen = set()

    for pattern, desc in _NAME_CONTAINS:
        for n in (cmds.ls(f"*{pattern}*") or []):
            if n in seen:
                continue
            seen.add(n)
            try:
                node_type = cmds.nodeType(n)
            except Exception:
                node_type = "unknown"
            results.append(CheckResult(
                target=n,
                message=f"自動生成ノード: {n}",
                details=[f"Type: {node_type}", desc],
                severity=Severity.ERROR,
            ))

    for node_type, desc in _TYPE_LIST:
        for n in (cmds.ls(type=node_type) or []):
            if n in seen:
                continue
            seen.add(n)
            results.append(CheckResult(
                target=n,
                message=f"自動生成ノード: {n}",
                details=[f"Type: {node_type}", desc],
                severity=Severity.ERROR,
            ))

    results.sort(key=lambda r: r.target)
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[autoNode] 該当ノードは見つかりませんでした。")
    else:
        print(f"[autoNode] {len(res)} 件")
        for r in res:
            print(r.message)
