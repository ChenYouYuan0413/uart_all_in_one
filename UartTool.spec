# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\race_save\\RoboMaste\\rm_vision_cyy\\uart_all_in_one\\project_files\\tools\\qt_json_editor.py'],
    pathex=[],
    binaries=[],
    datas=[('E:\\race_save\\RoboMaste\\rm_vision_cyy\\uart_all_in_one\\project_files\\examples', 'project_files/examples'), ('E:\\race_save\\RoboMaste\\rm_vision_cyy\\uart_all_in_one\\project_files\\examples', 'examples'), ('E:\\race_save\\RoboMaste\\rm_vision_cyy\\uart_all_in_one\\project_files\\tools\\modules', 'tools/modules'), ('E:\\race_save\\RoboMaste\\rm_vision_cyy\\uart_all_in_one\\project_files\\tools\\logo', 'tools/logo'), ('E:\\race_save\\RoboMaste\\rm_vision_cyy\\uart_all_in_one\\project_files\\config.json', 'project_files/config.json')],
    hiddenimports=['PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'serial', 'serial.tools.list_ports', 'matplotlib', 'matplotlib.backends', 'matplotlib.backends.backend_qt5agg', 'numpy', 'modules.oscilloscope', 'modules.terminal', 'modules.protocol_window', 'modules.theme_utils', 'logging', 'json', 'functools'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='UartTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
