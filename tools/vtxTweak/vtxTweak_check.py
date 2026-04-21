# -*- coding: utf-8 -*-
"""
vtx_check_optimized.py
シーン内の mesh で、vertex tweak（meshShape.pnts[]）が残っているものをリスト（高速化版）

改善点（元 vtx_check.py から）:
- multiIndices が取れた場合、pnts[i] を 1個ずつ getAttr せず、
  連番をレンジ化して getAttr("pnts[start:end]") でまとめ取得して走査（大幅に高速化しやすい）
- multiIndices が空のときの全頂点走査（フォールバック）を、
  pnts の要素数が 0 の場合はスキップして無駄走査を避ける

注意:
- デフォーマ等で動いている “結果の位置” は対象外（あくまで tweak/pnts の履歴）
"""

import maya.cmds as cmds

TOL = 1e-6          # 0判定許容
MAX_SHOW = 30       # 詳細に表示する頂点数
CHUNK = 4096        # フォールバック時のレンジ走査チャンク（元:2048）


from _util import (
    iter_scene_mesh_shapes as _iter_shapes,
    short_name as _short_name,
    parent_transform as _parent_transform,
)


def _vec_is_nonzero(v):
    # v は (x,y,z) or [x,y,z]
    return (abs(v[0]) > TOL) or (abs(v[1]) > TOL) or (abs(v[2]) > TOL)


def _get_pnts_indices_fast(shape: str):
    """
    pnts の multiIndices を取得できれば最速。
    取得できない/空の場合は [] を返す。
    """
    try:
        idx = cmds.getAttr(f"{shape}.pnts", multiIndices=True) or []
        return list(idx)
    except Exception:
        return []


def _get_pnts_size(shape: str) -> int:
    """
    pnts マルチの要素数（size）を取得。
    環境/状況により例外になることがあるので、その場合は -1。
    """
    try:
        return int(cmds.getAttr(f"{shape}.pnts", size=True))
    except Exception:
        return -1


def _group_consecutive(sorted_indices):
    """
    [0,1,2, 5,6, 10] -> [(0,2),(5,6),(10,10)]
    """
    if not sorted_indices:
        return []
    ranges = []
    start = prev = sorted_indices[0]
    for i in sorted_indices[1:]:
        if i == prev + 1:
            prev = i
            continue
        ranges.append((start, prev))
        start = prev = i
    ranges.append((start, prev))
    return ranges


def _scan_pnts_by_ranges(shape: str, ranges):
    """
    (start,end) のレンジで pnts をまとめ取得し、非ゼロ頂点を数える/サンプル収集
    Returns: (count, samples[list[(i,(x,y,z))]])
    """
    count = 0
    samples = []
    for start, end in ranges:
        try:
            vals = cmds.getAttr(f"{shape}.pnts[{start}:{end}]") or []
        except Exception:
            # レンジ取得が通らない場合は保険として単発で読む（遅いが落ちない）
            vals = []
            for i in range(start, end + 1):
                try:
                    v = cmds.getAttr(f"{shape}.pnts[{i}]")[0]
                    vals.append(v)
                except Exception:
                    vals.append(None)

        for local_i, v in enumerate(vals):
            if v is None:
                continue
            if _vec_is_nonzero(v):
                i = start + local_i
                count += 1
                if len(samples) < MAX_SHOW:
                    samples.append((i, v))
    return count, samples


def _scan_pnts_by_indices_batched(shape: str, indices):
    """
    indices のみを調べる（高速化：連番をレンジ化してまとめ getAttr）
    Returns: (count, samples[list[(i,(x,y,z))]])
    """
    indices = sorted(set(int(i) for i in indices))
    ranges = _group_consecutive(indices)
    return _scan_pnts_by_ranges(shape, ranges)


def _scan_pnts_by_chunks(shape: str):
    """
    フォールバック:
    polyEvaluate の頂点数を元に、pnts[start:end] をレンジで取得して走査する
    Returns: (count, samples[list[(i,(x,y,z))]])
    """
    try:
        vtx_count = int(cmds.polyEvaluate(shape, v=True))
    except Exception:
        return 0, []

    count = 0
    samples = []

    for start in range(0, vtx_count, CHUNK):
        end = min(vtx_count - 1, start + CHUNK - 1)

        try:
            vals = cmds.getAttr(f"{shape}.pnts[{start}:{end}]") or []
        except Exception:
            break

        for local_i, v in enumerate(vals):
            if _vec_is_nonzero(v):
                i = start + local_i
                count += 1
                if len(samples) < MAX_SHOW:
                    samples.append((i, v))

    return count, samples


def get_results():
    results = []

    shapes = _iter_shapes()
    for shape in shapes:
        parent = _parent_transform(shape)
        parent_short = _short_name(parent)
        shape_short = _short_name(shape)

        # まずは fast（multiIndices）
        indices = _get_pnts_indices_fast(shape)

        if indices:
            # ★ 改善：単発getAttr連打をやめてレンジまとめ取得
            count, samples = _scan_pnts_by_indices_batched(shape, indices)
        else:
            # ★ 改善：pnts要素が0ならフォールバック走査を避ける
            pnts_size = _get_pnts_size(shape)
            if pnts_size == 0:
                continue
            count, samples = _scan_pnts_by_chunks(shape)

        if count <= 0:
            continue

        details = [
            f"Tweaked vertex count: {count}",
            f"Samples (max {MAX_SHOW}):",
        ]
        for i, v in samples:
            details.append(f"  - vtx[{i}] pnts=({v[0]:.6f}, {v[1]:.6f}, {v[2]:.6f})")

        results.append({
            "transform": parent_short,
            "message": f"頂点移動履歴あり: {shape_short}（{count} vtx）",
            "details": details,
        })

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[VTX] 頂点移動履歴（pnts tweak）のある mesh は見つかりませんでした。")
    else:
        print(f"[VTX] 頂点移動履歴あり: {len(res)} 件")
        for r in res:
            print(r["message"])
            for line in r.get("details", []):
                print("  - " + line)
