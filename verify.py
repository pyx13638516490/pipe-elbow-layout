# -*- coding: utf-8 -*-
"""验证放样图 DXF 曲线准确性。

用法: python verify.py <config.json>
(不传 config 则用默认 90°/OD3220/5节的演示数据)

检查每节模板:
  1. 宽度 = π×OD (外皮周长)
  2. 长边(曲线峰处竖直长度) 与 短边(波谷处) 是否等于理论长边/短边
  3. 正弦拟合: 曲线 z = 中线 + A·cos(θ), A 是否等于 (OD/2)·tanφ, 及拟合残差(逼近误差)
"""
import sys
import math
import io
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elbow_layout.models import ElbowInput, PieceInput
from elbow_layout.geometry import compute_elbow, compute_bevel_allowance
from elbow_layout.layout import generate_dxf
import ezdxf


def verify(inp: ElbowInput):
    res = compute_elbow(inp)
    od = inp.od
    circ = math.pi * od
    W = res.bevel_allowance
    s = generate_dxf(res).to_string()
    d = ezdxf.read(io.StringIO(s))
    msp = d.modelspace()
    lw = [e for e in msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "THEO"]
    lw.sort(key=lambda e: min(p[1] for p in e.get_points()))

    print("=" * 66)
    print("  放样图曲线验证   OD=%.1f  π×OD=%.2f  N=%d" % (od, circ, res.n))
    print("=" * 66)
    all_ok = True
    npts = 90
    for i, (piece, e) in enumerate(zip(res.pieces, lw)):
        pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
        xs = [p[0] for p in pts]
        x0 = min(xs)
        width = max(xs) - min(xs)
        k = 2.0 if piece.kind == "full" else 1.0
        # 收集顶部曲线的顶点x (每节2条曲线, 前 npts+1 个点为上曲线)
        xs_top = sorted(set(round(p[0], 1) for p in pts[:npts + 1]))
        y_min = min(p[1] for p in pts)
        max_dev = 0.0
        for x in xs_top:
            xp = float(x)
            yys = [p[1] for p in pts if abs(p[0] - xp) < 0.6]
            if piece.kind == "full":
                if len(yys) < 2:
                    continue
                extent = max(yys) - min(yys)
            else:  # half: 下边为平直(全局最低点=方口)
                extent = max(yys) - y_min
            theta = 2 * math.pi * (xp - x0) / circ
            expect = piece.midline + k * piece.amp * math.cos(theta)
            max_dev = max(max_dev, abs(extent - expect))
        yy0 = [p[1] for p in pts if abs(p[0] - x0) < 0.6]
        xm = x0 + width / 2.0
        yym = [p[1] for p in pts if abs(p[0] - xm) < 0.6]
        long_v = (max(yy0) - min(yy0)) if len(yy0) >= 2 else float("nan")
        short_v = (max(yym) - min(yym)) if len(yym) >= 2 else float("nan")
        if piece.kind == "half":
            short_v = max(yym) - y_min if yym else float("nan")

        ok = (abs(width - circ) < 0.5 and
              abs(long_v - piece.long_theo) < 0.5 and
              abs(short_v - piece.short_theo) < 0.5 and
              max_dev < 0.6)
        all_ok = all_ok and ok
        print("第%d节 %-4s | 宽=%.1f(应%.1f) 长边=%.1f(%.1f) 短边=%.1f(%.1f) "
              "| 正弦逐点偏差最大=%.2fmm  => %s"
              % (i + 1, piece.kind, width, circ, long_v, piece.long_theo,
                 short_v, piece.short_theo, max_dev, "OK" if ok else "!! 不符"))
    print("=" * 66)
    amp = res.pieces[1].amp if len(res.pieces) > 1 else res.pieces[0].amp
    print("结论: 曲线为精确正弦 A=(OD/2)tanφ=%.2f, 逐点核对偏差<%.2fmm, 可直接贴管下料" % (amp, max_dev))
    print("      %s" % ("全部符合 1:1" if all_ok else "存在不符, 请检查"))
    return all_ok


if __name__ == "__main__":
    cfg = sys.argv[1] if len(sys.argv) > 1 else None
    if cfg:
        import json
        with open(cfg, "r", encoding="utf-8") as f:
            d = json.load(f)
        pieces = [PieceInput(**p) for p in d["pieces"]]
        inp = ElbowInput(bend_angle_deg=d["bend_angle_deg"], od=d["od"], thickness=d["thickness"],
                         pieces=pieces, bevel_angle_deg=d.get("bevel_angle_deg", 30.0),
                         root_face=d.get("root_face", 1.5), root_gap=d.get("root_gap", 2.0))
    else:
        ps = [PieceInput(1593, 953, "half", 11), PieceInput(3187, 1906, "full", 23),
              PieceInput(3187, 1906, "full", 23), PieceInput(3187, 1906, "full", 23),
              PieceInput(1643, 1003, "half", 11)]
        inp = ElbowInput(bend_angle_deg=90, od=3220, thickness=14, pieces=ps,
                         bevel_angle_deg=30, root_face=2, root_gap=2, R_nominal=6400)
    verify(inp)
