# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

默认生成单文件 dist/main.exe；设置环境变量 VILLINK_ONEFILE=0
（或运行 build.bat onedir）生成启动更快的文件夹版 dist/main/main.exe。
"""

import os

ONEFILE = os.environ.get("VILLINK_ONEFILE", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    # 窗口图标；窗口内也会通过 utils/resources.py 读取同一文件
    datas=[("assets/icon.ico", "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Excel 读取已改用 openpyxl，这两个大依赖不再需要
        "pandas",
        "numpy",
        # 明确排除常见的重型可选依赖，避免被间接拖入
        "matplotlib",
        "scipy",
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        # 项目只处理 JPG/PNG 等常见格式，不需要 AVIF/FPX/MIC 解码器
        "PIL.AvifImagePlugin",
        "PIL.FpxImagePlugin",
        "PIL.MicImagePlugin",
        # python-docx 只用到 lxml.etree，HTML/objectify 等子模块不需要
        "lxml.html",
        "lxml.objectify",
        "lxml.isoschematron",
        "lxml.cssselect",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe_options = dict(
    name="main",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **exe_options)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **exe_options)
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="main",
    )
