"""DXF 输出（改用 ezdxf 生成标准合法 DXF，保证 CAD 可打开）。

接口与原 DXFBuilder 兼容：add_layer / add_line / add_polyline / add_circle / add_text / to_string。
"""
from __future__ import annotations

import io
from typing import Sequence, Tuple

import ezdxf


def _mm(v: float) -> float:
    return float(v)


class DXFBuilder:
    def __init__(self) -> None:
        self.doc = ezdxf.new("R2010", units=4)   # 4 = mm; 默认含图层 "0", 无需 setup 免字体告警
        # 设置文本样式字体, 支持中文 (宋体/SimSun; CAD 可渲染)
        try:
            st = self.doc.styles.get("Standard")
            st.dxf.font = "SimSun"
        except Exception:
            pass
        self.layers: dict[str, int] = {"0": 7}
        self._msp = self.doc.modelspace()

    def add_layer(self, name: str, color: int = 7) -> None:
        if name not in self.doc.layers:
            self.doc.layers.add(name, color=color)
        self.layers[name] = color

    def add_line(self, layer: str, x1: float, y1: float, x2: float, y2: float) -> None:
        self._msp.add_line((_mm(x1), _mm(y1)), (_mm(x2), _mm(y2)),
                           dxfattribs={"layer": layer})

    def add_polyline(self, layer: str, pts: Sequence[Tuple[float, float]], closed: bool = False) -> None:
        self._msp.add_lwpolyline([( _mm(x), _mm(y)) for (x, y) in pts],
                                 close=closed, dxfattribs={"layer": layer})

    def add_circle(self, layer: str, cx: float, cy: float, r: float) -> None:
        self._msp.add_circle((_mm(cx), _mm(cy)), _mm(r), dxfattribs={"layer": layer})

    def add_text(self, layer: str, text: str, x: float, y: float, height: float = 2.5) -> None:
        t = self._msp.add_text(str(text), dxfattribs={
            "layer": layer, "height": _mm(height), "insert": (_mm(x), _mm(y))})

    def add_linear_dim(self, layer: str, base, p1, p2, angle: float = 90.0,
                       txt: float = 100.0, color: int = 4) -> None:
        """添加线性尺寸标注(垂直测量长/短边), 带箭头和数值; base=尺寸线位置。"""
        dim = self._msp.add_linear_dim(
            base=(_mm(base[0]), _mm(base[1])),
            p1=(_mm(p1[0]), _mm(p1[1])), p2=(_mm(p2[0]), _mm(p2[1])),
            angle=angle, dimstyle="Standard",
            override={"dimtxt": _mm(txt), "dimasz": _mm(txt * 0.5),
                      "dimexe": _mm(txt * 0.2), "dimclrt": color,
                      "dimclrd": color, "dimclre": color,
                      "dimtm": 0, "dimtol": 0},
            dxfattribs={"layer": layer})
        dim.render()

    def to_string(self) -> str:
        buf = io.StringIO()
        self.doc.write(buf)
        return buf.getvalue()
