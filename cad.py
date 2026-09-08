"""查找并启动 AutoCAD (默认 2022, 兼容 2021/2023/2026), CLI 与 GUI 共用。"""
from __future__ import annotations

import os
import shutil
import subprocess


def _candidate_cad_paths() -> list[str]:
    cands: list[str] = []
    p = shutil.which("acad.exe")
    if p:
        cands.append(p)
    common = [
        r"F:\AutoCAD 2022\AutoCAD 2022\acad.exe",
        r"F:\AutoCAD 2026\AutoCAD 2026\acad.exe",
        r"C:\Program Files\Autodesk\AutoCAD 2022\acad.exe",
        r"C:\Program Files\Autodesk\AutoCAD 2021\acad.exe",
        r"C:\Program Files\Autodesk\AutoCAD 2023\acad.exe",
        r"C:\Program Files\Autodesk\AutoCAD 2020\acad.exe",
        r"C:\Program Files (x86)\Autodesk\AutoCAD 2022\acad.exe",
        r"D:\AutoCAD 2022\AutoCAD 2022\acad.exe",
        r"E:\AutoCAD 2022\AutoCAD 2022\acad.exe",
        r"C:\Program Files\Autodesk\AutoCAD 2026\acad.exe",
    ]
    for c in common:
        if os.path.exists(c):
            cands.append(c)
    return cands


def find_cad(cad_path: str | None = None) -> str | None:
    """返回 acad.exe 路径; 找不到返回 None。"""
    if cad_path:
        return cad_path if os.path.exists(cad_path) else None
    for c in _candidate_cad_paths():
        if os.path.exists(c):
            return c
    return None


def launch_cad(dxf_path: str, cad_path: str | None = None) -> str | None:
    """用 CAD 打开 DXF, 返回 acad.exe 路径; 未找到返回 None。"""
    cad = find_cad(cad_path)
    if not cad:
        return None
    subprocess.Popen([cad, dxf_path])
    return cad
