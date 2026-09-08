"""PyInstaller 入口：启动弯头放样 GUI。

正常运行时把包父目录(项目所在盘)加入 sys.path，便于 `python launcher.py`。
用 PyInstaller 打包时需加 `--paths 项目父目录`。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elbow_layout.gui import main  # noqa: E402

if __name__ == "__main__":
    main()
