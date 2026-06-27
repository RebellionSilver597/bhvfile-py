"""BHV Editor - 一键启动脚本
后端：FastAPI (port 8000)
前端：内置在 backend，自动加载 frontend/index.html

使用方法：
    python run.py
    然后浏览器打开 http://127.0.0.1:8000
"""

import os
import sys
import subprocess


def main():
    # Go to the project root
    root = os.path.dirname(os.path.abspath(__file__))
    backend = os.path.join(root, "backend")

    # Add backend to path
    sys.path.insert(0, backend)

    print("=" * 60)
    print("  BHV Editor - Python Edition")
    print("  浏览器打开: http://127.0.0.1:8000")
    print("=" * 60)

    import uvicorn
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[backend],
    )


if __name__ == "__main__":
    main()
