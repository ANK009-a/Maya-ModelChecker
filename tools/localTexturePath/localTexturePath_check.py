# -*- coding: utf-8 -*-
"""
localTexturePath_check.py

check処理:
ローカルドライブを参照している file ノードを検出します。
データ共有時に相手側からアクセスできなくなる絶対パスを洗い出すのが目的。

判定:
- UNC パス（`\\\\server\\share\\...`）          → 共有 OK
- ネットワークドライブ（`Z:\\` 等で REMOTE）   → 共有 OK
- ローカル固定ドライブ（DRIVE_FIXED）          → ✗ ローカル
- リムーバブル / CD-ROM / RAM Disk              → ✗ ローカル扱い
- ドライブ切断・不明（NO_ROOT_DIR / UNKNOWN）  → ✗ 警告

Windows 専用。Mac / Linux では判定不能として空の結果を返す。
"""
import os
import sys
import ctypes
import maya.cmds as cmds
from _results import CheckResult, Severity


# Windows GetDriveType 戻り値
_DRIVE_UNKNOWN     = 0
_DRIVE_NO_ROOT_DIR = 1
_DRIVE_REMOVABLE   = 2
_DRIVE_FIXED       = 3
_DRIVE_REMOTE      = 4
_DRIVE_CDROM       = 5
_DRIVE_RAMDISK     = 6

_DRIVE_LABELS = {
    _DRIVE_UNKNOWN:     "Unknown",
    _DRIVE_NO_ROOT_DIR: "Disconnected",
    _DRIVE_REMOVABLE:   "Removable",
    _DRIVE_FIXED:       "Local (Fixed)",
    _DRIVE_REMOTE:      "Network (Shared)",
    _DRIVE_CDROM:       "CD-ROM",
    _DRIVE_RAMDISK:     "RAM Disk",
}


def _is_windows():
    return sys.platform.startswith("win")


def _drive_type(path):
    """Windows パスのドライブ種別を返す。UNC は REMOTE 扱い。"""
    if not path:
        return _DRIVE_UNKNOWN
    p = path.replace("/", "\\")
    if p.startswith("\\\\"):
        return _DRIVE_REMOTE
    drive = os.path.splitdrive(p)[0]
    if not drive:
        return _DRIVE_UNKNOWN
    try:
        return ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")
    except Exception:
        return _DRIVE_UNKNOWN


def _expand(path):
    """環境変数 / ~ を展開した絶対パスを返す。"""
    if not path:
        return ""
    return os.path.expandvars(os.path.expanduser(path))


def get_results():
    results = []

    if not _is_windows():
        return [CheckResult(
            target="(platform)",
            message="Windows 以外の環境では判定できません",
            details=[f"sys.platform = {sys.platform}"],
            severity=Severity.ERROR,
        )]

    file_nodes = cmds.ls(type="file") or []
    for node in sorted(file_nodes):
        try:
            raw = cmds.getAttr(f"{node}.fileTextureName") or ""
        except Exception:
            continue
        if not raw:
            # 未設定は texturePath 側の責務なのでスキップ
            continue

        path = _expand(raw)
        dt = _drive_type(path)
        if dt == _DRIVE_REMOTE:
            continue  # 共有可能 → OK

        label = _DRIVE_LABELS.get(dt, f"Code {dt}")
        details = [
            f"Path: {raw}",
            f"Drive type: {label}",
        ]
        if path != raw:
            details.append(f"Resolved: {path}")

        if dt == _DRIVE_FIXED:
            details.append("⚠ ローカル固定ドライブ参照は他者に共有できません")
        elif dt == _DRIVE_REMOVABLE:
            details.append("⚠ リムーバブルメディア参照は他者に共有できません")
        elif dt == _DRIVE_NO_ROOT_DIR:
            details.append("⚠ ドライブが見つかりません（切断中 または 存在しないドライブ）")
        elif dt == _DRIVE_UNKNOWN:
            details.append("⚠ ドライブ種別が判定できませんでした")
        else:
            details.append(f"⚠ 共有不可種別: {label}")

        results.append(CheckResult(
            target=node,
            message=f"local texture: {node} ({label})",
            details=details,
            severity=Severity.ERROR,
        ))

    return results


if __name__ == "__main__":
    res = get_results()
    if not res:
        print("[localTexturePath] OK: 全テクスチャが共有可能なパスです。")
    else:
        print(f"[localTexturePath] {len(res)} 件")
        for r in res:
            print(r.message)
