# -*- coding: utf-8 -*-
"""
texturePath_check.py
シーン内の file ノードを検索し、以下の問題を報告する:
  - パス未設定
  - ファイルが存在しない
UDIM / シーケンステクスチャ（<UDIM>, %04d 等）は存在チェックをスキップする。
"""
import os
import maya.cmds as cmds


def get_results():
    results = []
    file_nodes = cmds.ls(type="file") or []

    for fn in file_nodes:
        path = (cmds.getAttr(f"{fn}.fileTextureName") or "").strip()

        if not path:
            results.append({
                "transform": fn,
                "message": f"パス未設定: {fn}",
                "details": ["fileTextureName が空です"],
            })
            continue

        issues = []
        details = [f"ノード: {fn}", f"パス: {path}"]

        is_sequence = "<" in path or "%" in path or "#" in path

        # ファイル存在チェック（シーケンス系はスキップ）
        if not is_sequence and not os.path.exists(path):
            issues.append("ファイル不存在")
            details.append("⚠ ファイルが見つかりません")

        if is_sequence:
            details.append("(UDIM / シーケンステクスチャ: 実在チェックをスキップ)")

        if issues:
            results.append({
                "transform": fn,
                "message": f"テクスチャ問題 ({', '.join(issues)}): {fn}",
                "details": details,
            })

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[texturePath] テクスチャパスの問題は見つかりませんでした。")
    else:
        for r in res:
            print(r["message"])
