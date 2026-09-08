"""把折弯/放样模板写成 DXF（外皮展开：理论线 + 含坡口余量的下切线）。

每节一张模板，纵向堆叠；每节高度按"中线长 + 上下两正弦峰各外扩(振幅+坡口余量)"计算，绝不出叠。
标注文字放在每节模板右侧（不占竖直空间，避免互相遮挡）。
"""
from __future__ import annotations

import math

from .dxfout import DXFBuilder
from .geometry import ElbowResult, PieceResult

N_PTS = 90


def _circ(od: float) -> float:
    return math.pi * od


def _cosu(u: float, circ: float) -> float:
    return math.cos(u * 2.0 * math.pi / circ)


def _poly(builder: DXFBuilder, layer: str, pts) -> None:
    builder.add_polyline(layer, [(x, y) for (x, y) in pts])


def draw_piece(builder: DXFBuilder, piece: PieceResult, od: float, y_base: float,
               W: float, x_lay: float = 0.0) -> float:
    """画出单节模板（闭合形状）；该节最低点落在 y_base，返回该节占用高度。"""
    circ = _circ(od)
    amp = piece.amp
    L0 = piece.midline
    kind = piece.kind
    e = piece.miter_edges
    yb = y_base + amp + e * W        # 让最低点(下弧谷)正好落在 y_base

    def curve(shift_y: float, top: bool):
        pts = []
        for i in range(N_PTS + 1):
            u = circ * i / N_PTS
            c = _cosu(u, circ)
            v = amp * c if top else -amp * c
            pts.append((x_lay + u, yb + v + shift_y))
        return pts

    # 闭合模板轮廓: 上正弦 + 下正弦(或方口) + 两端竖边(由 close 自动连接)
    theo_top = curve(L0, True)
    if kind == "full":
        theo_pts = theo_top + curve(0.0, False)[::-1]
    else:  # half: 下端方口平直
        theo_pts = theo_top + [(x_lay + circ, y_base), (x_lay, y_base)]
    builder.add_polyline("THEO", theo_pts, closed=True)

    cut_top = curve(L0 + e * W, True)
    if kind == "full":
        cut_pts = cut_top + curve(-e * W, False)[::-1]
    else:
        cut_pts = cut_top + [(x_lay + circ, y_base), (x_lay, y_base)]
    builder.add_polyline("CUT", cut_pts, closed=True)

    # ---- 长/短边参考线 (青) ----
    y_top_long = yb + L0 + amp
    y_top_short = yb + L0 - amp
    builder.add_line("DIM", x_lay, y_base, x_lay, y_top_long)
    builder.add_line("DIM", x_lay + circ / 2.0, y_base, x_lay + circ / 2.0, y_top_short)

    # ---- 标注文字放在模板右侧 (中文, 行距避免重合) ----
    label_h = max(circ * 0.016, 30.0)
    line_sp = label_h * 1.3
    labx = x_lay + circ + 60
    laby = yb + L0 / 2.0
    kind_cn = "半节" if kind == "half" else "全节"
    builder.add_text("LABEL", f"第{piece.index + 1}节  {kind_cn}", labx, laby + line_sp, label_h)
    builder.add_text("LABEL", f"理论  长边={piece.long_theo:.0f}  短边={piece.short_theo:.0f}",
                     labx, laby, label_h)
    builder.add_text("LABEL", f"下料  长边={piece.long_cut:.0f}  短边={piece.short_cut:.0f}"
                     f"  (坡口+{W:.1f})", labx, laby - line_sp, label_h)

    H = L0 + 2.0 * amp + 2.0 * e * W
    return H


def generate_dxf(res: ElbowResult) -> DXFBuilder:
    od = res.inp.od
    W = res.bevel_allowance
    b = DXFBuilder()
    b.add_layer("THEO", 3)
    b.add_layer("CUT", 1)
    b.add_layer("DIM", 4)
    b.add_layer("LABEL", 5)
    b.add_layer("LEGEND", 7)

    circ = _circ(od)
    y = 40.0
    for piece in res.pieces:
        h = draw_piece(b, piece, od, y, W, x_lay=10.0)
        y += h + 40.0                       # 每节之间留 40 空白
        b.add_line("DIM", 10.0, y - h, 10.0 + circ, y - h)          # 界栏底
        b.add_line("DIM", 10.0 + circ + 400, y - h, 10.0 + circ + 400, y)  # 界栏右

    # 图例
    lh = max(circ * 0.016, 30.0)
    b.add_text("LEGEND",
               "放样展开图(外皮):  绿色=理论线  红色=下切线(含单V坡口余量)  青色=长/短边参考线",
               10.0, y + lh * 1.2, lh)
    b.add_text("LEGEND",
               "外径OD=%.1f  t=%.1f  α=%.1f°  R=%.1f  θ=%.1f  p=%.1f  g=%.1f  | 需用直管=%.1f mm"
               % (od, res.inp.thickness, res.inp.bend_angle_deg, res.R,
                  res.inp.bevel_angle_deg, res.inp.root_face, res.inp.root_gap, res.material_len),
               10.0, y, lh)
    return b
