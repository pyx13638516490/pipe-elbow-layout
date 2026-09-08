"""弯头放样工具 V2 - 高交互版 (仿图纸布局)。

左侧: 输入(角度/段数/外径/壁厚/半径/坡口) + 可编辑每节长边短边表 + 直管用量 + 按钮
右侧: Notebook 分三页 —— 弯管图 / 单V坡口接口示意 / 下料放样图
流程: 填角度段数 ->【自动计算】出默认弯管图 -> 改每节长/短边 ->【生成】重新画吻合图 -> 输出放样DXF
"""
from __future__ import annotations

import os
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .cad import find_cad, launch_cad
from .geometry import compute_elbow, generate_pieces_from_design
from .dxfout import DXFBuilder
from .layout import generate_dxf
from .models import ElbowInput, PieceInput
from .report import build_report
from .render import bevel_scene, elbow_scene, layout_scene, paint

PAD = 6


class App2(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("弯头放样工具 V2  (图纸驱动 / 单V坡口·恒定近似)")
        self.geometry("1280x760")
        self.minsize(1080, 680)

        self.res = None
        self.last_dxf: str | None = None
        self._piece_widgets: list = []

        self._build_left()
        self._build_tabs()
        self._layout()

        self._set_defaults()
        self.on_compute()

    def _set_defaults(self) -> None:
        """默认数据 = 图中设计院数据 (OD=3220, t=14, α=90, N=5, R=6400, 单V θ=30/p=2/g=2)。"""
        self.v_alpha.set("90")
        self.v_od.set("3220")
        self.v_t.set("14")
        self.v_n.set(5)
        self.v_R.set("6400")
        self.v_theta.set("30")
        self.v_p.set("2")
        self.v_g.set("2")
        # 每节长/短边 (图中数据)
        segs = [("half", 1593, 953, 11), ("full", 3187, 1906, 23), ("full", 3187, 1906, 23),
                ("full", 3187, 1906, 23), ("half", 1643, 1003, 11)]
        self._rebuild_table()
        for i, (kind_var, long_var, short_var, c_var) in enumerate(self._piece_widgets):
            kind, lo, sh, ca = segs[i]
            kind_var.set(kind)
            long_var.set(str(lo))
            short_var.set(str(sh))
            c_var.set(str(ca))   # 设计院中心角; 弦布置下 Σ中心角可略大于弯头角, 属正常

    # ---------- 布局 ----------
    def _build_left(self) -> None:
        left = ttk.Frame(self, width=330)
        left.pack(side="left", fill="y", padx=(8, 4), pady=8)
        left.pack_propagate(False)
        self.left = left

        # 参数
        box = ttk.LabelFrame(left, text="弯头参数")
        box.pack(fill="x")
        self.v_alpha = tk.StringVar()
        self.v_od = tk.StringVar()
        self.v_t = tk.StringVar()
        self.v_n = tk.IntVar(value=3)
        self.v_R = tk.StringVar()
        self.v_theta = tk.StringVar(value="30")
        self.v_p = tk.StringVar(value="1.5")
        self.v_g = tk.StringVar(value="2")
        rows = [
            ("弯头角 α (°)", self.v_alpha, 0, False),
            ("外径 OD (mm)", self.v_od, 1, False),
            ("壁厚 t (mm)", self.v_t, 2, False),
            ("节数 N (2~12)", self.v_n, 3, True),
            ("弯曲半径 R (空=1.5×OD)", self.v_R, 4, False),
            ("坡口半角 θ (°)", self.v_theta, 5, False),
            ("钝边 p (mm)", self.v_p, 6, False),
            ("根部间隙 g (mm)", self.v_g, 7, False),
        ]
        for i, (lbl, var, _r, isspin) in enumerate(rows):
            ttk.Label(box, text=lbl).grid(row=i, column=0, sticky="e", padx=4, pady=3)
            if isspin:
                sp = ttk.Spinbox(box, from_=2, to=12, textvariable=var, width=9,
                                 command=self._rebuild_table)
                sp.grid(row=i, column=1, sticky="w")
            else:
                ttk.Entry(box, textvariable=var, width=10).grid(row=i, column=1, sticky="w")

        # 每节表
        tf = ttk.LabelFrame(left, text="每节长边 / 短边 (理论=图纸标注, 不含坡口)")
        tf.pack(fill="both", expand=True, padx=(0, 0), pady=(8, 0))
        self.table_frame = ttk.Frame(tf)
        self.table_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self._rebuild_table()

        # 直管用量 (主数据 = 保守值, 放大显示)
        mb = ttk.LabelFrame(left, text="需用直管")
        mb.pack(fill="x", pady=(8, 0))
        self.v_safe = tk.StringVar(value="-")     # 主: 保守(每节最长边)
        self.v_material = tk.StringVar(value="-") # 净长
        self.v_assembly = tk.StringVar(value="-")
        self.v_r = tk.StringVar(value="-")
        ttk.Label(mb, textvariable=self.v_safe, foreground="#c00",
                  font=("SimHei", 18, "bold")).pack(anchor="w", padx=8, pady=(2, 0))
        ttk.Label(mb, text="(Σ每节长边)", foreground="#c00").pack(anchor="w", padx=8)
        ttk.Label(mb, textvariable=self.v_material, foreground="#333").pack(anchor="w", padx=8)
        ttk.Label(mb, textvariable=self.v_assembly, foreground="#333").pack(anchor="w", padx=8)
        ttk.Label(mb, textvariable=self.v_r, foreground="#00c").pack(anchor="w", padx=8)

        # 按钮
        btn = ttk.Frame(left)
        btn.pack(fill="x", pady=(8, 0))
        ttk.Button(btn, text="自动计算", command=self.on_autogen).pack(fill="x")
        ttk.Button(btn, text="生成 (用表中的长/短边)", command=self.on_compute).pack(fill="x", pady=(4, 0))

        # 输出
        ob = ttk.LabelFrame(left, text="输出")
        ob.pack(fill="x", pady=(8, 0))
        self.v_out = tk.StringVar(value=str(Path.home() / "Desktop"))
        ttk.Entry(ob, textvariable=self.v_out, width=28).pack(fill="x", padx=4, pady=(4, 0))
        ttk.Button(ob, text="浏览目录", command=self._browse).pack(fill="x", padx=4, pady=2)
        ttk.Button(ob, text="输出放样图 DXF", command=self.on_output_dxf).pack(fill="x", padx=4, pady=2)
        ttk.Button(ob, text="用 AutoCAD 打开", command=self.on_open_cad).pack(fill="x", padx=4, pady=(2, 4))

    def _build_tabs(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(side="right", fill="both", expand=True, padx=(4, 8), pady=8)
        self.nb = nb

        # 弯管图
        t1 = ttk.Frame(nb)
        self.cv_elbow = tk.Canvas(t1, bg="white", highlightthickness=1, highlightbackground="#ccc")
        self.cv_elbow.pack(fill="both", expand=True, padx=4, pady=4)
        self.lbl_elbow = ttk.Label(t1, text="", anchor="w")
        self.lbl_elbow.pack(fill="x", padx=6, pady=(0, 4))
        nb.add(t1, text=" 弯管图 ")

        # 坡口接口示意
        t2 = ttk.Frame(nb)
        self.cv_bevel = tk.Canvas(t2, bg="white", highlightthickness=1, highlightbackground="#ccc")
        self.cv_bevel.pack(fill="both", expand=True, padx=4, pady=4)
        nb.add(t2, text=" 坡口/接口示意 ")

        # 放样图
        t3 = ttk.Frame(nb)
        self.cv_layout = tk.Canvas(t3, bg="white", highlightthickness=1, highlightbackground="#ccc")
        self.cv_layout.pack(fill="both", expand=True, padx=4, pady=4)
        nb.add(t3, text=" 放样图·下料 ")

    def _layout(self) -> None:
        # 让绘制区随窗口伸缩
        for cv in (self.cv_elbow, self.cv_bevel, self.cv_layout):
            cv.bind("<Configure>", lambda _e, c=cv: self._paint_canvas(c))

    # ---------- 表格 ----------
    def _rebuild_table(self) -> None:
        for w in self.table_frame.winfo_children():
            w.destroy()
        self._piece_widgets.clear()
        n = self._read_n()
        heads = ["节", "类型", "长边", "短边", "中心角°"]
        for j, h in enumerate(heads):
            ttk.Label(self.table_frame, text=h).grid(row=0, column=j, padx=4, pady=2)
        for i in range(n):
            r = i + 1
            ttk.Label(self.table_frame, text=str(i + 1)).grid(row=r, column=0, padx=4)
            kind_var = tk.StringVar(value="auto")
            ttk.Combobox(self.table_frame, textvariable=kind_var, width=7, state="readonly",
                         values=["auto", "half", "full"]).grid(row=r, column=1, padx=4, pady=2)
            long_var = tk.StringVar()
            short_var = tk.StringVar()
            c_var = tk.StringVar()
            ttk.Entry(self.table_frame, textvariable=long_var, width=9).grid(row=r, column=2, padx=4)
            ttk.Entry(self.table_frame, textvariable=short_var, width=9).grid(row=r, column=3, padx=4)
            ttk.Entry(self.table_frame, textvariable=c_var, width=7).grid(row=r, column=4, padx=4)
            self._piece_widgets.append((kind_var, long_var, short_var, c_var))

    def _read_n(self) -> int:
        try:
            return max(2, min(12, int(self.v_n.get())))
        except (tk.TclError, ValueError):
            return 3

    def _read_input(self) -> dict:
        def f(v):
            return float(v.get())
        alpha = f(self.v_alpha)
        od = f(self.v_od)
        t = f(self.v_t)
        theta = f(self.v_theta)
        p = f(self.v_p)
        g = f(self.v_g)
        R = f(self.v_R) if self.v_R.get().strip() else None
        alpha, od, t, theta, p, g = self._sanitize_positive(alpha, od, t, theta, p, g)
        return dict(alpha=alpha, od=od, t=t, theta=theta, p=p, g=g, R=R)

    @staticmethod
    def _sanitize_positive(*vals):
        out = []
        for v in vals:
            if not (v > 0):
                raise ValueError("参数必须为正数")
            out.append(v)
        return tuple(out)

    def _read_pieces(self) -> list:
        outs = []
        for (kind_var, long_var, short_var, c_var) in self._piece_widgets:
            k = kind_var.get()
            c = c_var.get().strip()
            outs.append(PieceInput(long_od=float(long_var.get()),
                                   short_od=float(short_var.get()),
                                   kind=None if k == "auto" else k,
                                   central_angle_deg=float(c) if c else None))
        return outs

    # ---------- 计算 ----------
    def _compute(self) -> None:
        d = self._read_input()
        pieces = self._read_pieces()
        inp = ElbowInput(bend_angle_deg=d["alpha"], od=d["od"], thickness=d["t"],
                         pieces=pieces, bevel_angle_deg=d["theta"], root_face=d["p"],
                         root_gap=d["g"], R_nominal=d["R"])
        self.res = compute_elbow(inp)
        self.inp = inp
        self.v_safe.set(f"需用直管 = {self.res.material_len:.1f} mm")
        self.v_material.set(f"含坡口余量 = {self.res.material_safe:.1f} mm")
        self.v_assembly.set(f"中线几何合计 = {self.res.material_mid:.1f} mm   "
                            f"装配 = {self.res.assembly_len:.1f} mm")
        Rshow = self.res.R_nominal if self.res.R_nominal > 0 else self.res.R
        self.v_r.set(f"R(画图/设计)={Rshow:.0f}  反推R={self.res.R:.0f}  "
                     f"Σ中心角={self.res.central_sum_deg:.2f}°  φ均={self.res.phi_mean_deg:.2f}°")
        self._paint_all()

    def on_autogen(self) -> None:
        """用 α/R/N 生成默认每节长/短边, 填入表格。"""
        try:
            d = self._read_input()
            n = self._read_n()
            R = d["R"] if d["R"] else 1.5 * d["od"]
            pieces = generate_pieces_from_design(d["alpha"], R, d["od"], n)
        except Exception as e:
            messagebox.showerror("自动计算失败", str(e))
            return
        self._rebuild_table()
        for (kind_var, long_var, short_var, c_var), pi in zip(self._piece_widgets, pieces):
            kind_var.set(pi.kind)
            long_var.set(f"{pi.long_od:.1f}")
            short_var.set(f"{pi.short_od:.1f}")
            c_var.set("")
        self._compute()

    def on_compute(self) -> None:
        try:
            self._compute()
        except Exception as e:
            messagebox.showerror("生成失败", str(e))

    # ---------- 绘制 ----------
    def _paint_all(self) -> None:
        if self.res is None:
            return
        self._paint_canvas(self.cv_elbow)
        if self.cv_bevel.winfo_viewable():
            self._paint_canvas(self.cv_bevel)
        self._paint_canvas(self.cv_layout)
        self.lbl_elbow.config(text="绿色=中心线虚线  红圈=接缝  蓝=总角度  灰=整体尺寸  (角度 α=%.0f, N=%d)"
                              % (self.inp.bend_angle_deg, self.res.n))

    def _paint_canvas(self, canvas) -> None:
        canvas.delete("all")
        if self.res is None:
            return
        w = max(canvas.winfo_width(), 200)
        h = max(canvas.winfo_height(), 200)
        if canvas is self.cv_elbow:
            pts, ops = elbow_scene(self.res)
            paint(canvas, pts, ops, w, h, margin=60)
        elif canvas is self.cv_bevel:
            pts, ops = bevel_scene(self.inp)
            paint(canvas, pts, ops, w, h, margin=50)
        elif canvas is self.cv_layout:
            pts, ops = layout_scene(self.res)
            paint(canvas, pts, ops, w, h, margin=40)

    # ---------- 输出 ----------
    def _browse(self) -> None:
        d = filedialog.askdirectory(initialdir=self.v_out.get())
        if d:
            self.v_out.set(d)

    def on_output_dxf(self) -> None:
        if self.res is None:
            messagebox.showinfo("提示", "请先【自动计算】或【生成】")
            return
        try:
            outdir = Path(self.v_out.get().strip() or str(Path.home()))
            outdir.mkdir(parents=True, exist_ok=True)
            stem = "elbow"
            rep_path = outdir / f"{stem}_report.txt"
            dxf_path = outdir / f"{stem}_template.dxf"
            rep_path.write_text(build_report(self.res), encoding="utf-8")
            dxf_path.write_text(generate_dxf(self.res).to_string(), encoding="ascii")
            self.last_dxf = str(dxf_path)
            messagebox.showinfo("已输出", f"报告: {rep_path}\nDXF: {dxf_path}")
        except Exception as e:
            messagebox.showerror("输出失败", str(e))

    def on_open_cad(self) -> None:
        if not self.last_dxf:
            messagebox.showinfo("提示", "请先【输出放样图 DXF】")
            return
        cad = find_cad()
        if not cad:
            messagebox.showwarning("未找到 AutoCAD", "未找到 acad.exe")
            return
        launch_cad(self.last_dxf)
        messagebox.showinfo("已打开", f"AutoCAD 打开:\n{self.last_dxf}")


def main() -> None:
    App2().mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
