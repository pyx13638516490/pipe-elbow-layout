"""把弯管计算结果生成"绘制指令"(draw ops)，供 tkinter Canvas 或 SVG 渲染。

三种视图: 弯管侧面图 / 单V坡口接口示意 / 下料放样图。
op 格式:
  ("poly", [(x,y)..], fill, outline)
  ("line", [(x,y),(x,y)], color, width)
  ("text", x, y, str, color, size)
  ("circle", cx, cy, r, outline, fill)
  ("arc", x0,y0,x1,y1,start,extent,outline,width)
坐标为 mm (模型空间)。paint() 负责缩放/翻转 Y 到 Canvas。
"""
from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

from .geometry import ElbowResult, compute_section, piece_quads
from .models import ElbowInput

Pt = Tuple[float, float]
Op = tuple


def _line(a: Pt, b: Pt, color="#000", width=1.5) -> Op:
    return ("line", [a, b], color, width)


def _text(x: float, y: float, s: str, color="#000", size=14) -> Op:
    return ("text", x, y, s, color, size)


def _poly(pts: List[Pt], fill="#e8f0ff", outline="#333", width=1.2) -> Op:
    return ("poly", pts, fill, outline, width)


def _circle(c: Pt, r: float, outline="#c00", fill="") -> Op:
    return ("circle", c[0], c[1], r, outline, fill)


# ---------- 弯管侧面图 (环形扇段式, 仿设计院弯管图) ----------
def _arc_pts(cx: float, cy: float, r: float, a0: float, a1: float, n: int = 24) -> List[Pt]:
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n),
             cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def elbow_scene(res: ElbowResult, R_draw: float | None = None) -> Tuple[List[Pt], List[Op]]:
    # 直管段(虾米弯)表示: 每节是一段直管(斜切拼接), 轴角对称; 不用曲线管.
    from .geometry import piece_quads
    quads, theta, verts = piece_quads(res)
    od = res.inp.od
    ops: List[Op] = []
    pts: List[Pt] = []

    # 每节直管块
    for (quad, vA, vB) in quads:
        ops.append(_poly(quad, fill="#e8f2ff", outline="#335", width=1.4))
        pts.extend(quad)

    # 中心线(折线, 虚线)
    ops.append(("dash_line", [(x, y) for (x, y) in verts], "#0a0", 1.2))
    pts.extend(verts)

    # 接缝圆点
    for v in verts:
        ops.append(_circle(v, 9, outline="#c00", fill="#fff"))
        pts.append(v)

    # 圆心 + 到两端管道中心距离 = R (两条半径线) + R 参考弧
    R = res.R_nominal if res.R_nominal > 0 else res.R
    p0 = verts[0]
    pN = verts[-1]
    d0 = (math.cos(theta[0]), math.sin(theta[0]))
    dN = (math.cos(theta[-1]), math.sin(theta[-1]))
    n0 = (-d0[1], d0[0])          # 入口轴左法向(弯内侧)
    nN = (-dN[1], dN[0])          # 出口轴左法向
    A = [[d0[0], -dN[0]], [d0[1], -dN[1]]]
    b = (pN[0] + R * nN[0] - p0[0] - R * n0[0],
         pN[1] + R * nN[1] - p0[1] - R * n0[1])
    det = A[0][0] * A[1][1] - A[0][1] * A[1][0]
    if abs(det) > 1e-9:
        s = (b[0] * A[1][1] - A[0][1] * b[1]) / det
        cenx = p0[0] + R * n0[0] + s * d0[0]
        ceny = p0[1] + R * n0[1] + s * d0[1]
    else:
        cenx, ceny = 0.0, 0.0
    # 圆心
    ops.append(_circle((cenx, ceny), 11, outline="#f60", fill=""))
    pts.append((cenx, ceny))
    # 两条 R 半径线(到两端)
    ops.append(_line((cenx, ceny), p0, color="#f60", width=1.3))
    ops.append(_line((cenx, ceny), pN, color="#f60", width=1.3))
    pts.extend([p0, pN])
    # R 文字 (标在到入口的半径线中点旁)
    mmid = ((cenx + p0[0]) / 2, (ceny + p0[1]) / 2)
    ops.append(_text(mmid[0] + R * 0.05, mmid[1], f"R={R:.0f}", color="#f60", size=13))
    pts.append((mmid[0] + R * 0.05, mmid[1]))
    # R 参考弧(虚线): 经过两端点 (平滑弯头中心线参考)
    a0 = math.atan2(p0[1] - ceny, p0[0] - cenx)
    a1 = math.atan2(pN[1] - ceny, pN[0] - cenx)
    if a1 < a0:
        a0, a1 = a1, a0
    if a1 - a0 > math.pi:
        a1 = a0 + (math.pi * 2 - (a1 - a0))
    acpts = _arc_pts(cenx, ceny, R, a0, a1, 60)
    ops.append(("dash_line", acpts, "#e60", 1.0))
    pts.extend(acpts)

    # 每节尺寸标注(学设计院): 长边/短边, 放在每节外弧侧
    for i, (quad, vA, vB) in enumerate(quads):
        cxq = sum(p[0] for p in quad) / 4.0
        cyq = sum(p[1] for p in quad) / 4.0
        d = (math.cos(theta[i]), math.sin(theta[i]))
        perp = (-d[1], d[0])
        p = res.pieces[i]
        lblx = cxq + perp[0] * od * 0.05
        lbly = cyq + perp[1] * od * 0.05
        ops.append(_text(lblx, lbly, f"{p.short_theo:.0f}", color="#00c", size=11))
        pts.append((lblx, lbly))

    # 进出口直管段
    stub = od * 0.55
    t_in = (math.cos(theta[0]), math.sin(theta[0]))
    r_in = (-t_in[1], t_in[0])
    p0 = verts[0]
    for sgn in (1, -1):
        e = (p0[0] + sgn * od / 2 * r_in[0], p0[1] + sgn * od / 2 * r_in[1])
        e2 = (e[0] - stub * t_in[0], e[1] - stub * t_in[1])
        ops.append(_line(e, e2, color="#226", width=1.6))
        pts.extend([e, e2])
    t_out = (math.cos(theta[-1]), math.sin(theta[-1]))
    r_out = (-t_out[1], t_out[0])
    pN = verts[-1]
    for sgn in (1, -1):
        e = (pN[0] + sgn * od / 2 * r_out[0], pN[1] + sgn * od / 2 * r_out[1])
        e2 = (e[0] + stub * t_out[0], e[1] + stub * t_out[1])
        ops.append(_line(e, e2, color="#226", width=1.6))
        pts.extend([e, e2])

    # 整体尺寸链(宽/高)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    yy = y0 - od * 0.30
    ops.append(_line((x0, yy), (x1, yy), color="#666", width=1.0))
    ops.append(_line((x0, yy - 12), (x0, yy + 12), color="#666", width=1.0))
    ops.append(_line((x1, yy - 12), (x1, yy + 12), color="#666", width=1.0))
    ops.append(_text((x0 + x1) / 2, yy - od * 0.14, f"宽={x1 - x0:.0f}", color="#666", size=13))
    pts.append(((x0 + x1) / 2, yy - od * 0.14))
    xx = x0 - od * 0.30
    ops.append(_line((xx, y0), (xx, y1), color="#666", width=1.0))
    ops.append(_line((xx - 12, y0), (xx + 12, y0), color="#666", width=1.0))
    ops.append(_line((xx - 12, y1), (xx + 12, y1), color="#666", width=1.0))
    ops.append(_text(xx - od * 0.14, (y0 + y1) / 2, f"高={y1 - y0:.0f}", color="#666", size=13))
    pts.append((xx - od * 0.14, (y0 + y1) / 2))

    # 说明
    R = res.R_nominal if res.R_nominal > 0 else res.R
    ops.append(_text(x0 - od * 0.02, y0 - od * 0.55,
                     f"α={res.inp.bend_angle_deg:.0f}°  N={res.n}  R={R:.0f}", color="#000", size=13))
    pts.append((x0 - od * 0.02, y0 - od * 0.55))
    return pts, ops


# ---------- 单V坡口接口示意 ----------
def bevel_scene(inp: ElbowInput) -> Tuple[List[Pt], List[Op]]:
    t = inp.thickness
    p = inp.root_face
    g = inp.root_gap
    theta_deg = inp.bevel_angle_deg
    theta = math.radians(theta_deg)
    off = (t - p) * math.tan(theta)

    # 定位: 使关节居中
    ox = -(g + 2 * t) / 2.0
    def X(v): return v + ox

    ops: List[Op] = []
    pts: List[Pt] = []
    # 左壁 (5 顶点)
    left_wall = [(X(-t), 0), (X(-t), t), (X(-off), t), (X(0), p), (X(0), 0)]
    ops.append(_poly(left_wall, fill="#d9d9d9", outline="#222", width=1.5))
    pts.extend(left_wall)
    # 右壁
    right_wall = [(X(g), 0), (X(g), p), (X(g + off), t), (X(g + t), t), (X(g + t), 0)]
    ops.append(_poly(right_wall, fill="#d9d9d9", outline="#222", width=1.5))
    pts.extend(right_wall)

    # 根部间隙 g (水平)
    ops.append(_line((X(g), 0), (X(g), p), color="#c00", width=1.2))
    ops.append(_line((X(0), 0), (X(0), p), color="#c00", width=1.2))
    ops.append(_text((X(0) + X(g)) / 2, -0.6 * t, f"g={g:.1f}", color="#c00", size=14))
    pts.append((X(0), -0.6 * t))

    # 钝边 p (左侧竖直)
    ops.append(_line((X(-t) - 0.4 * t, 0), (X(-t) - 0.4 * t, p), color="#00c", width=1.2))
    ops.append(_line((X(-t) - 0.4 * t - 6, 0), (X(-t) - 0.4 * t + 6, 0), color="#00c", width=1.2))
    ops.append(_line((X(-t) - 0.4 * t - 6, p), (X(-t) - 0.4 * t + 6, p), color="#00c", width=1.2))
    ops.append(_text(X(-t) - 0.4 * t - 8, p / 2, f"p={p:.1f}", color="#00c", size=14))
    pts.append((X(-t) - 0.4 * t - 8, p / 2))

    # 壁厚 t (左侧水平)
    ops.append(_line((X(-t), t + 0.5), (X(0), t + 0.5), color="#080", width=1.2))
    ops.append(_line((X(-t), t + 0.5 - 6), (X(-t), t + 0.5 + 6), color="#080", width=1.2))
    ops.append(_line((X(0), t + 0.5 - 6), (X(0), t + 0.5 + 6), color="#080", width=1.2))
    ops.append(_text((X(-t) + X(0)) / 2, t + 0.5 * t, f"t={t:.1f}", color="#080", size=14))
    pts.append(((X(-t) + X(0)) / 2, t + 0.5 * t))

    # 坡口角 θ (左壁角点) —— 两条射线 + 角内文字, 落在角上
    vtx = (X(0), p)                       # 角点(钝边顶, 坡口起点)
    ray_len = 0.85 * t
    dir_up = (0.0, 1.0)                   # 垂直向上 (钝边延长)
    dir_bev = (-math.sin(theta), math.cos(theta))   # 沿坡口面方向
    end_up = (vtx[0] + ray_len * dir_up[0], vtx[1] + ray_len * dir_up[1])
    end_bev = (vtx[0] + ray_len * dir_bev[0], vtx[1] + ray_len * dir_bev[1])
    ops.append(_line(vtx, end_up, color="#f60", width=1.3))
    ops.append(_line(vtx, end_bev, color="#f60", width=1.3))
    # 角内文字(沿两射线角平分线方向放置)
    bx = dir_up[0] + dir_bev[0]
    by = dir_up[1] + dir_bev[1]
    nb = math.hypot(bx, by)
    bx, by = bx / nb, by / nb
    tp_pt = (vtx[0] + 0.95 * t * bx, vtx[1] + 0.95 * t * by)
    ops.append(_text(tp_pt[0], tp_pt[1], f"θ={theta_deg:.0f}°", color="#f60", size=14))
    pts.append(tp_pt)

    # 标题
    ops.append(_text((X(-t) + X(g + t)) / 2, t + 2.2 * t,
                     f"单V坡口  (θ={theta_deg:.0f}°  p={p:.1f}  g={g:.1f}  t={t:.1f})",
                     color="#000", size=15))
    pts.append(((X(-t) + X(g + t)) / 2, t + 2.2 * t))
    return pts, ops


# ---------- 下料放样图 (开发模板预览) ----------
def _cos(u: float, circ: float) -> float:
    return math.cos(u * 2.0 * math.pi / circ)


def layout_scene(res: ElbowResult) -> Tuple[List[Pt], List[Op]]:
    od = res.inp.od
    W = res.bevel_allowance
    circ = math.pi * od
    ops: List[Op] = []
    pts: List[Pt] = []
    n_pts = 90
    n = len(res.pieces)

    def cosc(u): return math.cos(u * 2.0 * math.pi / circ)
    def pt(u): return circ * u / n_pts

    hs = [p.midline + 2.0 * p.amp + 2.0 * p.miter_edges * W for p in res.pieces]
    gap = max(circ * 0.08, 230.0)
    total = sum(hs) + gap * (n - 1)
    y_top = total                 # 第1节在最上面
    for i, p in enumerate(res.pieces):
        amp = p.amp
        L0 = p.midline
        e = p.miter_edges
        ybot = y_top - hs[i]      # 该节最低点
        theo_top = [(pt(j), ybot + amp + L0 + amp * cosc(pt(j))) for j in range(n_pts + 1)]
        if p.kind == "full":
            theo_bot = [(pt(j), ybot + amp - amp * cosc(pt(j))) for j in range(n_pts + 1)]
            ops.append(_poly(theo_top + list(reversed(theo_bot)),
                             fill="#e6f2ff", outline="#228", width=1.3))
            cut_top = [(pt(j), ybot + amp + L0 + W + amp * cosc(pt(j))) for j in range(n_pts + 1)]
            cut_bot = [(pt(j), ybot + amp - W - amp * cosc(pt(j))) for j in range(n_pts + 1)]
            ops.append(_poly(cut_top + list(reversed(cut_bot)), fill="", outline="#f00", width=1.3))
            pts.extend(theo_top + theo_bot + cut_top + cut_bot)
        else:                     # half: 下端方口
            ops.append(_poly(theo_top + [(circ, ybot), (0, ybot)],
                             fill="#e6f2ff", outline="#228", width=1.3))
            cut_top = [(pt(j), ybot + L0 + W + amp * cosc(pt(j))) for j in range(n_pts + 1)]
            ops.append(_poly(cut_top + [(circ, ybot), (0, ybot)], fill="", outline="#f00", width=1.3))
            pts.extend(theo_top + [(circ, ybot), (0, ybot)] + cut_top)
        # 标注放在该节下方间隔
        lbl_y = ybot - gap * 0.40
        ops.append(_text(6, lbl_y, f"#{i+1} {p.kind}  下料长={p.long_cut:.1f}"
                        f"  短={p.short_cut:.1f}  中线={L0:.1f}", color="#000", size=11))
        pts.append((6, lbl_y))
        y_top = ybot - gap
    # 标题(底部)
    ops.append(_text(6, y_top + 6, f"放样展开图 (n={res.n})  需用直管≈{res.material_len:.1f} mm",
                     color="#000", size=14))
    pts.append((6, y_top + 6))
    return pts, ops


# ---------- 渲染到 Canvas ----------
def paint(canvas, pts: List[Pt], ops: List[Op], width: int, height: int, margin: int = 40) -> None:
    if not pts:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    spanx = max(x1 - x0, 1e-6)
    spany = max(y1 - y0, 1e-6)

    # 等比例缩放(保持纵横比), 避免水平/竖直距离被拉伸成不一样长
    sx = (width - 2 * margin) / spanx
    sy = (height - 2 * margin) / spany
    scale = min(sx, sy)
    offx = (width - spanx * scale) / 2.0
    offy = (height - spany * scale) / 2.0

    def tx(x): return offx + (x - x0) * scale
    def ty(y): return height - offy - (y - y0) * scale

    for op in ops:
        kind = op[0]
        if kind == "poly":
            _, pts2, fill, outline, wd = op
            coords = []
            for (x, y) in pts2:
                coords.extend([tx(x), ty(y)])
            canvas.create_polygon(coords, fill=fill or "", outline=outline, width=wd)
        elif kind == "line":
            _, pts2, color, wd = op
            (ax, ay), (bx, by) = pts2
            canvas.create_line(tx(ax), ty(ay), tx(bx), ty(by), fill=color, width=wd)
        elif kind == "dash_line":
            _, pts2, color, wd = op
            coords = []
            for (x, y) in pts2:
                coords.extend([tx(x), ty(y)])
            canvas.create_line(coords, fill=color, width=wd, dash=(6, 4))
        elif kind == "text":
            _, x, y, s, color, size = op
            canvas.create_text(tx(x), ty(y), text=s, fill=color, font=("SimSun", max(8, int(size))))
        elif kind == "circle":
            _, cx, cy, r, outline, fill = op
            canvas.create_oval(tx(cx) - r, ty(cy) - r, tx(cx) + r, ty(cy) + r,
                               outline=outline or "", fill=fill or "")
        elif kind == "arc":
            _, x0a, y0a, x1a, y1a, start, ext, color, wd = op
            canvas.create_arc(tx(min(x0a, x1a)), ty(max(y0a, y1a)), tx(max(x0a, x1a)), ty(min(y0a, y1a)),
                              start=start, extent=ext, style="arc", outline=color, width=wd)
        else:
            raise ValueError(f"unknown op: {kind}")


def scene_bbox(pts: List[Pt]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def to_svg(pts: List[Pt], ops: List[Op], width: int = 900, height: int = 700,
           margin: int = 40) -> str:
    """把绘制指令导出为 SVG 字符串（浏览器可直接打开，无需 CAD）。"""
    if not pts:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"></svg>' % (width, height)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    spanx = max(x1 - x0, 1e-6)
    spany = max(y1 - y0, 1e-6)
    scale = min((width - 2 * margin) / spanx, (height - 2 * margin) / spany)
    offx = (width - spanx * scale) / 2.0
    offy = (height - spany * scale) / 2.0

    def tx(x): return offx + (x - x0) * scale
    def ty(y): return height - offy - (y - y0) * scale

    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d" style="background:#fff;font-family:sans-serif;">' % (width, height, width, height)]
    for op in ops:
        kind = op[0]
        if kind == "poly":
            _, pts2, fill, outline, wd = op
            pstr = " ".join("%g,%g" % (tx(x), ty(y)) for (x, y) in pts2)
            out.append('<polygon points="%s" fill="%s" stroke="%s" stroke-width="%s"/>' % (pstr, fill, outline, wd))
        elif kind == "line":
            _, pts2, color, wd = op
            (ax, ay), (bx, by) = pts2
            out.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="%s"/>'
                       % (tx(ax), ty(ay), tx(bx), ty(by), color, wd))
        elif kind == "dash_line":
            _, pts2, color, wd = op
            pstr = " ".join("%g,%g" % (tx(x), ty(y)) for (x, y) in pts2)
            out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%s" stroke-dasharray="10,6"/>'
                       % (pstr, color, wd))
        elif kind == "text":
            _, x, y, s, color, size = op
            xm, ym, anchor = (tx(x), ty(y), "middle")
            out.append('<text x="%g" y="%g" fill="%s" font-size="%d" text-anchor="%s">%s</text>'
                       % (xm, ym, color, max(9, int(size)), anchor, s))
        elif kind == "circle":
            _, cx, cy, r, outline, fill = op
            rr = max(3.0, r * scale * 1.0)
            out.append('<circle cx="%g" cy="%g" r="%g" fill="%s" stroke="%s"/>'
                       % (tx(cx), ty(cy), rr, fill, outline))
        elif kind == "arc":
            _, x0a, y0a, x1a, y1a, start, ext, color, wd = op
            from math import radians, cos, sin
            cx, cy = (x0a + x1a) / 2.0, (y0a + y1a) / 2.0
            rr = abs(x1a - x0a) / 2.0
            sa, ea = radians(start), radians(start + ext)
            xa, ya, xb, yb = cx + rr * cos(sa), cy + rr * sin(sa), cx + rr * cos(ea), cy + rr * sin(ea)
            large = 1 if abs(ext) > 180 else 0
            out.append('<path d="M %g,%g A %g,%g 0 %d 1 %g,%g" fill="none" stroke="%s" stroke-width="%s"/>'
                       % (tx(xa), ty(ya), rr * scale, rr * scale, large, tx(xb), ty(yb), color, wd))
    out.append("</svg>")
    return "\n".join(out)
