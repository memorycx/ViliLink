"""一键打包脚本（供 build.bat 调用，也可直接 python tools/build.py）。

用法：
    python tools/build.py            # 单文件 dist/main.exe
    python tools/build.py onedir     # 文件夹版 dist/main/main.exe（启动更快）

只安装 requirements-build.txt 中声明的运行时依赖 + PyInstaller，
不会把系统 Python 里的其他包带进 exe。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
if os.name == "nt":
    VENV_PYTHON = VENV / "Scripts" / "python.exe"
else:
    VENV_PYTHON = VENV / "bin" / "python"


def run(args: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(str(item) for item in args), flush=True)
    subprocess.run(args, cwd=ROOT, env=env, check=True)


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "onefile").strip().lower()
    if mode not in {"onefile", "onedir"}:
        print("用法: python tools/build.py [onefile|onedir]")
        return 2

    if not VENV_PYTHON.is_file():
        print("[1/5] 创建虚拟环境 .venv ...")
        run([sys.executable, "-m", "venv", str(VENV)])
    else:
        print("[1/5] 使用现有虚拟环境 .venv")

    print("[2/5] 安装打包依赖 ...")
    run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(VENV_PYTHON), "-m", "pip", "install", "-r", "requirements-build.txt"])

    print("[3/5] 生成图标 ...")
    run([str(VENV_PYTHON), "tools/make_icon.py"])

    print(f"[4/5] 打包（{mode}）...")
    env = os.environ.copy()
    env["VILLINK_ONEFILE"] = "1" if mode == "onefile" else "0"
    run(
        [str(VENV_PYTHON), "-m", "PyInstaller", "main.spec", "--noconfirm", "--clean"],
        env=env,
    )

    print("[5/5] 复制运行所需的外部文件 ...")
    out_dir = ROOT / "dist" if mode == "onefile" else ROOT / "dist" / "main"
    out_dir.mkdir(parents=True, exist_ok=True)

    facility_file = ROOT / "编号集合.xlsx"
    if facility_file.is_file():
        shutil.copy2(facility_file, out_dir / facility_file.name)

    shutil.copy2(ROOT / ".env.example", out_dir / ".env.example")

    env_file = ROOT / ".env"
    if env_file.is_file():
        shutil.copy2(env_file, out_dir / ".env")

    print(f"\n打包完成：{out_dir / 'main.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
