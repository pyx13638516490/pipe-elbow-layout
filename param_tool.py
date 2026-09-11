# -*- coding: utf-8 -*-
"""参数影响小工具: 拖动直径 D 和切入角 φ, 实时看展开正弦曲线怎么变。

正弦公式:  z(u) = A·cos(2πu / (πD)) ,  A=(D/2)·tanφ ,  u∈[0, πD]
"""
import math
import tkinter as tk
from tkinter import ttk


class ParamTool(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("正弦曲线参数影响工具   z(u)=A·cos(2πu/πD),  A=(D/2)·tanφ")
        self.geometry("960x660")
        self.minsize(780, 560)

        self.vD = tk.DoubleVar(value=3220.0)
        self.vphi = tk.DoubleVar(value=11.25)
        self.vexag = tk.DoubleVar(value=6.0)

        ctrl = ttk.LabelFrame(self, text="参数")
        ctrl.pack(fill="x", padx=10, pady=(8, 4))

        # 直径
        ttk.Label(ctrl, text="管外径 D (mm)").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        sD = ttk.Scale(ctrl, from_=100, to=6000, variable=self.vD,
                       command=lambda _e: self.redraw(), length=420)
        sD.grid(row=0, column=1, sticky="w")
        self.lblD = ttk.Label(ctrl, text="3220", width=8)
        self.lblD.grid(row=0, column=2, sticky="w")
        # 切入角
        ttk.Label(ctrl, text="切入角 φ (°)").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        sP = ttk.Scale(ctrl, from_=0.5, to=45, variable=self.vphi,
                       command=lambda _e: self.redraw(), length=420)
        sP.grid(row=1, column=1, sticky="w")
        self.lblP = ttk.Label(ctrl, text="11.25", width=8)
        self.lblP.grid(row=1, column=2, sticky="w")
        # 纵向放大(仅显示用)
        ttk.Label(ctrl, text="纵向放大(仅显示)").grid(row=2, column=0, sticky="e", padx=4, pady=3)
        sE = ttk.Scale(ctrl, from_=1, to=40, variable=self.vexag,
                       command=lambda _e: self.redraw(), length=420)
        sE.grid(row=2, column=1, sticky="w")
        self.lblE = ttk.Label(ctrl, text="6", width=8)
        self.lblE.grid(row=2, column=2, sticky="w")

        self.cv = tk.Canvas(self, bg="white", highlightthickness=1, highlightbackground="#ccc")
        self.cv.pack(fill="both", expand=True, padx=10, pady=6)
        self.cv.bind("<Configure>", lambda _e: self.redraw())

        self.info = ttk.Label(self, text="", foreground="#004", justify="left")
        self.info.pack(fill="x", padx=12, pady=(0, 4))
        ttk.Label(self, text="tanφ = 轴向上升 / 径向距离;  A=(D/2)·tanφ = 振幅;  波长(展开宽)=πD;  "
                             "长-短差(单切口)=D·tanφ。  D 只改变大小(形状不变), φ 改变陡峭度(宽度不变)。",
                  foreground="#666", wraplength=920, justify="left").pack(fill="x", padx=12, pady=(0, 8))
        self.redraw()

    def redraw(self):
        cv = self.cv
        cv.delete("all")
        D = float(self.vD.get())
        phi = float(self.vphi.get())
        exag = float(self.vexag.get())
        tphi = math.tan(math.radians(phi))
        A = (D / 2.0) * tphi
        circ = math.pi * D

        self.lblD.config(text="%.0f" % D)
        self.lblP.config(text="%.2f" % phi)
        self.lblE.config(text="%.0f" % exag)

        w = max(cv.winfo_width(), 300)
        h = max(cv.winfo_height(), 200)
        m = 60
        sx = (w - 2 * m) / circ            # 横向: 周长铺满
        sz = sx * exag                      # 纵向: 同比例 × 放大
        cy = h / 2.0

        def X(u): return m + u * sx
        def Y(z): return cy - z * sz

        # 中线
        cv.create_line(m, cy, w - m, cy, fill="#c8c8c8", dash=(6, 4))
        # 正弦曲线 z(u)=A cos(2pi u/circ)
        pts = []
        for i in range(361):
            u = circ * i / 360.0
            z = A * math.cos(2 * math.pi * u / circ)
            pts.extend([X(u), Y(z)])
        cv.create_line(*pts, fill="#d00000", width=2, smooth=True)
        # 长边(u=0) 与 短边(u=πD/2) 竖线
        cv.create_line(X(0), Y(A), X(0), Y(-A), fill="#06c", width=1)
        cv.create_line(X(circ / 2), Y(-A), X(circ / 2), Y(A), fill="#06c", width=1)
        cv.create_line(X(circ), Y(A), X(circ), Y(-A), fill="#06c", width=1)
        cv.create_text(X(0) + 6, Y(A) - 12, text="长边 z0+A", fill="#06c", anchor="w")
        cv.create_text(X(circ / 2), Y(-A) + 12, text="短边 z0-A", fill="#06c", anchor="n")
        # 宽度标注
        cv.create_line(m, h - 24, w - m, h - 24, fill="#666")
        cv.create_text(w / 2, h - 12, text="展开宽度 = πD = %.1f mm" % circ, fill="#666")
        # 公式
        cv.create_text(m + 6, 16, anchor="w", fill="#000",
                       text="z(u) = A·cos(2πu/πD),  A=(D/2)tanφ")

        self.info.config(text=(
            "D=%.0f mm   φ=%.3f°   tanφ=%.4f\n"
            "振幅 A=(D/2)·tanφ = %.2f mm    波长(πD) = %.1f mm\n"
            "长-短差(单切口)= D·tanφ = %.2f mm    形状比 A/πD = tanφ/(2π) = %.5f"
            % (D, phi, tphi, A, circ, D * tphi, A / circ)))


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    ParamTool(root)
    root.mainloop()
