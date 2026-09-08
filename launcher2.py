"""PyInstaller 入口：启动弯头放样工具 V2 GUI。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elbow_layout.gui2 import main  # noqa: E402

if __name__ == "__main__":
    main()
