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
    """画出单节模板；该节最低点落在 y_base，返回该节占用高度。"""
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

    # ---- 理论线 (绿) ----
    if kind == "full":
        _poly(builder, "THEO", curve(L0, True))
        _poly(builder, "THEO", curve(0.0, False))
    else:  # half: 下端方口平直
        builder.add_line("THEO", x_lay, y_base, x_lay + circ, y_base)
        _poly(builder, "THEO", curve(L0, True))

    # ---- 下切线 (红, 含坡口余量) ----
    if kind == "full":
        _poly(builder, "CUT", curve(L0 + e * W, True))
        _poly(builder, "CUT", curve(-e * W, False))
    else:
        builder.add_line("CUT", x_lay, y_base, x_lay + circ, y_base)
        _poly(builder, "CUT", curve(L0 + W, True))

    # ---- 长/短边参考线 (青) ----
    y_top_long = yb + L0 + amp
    y_top_short = yb + L0 - amp
    builder.add_line("DIM", x_lay, y_base, x_lay, y_top_long)
    builder.add_line("DIM", x_lay + circ / 2.0, y_base, x_lay + circ / 2.0, y_top_short)

    # ---- 标注文字放在模板右侧 ----
    labx = x_lay + circ + 30
    laby = yb + L0 / 2.0
    builder.add_text("LABEL", f"#{piece.index + 1} {kind}", labx, laby - 6, 3.0)
    builder.add_text("LABEL", "THEO  L=%.1f  S=%.1f" % (piece.long_theo, piece.short_theo),
                     labx, laby, 3.0)
    builder.add_text("LABEL", "CUT   L=%.1f  S=%.1f  (bevel +%.2f/edge)" % (
        piece.long_cut, piece.short_cut, W), labx, laby + 6, 3.0)

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
    b.add_text("LEGEND",
               "STUB LAYOUT (outer surface): GREEN=theo  RED=cut(with single-V bevel)  BLUE=dims/labels",
               10.0, y + 6, 3.0)
    b.add_text("LEGEND",
               "OD=%.1f  t=%.1f  alpha=%.1f deg  R=%.1f  theta=%.1f  p=%.1f  g=%.1f  |  pipe_len=%.1f mm"
               % (od, res.inp.thickness, res.inp.bend_angle_deg, res.R,
                  res.inp.bevel_angle_deg, res.inp.root_face, res.inp.root_gap, res.material_len),
               10.0, y + 2, 3.0)
    return b
