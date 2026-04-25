# -*- coding: utf-8 -*-
"""
詳細ビューの HTML 整形 / オブジェクトキー圧縮 / 結果正規化ユーティリティ。
"""

import html
import sys


def _component_pattern():
    """_widgets.COMPONENT_PATTERN を遅延参照（bootstrap 順序非依存）"""
    widgets = sys.modules.get("_widgets")
    if widgets and hasattr(widgets, "COMPONENT_PATTERN"):
        return widgets.COMPONENT_PATTERN
    import re
    return re.compile(
        r'(?:\|?[A-Za-z_][A-Za-z0-9_:\|]*\.)?'
        r'(?:vtx|f|e|map|uv|cv|ep|pt)\[[0-9:,\-\s]+\]'
    )


def wrap_components(escaped_text):
    """エスケープ済みテキスト内の Maya コンポーネントを pill 状の <span> で包む"""
    return _component_pattern().sub(
        lambda m: (
            f"<span style='background:#14243c; color:#88b8f0;"
            f" border: 1px solid #1e3554;"
            f" border-radius:3px; padding:0 4px;'>{m.group(0)}</span>"
        ),
        escaped_text,
    )


def format_details_html(details):
    """details リストを見やすい HTML に整形する。
    - 1 行目（message）: 強調見出し
    - ⚠ で始まる行: 警告色（アンバー）
    - インデント行（先頭スペース2文字以上）: モノスペースでサンプル/座標を整列表示
    - "key: value" 形式: ラベルと値を色分け
    - その他: 通常テキスト
    - Maya コンポーネント（vtx[..] 等）は pill 状にスタイリング → クリックで Maya 選択
    """
    if not details:
        return ""
    out = []
    for i, raw in enumerate(details):
        text = html.escape(str(raw))
        if i == 0:
            out.append(
                f"<div style='font-weight:bold; color:#7aa3d0;"
                f" font-size:13px; margin-bottom:8px;'>{wrap_components(text)}</div>"
            )
            continue
        stripped = str(raw).lstrip()
        leading = len(str(raw)) - len(stripped)
        if stripped.startswith("⚠"):
            out.append(
                f"<div style='color:#e0b060; padding:1px 0;'>{wrap_components(text)}</div>"
            )
            continue
        if leading >= 2:
            indent_px = leading * 4
            out.append(
                f"<div style='font-family:Consolas,monospace; color:#a0c4e0;"
                f" padding:1px 0 1px {indent_px}px; white-space:pre;'>"
                f"{wrap_components(html.escape(stripped))}</div>"
            )
            continue
        if ": " in text:
            k, _, v = text.partition(": ")
            out.append(
                f"<div style='padding:1px 0;'>"
                f"<span style='color:#7a9aae;'>{k}:</span> "
                f"<span style='color:#ccddef; font-family:Consolas,monospace;'>{wrap_components(v)}</span>"
                f"</div>"
            )
            continue
        out.append(
            f"<div style='padding:1px 0; color:#ccddef;'>{wrap_components(text)}</div>"
        )
    return "".join(out)


def disambiguate_keys(keys):
    """
    long path のリストから「最小限で一意になる表示名」へのマップを返す。
    例:
      ["|grp_A|pCube1", "|grp_B|pCube1", "animCurveTA1"]
      → {"|grp_A|pCube1": "grp_A | pCube1",
          "|grp_B|pCube1": "grp_B | pCube1",
          "animCurveTA1":   "animCurveTA1"}
    """
    result = {}
    for path in keys:
        parts = path.lstrip("|").split("|")
        for n in range(1, len(parts) + 1):
            suffix = "|" + "|".join(parts[-n:])
            collide = any(
                other != path and other.endswith(suffix)
                for other in keys
            )
            if not collide:
                result[path] = " | ".join(parts[-n:])
                break
        else:
            result[path] = path
    return result


_SEV_RANK = {None: 0, "info": 1, "warning": 2, "error": 3}


def _max_severity(a, b):
    """error > warning > info の優先度で大きい方を返す"""
    return a if _SEV_RANK.get(a, 0) >= _SEV_RANK.get(b, 0) else b


def normalize_structured(structured):
    """check / fix の戻り値を (obj_to_details, severities) に正規化する。

    Returns:
        (obj_to_details, severities)
        - obj_to_details : dict[str, list[str]]
        - severities     : dict[str, str]   "error" / "warning" / "info"

    受け付ける入力形式:
        - dict[str, list[str]]                 : 旧形式。severity は "error" 既定
        - list[dict]                           : 旧形式（transform/message/details）
        - list[CheckResult]                    : 新形式（_results.CheckResult）
        - 上記 list に dict と CheckResult が混在しても可
    """
    obj_to_details = {}
    severities = {}
    DEFAULT_SEV = "error"

    if structured is None:
        return obj_to_details, severities

    if isinstance(structured, dict):
        for k, v in structured.items():
            key = str(k)
            obj_to_details[key] = [str(x) for x in v] if isinstance(v, list) else [str(v)]
            severities.setdefault(key, DEFAULT_SEV)
        return obj_to_details, severities

    if isinstance(structured, list):
        for entry in structured:
            # 新 API: CheckResult（duck-typed で判定）
            if hasattr(entry, "target") and hasattr(entry, "details") and not isinstance(entry, dict):
                key = str(entry.target or "Unknown")
                msg = getattr(entry, "message", "") or ""
                details = entry.details or []
                severity = getattr(entry, "severity", DEFAULT_SEV) or DEFAULT_SEV
                lines = []
                if msg:
                    lines.append(str(msg))
                if isinstance(details, list):
                    lines.extend(str(x) for x in details)
                elif details:
                    lines.append(str(details))
                obj_to_details.setdefault(key, []).extend(lines)
                severities[key] = _max_severity(severities.get(key), severity)
                continue

            # 旧 API: dict
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("transform") or entry.get("name") or "Unknown")
            msg = entry.get("message", "")
            details = entry.get("details", [])
            severity = entry.get("severity", DEFAULT_SEV)
            lines = []
            if msg:
                lines.append(str(msg))
            if isinstance(details, list):
                lines.extend(str(x) for x in details)
            elif details:
                lines.append(str(details))
            obj_to_details.setdefault(key, []).extend(lines)
            severities[key] = _max_severity(severities.get(key), severity)

    return obj_to_details, severities
