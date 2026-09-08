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
    """画出单节模板（闭合形状，1:1 mm）；该节最低点落在 y_base，返回该节占用高度。

    半节: 下端为方口(平直), 上端为斜口;  长边=中线+振幅, 短边=中线-振幅。
    全节: 上下都是斜口;  长边=中线+2×振幅, 短边=中线-2×振幅。
    """
    circ = _circ(od)
    amp = piece.amp
    L0 = piece.midline
    kind = piece.kind
    e = piece.miter_edges

    def cosc(u):
        return math.cos(u * 2.0 * math.pi / circ)

    def uu(i):
        return x_lay + circ * i / N_PTS

    if kind == "full":
        C = y_base + amp + W                 # 使下切谷正好落在 y_base
        theo_bot = [(uu(i), C - amp * cosc(uu(i) - x_lay)) for i in range(N_PTS + 1)]
        theo_top = [(uu(i), C + L0 + amp * cosc(uu(i) - x_lay)) for i in range(N_PTS + 1)]
        builder.add_polyline("THEO", theo_top + theo_bot[::-1], closed=True)
        cut_bot = [(x, y - W) for (x, y) in theo_bot]
        cut_top = [(x, y + W) for (x, y) in theo_top]
        builder.add_polyline("CUT", cut_top + cut_bot[::-1], closed=True)
        # 长/短边(理论) 竖向参考线: u=0 长边, u=π 短边
        long_bot, long_top = C - amp, C + L0 + amp
        short_bot, short_top = C + amp, C + L0 - amp
        H = L0 + 2.0 * amp + 2.0 * W
    else:  # half
        theo_top = [(uu(i), y_base + L0 + amp * cosc(uu(i) - x_lay)) for i in range(N_PTS + 1)]
        builder.add_polyline("THEO", theo_top + [(x_lay + circ, y_base), (x_lay, y_base)], closed=True)
        cut_top = [(x, y + W) for (x, y) in theo_top]
        builder.add_polyline("CUT", cut_top + [(x_lay + circ, y_base), (x_lay, y_base)], closed=True)
        long_bot, long_top = y_base, y_base + L0 + amp
        short_bot, short_top = y_base, y_base + L0 - amp
        H = L0 + amp + W

    # 长/短边竖向参考线(青)
    builder.add_line("DIM", x_lay, long_bot, x_lay, long_top)
    builder.add_line("DIM", x_lay + circ / 2.0, short_bot, x_lay + circ / 2.0, short_top)

    # 标注文字(中文, 行距避免重合)
    label_h = max(circ * 0.016, 30.0)
    line_sp = label_h * 1.3
    labx = x_lay + circ + 60
    laby = y_base + L0 / 2.0
    kind_cn = "半节" if kind == "half" else "全节"
    builder.add_text("LABEL", f"第{piece.index + 1}节  {kind_cn}", labx, laby + line_sp, label_h)
    builder.add_text("LABEL", "理论  长边=%.0f  短边=%.0f" % (piece.long_theo, piece.short_theo),
                     labx, laby, label_h)
    builder.add_text("LABEL", "下料  长边=%.0f  短边=%.0f  (坡口+%.1f)" % (
        piece.long_cut, piece.short_cut, W), labx, laby - line_sp, label_h)
    return H

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
               "放样展开图(外皮)  单位mm, 按 1:1 绘制  打印请按1:1  |  绿=理论线  红=下切线(含坡口)  青=长/短边",
               10.0, y + lh * 1.2, lh)
    b.add_text("LEGEND",
               "外径OD=%.1f  t=%.1f  α=%.1f°  R=%.1f  θ=%.1f  p=%.1f  g=%.1f  | 需用直管=%.1f mm"
               % (od, res.inp.thickness, res.inp.bend_angle_deg, res.R,
                  res.inp.bevel_angle_deg, res.inp.root_face, res.inp.root_gap, res.material_len),
               10.0, y, lh)
    return b
