# -*- coding: utf-8 -*-
"""
unusedShadingNode_check.py

check処理:
shadingEngine に到達しないシェーディング関連ノード（マテリアル / テクスチャ / utility）
を検出します。Maya 標準の "Delete Unused Nodes" 相当。

対象（シーン全体・選択に関係なく常に全件）:
- materials (lambert, blinn, phong, surfaceShader, ...)
- textures  (file, ramp, ...)
- 主要 shading utility ノード

リファレンス由来のノードと、Maya がシーン作成時に生成する既定ノード
（lambert1 / particleCloud1 / shaderGlow1）は除外。

severity: WARNING
  → 検出されても削除推奨だが、テンプレート用 / 後で接続予定 / リギング都合で
    意図的に残しているケースもあるため、誤検知を考慮して警告扱いとする。
"""
import maya.cmds as cmds
from _results import CheckResult, Severity


_DEFAULT_NAMES = {"lambert1", "particleCloud1", "shaderGlow1"}

_UTIL_TYPES = [
    "place2dTexture", "place3dTexture", "bump2d", "bump3d",
    "reverse", "multiplyDivide", "blendColors", "condition",
    "plusMinusAverage", "samplerInfo", "luminance", "contrast",
    "remapValue", "remapColor", "remapHsv", "gammaCorrect",
    "rgbToHsv", "hsvToRgb", "clamp", "setRange", "vectorProduct",
    "layeredTexture", "projection", "stencil",
]


def _candidates():
    s = set()
    s.update(cmds.ls(materials=True) or [])
    s.update(cmds.ls(textures=True) or [])
    for t in _UTIL_TYPES:
        s.update(cmds.ls(type=t) or [])
    return s - _DEFAULT_NAMES


def _has_downstream_shading_engine(node):
    """node から下流をたどって shadingEngine に到達できれば True。"""
    visited = {node}
    queue = [node]
    while queue:
        cur = queue.pop(0)
        if cmds.nodeType(cur) == "shadingEngine":
            return True
        downs = cmds.listConnections(cur, source=False, destination=True) or []
        for d in downs:
            if d not in visited:
                visited.add(d)
                queue.append(d)
    return False


def _is_referenced(node):
    try:
        return cmds.referenceQuery(node, isNodeReferenced=True)
    except Exception:
        return False


def get_results():
    results = []
    for n in sorted(_candidates()):
        if _is_referenced(n):
            continue
        if _has_downstream_shading_engine(n):
            continue
        try:
            t = cmds.nodeType(n)
        except Exception:
            continue
        results.append(CheckResult(
            target=n,
            message=f"unused: {n} ({t})",
            details=[
                f"Type: {t}",
                "shadingEngine への接続なし",
            ],
            severity=Severity.ERROR,
        ))
    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[unusedShadingNode] 該当ノードは見つかりませんでした。")
    else:
        print(f"[unusedShadingNode] {len(res)} 件")
        for r in res:
            print(r.message)
