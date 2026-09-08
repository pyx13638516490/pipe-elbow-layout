"""最小的自包含 ASCII DXF (R2000/AC1015) 生成器。不依赖第三方库。

支持: 图层定义、LWPOLYLINE、LINE、TEXT、圆(CIRCLE)。足够输出放样图。
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence, Tuple


def _fmt(v: float) -> str:
    # 去掉无用小数, 保留最多 3 位
    s = f"{v:.6f}"
    return s


class DXFBuilder:
    def __init__(self) -> None:
        self.layers: dict[str, int] = {"0": 7}   # layer -> color
        self.entities: list[list] = []

    def add_layer(self, name: str, color: int = 7) -> None:
        """color: AutoCAD 索引色 (1红 2黄 3绿 4青 5蓝 6品红 7白)。"""
        self.layers[name] = color

    # ---- 实体 ----
    def add_line(self, layer: str, x1: float, y1: float, x2: float, y2: float) -> None:
        self.entities.append(["LINE", layer, (x1, y1), (x2, y2)])

    def add_polyline(self, layer: str, pts: Sequence[Tuple[float, float]], closed: bool = False) -> None:
        self.entities.append(["LWPOLYLINE", layer, list(pts), closed])

    def add_circle(self, layer: str, cx: float, cy: float, r: float) -> None:
        self.entities.append(["CIRCLE", layer, (cx, cy, r)])

    def add_text(self, layer: str, text: str, x: float, y: float, height: float = 2.5) -> None:
        self.entities.append(["TEXT", layer, text, (x, y), height])

    def _header(self) -> str:
        return (
            "0\nSECTION\n2\nHEADER\n"
            "9\n$ACADVER\n1\nAC1015\n"
            "9\n$INSUNITS\n70\n4\n"      # mm
            "0\nENDSEC\n"
        )

    def _tables(self) -> str:
        s = "0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nLAYER\n70\n%d\n" % len(self.layers)
        for name, color in self.layers.items():
            s += (
                "0\nLAYER\n"
                "2\n%s\n" % name +
                "70\n0\n"
                "62\n%d\n" % color +
                "6\nCONTINUOUS\n"
            )
        s += "0\nENDTAB\n0\nENDSEC\n"
        return s

    def _entities(self) -> str:
        s = "0\nSECTION\n2\nENTITIES\n"
        for ent in self.entities:
            kind = ent[0]
            layer = ent[1]
            if kind == "LINE":
                x1, y1 = ent[2]
                x2, y2 = ent[3]
                s += "0\nLINE\n8\n%s\n" % layer
                s += "10\n%s\n20\n%s\n30\n0\n" % (_fmt(x1), _fmt(y1))
                s += "11\n%s\n21\n%s\n31\n0\n" % (_fmt(x2), _fmt(y2))
            elif kind == "LWPOLYLINE":
                pts = ent[2]
                closed = 1 if ent[3] else 0
                s += "0\nLWPOLYLINE\n8\n%s\n" % layer
                s += "90\n%d\n70\n%d\n" % (len(pts), closed)
                for (x, y) in pts:
                    s += "10\n%s\n20\n%s\n" % (_fmt(x), _fmt(y))
            elif kind == "CIRCLE":
                cx, cy, r = ent[2]
                s += "0\nCIRCLE\n8\n%s\n" % layer
                s += "10\n%s\n20\n%s\n30\n0\n40\n%s\n" % (_fmt(cx), _fmt(cy), _fmt(r))
            elif kind == "TEXT":
                text = ent[2]
                (x, y) = ent[3]
                h = ent[4]
                s += "0\nTEXT\n8\n%s\n" % layer
                s += "10\n%s\n20\n%s\n30\n0\n" % (_fmt(x), _fmt(y))
                s += "40\n%s\n1\n%s\n" % (_fmt(h), text)
            else:
                raise ValueError("unknown entity: %r" % (kind,))
        s += "0\nENDSEC\n"
        return s

    def to_string(self) -> str:
        return (
            self._header() +
            self._tables() +
            self._entities() +
            "0\nEOF\n"
        )


def point_text(p: str, fmt: str = "%.2f") -> str:
    return fmt % (float(p),)
