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

    def to_string(self) -> str:
        buf = io.StringIO()
        self.doc.write(buf)
        return buf.getvalue()
