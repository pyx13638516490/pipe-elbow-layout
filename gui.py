"""弯头放样工具 - tkinter 图形界面 (无第三方依赖)。

双击 EXE 一键启动; 填参数 -> 计算并输出 DXF -> 一键用 AutoCAD 打开。
"""
from __future__ import annotations

import os
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .cad import find_cad, launch_cad
from .geometry import compute_elbow, generate_pieces_from_design
from .layout import generate_dxf
from .models import ElbowInput
from .report import build_report


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("弯头放样工具  (图纸驱动 / 单V坡口·恒定近似)")
        self.geometry("1000x720")
        self.minsize(880, 620)

        self.last_dxf: str | None = None
        self._piece_widgets: list = []   # (kind_var, long_var, short_var)

        self._build_basic_frame()
        self._build_piece_frame()
        self._build_buttons_and_output()

        self.report_text = tk.Text(self, wrap="none", font=("Consolas", 10))
        self.report_text.grid(row=4, column=0, sticky="nsew", padx=10, pady=6)
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 默认用 90° 三节样例填充, 方便直接看到效果
        self._fill_default()
        self.on_autogen()

    # ---------- 界面 ----------
    def _build_basic_frame(self) -> None:
        f = ttk.LabelFrame(self, text="弯头参数")
        f.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))

        self.v_alpha = tk.StringVar(value="90")
        self.v_od = tk.StringVar(value="108")
        self.v_t = tk.StringVar(value="4")
        self.v_n = tk.IntVar(value=3)
        self.v_R = tk.StringVar(value="")          # 空 = 自动 1.5*OD
        self.v_theta = tk.StringVar(value="30")
        self.v_p = tk.StringVar(value="1.5")
        self.v_g = tk.StringVar(value="2")

        fields = [
            ("弯头角 α (°)", self.v_alpha),
            ("外径 OD (mm)", self.v_od),
            ("壁厚 t (mm)", self.v_t),
            ("节数 N", self.v_n),
            ("弯曲半径 R (mm,空=自动1.5×OD)", self.v_R),
            ("坡口半角 θ (°)", self.v_theta),
            ("钝边 p (mm)", self.v_p),
            ("根部间隙 g (mm)", self.v_g),
        ]
        for i, (label, var) in enumerate(fields):
            r, c = divmod(i, 4)
            ttk.Label(f, text=label).grid(row=r, column=c * 2, sticky="e", padx=(6, 2), pady=3)
            if isinstance(var, tk.IntVar):
                sp = ttk.Spinbox(f, from_=2, to=12, textvariable=var, width=8,
                                 command=self.on_n_change)
                sp.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 6))
            else:
                e = ttk.Entry(f, textvariable=var, width=10)
                e.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 6))

        ttk.Button(f, text="由 α / R / N 自动生成每节", command=self.on_autogen)\
            .grid(row=2, column=0, columnspan=8, sticky="w", padx=6, pady=(6, 2))

    def _build_piece_frame(self) -> None:
        self.piece_frame = ttk.LabelFrame(self, text="每节长边 / 短边  (理论=图纸标注, 不含坡口)")
        self.piece_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        self._rebuild_piece_rows()

    def _build_buttons_and_output(self) -> None:
        bar = ttk.Frame(self)
        bar.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
        self.v_out = tk.StringVar(value=str(Path.home() / "Desktop"))
        ttk.Label(bar, text="输出目录").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.v_out, width=42).pack(side="left")
        ttk.Button(bar, text="浏览", command=self._browse).pack(side="left", padx=4)

        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        ttk.Button(actions, text="计算并输出 DXF", command=self.on_compute)\
            .pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="用 AutoCAD 打开", command=self.on_open_cad)\
            .pack(side="left", padx=(0, 8))
        self.status = tk.StringVar(value="就绪")
        ttk.Label(actions, textvariable=self.status, foreground="#333").pack(side="left")

    # ---------- 交互 ----------
    def _browse(self) -> None:
        d = filedialog.askdirectory(title="选择输出目录", initialdir=self.v_out.get())
        if d:
            self.v_out.set(d)

    def on_n_change(self) -> None:
        try:
            n = max(2, int(self.v_n.get()))
        except (tk.TclError, ValueError):
            return
        self._rebuild_piece_rows()

    def _rebuild_piece_rows(self) -> None:
        for w in self.piece_frame.winfo_children():
            w.destroy()
        self._piece_widgets.clear()
        n = max(2, int(self.v_n.get()))
        # 表头
        ttk.Label(self.piece_frame, text="节号").grid(row=0, column=0, padx=6, pady=3)
        ttk.Label(self.piece_frame, text="类型").grid(row=0, column=1, padx=6, pady=3)
        ttk.Label(self.piece_frame, text="长边 (mm)").grid(row=0, column=2, padx=6, pady=3)
        ttk.Label(self.piece_frame, text="短边 (mm)").grid(row=0, column=3, padx=6, pady=3)
        ttk.Label(self.piece_frame, text="(首尾=半节 中间=全节)").grid(row=0, column=4, padx=6)
        for i in range(n):
            r = i + 1
            ttk.Label(self.piece_frame, text=str(i + 1)).grid(row=r, column=0)
            kind_var = tk.StringVar(value="auto")
            cb = ttk.Combobox(self.piece_frame, textvariable=kind_var, width=7, state="readonly",
                              values=["auto", "half", "full"])
            cb.grid(row=r, column=1, padx=4, pady=2)
            long_var = tk.StringVar()
            short_var = tk.StringVar()
            ttk.Entry(self.piece_frame, textvariable=long_var, width=10)\
                .grid(row=r, column=2, padx=4)
            ttk.Entry(self.piece_frame, textvariable=short_var, width=10)\
                .grid(row=r, column=3, padx=4)
            self._piece_widgets.append((kind_var, long_var, short_var))

    def on_autogen(self) -> None:
        """用 α/R/N 生成每节长边/短边并填入表格 (设计模式)。"""
        try:
            alpha = float(self.v_alpha.get())
            od = float(self.v_od.get())
            n = max(2, int(self.v_n.get()))
            R = float(self.v_R.get()) if self.v_R.get().strip() else 1.5 * od
        except (tk.TclError, ValueError):
            messagebox.showerror("输入错误", "请检查 弯头角/外径/节数/弯曲半径 是否为数字")
            return
        try:
            pieces = generate_pieces_from_design(alpha, R, od, n)
        except Exception as e:
            messagebox.showerror("生成失败", str(e))
            return
        # 确保表格行数与 N 一致
        self._rebuild_piece_rows()
        for (kind_var, long_var, short_var), pi in zip(self._piece_widgets, pieces):
            kind_var.set(pi.kind)
            long_var.set(f"{pi.long_od:.1f}")
            short_var.set(f"{pi.short_od:.1f}")

    def _read_pieces(self):
        from .models import PieceInput
        outs = []
        for (kind_var, long_var, short_var) in self._piece_widgets:
            k = kind_var.get()
            kind = None if k == "auto" else k
            outs.append(PieceInput(long_od=float(long_var.get()),
                                   short_od=float(short_var.get()), kind=kind))
        return outs

    def on_compute(self) -> None:
        try:
            alpha = float(self.v_alpha.get())
            od = float(self.v_od.get())
            t = float(self.v_t.get())
            theta = float(self.v_theta.get())
            p = float(self.v_p.get())
            g = float(self.v_g.get())
            pieces = self._read_pieces()
            inp = ElbowInput(bend_angle_deg=alpha, od=od, thickness=t, pieces=pieces,
                             bevel_angle_deg=theta, root_face=p, root_gap=g)
            res = compute_elbow(inp)

            outdir = Path(self.v_out.get().strip() or str(Path.home()))
            outdir.mkdir(parents=True, exist_ok=True)
            stem = "elbow"
            rep_path = outdir / f"{stem}_report.txt"
            dxf_path = outdir / f"{stem}_template.dxf"
            rep_path.write_text(build_report(res), encoding="utf-8")
            dxf_path.write_text(generate_dxf(res).to_string(), encoding="ascii")

            self.last_dxf = str(dxf_path)
            self.report_text.delete("1.0", "end")
            self.report_text.insert("end", build_report(res))
            self.status.set(f"已输出 报告: {rep_path.name}  DXF: {dxf_path.name}")
        except Exception as e:
            messagebox.showerror("计算失败", str(e))

    def on_open_cad(self) -> None:
        if not self.last_dxf:
            messagebox.showinfo("提示", "请先点击【计算并输出 DXF】")
            return
        cad = find_cad()
        if not cad:
            messagebox.showwarning("未找到 AutoCAD", "未找到 acad.exe, 请确认已安装 AutoCAD")
            return
        try:
            launch_cad(self.last_dxf)
            self.status.set(f"已用 AutoCAD 打开:\n{self.last_dxf}")
        except Exception as e:
            messagebox.showerror("打开失败", str(e))

    def _fill_default(self) -> None:
        # 默认 90° 三节, 用设计模式生成 (on_autogen 会调用 generate_pieces_from_design)
        pass


def main() -> None:
    App().mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
