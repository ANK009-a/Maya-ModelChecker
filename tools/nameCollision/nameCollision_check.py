# -*- coding: utf-8 -*-
"""
nameCollision_check.py / check.py
シーン内で名称が衝突している DAG ノードを検出して返す。

- DAG ノードの fullPath(例: |group1|foo) を列挙
- leaf 名(例: foo) ごとにグルーピング
- 同じ leaf 名が複数存在するものを「名称衝突」として報告

checkList.py のUI連携想定:
- get_results() が list[dict] を返す
- dict には transform / message / details を入れる
"""

from collections import defaultdict
import maya.cmds as cmds
from _util import (
    short_name as _leaf_name,
    checker_selection as _checker_selection,
)
from _results import CheckResult, Severity

# 必要なら除外したい “標準” ノード（カメラ類）
_DEFAULT_EXCLUDES = {
    "persp", "top", "front", "side",
    "perspShape", "topShape", "frontShape", "sideShape",
}


def get_results(exclude_defaults: bool = True):
    """
    Returns:
        list[dict]: [
          {
            "transform": "<衝突している短い名前>",
            "message": "...",
            "details": ["|path|to|node (type)", ...]
          },
          ...
        ]
    """
    sel = _checker_selection()
    if sel:
        dag_paths = cmds.ls(sel, dag=True, long=True) or []
    else:
        dag_paths = cmds.ls(dag=True, long=True) or []
    groups = defaultdict(list)

    for p in dag_paths:
        leaf = _leaf_name(p)
        if exclude_defaults and leaf in _DEFAULT_EXCLUDES:
            continue
        groups[leaf].append(p)

    results = []
    for leaf in sorted(groups.keys()):
        items = groups[leaf]
        if len(items) <= 1:
            continue

        details = []
        for p in items:
            try:
                t = cmds.nodeType(p)
            except Exception:
                t = "unknown"
            details.append(f"{p} ({t})")

        results.append(CheckResult(
            target=leaf,  # UI左の一覧で「衝突名」ごとにまとまる
            message=f"名称衝突: '{leaf}' が {len(items)} 個あります。",
            details=details,
            severity=Severity.ERROR,
        ))

    return results


if __name__ == "__main__":
    # Script Editor で単体実行したときの表示
    res = get_results()
    if not res:
        print("[NameCollision] 名称衝突は見つかりませんでした。")
    else:
        print(f"[NameCollision] 名称衝突が {len(res)} 件見つかりました。")
        for r in res:
            print(r.message)
            for line in r.details:
                print("  - " + line)
