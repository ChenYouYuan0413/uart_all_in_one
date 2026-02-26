#!/usr/bin/env python3
"""
打包工具 - 将串口通信工具打包成可执行文件
支持 Windows 和 Linux 平台
"""

import os
import sys
import subprocess
import shutil

# 项目根目录 (build.py 在 project_files/tools/ 下，需要往上两级)
BUILD_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# build.py 在 tools 目录下，需要往上一级到 project_files，再往上一级到根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(BUILD_SCRIPT_DIR))

# 主程序入口
MAIN_SCRIPT = os.path.join(BUILD_SCRIPT_DIR, 'qt_json_editor.py')

# 输出目录
DIST_DIR = os.path.join(PROJECT_ROOT, 'dist')
BUILD_DIR = os.path.join(PROJECT_ROOT, 'build')

# 示例文件目录
EXAMPLES_DIR = os.path.join(PROJECT_ROOT, 'project_files', 'examples')

# Modules 目录
MODULES_DIR = os.path.join(BUILD_SCRIPT_DIR, 'modules')

# Logo 目录
LOGO_DIR = os.path.join(BUILD_SCRIPT_DIR, 'logo')

# Config 文件
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'project_files', 'config.json')


def check_dependencies():
    """检查必要的依赖"""
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("Error: PyInstaller not installed.")
        print("Please install: pip install pyinstaller")
        return False
    return True


def clean_build():
    """清理之前的构建文件"""
    print("Cleaning previous build files...")

    # 清理 dist 和 build 目录
    for dir_path in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            print(f"  Removed: {dir_path}")


def build_exe(platform=None):
    """构建可执行文件"""

    # 平台特定的路径分隔符
    sep = ';' if sys.platform == 'win32' else ':'

    # PyInstaller 命令
    cmd = [
        'pyinstaller',
        '--onefile',          # 打包成单个文件
        '--windowed',         # Windows 下不显示控制台
        '--name=UartTool',    # 输出文件名
        f'--add-data={EXAMPLES_DIR}{sep}project_files/examples',  # 添加示例文件
        f'--add-data={EXAMPLES_DIR}{sep}examples',  # 添加示例文件到根目录
        f'--add-data={MODULES_DIR}{sep}tools/modules',  # 添加 modules 目录
        f'--add-data={LOGO_DIR}{sep}tools/logo',  # 添加 logo 目录
        f'--add-data={CONFIG_FILE}{sep}project_files/config.json',  # 添加配置文件
        '--hidden-import=PyQt5',
        '--hidden-import=PyQt5.QtCore',
        '--hidden-import=PyQt5.QtGui',
        '--hidden-import=PyQt5.QtWidgets',
        '--hidden-import=serial',
        '--hidden-import=serial.tools.list_ports',
        '--hidden-import=matplotlib',
        '--hidden-import=matplotlib.backends',
        '--hidden-import=matplotlib.backends.backend_qt5agg',
        '--hidden-import=numpy',
        '--hidden-import=modules.oscilloscope',
        '--hidden-import=modules.terminal',
        '--hidden-import=modules.protocol_window',
        '--hidden-import=modules.theme_utils',
        '--hidden-import=logging',
        '--hidden-import=json',
        '--hidden-import=functools',
    ]

    # 添加图标（如果存在）
    icon_path = os.path.join(BUILD_SCRIPT_DIR, 'app_icon.ico')
    if os.path.exists(icon_path):
        cmd.append(f'--icon={icon_path}')

    # 添加主程序
    cmd.append(MAIN_SCRIPT)

    print(f"Building {'Windows' if platform == 'win' else 'Linux'} executable...")
    print(f"Command: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
        print("\nBuild completed successfully!")
        print(f"Output: {os.path.join(DIST_DIR, 'UartTool.exe' if sys.platform == 'win32' else 'UartTool')}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        return False


def build_linux():
    """构建 Linux 可执行文件（在 Linux 系统上）"""
    if sys.platform != 'linux' and sys.platform != 'darwin':
        print("Error: Linux build only supported on Linux/macOS")
        return False

    return build_exe('linux')


def build_windows():
    """构建 Windows 可执行文件"""
    return build_exe('win')


def main():
    """主函数"""
    print("=" * 50)
    print("串口通信工具 - 打包工具")
    print("=" * 50)

    # 检查依赖
    if not check_dependencies():
        return 1

    # 解析命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == 'clean':
            clean_build()
            return 0
        elif sys.argv[1] == 'linux':
            return 0 if build_linux() else 1
        elif sys.argv[1] == 'win' or sys.argv[1] == 'windows':
            return 0 if build_windows() else 1

    # 默认：清理并构建
    clean_build()
    result = build_windows() if sys.platform == 'win32' else build_linux()

    print("\n" + "=" * 50)
    print("Usage:")
    print("  python build.py           - Build for current platform")
    print("  python build.py win      - Build for Windows")
    print("  python build.py linux    - Build for Linux")
    print("  python build.py clean   - Clean build files")
    print("=" * 50)

    return 0 if result else 1


if __name__ == '__main__':
    sys.exit(main())
