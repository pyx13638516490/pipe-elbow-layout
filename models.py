"""数据模型：弯头输入参数（图纸驱动）。

图纸上标注的"长边/短边"指外皮基准、且**不含坡口**（坡口根/钝边基准）。
坡口为单V，恒定近似。所有长度单位 mm，角度单位度。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PieceInput:
    """单节输入。kind 为 'half'(半节) 或 'full'(全节)；None 表示由位置自动判定。"""
    long_od: float          # 长边 (外皮, 不含坡口)
    short_od: float         # 短边 (外皮, 不含坡口)
    kind: Optional[str] = None   # 'half' | 'full' | None(自动)   # noqa: E501
    central_angle_deg: Optional[float] = None  # 设计院给出的该节中心角(度); None=由长/短边反推

    @property
    def requested_kind(self) -> Optional[str]:
        return self.kind


@dataclass
class ElbowInput:
    """整个弯头的输入集合。"""
    bend_angle_deg: float          # 弯头总角度 α
    od: float                      # 外径 OD
    thickness: float               # 壁厚 t
    pieces: List[PieceInput]       # 首→尾 依次排列
    # 单V坡口参数
    bevel_angle_deg: float = 30.0  # 坡口半角 θ (每侧)
    root_face: float = 1.5         # 钝边 p
    root_gap: float = 2.0          # 根部间隙 g
    R_nominal: Optional[float] = None  # 设计给出的中心线弯曲半径(用于画弯管图); None=用反推值

    def __post_init__(self) -> None:
        if self.thickness <= 0:
            raise ValueError("壁厚必须为正")
        if self.bevel_angle_deg <= 0 or self.bevel_angle_deg >= 90:
            raise ValueError("坡口角必须在 0~90 之间")
        if self.root_face < 0:
            raise ValueError("钝边不能为负")
        if self.root_face >= self.thickness:
            raise ValueError("钝边必须小于壁厚")
        if self.root_gap < 0:
            raise ValueError("根部间隙不能为负")


def default_kind(index: int, n: int) -> str:
    """自动判定节类型：首尾半节，中间全节。"""
    if index == 0 or index == n - 1:
        return "half"
    return "full"
