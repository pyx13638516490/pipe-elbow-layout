"""命令行入口。

用法:
    python -m elbow_layout.main configs\\demo_90.json            # 仅计算+出DXF
    python -m elbow_layout.main configs\\demo_90.json --open-cad # 计算后自动用CAD打开

输出:
    计算报告 .txt  +  放样展开图 .dxf
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .cad import find_cad
from .dxfout import DXFBuilder
from .geometry import compute_elbow
from .layout import generate_dxf
from .models import ElbowInput, PieceInput
from .report import build_report


def load_config(path: str) -> ElbowInput:
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    pieces = [PieceInput(**p) for p in d["pieces"]]
    return ElbowInput(
        bend_angle_deg=d["bend_angle_deg"],
        od=d["od"],
        thickness=d["thickness"],
        pieces=pieces,
        bevel_angle_deg=d.get("bevel_angle_deg", 30.0),
        root_face=d.get("root_face", 1.5),
        root_gap=d.get("root_gap", 2.0),
    )


def main() -> int:  # pragma: no cover - CLI
    # 让控制台支持 UTF-8 (含 ✓/✗ 等符号), 避免 GBK 控制台崩溃
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="弯头放样计算 + DXF 输出")
    ap.add_argument("config", nargs="?", default="configs/demo_90.json")
    ap.add_argument("--out", default="out", help="输出目录 (默认 ./out)")
    ap.add_argument("--open-cad", action="store_true", help="计算后自动启动 AutoCAD 打开 DXF")
    ap.add_argument("--cad-path", default=None, help="acad.exe 完整路径(可选, 覆盖自动检测)")
    ap.add_argument("--no-launch", action="store_true", help="只检测CAD, 不实际打开")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = here / cfg_path

    inp = load_config(str(cfg_path))
    res = compute_elbow(inp)

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = Path(os.getcwd()) / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = cfg_path.stem
    report_txt = build_report(res)
    rep_path = out_dir / f"{stem}_report.txt"
    rep_path.write_text(report_txt, encoding="utf-8")

    builder = generate_dxf(res)
    dxf_path = out_dir / f"{stem}_template.dxf"
    dxf_path.write_text(builder.to_string(), encoding="ascii")

    print(report_txt)
    print()
    print(f"报告: {rep_path}")
    print(f"DXF : {dxf_path}")

    cad = None if args.no_launch else find_cad(args.cad_path)
    if not args.no_launch:
        if cad:
            print(f"找到 CAD: {cad}")
        elif args.cad_path:
            print(f"警告: 指定的 acad.exe 不存在: {args.cad_path}")
        else:
            print("未找到 acad.exe (可 --cad-path 指定路径)")

    if args.open_cad and cad:
        print("启动 AutoCAD 打开 DXF ...")
        subprocess.Popen([cad, str(dxf_path)])
    elif args.open_cad and not cad:
        print("未启动: 未找到 AutoCAD")

    return 0


if __name__ == "__main__":
    sys.exit(main())
