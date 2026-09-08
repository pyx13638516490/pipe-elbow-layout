"""核心几何引擎：从图纸每节的长边/短边还原斜切角 φ、中线长、弯曲半径，并做一致性校验。

约定：
- 长边/短边为外皮(OD)基准、不含坡口，即"坡口根/钝边基准"的理论线。
- 斜切角按外皮差反推：
    半节: tanφ = (长边 - 短边) / OD
    全节: tanφ = (长边 - 短边) / (2·OD)
- 中线长 L0 = (长边 + 短边) / 2，用于弯曲半径与装配。
- 弯曲半径 R 采用"中心线弧长"约定：R = L0 / (该节所占中心角度)。

注意：这里"中心角度"半节取 φ、全节取 2φ（即 2φ 方向改变），若图纸用弦长约定，R 会有微小差别。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from .models import ElbowInput, PieceInput, default_kind


@dataclass
class PieceResult:
    index: int
    kind: str               # 'half' | 'full'
    long_theo: float        # 理论长边 (外皮, 无坡口) ==== 图纸标注
    short_theo: float       # 理论短边
    midline: float          # L0 = (long+short)/2
    phi_deg: float          # 斜切角 φ
    phi_rad: float
    miter_edges: int        # 1=半节, 2=全节 (含坡口边数)
    amp: float              # 外皮正弦振幅 = (OD/2)·tanφ
    long_cut: float         # 下料长边 = 理论 + miter_edges·W
    short_cut: float        # 下料短边 = 理论 + miter_edges·W
    central_angle_rad: float = 0.0   # 该节所占中心角度 (半节φ/全节2φ); 若设计给了则用设计值
    central_angle_deg: float = 0.0   # 同上, 度
    R_piece: float = 0.0             # 该节反推的弯曲半径


@dataclass
class ElbowResult:
    inp: ElbowInput
    mid_diameter: float
    pieces: List[PieceResult]
    R: float                 # 平均弯曲半径
    phi_mean_deg: float
    phi_std_deg: float       # 各节斜切角离散程度 (0=完全对称)
    turn_total_deg: float    # Σ各节方向改变 = 2φ·(N-1)
    bend_angle_deg: float    # 输入 α
    turn_error_deg: float    # turn_total - α
    bevel_allowance: float   # W = (t-p)·tanθ (每坡口边)
    material_len: float      # 需用直管 = Σ每节理论长边 (每节至少按长边切)
    material_safe: float     # 含坡口余量 = Σ每节下料长边
    material_mid: float      # 中心线几何合计 = Σ每节中线 (参考, 非下料)
    assembly_len: float      # 装配总长 ≈ Σ中线 + (N-1)·g
    R_nominal: float = 0.0   # 用户/设计给出的 R (用于画弯管图), 0=用 R
    central_sum_deg: float = 0.0  # Σ每节中心角

    @property
    def n(self) -> int:
        return len(self.pieces)


def _resolve_kind(idx: int, n: int, requested: Optional[str]) -> str:
    if requested in ("half", "full"):
        return requested
    return default_kind(idx, n)


def compute_bevel_allowance(bevel_angle_deg: float, root_face: float, thickness: float) -> float:
    """单V坡口恒定近似余量 W = (t - p)·tanθ。每坡口边贡献一次 W。"""
    theta = math.radians(bevel_angle_deg)
    usable = thickness - root_face
    return usable * math.tan(theta)


def generate_pieces_from_design(bend_angle_deg: float, R: float, od: float, n: int):
    """设计模式：由 弯头角α、弯曲半径R、外径OD、节数N 生成每节的理论长边/短边。

    结构固定为 2 半节 + (N-2) 全节。
    φ = α / (2·(N-1))；全节中线长 = R·(2φ)，半节中线长 = R·φ。
    外皮振幅 = (OD/2)·tanφ。
    """
    from .models import PieceInput, default_kind
    if n < 2:
        raise ValueError("节数至少为 2")
    phi_rad = math.radians(bend_angle_deg) / (2.0 * (n - 1))
    tan_phi = math.tan(phi_rad)
    amp_half = (od / 2.0) * tan_phi            # 半节一侧
    amp_full = od * tan_phi                     # 全节两侧合计
    pieces = []
    for i in range(n):
        kind = default_kind(i, n)
        if kind == "half":
            L0 = R * phi_rad
            long_v = L0 + amp_half
            short_v = L0 - amp_half
        else:
            L0 = R * (2.0 * phi_rad)
            long_v = L0 + amp_full
            short_v = L0 - amp_full
        pieces.append(PieceInput(long_od=long_v, short_od=short_v, kind=kind))
    return pieces


def compute_elbow(inp: ElbowInput) -> ElbowResult:
    n = len(inp.pieces)
    if n < 2:
        raise ValueError("至少需要 2 节才能构成弯头")
    od = inp.od
    t = inp.thickness
    mid_d = od - t
    W = compute_bevel_allowance(inp.bevel_angle_deg, inp.root_face, inp.thickness)

    results: List[PieceResult] = []
    for idx, p in enumerate(inp.pieces):
        kind = _resolve_kind(idx, n, p.requested_kind)
        L = p.long_od
        S = p.short_od
        if L <= 0 or S <= 0:
            raise ValueError(f"第{idx+1}节长边/短边必须为正")
        if L < S:
            raise ValueError(f"第{idx+1}节长边({L})小于短边({S})")

        if kind == "half":
            tan_phi = (L - S) / od
            miter_edges = 1
        else:
            tan_phi = (L - S) / (2.0 * od)
            miter_edges = 2

        if tan_phi < 0:
            raise ValueError(f"第{idx+1}节长边-短边为负, 无法得到正斜切角")

        phi_rad = math.atan(tan_phi)
        phi_deg = math.degrees(phi_rad)
        midline = (L + S) / 2.0
        amp = (od / 2.0) * math.tan(phi_rad)
        long_cut = L + miter_edges * W
        short_cut = S + miter_edges * W
        # 该节所占中心角度: 半节 φ, 全节 2φ; 若设计直接给了中心角则用设计值
        if p.central_angle_deg is not None and p.central_angle_deg > 0:
            central_angle_deg = float(p.central_angle_deg)
            central_angle_rad = math.radians(central_angle_deg)
        else:
            central_angle_rad = phi_rad * miter_edges
            central_angle_deg = math.degrees(central_angle_rad)
        R_piece = midline / central_angle_rad if central_angle_rad > 1e-9 else 0.0

        results.append(PieceResult(
            index=idx, kind=kind,
            long_theo=L, short_theo=S, midline=midline,
            phi_deg=phi_deg, phi_rad=phi_rad,
            miter_edges=miter_edges, amp=amp,
            long_cut=long_cut, short_cut=short_cut,
            central_angle_rad=central_angle_rad, central_angle_deg=central_angle_deg,
            R_piece=R_piece,
        ))

    # 弯曲半径 R：取各节反推值（对称弯头应一致）
    R_vals = [r.R_piece for r in results if r.R_piece > 0]
    R = sum(R_vals) / len(R_vals) if R_vals else 0.0

    # 斜切角一致性
    if results:
        phi_mean_deg = sum(r.phi_deg for r in results) / n
        phi_std_deg = math.sqrt(sum((r.phi_deg - phi_mean_deg) ** 2 for r in results) / n)
    else:
        phi_mean_deg = 0.0
        phi_std_deg = 0.0

    # 方向改变总量 = 2φ·(N-1)
    turn_total_deg = 2.0 * phi_mean_deg * (n - 1)
    turn_error_deg = turn_total_deg - inp.bend_angle_deg

    # 需用直管 = Σ每节理论长边 (每节至少要按长边切出); 含坡口 = Σ每节下料长边; 中线合计(参考)
    material_len = sum(r.long_theo for r in results)
    material_safe = sum(r.long_cut for r in results)
    material_mid = sum(r.midline for r in results)
    # 装配总长：Σ中线 + (N-1)·g
    assembly_len = sum(r.midline for r in results) + (n - 1) * inp.root_gap
    central_sum_deg = sum(r.central_angle_deg for r in results)
    R_nominal = inp.R_nominal if (inp.R_nominal and inp.R_nominal > 0) else 0.0

    return ElbowResult(
        inp=inp, mid_diameter=mid_d,
        pieces=results, R=R,
        phi_mean_deg=phi_mean_deg, phi_std_deg=phi_std_deg,
        turn_total_deg=turn_total_deg,
        bend_angle_deg=inp.bend_angle_deg,
        turn_error_deg=turn_error_deg,
        bevel_allowance=W,
        material_len=material_len,
        material_safe=material_safe,
        material_mid=material_mid,
        assembly_len=assembly_len,
        R_nominal=R_nominal,
        central_sum_deg=central_sum_deg,
    )


def generated_curve(piece: PieceResult, od: float, circumference: float,
                    shift: float, top: bool, n_pts: int = 48):
    """返回[ (u, v), ... ]：外皮正弦曲线(理论线)。u 为周长方向 0~π·OD。
    shift 为竖直平移; top 决定正弦符号方向。
    """
    amp = piece.amp
    phi = piece.phi_rad
    ctod = 2.0 * math.pi  # 对应于把 θ∈[0,2π] 映射到 u∈[0, π·OD]
    pts = []
    for i in range(n_pts + 1):
        u = circumference * i / n_pts
        cosv = math.cos(u * ctod / circumference)  # cos(2π·u/circ)
        v = amp * cosv
        pts.append((u, v + shift))
    return pts


def compute_section(res: ElbowResult):
    """由各节 phi/中线长 计算装配侧面视图的"拼线"几何。

    返回:
      theta: list[float] 每节轴线方向(弧度)
      verts: list[(x,y)] n+1 个拼线顶点(seam 中心, verts[0]=入口, verts[n]=出口)
      方向改变在每个 seam 处为 phi[i] + phi[i+1]; 端面(首节入口/末节出口)为垂直切口。
    """
    n = res.n
    theta = [0.0] * n
    for i in range(1, n):
        theta[i] = theta[i - 1] + res.pieces[i - 1].phi_rad + res.pieces[i].phi_rad
    verts = [(0.0, 0.0)]
    for i in range(n):
        dx, dy = math.cos(theta[i]), math.sin(theta[i])
        vx = verts[-1][0] + res.pieces[i].midline * dx
        vy = verts[-1][1] + res.pieces[i].midline * dy
        verts.append((vx, vy))
    return theta, verts


def _intersect(p1, d1, p2, d2):
    """两条直线交点 (每线 = 点+方向)。"""
    det = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(det) < 1e-12:
        return p1
    t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / det
    return (p1[0] + t * d1[0], p1[1] + t * d1[1])


def piece_quads(res: ElbowResult):
    """返回每节在侧面剖视图中的四边形 (按 A(始-外) C(末-外) D(末-内) B(始-内) 顺序)。

    每节: 轴=verts[i]→verts[i+1], 管外皮半径 r=OD/2, 两端为 miter 面或垂直端面。
    """
    theta, verts = compute_section(res)
    n = res.n
    od = res.inp.od
    r = od / 2.0
    quads = []
    for i in range(n):
        d = (math.cos(theta[i]), math.sin(theta[i]))
        perp = (-d[1], d[0])
        vA = verts[i]
        vB = verts[i + 1]
        # 起始端面
        if i == 0:
            s_face_dir = perp
        else:
            b = (math.cos(theta[i - 1]) + d[0], math.sin(theta[i - 1]) + d[1])
            nb = math.hypot(b[0], b[1])
            b = (b[0] / nb, b[1] / nb)
            s_face_dir = (-b[1], b[0])
        # 终止端面
        if i == n - 1:
            e_face_dir = perp
        else:
            b = (d[0] + math.cos(theta[i + 1]), d[1] + math.sin(theta[i + 1]))
            nb = math.hypot(b[0], b[1])
            b = (b[0] / nb, b[1] / nb)
            e_face_dir = (-b[1], b[0])
        # 外皮两条平行边界线
        top_pt = (vA[0] + r * perp[0], vA[1] + r * perp[1])
        bot_pt = (vA[0] - r * perp[0], vA[1] - r * perp[1])
        A = _intersect(top_pt, d, vA, s_face_dir)
        B = _intersect(bot_pt, d, vA, s_face_dir)
        C = _intersect(top_pt, d, vB, e_face_dir)
        D = _intersect(bot_pt, d, vB, e_face_dir)
        quads.append(([A, C, D, B], vA, vB))
    return quads, theta, verts
