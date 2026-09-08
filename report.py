"""文本报告与材料用量汇总。"""
from __future__ import annotations

from .geometry import ElbowResult


def _fmt(v: float, nd: int = 1) -> str:
    return f"{v:.{nd}f}"


def build_report(res: ElbowResult) -> str:
    inp = res.inp
    lines: list[str] = []
    A = lines.append
    A("=" * 62)
    A("  弯头放样计算报告     (图纸驱动 / 单V坡口·恒定近似)")
    A("=" * 62)
    A(f"弯头总角度 α        : {inp.bend_angle_deg:.2f} °")
    A(f"外径 OD            : {inp.od:.2f} mm")
    A(f"壁厚 t             : {inp.thickness:.2f} mm")
    A(f"中径 = OD - t       : {res.mid_diameter:.2f} mm")
    A(f"节数 N             : {res.n}")
    Rshow = res.R_nominal if res.R_nominal > 0 else res.R
    A(f"设计R(画图) / 反推R : {Rshow:.1f} / {res.R:.1f} mm")
    A(f"Σ每节中心角         : {res.central_sum_deg:.2f} ° (α={inp.bend_angle_deg:.2f}°)")
    A(f"坡口半角 θ / 钝边 p : {inp.bevel_angle_deg:.2f}° / {inp.root_face:.2f} mm")
    A(f"根部间隙 g         : {inp.root_gap:.2f} mm")
    A(f"坡口余量 W=(t-p)tanθ: {res.bevel_allowance:.3f} mm / 每坡口边")
    A("")

    A("---- 一致性校验 ----")
    A(f"平均斜切角 φ      : {res.phi_mean_deg:.3f} °")
    A(f"各节 φ 离散 std   : {res.phi_std_deg:.4f} °   (0=完全对称)")
    A(f"Σ方向改变 = 2φ(N-1): {res.turn_total_deg:.3f} °")
    A(f"输入 α           : {res.bend_angle_deg:.3f} °")
    d = res.turn_error_deg
    if abs(d) < 0.5:
        A(f"                  ✓ 一致 (偏差 {d:+.3f} °)")
    elif abs(d) < 5.0:
        A(f"                  ! 轻微偏差 {d:+.3f} °，请核对图纸")
    else:
        A(f"                  ✗ 偏差 {d:+.3f} °，图纸冲突，需人工核实")
    if abs(res.central_sum_deg - inp.bend_angle_deg) > 0.01:
        A(f"注意: Σ每节中心角({res.central_sum_deg:.2f}°) ≠ 弯头角(α={inp.bend_angle_deg:.2f}°)。"
          f"虾米弯每节为直管(弦), 弦布置下弧的中心角之和会略大于实际方向改变, 属正常。")
    A("")

    A("---- 每节明细 (理论 = 图纸标注, 下料 = 含坡口余量) ----")
    A(f"{'节':<3}{'类型':<6}{'理论长边':>10}{'理论短边':>10}{'中线L0':>10}"
      f"{'中心角':>9}{'R反推':>9}{'斜切φ':>9}{'下料长边':>10}{'下料短边':>10}")
    for p in res.pieces:
        A(f"{p.index+1:<3}{p.kind:<6}{_fmt(p.long_theo):>10}{_fmt(p.short_theo):>10}"
          f"{_fmt(p.midline):>10}{_fmt(p.central_angle_deg,2):>9}{_fmt(p.R_piece):>9}"
          f"{_fmt(p.phi_deg,3):>9}"
          f"{_fmt(p.long_cut):>10}{_fmt(p.short_cut):>10}")
    A("")

    A("---- 材料汇总 ----")
    A(f"需用直管(Σ每节长边)            : {_fmt(res.material_len)} mm")
    A(f"  含坡口余量(Σ每节下料长边)     : {_fmt(res.material_safe)} mm")
    A(f"  中心线几何合计(Σ中线, 参考)   : {_fmt(res.material_mid)} mm")
    A(f"装配总长(Σ中线 + (N-1)·g)      : {_fmt(res.assembly_len)} mm")
    A("")
    A("备注: 直管用量为「分开切」保守值; 若套料可减少。")
    A("=" * 62)
    return "\n".join(lines)
