# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

HERE = Path(SPECPATH)
sys.path.insert(0, str(HERE.parent))
from figspec_designer import __version__

a = Analysis(
    [str(HERE.parent / "figspec_designer" / "app.py")],
    pathex=[str(HERE.parent), str(HERE.parent.parent)],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, exclude_binaries=True, name="FigSpec Designer",
          console=False, target_arch="arm64")
coll = COLLECT(exe, a.binaries, a.datas, name="FigSpec Designer")
app = BUNDLE(
    coll,
    name="FigSpec Designer.app",
    icon=str(HERE / "assets" / "AppIcon.icns"),
    bundle_identifier="com.github.sebdeng.figspec-designer",
    version=__version__,
    info_plist={"NSHighResolutionCapable": True,
                "LSMinimumSystemVersion": "12.0"},
)
