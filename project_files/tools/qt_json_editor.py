#!/usr/bin/env python3
# 简单的 PyQt5 JSON 可视化编辑器，用于编辑 struct_definition.json

import sys
import os
import json
from functools import partial
import subprocess
import shutil
import logging
import traceback

# 简单日志配置，输出到 stderr
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
log = logging.getLogger('qt_json_editor')

try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
        QTableWidget, QTableWidgetItem, QPushButton, QComboBox, QSpinBox, QFileDialog, QMessageBox, QCheckBox, QSizePolicy,
        QTabWidget, QTextEdit, QGroupBox, QGridLayout, QButtonGroup, QRadioButton, QToolBar, QScrollArea, QDialog, QListWidget, QAbstractItemView, QHeaderView,
        QSplitter
    )
    from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
    from PyQt5.QtGui import QPalette, QColor, QBrush, QPixmap, QFont, QDoubleValidator
except Exception:
    print('请安装 PyQt5: pip install PyQt5')
    raise

# 尝试导入 matplotlib
try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print('请安装 matplotlib 和 numpy: pip install matplotlib numpy')

# 导入模块类
from modules import OscilloWindow, TerminalWindow, ProtocolWindow

TYPES = ['int', 'uint8', 'uint16', 'int8', 'int16', 'float', 'char', 'bool']


def default_json_path():
    """默认JSON文件路径 - 支持开发和打包后的exe"""
    base = get_app_dir()
    return os.path.join(base, 'examples', 'struct_definition.json')


def config_file_path():
    """配置文件路径 - 支持开发和打包后的exe"""
    # 获取应用程序所在目录
    if getattr(sys, 'frozen', False):
        # 打包后的exe，使用exe所在目录
        base = os.path.dirname(sys.executable)
    else:
        # 开发环境，使用脚本所在目录的上一级
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(base, 'config.json')


def get_app_dir():
    """获取应用程序所在目录"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def get_resource_path(relative_path):
    """获取资源文件的正确路径，支持开发和打包后的exe"""
    if getattr(sys, 'frozen', False):
        # 打包后的exe，从exe所在目录获取
        base_path = os.path.dirname(sys.executable)
        resource_path = os.path.join(base_path, relative_path)
        if os.path.exists(resource_path):
            return resource_path
        # 尝试从临时解压目录获取
        if hasattr(sys, '_MEIPASS'):
            meipass_path = os.path.join(sys._MEIPASS, relative_path)
            if os.path.exists(meipass_path):
                return meipass_path
        return resource_path
    else:
        # 开发环境，从脚本所在目录获取
        return os.path.join(os.path.dirname(__file__), relative_path)


class JsonEditor(QMainWindow):
    def __init__(self, json_path=None):
        super().__init__()
        self.setWindowTitle('Struct JSON 编辑器')
        self.json_path = json_path or default_json_path()
        self.data = None
        self.loading_config = True  # 配置加载标志，初始为True防止误触发
        log.debug('JsonEditor.__init__ start; json_path=%s', self.json_path)
        self.init_ui()
        self.load_json(self.json_path)

        # 加载配置
        self.load_config()
        self.loading_config = False  # 加载完成后设为False，允许保存

        # 强制刷新一次完整的主题（调用完整链）
        # 注意：使用已加载的主题，而不是 theme_cb 的当前值（可能是默认的暗色主题）
        if hasattr(self, 'loaded_theme'):
            self.on_theme_changed(self.loaded_theme)

        log.debug('JsonEditor.__init__ done')

    def load_config(self):
        """加载配置"""
        config_path = config_file_path()
        if not os.path.exists(config_path):
            self.loaded_theme = '暗色主题'  # 默认主题
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 恢复窗口位置和大小
            if 'window_geometry' in config:
                geom = config['window_geometry']
                self.setGeometry(geom[0], geom[1], geom[2], geom[3])

            # 恢复主题
            if 'theme' in config:
                theme = config['theme']
                self.loaded_theme = theme  # 保存加载的主题供后续使用
                if hasattr(self, 'theme_cb'):
                    self.theme_cb.blockSignals(True)
                    self.theme_cb.setCurrentText(theme)
                    self.theme_cb.blockSignals(False)
                    self.on_theme_changed(theme)
            else:
                self.loaded_theme = '暗色主题'  # 默认主题

            # 恢复串口配置
            if 'serial_port' in config and hasattr(self, 'serial_port_cb'):
                # 先刷新串口列表
                self.refresh_ports()
                # 尝试选择上次使用的串口
                saved_port = config['serial_port']
                if self.serial_port_cb.findText(saved_port) >= 0:
                    self.serial_port_cb.blockSignals(True)
                    self.serial_port_cb.setCurrentText(saved_port)
                    self.serial_port_cb.blockSignals(False)

            if 'baudrate' in config and hasattr(self, 'baudrate_cb'):
                self.baudrate_cb.blockSignals(True)
                self.baudrate_cb.setCurrentText(str(config['baudrate']))
                self.baudrate_cb.blockSignals(False)
            if 'databits' in config and hasattr(self, 'databits_cb'):
                self.databits_cb.blockSignals(True)
                self.databits_cb.setCurrentText(str(config['databits']))
                self.databits_cb.blockSignals(False)
            if 'stopbits' in config and hasattr(self, 'stopbits_cb'):
                self.stopbits_cb.blockSignals(True)
                self.stopbits_cb.setCurrentText(str(config['stopbits']))
                self.stopbits_cb.blockSignals(False)
            if 'parity' in config and hasattr(self, 'parity_cb'):
                self.parity_cb.blockSignals(True)
                self.parity_cb.setCurrentText(config['parity'])
                self.parity_cb.blockSignals(False)
            if 'encoding' in config and hasattr(self, 'encoding_cb'):
                self.encoding_cb.blockSignals(True)
                self.encoding_cb.setCurrentText(config['encoding'])
                self.encoding_cb.blockSignals(False)
            if 'send_encoding' in config and hasattr(self, 'send_encoding_cb'):
                self.send_encoding_cb.blockSignals(True)
                self.send_encoding_cb.setCurrentText(config['send_encoding'])
                self.send_encoding_cb.blockSignals(False)

            # 恢复发送/接收模式
            if 'send_mode' in config:
                if config['send_mode'] == 'HEX' and hasattr(self, 'rb_hex_send'):
                    self.rb_hex_send.blockSignals(True)
                    self.rb_hex_send.setChecked(True)
                    self.rb_hex_send.blockSignals(False)
                elif hasattr(self, 'rb_ascii_send'):
                    self.rb_ascii_send.blockSignals(True)
                    self.rb_ascii_send.setChecked(True)
                    self.rb_ascii_send.blockSignals(False)
            if 'recv_mode' in config:
                if config['recv_mode'] == 'HEX' and hasattr(self, 'rb_hex_recv'):
                    self.rb_hex_recv.blockSignals(True)
                    self.rb_hex_recv.setChecked(True)
                    self.rb_hex_recv.blockSignals(False)
                elif hasattr(self, 'rb_ascii_recv'):
                    self.rb_ascii_recv.blockSignals(True)
                    self.rb_ascii_recv.setChecked(True)
                    self.rb_ascii_recv.blockSignals(False)

            # 恢复自动滚屏和解析
            if 'auto_scroll' in config and hasattr(self, 'chk_auto_scroll'):
                self.chk_auto_scroll.blockSignals(True)
                self.chk_auto_scroll.setChecked(config['auto_scroll'])
                self.chk_auto_scroll.blockSignals(False)
            if 'auto_parse' in config and hasattr(self, 'chk_auto_parse'):
                self.chk_auto_parse.blockSignals(True)
                self.chk_auto_parse.setChecked(config['auto_parse'])
                self.chk_auto_parse.blockSignals(False)

            # 恢复显示模块设置
            if hasattr(self, 'chk_show_config'):
                # 直接设置group的可见性
                if hasattr(self, 'serial_config_group'):
                    self.serial_config_group.setVisible(config.get('show_config', True))
                if hasattr(self, 'serial_send_group'):
                    self.serial_send_group.setVisible(config.get('show_send', True))
                if hasattr(self, 'serial_recv_group'):
                    self.serial_recv_group.setVisible(config.get('show_recv', True))
                if hasattr(self, 'serial_terminal_group'):
                    self.serial_terminal_group.setVisible(config.get('show_terminal', False))
                if hasattr(self, 'serial_debug_group'):
                    self.serial_debug_group.setVisible(config.get('show_debug', False))
                if hasattr(self, 'serial_parse_group'):
                    self.serial_parse_group.setVisible(config.get('show_parse', False))
                if hasattr(self, 'serial_oscillo_group'):
                    self.serial_oscillo_group.setVisible(config.get('show_oscillo', False))

                # 然后恢复复选框状态（不触发信号）
                self.chk_show_config.blockSignals(True)
                self.chk_show_config.setChecked(config.get('show_config', True))
                self.chk_show_config.blockSignals(False)

                self.chk_show_send.blockSignals(True)
                self.chk_show_send.setChecked(config.get('show_send', True))
                self.chk_show_send.blockSignals(False)

                self.chk_show_recv.blockSignals(True)
                self.chk_show_recv.setChecked(config.get('show_recv', True))
                self.chk_show_recv.blockSignals(False)

                self.chk_show_terminal.blockSignals(True)
                self.chk_show_terminal.setChecked(config.get('show_terminal', False))
                self.chk_show_terminal.blockSignals(False)

                self.chk_show_debug.blockSignals(True)
                self.chk_show_debug.setChecked(config.get('show_debug', False))
                self.chk_show_debug.blockSignals(False)

                self.chk_show_parse.blockSignals(True)
                self.chk_show_parse.setChecked(config.get('show_parse', False))
                self.chk_show_parse.blockSignals(False)

                self.chk_show_oscillo.blockSignals(True)
                self.chk_show_oscillo.setChecked(config.get('show_oscillo', False))
                self.chk_show_oscillo.blockSignals(False)

            # 恢复已加载的协议列表
            if 'protocols_loaded' in config and hasattr(self, 'load_protocol'):
                saved_protocols = config.get('protocols_loaded', [])
                for proto in saved_protocols:
                    if os.path.exists(proto.get('path', '')):
                        # 重新加载协议文件
                        try:
                            with open(proto['path'], 'r', encoding='utf-8') as f:
                                protocol = json.load(f)
                            if not hasattr(self, 'protocols_loaded'):
                                self.protocols_loaded = []
                            self.protocols_loaded.append({
                                'name': proto.get('name', ''),
                                'path': proto.get('path', ''),
                                'data': protocol
                            })
                            # 更新协议选择下拉框
                            if hasattr(self, 'protocol_cb'):
                                existing = [self.protocol_cb.itemText(i) for i in range(self.protocol_cb.count())]
                                if proto.get('name', '') not in existing:
                                    self.protocol_cb.addItem(proto.get('name', ''))
                            # 如果有调试表格，也更新它
                            if hasattr(self, 'debug_table') and hasattr(self, 'populate_debug_table'):
                                self.populate_debug_table(protocol)
                            log.info('Loaded protocol from config: %s', proto.get('name', ''))
                        except Exception as e:
                            log.warning('Failed to load protocol from config: %s', e)

            # 恢复已加载的调试协议列表
            if 'debug_protocols_loaded' in config and hasattr(self, 'load_debug_protocol'):
                saved_debug_protocols = config.get('debug_protocols_loaded', [])
                for proto in saved_debug_protocols:
                    proto_path = proto.get('path', '')
                    if proto_path and os.path.exists(proto_path):
                        try:
                            with open(proto_path, 'r', encoding='utf-8') as f:
                                protocol = json.load(f)
                            if not hasattr(self, 'debug_protocols'):
                                self.debug_protocols = {}
                            if not hasattr(self, 'debug_protocols_paths'):
                                self.debug_protocols_paths = {}
                            struct_name = protocol.get('structName', proto.get('name', ''))
                            self.debug_protocols[struct_name] = protocol
                            self.debug_protocols_paths[struct_name] = proto_path
                            # 更新调试协议下拉框
                            if hasattr(self, 'debug_protocol_cb'):
                                existing = [self.debug_protocol_cb.itemText(i) for i in range(self.debug_protocol_cb.count())]
                                if struct_name not in existing:
                                    self.debug_protocol_cb.addItem(struct_name)
                            # 填充调试表格
                            if hasattr(self, 'populate_debug_table'):
                                self.populate_debug_table(protocol)
                            log.info('Loaded debug protocol from config: %s', struct_name)
                        except Exception as e:
                            log.warning('Failed to load debug protocol from config: %s', e)

            log.info('Config loaded from %s', config_path)

        except Exception as e:
            log.warning('Failed to load config: %s', e)

    def save_config(self):
        """保存配置"""
        # 如果正在加载配置，不保存
        if getattr(self, 'loading_config', False):
            return

        config_path = config_file_path()

        try:
            config = {
                # 窗口位置和大小
                'window_geometry': [self.x(), self.y(), self.width(), self.height()],
                # 主题
                'theme': self.theme_cb.currentText() if hasattr(self, 'theme_cb') else '暗色',
                # 串口配置
                'serial_port': self.serial_port_cb.currentText() if hasattr(self, 'serial_port_cb') else '',
                'baudrate': self.baudrate_cb.currentText() if hasattr(self, 'baudrate_cb') else '115200',
                'databits': self.databits_cb.currentText() if hasattr(self, 'databits_cb') else '8',
                'stopbits': self.stopbits_cb.currentText() if hasattr(self, 'stopbits_cb') else '1',
                'parity': self.parity_cb.currentText() if hasattr(self, 'parity_cb') else '无',
                'encoding': self.encoding_cb.currentText() if hasattr(self, 'encoding_cb') else 'GBK',
                'send_encoding': self.send_encoding_cb.currentText() if hasattr(self, 'send_encoding_cb') else 'GBK',
                # 发送/接收模式
                'send_mode': 'HEX' if hasattr(self, 'rb_hex_send') and self.rb_hex_send.isChecked() else 'ASCII',
                'recv_mode': 'HEX' if hasattr(self, 'rb_hex_recv') and self.rb_hex_recv.isChecked() else 'ASCII',
                # 自动滚屏和解析
                'auto_scroll': self.chk_auto_scroll.isChecked() if hasattr(self, 'chk_auto_scroll') else True,
                'auto_parse': self.chk_auto_parse.isChecked() if hasattr(self, 'chk_auto_parse') else True,
                # 显示模块设置
                'show_config': self.chk_show_config.isChecked() if hasattr(self, 'chk_show_config') else True,
                'show_send': self.chk_show_send.isChecked() if hasattr(self, 'chk_show_send') else True,
                'show_recv': self.chk_show_recv.isChecked() if hasattr(self, 'chk_show_recv') else True,
                'show_terminal': self.chk_show_terminal.isChecked() if hasattr(self, 'chk_show_terminal') else False,
                'show_debug': self.chk_show_debug.isChecked() if hasattr(self, 'chk_show_debug') else False,
                'show_parse': self.chk_show_parse.isChecked() if hasattr(self, 'chk_show_parse') else False,
                'show_oscillo': self.chk_show_oscillo.isChecked() if hasattr(self, 'chk_show_oscillo') else False,
                # 已加载的协议列表
                'protocols_loaded': getattr(self, 'protocols_loaded', []),
                # 已加载的调试协议列表
                'debug_protocols_loaded': [
                    {'name': name, 'path': getattr(self, 'debug_protocols_paths', {}).get(name, '')}
                    for name in getattr(self, 'debug_protocols', {}).keys()
                ] if hasattr(self, 'debug_protocols') else [],
            }

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            log.info('Config saved to %s', config_path)

        except Exception as e:
            log.warning('Failed to save config: %s', e)

    def moveEvent(self, event):
        """窗口移动时保存位置"""
        self.save_config()
        super().moveEvent(event)

    def resizeEvent(self, event):
        """窗口大小变化时保存"""
        self.save_config()
        super().resizeEvent(event)

    def closeEvent(self, event):
        """窗口关闭时保存配置"""
        self.save_config()
        event.accept()

    def init_ui(self):
        log.debug('init_ui start')

        # 创建TabWidget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 创建结构体配置标签页
        self.create_struct_tab()

        # 创建串口调试标签页
        self.create_serial_tab()

        # 主布局
        v = QVBoxLayout()
        v.addWidget(self.tabs)
        w = QWidget()
        w.setLayout(v)
        self.setCentralWidget(w)

        # 创建工具栏（包含主题切换）
        self.create_toolbar()

        self.resize(900, 600)

    def create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # 主题切换
        toolbar.addWidget(QLabel('  主题:'))
        self.theme_cb = QComboBox()
        self.theme_cb.addItems(['暗色主题', '亮色主题'])
        self.theme_cb.setCurrentText('暗色主题')
        self.theme_cb.currentTextChanged.connect(self.on_theme_changed)
        toolbar.addWidget(self.theme_cb)

        toolbar.addSeparator()

        # 添加 stretches 让按钮靠右
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # 添加 logo（支持开发和打包后的exe），1.5倍大小
        logo_height = 48  # 32 * 1.5 = 48
        logo_paths = [
            get_resource_path(os.path.join('..', 'tools', 'logo', 'qrs_logo.png')),
            get_resource_path(os.path.join('..', 'tools', 'logo', 'yqlogo.jpg'))
        ]
        for logo_path in logo_paths:
            if os.path.exists(logo_path):
                try:
                    pix = QPixmap(logo_path)
                    if not pix.isNull():
                        # 按高度比例缩放
                        scale = logo_height / pix.height() if pix.height() > 0 else 1
                        new_width = int(pix.width() * scale)
                        scaled_pix = pix.scaled(new_width, logo_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        logo_label = QLabel()
                        logo_label.setPixmap(scaled_pix)
                        logo_label.setFixedSize(scaled_pix.size())
                        logo_label.setAlignment(Qt.AlignCenter)
                        toolbar.addWidget(logo_label)
                except Exception:
                    pass

    def create_struct_tab(self):
        """创建结构体配置标签页"""
        v = QVBoxLayout()

        # 发送/接收语言选择
        hlangs = QHBoxLayout()
        hlangs.addWidget(QLabel('发送语言:'))
        self.send_lang_cb = QComboBox()
        self.send_lang_cb.addItems(['python', 'c', 'cpp'])
        self.send_lang_cb.setCurrentText('python')
        hlangs.addWidget(self.send_lang_cb)
        hlangs.addWidget(QLabel('接收语言:'))
        self.recv_lang_cb = QComboBox()
        self.recv_lang_cb.addItems(['python', 'c', 'cpp'])
        self.recv_lang_cb.setCurrentText('python')
        hlangs.addWidget(self.recv_lang_cb)
        self.chk_sync = QCheckBox('接收同发送')
        self.chk_sync.setChecked(True)
        self.chk_sync.stateChanged.connect(self.on_sync_changed)
        hlangs.addWidget(self.chk_sync)
        v.addLayout(hlangs)

        # 文件选择与保存行
        hfile = QHBoxLayout()
        self.path_edit = QLineEdit(self.json_path)
        btn_browse = QPushButton('打开文件')
        btn_browse.clicked.connect(self.browse_file)
        btn_reload = QPushButton('重新加载')
        btn_reload.clicked.connect(self.on_reload)
        btn_save = QPushButton('保存')
        btn_save.clicked.connect(self.on_save)
        hfile.addWidget(QLabel('JSON:'))
        hfile.addWidget(self.path_edit)
        hfile.addWidget(btn_browse)
        hfile.addWidget(btn_reload)
        hfile.addWidget(btn_save)
        v.addLayout(hfile)

        # structName
        hname = QHBoxLayout()
        hname.addWidget(QLabel('structName:'))
        self.struct_name = QLineEdit()
        hname.addWidget(self.struct_name)
        v.addLayout(hname)

        # 包头/包尾 配置
        hhf = QHBoxLayout()
        self.chk_hf = QCheckBox('启用包头/包尾')
        self.chk_hf.stateChanged.connect(self.on_toggle_hf)
        hhf.addWidget(self.chk_hf)
        hhf.addWidget(QLabel('Header:'))
        self.edit_header = QLineEdit('0xAA')
        self.edit_header.setFixedWidth(80)
        hhf.addWidget(self.edit_header)
        hhf.addWidget(QLabel('Header字节数:'))
        self.spin_header_len = QSpinBox()
        self.spin_header_len.setRange(1, 8)
        self.spin_header_len.setValue(1)
        self.spin_header_len.setFixedWidth(60)
        hhf.addWidget(self.spin_header_len)
        hhf.addWidget(QLabel('Footer字节数:'))
        self.spin_footer_len = QSpinBox()
        self.spin_footer_len.setRange(1, 8)
        self.spin_footer_len.setValue(1)
        self.spin_footer_len.setFixedWidth(60)
        hhf.addWidget(self.spin_footer_len)
        hhf.addStretch()
        self.chk_data_len = QCheckBox('包含data_len')
        self.chk_data_len.setChecked(True)
        hhf.addWidget(self.chk_data_len)
        hhf.addStretch()
        hhf.addWidget(QLabel('Footer:'))
        self.edit_footer = QLineEdit('0x55')
        self.edit_footer.setFixedWidth(80)
        hhf.addWidget(self.edit_footer)
        v.addLayout(hhf)

        # 表格：字段
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['name', 'type', 'length'])
        self.table.horizontalHeader().setStretchLastSection(True)
        # 使表格背景透明且禁用交替行高亮
        try:
            self.table.setStyleSheet('background: transparent;')
            self.table.setAttribute(Qt.WA_TranslucentBackground, True)
            self.table.viewport().setAttribute(Qt.WA_TranslucentBackground, True)
            self.table.setAlternatingRowColors(False)
        except Exception:
            pass
        v.addWidget(self.table)

        # 按钮：添加/删除/插入
        hbtn = QHBoxLayout()
        btn_add = QPushButton('添加字段')
        btn_add.clicked.connect(self.add_field)
        btn_remove = QPushButton('删除选中')
        btn_remove.clicked.connect(self.remove_selected)
        btn_insert = QPushButton('插入字段')
        btn_insert.clicked.connect(self.insert_field)
        hbtn.addWidget(btn_add)
        hbtn.addWidget(btn_insert)
        hbtn.addWidget(btn_remove)
        # 生成代码按钮
        btn_gen = QPushButton('生成代码')
        btn_gen.clicked.connect(self.on_generate)
        hbtn.addWidget(btn_gen)
        v.addLayout(hbtn)

        # 校验方式选择
        hverify = QHBoxLayout()
        hverify.addWidget(QLabel('校验方式:'))
        self.verify_type_cb = QComboBox()
        self.verify_type_cb.addItems(['无校验', 'CRC8', 'CRC16', '求和校验(Sum)', '异或校验(XOR)'])
        self.verify_type_cb.setCurrentText('求和校验(Sum)')
        hverify.addWidget(self.verify_type_cb)

        # 字节对齐选项
        hverify.addWidget(QLabel('  字节对齐:'))
        self.align_cb = QComboBox()
        self.align_cb.addItems(['1', '2', '4', '8'])
        self.align_cb.setCurrentText('4')
        hverify.addWidget(self.align_cb)

        hverify.addStretch()
        v.addLayout(hverify)

        # 创建结构体配置标签页（带滚动条）
        struct_widget = QWidget()
        struct_widget.setLayout(v)
        self.scroll_struct = QScrollArea()
        self.scroll_struct.setWidget(struct_widget)
        self.scroll_struct.setWidgetResizable(True)
        self.scroll_struct.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_struct.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tabs.addTab(self.scroll_struct, '结构体配置')

        # 应用深色主题与背景图
        log.debug('calling apply_theme')
        try:
            self.apply_theme()
            log.debug('apply_theme finished')
        except Exception:
            log.exception('apply_theme failed')

    def browse_file(self):
        p, _ = QFileDialog.getOpenFileName(self, '选择 JSON 文件', os.path.dirname(self.json_path), 'JSON Files (*.json)')
        if p:
            self.path_edit.setText(p)
            self.load_json(p)

    def on_reload(self):
        self.load_json(self.path_edit.text())

    def load_json(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
            # remove BOM
            if text.startswith('\ufeff'):
                text = text.lstrip('\ufeff')
            self.data = json.loads(text)
        except Exception as e:
            QMessageBox.critical(self, '加载失败', f'无法加载 JSON: {e}')
            return
        self.json_path = path
        self.path_edit.setText(path)
        # populate
        self.struct_name.setText(self.data.get('structName', ''))
        fields = self.data.get('fields', [])
        self.table.setRowCount(0)
        for fld in fields:
            name = fld.get('name', '')
            typ = fld.get('type', 'int')
            if 'length' in fld:
                length = fld.get('length')
            else:
                # 如果是 char 则默认 32，否则默认 4
                length = 32 if typ == 'char' else 4
            self._append_row(name, typ, length)
        # 处理 header/footer
        header = self.data.get('header', None)
        footer = self.data.get('footer', None)
        header_len = self.data.get('header_len', 1)
        if header is not None and footer is not None:
            self.chk_hf.setChecked(True)
            try:
                self.edit_header.setText(hex(int(header)))
            except Exception:
                self.edit_header.setText(str(header))
            try:
                self.edit_footer.setText(hex(int(footer)))
            except Exception:
                self.edit_footer.setText(str(footer))
            self.spin_header_len.setValue(header_len)
            footer_len = self.data.get('footer_len', 1)
            self.spin_footer_len.setValue(footer_len)
            data_len_enabled = self.data.get('data_len', True)
            self.chk_data_len.setChecked(data_len_enabled)
        else:
            self.chk_hf.setChecked(False)
            self.edit_header.setText('0xAA')
            self.edit_footer.setText('0x55')
            self.spin_header_len.setValue(1)
            self.spin_footer_len.setValue(1)
            self.chk_data_len.setChecked(True)

        # 处理校验方式
        verify_map = {
            'none': '无校验',
            'crc8': 'CRC8',
            'crc16': 'CRC16',
            'sum': '求和校验(Sum)',
            'xor': '异或校验(XOR)'
        }
        verify = self.data.get('verify', 'sum')
        self.verify_type_cb.setCurrentText(verify_map.get(verify, '求和校验(Sum)'))

        # 加载字节对齐
        align = self.data.get('align', 4)
        self.align_cb.setCurrentText(str(align))

        self.on_toggle_hf()

    def _append_row(self, name, typ, length):
        r = self.table.rowCount()
        self.table.insertRow(r)
        # name
        item = QTableWidgetItem(name)
        self.table.setItem(r, 0, item)
        # type combo
        cb = QComboBox()
        cb.addItems(TYPES)
        if typ in TYPES:
            cb.setCurrentText(typ)
        cb.currentTextChanged.connect(partial(self.on_type_changed, r))
        self.table.setCellWidget(r, 1, cb)
        # length spinner
        sp = QSpinBox()
        sp.setRange(1, 1024)
        # 根据类型设置默认值：char 的 length 有意义，默认 32；其他类型默认 4
        if typ == 'char':
            sp.setValue(int(length) if isinstance(length, int) else 32)
        else:
            sp.setValue(int(length) if isinstance(length, int) else 4)
        # length only meaningful for 'char'
        sp.setEnabled(typ == 'char')
        self.table.setCellWidget(r, 2, sp)

    def add_field(self):
        self._append_row('field', 'int', 4)

    def insert_field(self):
        cur = self.table.currentRow()
        if cur < 0:
            self._append_row('field', 'int', 4)
            return
        # insert before cur
        self.table.insertRow(cur)
        # name
        item = QTableWidgetItem('field')
        self.table.setItem(cur, 0, item)
        cb = QComboBox()
        cb.addItems(TYPES)
        cb.setCurrentText('int')
        cb.currentTextChanged.connect(partial(self.on_type_changed, cur))
        self.table.setCellWidget(cur, 1, cb)
        sp = QSpinBox()
        sp.setRange(1, 1024)
        sp.setValue(4)
        sp.setEnabled(False)
        self.table.setCellWidget(cur, 2, sp)

    def remove_selected(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def on_type_changed(self, row, new_type):
        # 根据 type 启用或禁用 length
        w = self.table.cellWidget(row, 2)
        if isinstance(w, QSpinBox):
            w.setEnabled(new_type == 'char')

    def collect_fields(self):
        fields = []
        for r in range(self.table.rowCount()):
            name_item = self.table.item(r, 0)
            name = name_item.text() if name_item else ''
            typ = self.table.cellWidget(r, 1).currentText()
            sp = self.table.cellWidget(r, 2)
            length = sp.value() if isinstance(sp, QSpinBox) else None
            fld = {'name': name, 'type': typ}
            if typ == 'char':
                fld['length'] = int(length)
            fields.append(fld)
        return fields
 
    def on_save(self):
        # 弹出保存对话框让用户选择文件位置
        default_name = self.struct_name.text() if self.struct_name.text() else 'protocol'
        file_path, _ = QFileDialog.getSaveFileName(
            self, '保存协议文件', default_name + '.json', 'JSON Files (*.json);;All Files (*)'
        )
        if not file_path:
            return

        # 确保文件扩展名为 .json
        if not file_path.endswith('.json'):
            file_path += '.json'

        # 更新 json_path
        self.json_path = file_path
        self.path_edit.setText(file_path)
        obj = {'structName': self.struct_name.text(), 'fields': self.collect_fields()}

        # 保存校验方式
        verify_type_map = {
            '无校验': 'none',
            'CRC8': 'crc8',
            'CRC16': 'crc16',
            '求和校验(Sum)': 'sum',
            '异或校验(XOR)': 'xor'
        }
        obj['verify'] = verify_type_map.get(self.verify_type_cb.currentText(), 'sum')

        # 保存字节对齐
        obj['align'] = int(self.align_cb.currentText())

        # 如果启用了包头包尾，则验证并写入 header/footer
        if self.chk_hf.isChecked():
            try:
                def parse_hex(s):
                    s = s.strip()
                    return int(s, 0)
                h = parse_hex(self.edit_header.text())
                f = parse_hex(self.edit_footer.text())
                header_len = self.spin_header_len.value()
                if header_len == 1:
                    if not (0 <= h <= 255):
                        raise ValueError('header 必须在 0-255 范围')
                else:
                    # 多字节header，检查是否在有效范围内
                    max_val = (256 ** header_len) - 1
                    if not (0 <= h <= max_val):
                        raise ValueError(f'{header_len}字节 header 必须在 0-{max_val} 范围')
                footer_len = self.spin_footer_len.value()
                if footer_len == 1:
                    if not (0 <= f <= 255):
                        raise ValueError('footer 必须在 0-255 范围')
                else:
                    max_val = (256 ** footer_len) - 1
                    if not (0 <= f <= max_val):
                        raise ValueError(f'{footer_len}字节 footer 必须在 0-{max_val} 范围')
                data_len_enabled = self.chk_data_len.isChecked()
                obj['header'] = h
                obj['header_len'] = header_len
                obj['footer'] = f
                obj['footer_len'] = footer_len
                obj['data_len'] = data_len_enabled
            except Exception as e:
                QMessageBox.critical(self, '保存失败', f'Header/Footer 值无效: {e}')
                return
        # 保存文件
        try:
            with open(self.json_path, 'w', encoding='utf-8') as fobj:
                json.dump(obj, fobj, ensure_ascii=False, indent=2)
            QMessageBox.information(self, '保存', '保存成功')
        except Exception as e:
            QMessageBox.critical(self, '保存失败', f'无法保存 JSON: {e}')
    def on_sync_changed(self):
        if self.chk_sync.isChecked():
            self.recv_lang_cb.setCurrentText(self.send_lang_cb.currentText())
            self.recv_lang_cb.setEnabled(False)
        else:
            self.recv_lang_cb.setEnabled(True)

    def on_generate(self):
        # 先保存当前 JSON 内容到文件
        if not self.json_path:
            QMessageBox.warning(self, '未指定', '请先选择一个 JSON 文件路径')
            return
        obj = {'structName': self.struct_name.text(), 'fields': self.collect_fields()}

        # 保存校验方式
        verify_type_map = {
            '无校验': 'none',
            'CRC8': 'crc8',
            'CRC16': 'crc16',
            '求和校验(Sum)': 'sum',
            '异或校验(XOR)': 'xor'
        }
        obj['verify'] = verify_type_map.get(self.verify_type_cb.currentText(), 'sum')

        # 保存字节对齐
        obj['align'] = int(self.align_cb.currentText())

        if self.chk_hf.isChecked():
            try:
                def parse_hex(s):
                    s = s.strip()
                    return int(s, 0)
                h = parse_hex(self.edit_header.text())
                f = parse_hex(self.edit_footer.text())
                header_len = self.spin_header_len.value()
                footer_len = self.spin_footer_len.value()
                if header_len == 1:
                    if not (0 <= h <= 255):
                        raise ValueError('header 必须在 0-255 范围')
                else:
                    max_val = (256 ** header_len) - 1
                    if not (0 <= h <= max_val):
                        raise ValueError(f'{header_len}字节 header 必须在 0-{max_val} 范围')
                if footer_len == 1:
                    if not (0 <= f <= 255):
                        raise ValueError('footer 必须在 0-255 范围')
                else:
                    max_val = (256 ** footer_len) - 1
                    if not (0 <= f <= max_val):
                        raise ValueError(f'{footer_len}字节 footer 必须在 0-{max_val} 范围')
                data_len_enabled = self.chk_data_len.isChecked()
                obj['header'] = h
                obj['header_len'] = header_len
                obj['footer'] = f
                obj['footer_len'] = footer_len
                obj['data_len'] = data_len_enabled
            except Exception as e:
                QMessageBox.critical(self, '生成失败', f'Header/Footer 值无效: {e}')
                return
        try:
            with open(self.json_path, 'w', encoding='utf-8') as fobj:
                json.dump(obj, fobj, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, '生成失败', f'无法保存 JSON: {e}')
            return

        # 找到 generator.py - 使用get_app_dir获取基础目录
        app_dir = get_app_dir()
        gen_path = os.path.join(app_dir, 'generator.py')
        if not os.path.exists(gen_path):
            QMessageBox.critical(self, '生成失败', f'未找到生成器: {gen_path}')
            return

        out_dir = os.path.join(os.path.dirname(self.json_path), '..', 'generated')
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)

        send_lang = self.send_lang_cb.currentText()
        recv_lang = self.recv_lang_cb.currentText()

        cmd = [sys.executable, gen_path, self.json_path, '--send-lang', send_lang, '--recv-lang', recv_lang, '--out', out_dir]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                QMessageBox.critical(self, '生成失败', f'生成器返回错误:\n{proc.stderr}')
                return
            QMessageBox.information(self, '生成成功', f'代码已生成到: {out_dir}')
            # 若有可视化打开生成目录
            try:
                if shutil.which('explorer') and os.name == 'nt':
                    subprocess.Popen(['explorer', out_dir])
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, '生成失败', f'调用生成器失败: {e}')

    def on_toggle_hf(self):
        en = self.chk_hf.isChecked()
        self.edit_header.setEnabled(en)
        self.edit_footer.setEnabled(en)

    def apply_theme(self, theme_name='暗色主题'):
        """应用主题设置。"""
        # 统一使用 theme_cb 的文本值
        is_light = (theme_name == '亮色主题')
        self.current_theme = 'light' if is_light else 'dark'

        if is_light:
            # 亮色主题
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(240, 240, 240))
            palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
            palette.setColor(QPalette.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
            palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
            palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
            palette.setColor(QPalette.Text, QColor(0, 0, 0))
            palette.setColor(QPalette.Button, QColor(220, 220, 220))
            palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
            palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
            palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
            self.setPalette(palette)

            style = """
            QWidget { background-color: #f0f0f0; color: #000000; font-family: 'Segoe UI', Arial; }
            QLineEdit, QSpinBox, QComboBox { background-color: #ffffff; border: 1px solid #cccccc; }
            QTableWidget { background: #ffffff; gridline-color: #d0d0d0; }
            QTableWidget::item { background: #ffffff; }
            QPushButton { background-color: #e0e0e0; border: 1px solid #aaa; padding: 4px; color: #000000; }
            QPushButton:hover { background-color: #d0d0d0; }
            QHeaderView::section { background-color: #e0e0e0; padding: 4px; border: 1px solid #ccc; }
            QCheckBox { spacing: 6px; }
            QToolBar { background-color: #e8e8e8; border: none; }
            QTabWidget::pane { border: 1px solid #cccccc; background-color: #f0f0f0; }
            QTabBar::tab { background-color: #e0e0e0; color: #000000; padding: 8px 16px; border: 1px solid #cccccc; border-bottom: none; }
            QTabBar::tab:selected { background-color: #ffffff; border-bottom: 2px solid #0078d4; }
            QTabBar::tab:hover { background-color: #d0d0d0; }
            QGroupBox { border: 1px solid #ccc; margin-top: 10px; }
            QGroupBox::title { color: #000000; }
            QScrollArea { background-color: #f0f0f0; color: #000000; }
            QScrollArea > QWidget { background-color: #f0f0f0; color: #000000; }
            QScrollBar:horizontal { background: #f0f0f0; }
            QScrollBar:vertical { background: #f0f0f0; }
            """
            self.current_theme = 'light'
        else:
            # 暗色主题
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
            palette.setColor(QPalette.Base, QColor(45, 45, 45))
            palette.setColor(QPalette.AlternateBase, QColor(37, 37, 37))
            palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
            palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
            palette.setColor(QPalette.Text, QColor(220, 220, 220))
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
            palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.Highlight, QColor(142, 45, 197))
            palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
            self.setPalette(palette)

            style = """
            QWidget { background-color: #1e1e1e; color: #e0e0e0; font-family: 'Segoe UI', Arial; }
            QLineEdit, QSpinBox, QComboBox { background-color: rgba(45,45,45,200); border: 1px solid #3c3c3c; }
            QTableWidget { background: transparent; gridline-color: rgba(60,60,60,180); }
            QTableWidget::item { background: rgba(0,0,0,0); }
            QPushButton { background-color: #3a3a3a; border: 1px solid #555; padding: 4px; color: #e0e0e0; }
            QPushButton:hover { background-color: #505050; }
            QHeaderView::section { background-color: rgba(45,45,45,200); padding: 4px; border: 1px solid #3c3c3c; }
            QCheckBox { spacing: 6px; }
            QToolBar { background-color: #2d2d2d; border: none; }
            QTabWidget::pane { border: 1px solid #3c3c3c; background-color: #1e1e1e; }
            QTabBar::tab { background-color: #2d2d2d; color: #e0e0e0; padding: 8px 16px; border: 1px solid #3c3c3c; border-bottom: none; }
            QTabBar::tab:selected { background-color: #3a3a3a; border-bottom: 2px solid #8e45c5; }
            QTabBar::tab:hover { background-color: #404040; }
            QGroupBox { border: 1px solid #555; margin-top: 10px; }
            QGroupBox::title { color: #e0e0e0; }
            QScrollArea { background-color: #1e1e1e; color: #e0e0e0; }
            QScrollArea > QWidget { background-color: #1e1e1e; color: #e0e0e0; }
            QScrollBar:horizontal { background: #2d2d2d; }
            QScrollBar:vertical { background: #2d2d2d; }
            """
            self.current_theme = 'dark'

        self.setStyleSheet(style)

        # 设置 tabs 和标签页内容的背景
        is_light = (theme_name == '亮色主题')
        if hasattr(self, 'tabs'):
            if is_light:
                self.tabs.setStyleSheet("""
                    QTabWidget::pane { border: 1px solid #cccccc; background-color: #f0f0f0; }
                    QTabWidget QWidget { background-color: #f0f0f0; }
                """)
            else:
                self.tabs.setStyleSheet("""
                    QTabWidget::pane { border: 1px solid #3c3c3c; background-color: #1e1e1e; }
                    QTabWidget QWidget { background-color: #1e1e1e; }
                """)

        try:
            self.setAutoFillBackground(True)
            self.setPalette(palette)
        except Exception:
            pass

        # 更新特定控件的样式
        self.update_widgets_theme(theme_name)

        # 更新独立窗口的主题
        self.update_child_windows_theme()

    def update_widgets_theme(self, theme_name):
        """更新子控件的主题样式"""
        # 统一处理 theme_name
        is_dark = (theme_name != '亮色主题')  # 不是亮色主题就是暗色主题

        # 更新滚动区域背景和字体颜色 - 直接设置样式，不追加到全局样式表
        if hasattr(self, 'scroll_struct'):
            if is_dark:
                self.scroll_struct.setStyleSheet("background-color: #1e1e1e; color: #e0e0e0;")
                self.scroll_struct.widget().setStyleSheet("background-color: #1e1e1e; color: #e0e0e0;")
            else:
                self.scroll_struct.setStyleSheet("background-color: #f0f0f0; color: #000000;")
                self.scroll_struct.widget().setStyleSheet("background-color: #f0f0f0; color: #000000;")
        if hasattr(self, 'scroll_serial'):
            if is_dark:
                self.scroll_serial.setStyleSheet("background-color: #1e1e1e; color: #e0e0e0;")
                self.scroll_serial.widget().setStyleSheet("background-color: #1e1e1e; color: #e0e0e0;")
            else:
                self.scroll_serial.setStyleSheet("background-color: #f0f0f0; color: #000000;")
                self.scroll_serial.widget().setStyleSheet("background-color: #f0f0f0; color: #000000;")

        # 更新结构体配置表格
        if hasattr(self, 'table'):
            if is_dark:
                self.table.setStyleSheet('background: transparent; color: #e0e0e0;')
                self.table.viewport().setStyleSheet('background: #2d2d2d;')
            else:
                self.table.setStyleSheet('background: transparent; color: #000000;')
                self.table.viewport().setStyleSheet('background: #ffffff;')

        # 更新接收文本框
        if hasattr(self, 'recv_text'):
            if is_dark:
                self.recv_text.setStyleSheet('QTextEdit { background-color: #1e1e1e; color: #e0e0e0; }')
            else:
                self.recv_text.setStyleSheet('QTextEdit { background-color: #ffffff; color: #000000; }')

        # 更新发送文本框
        if hasattr(self, 'send_text'):
            if is_dark:
                self.send_text.setStyleSheet('QTextEdit { background-color: #2d2d2d; color: #e0e0e0; }')
            else:
                self.send_text.setStyleSheet('QTextEdit { background-color: #ffffff; color: #000000; }')

        # 更新终端显示区
        if hasattr(self, 'terminal_display'):
            if is_dark:
                self.terminal_display.setStyleSheet('QTextEdit { background-color: #0c0c0c; color: #00ff00; }')
            else:
                self.terminal_display.setStyleSheet('QTextEdit { background-color: #ffffff; color: #000000; }')

        # 更新调试表格
        if hasattr(self, 'debug_table'):
            if is_dark:
                self.debug_table.setStyleSheet('QTableWidget { background-color: #2d2d2d; color: #e0e0e0; }')
                self.debug_table.viewport().setStyleSheet('background: #2d2d2d;')
            else:
                self.debug_table.setStyleSheet('QTableWidget { background-color: #ffffff; color: #000000; }')
                self.debug_table.viewport().setStyleSheet('background: #ffffff;')

        # 更新调试发送HEX显示
        if hasattr(self, 'debug_send_hex'):
            if is_dark:
                self.debug_send_hex.setStyleSheet('QTextEdit { background-color: #2d2d2d; color: #00ff00; font-family: monospace; }')
            else:
                self.debug_send_hex.setStyleSheet('QTextEdit { background-color: #ffffff; color: #000000; font-family: monospace; }')

        # 更新提示标签颜色
        if hasattr(self, 'tip_label'):
            if is_dark:
                self.tip_label.setStyleSheet('color: #888; padding: 5px;')
            else:
                self.tip_label.setStyleSheet('color: #666; padding: 5px;')

        # 更新示波器提示标签
        if hasattr(self, 'oscillo_tip'):
            if is_dark:
                self.oscillo_tip.setStyleSheet('color: #888; padding: 10px;')
            else:
                self.oscillo_tip.setStyleSheet('color: #666; padding: 10px;')

        # 更新帧解析表格
        if hasattr(self, 'parse_table'):
            if is_dark:
                self.parse_table.setStyleSheet('QTableWidget { background-color: #2d2d2d; color: #e0e0e0; }')
                self.parse_table.viewport().setStyleSheet('background: #2d2d2d;')
            else:
                self.parse_table.setStyleSheet('QTableWidget { background-color: #ffffff; color: #000000; }')
                self.parse_table.viewport().setStyleSheet('background: #ffffff;')

        # 更新帧解析协议内容
        if hasattr(self, 'protocol_content'):
            if is_dark:
                self.protocol_content.setStyleSheet('QTextEdit { background-color: #2d2d2d; color: #e0e0e0; }')
            else:
                self.protocol_content.setStyleSheet('QTextEdit { background-color: #ffffff; color: #000000; }')

        # 更新帧解析结果
        if hasattr(self, 'parse_result'):
            if is_dark:
                self.parse_result.setStyleSheet('QTextEdit { background-color: #2d2d2d; color: #e0e0e0; }')
            else:
                self.parse_result.setStyleSheet('QTextEdit { background-color: #ffffff; color: #000000; }')

    def update_child_windows_theme(self):
        """更新子窗口的主题"""
        # 使用 theme_cb 的当前值
        theme = self.theme_cb.currentText() if hasattr(self, 'theme_cb') else '暗色主题'

        # 更新示波器窗口
        if hasattr(self, 'oscillo_window') and self.oscillo_window:
            self.oscillo_window.apply_theme(theme)

        # 更新协议窗口
        if hasattr(self, 'protocol_window') and self.protocol_window:
            self.protocol_window.apply_theme(theme)

        # 更新终端窗口
        if hasattr(self, 'terminal_window') and self.terminal_window:
            self.terminal_window.apply_theme(theme)

    def on_theme_changed(self, theme_name):
        """主题切换 - 直接使用 theme_cb 的值"""
        from PyQt5.QtWidgets import QApplication
        self.loaded_theme = theme_name  # 更新当前主题
        self.apply_theme(theme_name)
        self.update_widgets_theme(theme_name)
        # 强制刷新所有子控件以确保样式生效
        QApplication.processEvents()
        self.update()
        self.repaint()
        QApplication.processEvents()
        self.save_config()

    def create_serial_tab(self):
        """创建串口调试标签页"""
        # 尝试导入pyserial
        try:
            import serial
            import serial.tools.list_ports
            self.serial_available = True
        except ImportError:
            self.serial_available = False
            log.warning('pyserial not installed')

        v = QVBoxLayout()

        # 功能开关栏
        toggle_bar = QHBoxLayout()
        toggle_bar.addWidget(QLabel('显示模块:'))

        self.chk_show_config = QCheckBox('串口配置')
        self.chk_show_config.setChecked(True)
        self.chk_show_config.stateChanged.connect(lambda s: (self._toggle_section('config', s), self.save_config()))
        toggle_bar.addWidget(self.chk_show_config)

        self.chk_show_send = QCheckBox('发送')
        self.chk_show_send.setChecked(True)
        self.chk_show_send.stateChanged.connect(lambda s: (self._toggle_section('send', s), self.save_config()))
        toggle_bar.addWidget(self.chk_show_send)

        self.chk_show_recv = QCheckBox('接收')
        self.chk_show_recv.setChecked(True)
        self.chk_show_recv.stateChanged.connect(lambda s: (self._toggle_section('recv', s), self.save_config()))
        toggle_bar.addWidget(self.chk_show_recv)

        self.chk_show_terminal = QCheckBox('终端')
        self.chk_show_terminal.stateChanged.connect(lambda s: (self._toggle_section('terminal', s), self.save_config()))
        toggle_bar.addWidget(self.chk_show_terminal)

        self.chk_show_debug = QCheckBox('协议调试')
        self.chk_show_debug.stateChanged.connect(lambda s: (self._toggle_section('debug', s), self.save_config()))
        toggle_bar.addWidget(self.chk_show_debug)

        self.chk_show_parse = QCheckBox('帧解析')
        self.chk_show_parse.stateChanged.connect(lambda s: (self._toggle_section('parse', s), self.save_config()))
        toggle_bar.addWidget(self.chk_show_parse)

        self.chk_show_oscillo = QCheckBox('示波器')
        self.chk_show_oscillo.stateChanged.connect(lambda s: (self._toggle_section('oscillo', s), self.save_config()))
        toggle_bar.addWidget(self.chk_show_oscillo)

        toggle_bar.addStretch()
        v.addLayout(toggle_bar)

        # 使用 Splitter 让模块可以随意拖动大小
        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setHandleWidth(4)  # 设置分隔条宽度
        self.main_splitter.setChildrenCollapsible(False)  # 不允许折叠
        self.main_splitter.setStretchFactor(0, 0)  # 不自动拉伸
        # 设置分隔条样式
        self.main_splitter.setStyleSheet("QSplitter::handle { background-color: #505050; }")

        # 串口配置区域
        config_group = QGroupBox('串口配置')
        config_grid = QGridLayout()

        # 串口选择
        config_grid.addWidget(QLabel('串口:'), 0, 0)
        self.serial_port_cb = QComboBox()
        self.serial_port_cb.setEditable(True)
        self.serial_port_cb.setCompleter(None)
        self.serial_port_cb.currentTextChanged.connect(
            lambda _: self.save_config() if not getattr(self, 'loading_config', False) else None)
        config_grid.addWidget(self.serial_port_cb, 0, 1)
        self.btn_refresh = QPushButton('刷新')
        self.btn_refresh.clicked.connect(self.refresh_ports)
        config_grid.addWidget(self.btn_refresh, 0, 2)

        # 自定义串口路径输入框（支持Linux设备如 /dev/ttyUSB0）
        self.custom_port_edit = QLineEdit()
        self.custom_port_edit.setPlaceholderText('或输入自定义路径，如 /dev/ttyUSB0')
        self.custom_port_edit.setFixedWidth(200)
        config_grid.addWidget(self.custom_port_edit, 0, 5)

        # 波特率
        config_grid.addWidget(QLabel('波特率:'), 0, 3)
        self.baudrate_cb = QComboBox()
        self.baudrate_cb.addItems(['9600', '19200', '38400', '57600', '115200', '230400', '460800', '921600'])
        self.baudrate_cb.setCurrentText('115200')
        self.baudrate_cb.currentTextChanged.connect(lambda _: self.save_config())
        config_grid.addWidget(self.baudrate_cb, 0, 4)

        # 数据位
        config_grid.addWidget(QLabel('数据位:'), 1, 0)
        self.databits_cb = QComboBox()
        self.databits_cb.addItems(['5', '6', '7', '8'])
        self.databits_cb.setCurrentText('8')
        self.databits_cb.currentTextChanged.connect(lambda _: self.save_config())
        config_grid.addWidget(self.databits_cb, 1, 1)

        # 停止位
        config_grid.addWidget(QLabel('停止位:'), 1, 2)
        self.stopbits_cb = QComboBox()
        self.stopbits_cb.addItems(['1', '1.5', '2'])
        self.stopbits_cb.setCurrentText('1')
        self.stopbits_cb.currentTextChanged.connect(lambda _: self.save_config())
        config_grid.addWidget(self.stopbits_cb, 1, 3)

        # 校验位
        config_grid.addWidget(QLabel('校验位:'), 1, 4)
        self.parity_cb = QComboBox()
        self.parity_cb.addItems(['无', '奇校验', '偶校验'])
        self.parity_cb.setCurrentText('无')
        self.parity_cb.currentTextChanged.connect(lambda _: self.save_config())
        config_grid.addWidget(self.parity_cb, 1, 5)

        # 打开/关闭串口按钮
        self.btn_open_serial = QPushButton('打开串口')
        self.btn_open_serial.clicked.connect(self.toggle_serial)
        config_grid.addWidget(self.btn_open_serial, 0, 6)
        config_grid.addWidget(QLabel(''), 1, 6)

        config_group.setObjectName('config_group')
        config_group.setLayout(config_grid)
        self.serial_config_group = config_group
        self.main_splitter.addWidget(config_group)

        # 发送区域
        send_group = QGroupBox('发送')
        send_v = QVBoxLayout()

        send_mode_h = QHBoxLayout()
        send_mode_h.addWidget(QLabel('模式:'))
        self.send_mode_group = QButtonGroup()
        self.rb_ascii_send = QRadioButton('ASCII')
        self.rb_hex_send = QRadioButton('HEX')
        self.rb_ascii_send.setChecked(True)
        self.rb_ascii_send.toggled.connect(lambda _: self.save_config())
        self.send_mode_group.addButton(self.rb_ascii_send)
        self.send_mode_group.addButton(self.rb_hex_send)
        send_mode_h.addWidget(self.rb_ascii_send)
        send_mode_h.addWidget(self.rb_hex_send)

        # 添加编码选择
        send_mode_h.addWidget(QLabel('  编码:'))
        self.send_encoding_cb = QComboBox()
        self.send_encoding_cb.addItems(['GBK', 'UTF-8', 'GB2312', 'ASCII', 'Latin-1'])
        self.send_encoding_cb.setCurrentText('GBK')
        self.send_encoding_cb.currentTextChanged.connect(lambda _: self.save_config())
        send_mode_h.addWidget(self.send_encoding_cb)

        send_mode_h.addStretch()
        send_v.addLayout(send_mode_h)

        self.send_text = QTextEdit()
        self.send_text.setMinimumHeight(60)
        self.send_text.setMaximumHeight(200)
        self.send_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.send_text.setPlaceholderText('输入要发送的数据...')
        send_v.addWidget(self.send_text)

        send_btn_h = QHBoxLayout()
        self.btn_send = QPushButton('发送')
        self.btn_send.clicked.connect(self.send_data)
        self.btn_send.setEnabled(False)
        send_btn_h.addWidget(self.btn_send)

        self.chk_loop_send = QCheckBox('循环发送')
        self.chk_loop_send.stateChanged.connect(self.on_loop_send_changed)
        send_btn_h.addWidget(self.chk_loop_send)

        send_btn_h.addWidget(QLabel('间隔(ms):'))
        self.loop_interval = QSpinBox()
        self.loop_interval.setRange(10, 10000)
        self.loop_interval.setValue(1000)
        self.loop_interval.setEnabled(False)
        send_btn_h.addWidget(self.loop_interval)

        send_btn_h.addStretch()
        send_btn_h.addWidget(QLabel('发送计数:'))
        self.send_count = QLabel('0')
        send_btn_h.addWidget(self.send_count)

        send_v.addLayout(send_btn_h)
        send_group.setObjectName('send_group')
        send_group.setLayout(send_v)
        self.serial_send_group = send_group
        self.main_splitter.addWidget(send_group)

        # 接收区域
        recv_group = QGroupBox('接收')
        recv_v = QVBoxLayout()

        recv_mode_h = QHBoxLayout()
        recv_mode_h.addWidget(QLabel('模式:'))
        self.recv_mode_group = QButtonGroup()
        self.rb_ascii_recv = QRadioButton('ASCII')
        self.rb_hex_recv = QRadioButton('HEX')
        self.rb_ascii_recv.setChecked(True)
        self.rb_ascii_recv.toggled.connect(lambda _: self.save_config())
        self.recv_mode_group.addButton(self.rb_ascii_recv)
        self.recv_mode_group.addButton(self.rb_hex_recv)
        recv_mode_h.addWidget(self.rb_ascii_recv)
        recv_mode_h.addWidget(self.rb_hex_recv)

        # 添加编码选择
        recv_mode_h.addWidget(QLabel('  编码:'))
        self.encoding_cb = QComboBox()
        self.encoding_cb.addItems(['GBK', 'UTF-8', 'GB2312', 'ASCII', 'Latin-1'])
        self.encoding_cb.setCurrentText('GBK')  # 默认 GBK，兼容中文 Windows
        self.encoding_cb.currentTextChanged.connect(lambda _: self.save_config())
        recv_mode_h.addWidget(self.encoding_cb)

        recv_mode_h.addStretch()
        recv_mode_h.addWidget(QLabel('接收计数:'))
        self.recv_count = QLabel('0')
        recv_mode_h.addWidget(self.recv_count)
        recv_v.addLayout(recv_mode_h)

        self.recv_text = QTextEdit()
        self.recv_text.setReadOnly(True)
        self.recv_text.setMinimumHeight(100)
        self.recv_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        recv_v.addWidget(self.recv_text)

        recv_btn_h = QHBoxLayout()
        self.btn_clear_recv = QPushButton('清空接收')
        self.btn_clear_recv.clicked.connect(self.clear_recv)
        recv_btn_h.addWidget(self.btn_clear_recv)

        self.chk_auto_scroll = QCheckBox('自动滚屏')
        self.chk_auto_scroll.setChecked(True)
        self.chk_auto_scroll.stateChanged.connect(lambda s: self.save_config())
        recv_btn_h.addWidget(self.chk_auto_scroll)

        self.chk_auto_parse = QCheckBox('自动解析')
        self.chk_auto_parse.setChecked(True)
        self.chk_auto_parse.stateChanged.connect(lambda s: self.save_config())
        recv_btn_h.addWidget(self.chk_auto_parse)

        recv_btn_h.addStretch()
        recv_v.addLayout(recv_btn_h)
        recv_group.setObjectName('recv_group')
        recv_group.setLayout(recv_v)
        self.serial_recv_group = recv_group
        self.main_splitter.addWidget(recv_group)

        # 终端模式（类似MobaXterm交互界面）
        terminal_group = QGroupBox('串口终端')
        terminal_v = QVBoxLayout()

        terminal_ctrl_h = QHBoxLayout()
        self.chk_terminal_mode = QCheckBox('启用终端模式')
        self.chk_terminal_mode.setToolTip('启用类似MobaXterm的终端交互界面')
        self.chk_terminal_mode.stateChanged.connect(self.on_terminal_mode_changed)
        terminal_ctrl_h.addWidget(self.chk_terminal_mode)

        terminal_ctrl_h.addWidget(QLabel('提示符:'))
        self.terminal_prompt = QLineEdit('root@localhost:~$ ')
        self.terminal_prompt.setFixedWidth(120)
        terminal_ctrl_h.addWidget(self.terminal_prompt)

        terminal_ctrl_h.addWidget(QLabel('编码:'))
        self.terminal_encoding_cb = QComboBox()
        self.terminal_encoding_cb.addItems(['UTF-8', 'GBK', 'GB2312', 'ASCII', 'Latin-1'])
        self.terminal_encoding_cb.setCurrentText('UTF-8')
        self.terminal_encoding_cb.setFixedWidth(80)
        terminal_ctrl_h.addWidget(self.terminal_encoding_cb)

        # HEX显示选项
        self.chk_terminal_hex = QCheckBox('显示HEX')
        self.chk_terminal_hex.setToolTip('以HEX格式显示原始数据')
        terminal_ctrl_h.addWidget(self.chk_terminal_hex)

        # 本地回显选项
        self.chk_local_echo = QCheckBox('本地回显')
        self.chk_local_echo.setChecked(True)
        self.chk_local_echo.setToolTip('在终端显示发送的命令')
        terminal_ctrl_h.addWidget(self.chk_local_echo)

        # 诊断按钮
        self.btn_diag = QPushButton('诊断')
        self.btn_diag.setToolTip('显示原始数据诊断信息')
        self.btn_diag.clicked.connect(self.run_diagnosis)
        terminal_ctrl_h.addWidget(self.btn_diag)

        # Linux串口配置按钮
        self.btn_stty_config = QPushButton('配置Linux串口')
        self.btn_stty_config.setToolTip('发送stty命令配置Linux串口')
        self.btn_stty_config.clicked.connect(self.config_linux_terminal)
        terminal_ctrl_h.addWidget(self.btn_stty_config)

        terminal_ctrl_h.addStretch()
        terminal_v.addLayout(terminal_ctrl_h)

        # 终端显示区域
        self.terminal_display = QTextEdit()
        self.terminal_display.setReadOnly(True)
        self.terminal_display.setMinimumHeight(100)
        self.terminal_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.terminal_display.setStyleSheet('font-family: Consolas, Monaco, monospace; font-size: 12px;')
        terminal_v.addWidget(self.terminal_display)

        # 终端输入区域
        terminal_input_h = QHBoxLayout()
        self.terminal_input = QLineEdit()
        self.terminal_input.setStyleSheet('font-family: Consolas, Monaco, monospace; font-size: 12px;')
        self.terminal_input.setPlaceholderText('输入命令并回车发送...')
        self.terminal_input.returnPressed.connect(self.send_terminal_command)
        self.terminal_input.setEnabled(False)
        terminal_input_h.addWidget(self.terminal_input)

        self.btn_terminal_clear = QPushButton('清空')
        self.btn_terminal_clear.clicked.connect(self.clear_terminal)
        terminal_input_h.addWidget(self.btn_terminal_clear)

        # 弹出独立窗口按钮
        self.btn_popup_terminal = QPushButton('弹出终端窗口')
        self.btn_popup_terminal.clicked.connect(self.popup_terminal_window)
        terminal_input_h.addWidget(self.btn_popup_terminal)

        terminal_v.addLayout(terminal_input_h)

        terminal_group.setObjectName('terminal_group')
        terminal_group.setLayout(terminal_v)
        self.serial_terminal_group = terminal_group
        terminal_group.setVisible(False)  # 默认隐藏
        self.main_splitter.addWidget(terminal_group)

        # 初始化独立窗口
        self.terminal_window = None

        # ========== 协议调试区域 ==========
        debug_group = QGroupBox('协议调试')
        debug_v = QVBoxLayout()

        debug_ctrl_h = QHBoxLayout()
        self.btn_load_protocol = QPushButton('加载协议')
        self.btn_load_protocol.clicked.connect(self.load_debug_protocol)
        debug_ctrl_h.addWidget(self.btn_load_protocol)

        self.btn_scan_protocols = QPushButton('扫描协议文件夹')
        self.btn_scan_protocols.clicked.connect(self.scan_protocols_folder)
        debug_ctrl_h.addWidget(self.btn_scan_protocols)

        # 协议文件夹路径输入
        self.protocol_folder_edit = QLineEdit()
        self.protocol_folder_edit.setPlaceholderText('协议文件夹路径')
        self.protocol_folder_edit.setFixedWidth(200)
        debug_ctrl_h.addWidget(self.protocol_folder_edit)

        debug_ctrl_h.addWidget(QLabel('协议:'))
        self.debug_protocol_cb = QComboBox()
        self.debug_protocol_cb.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.debug_protocol_cb.currentTextChanged.connect(self.on_debug_protocol_changed)
        debug_ctrl_h.addWidget(self.debug_protocol_cb)

        self.btn_clear_debug_table = QPushButton('清空表格')
        self.btn_clear_debug_table.clicked.connect(self.clear_debug_table)
        debug_ctrl_h.addWidget(self.btn_clear_debug_table)

        debug_ctrl_h.addStretch()

        # 发送频率设置
        debug_ctrl_h.addWidget(QLabel('发送频率:'))
        self.debug_interval = QSpinBox()
        self.debug_interval.setRange(10, 10000)
        self.debug_interval.setValue(1000)
        self.debug_interval.setSuffix(' ms')
        self.debug_interval.setFixedWidth(100)
        debug_ctrl_h.addWidget(self.debug_interval)

        self.chk_debug_loop = QCheckBox('循环发送')
        self.chk_debug_loop.stateChanged.connect(self.on_debug_loop_changed)
        debug_ctrl_h.addWidget(self.chk_debug_loop)

        self.btn_debug_send = QPushButton('发送')
        self.btn_debug_send.clicked.connect(self.send_debug_packet)
        self.btn_debug_send.setEnabled(False)
        debug_ctrl_h.addWidget(self.btn_debug_send)

        debug_v.addLayout(debug_ctrl_h)

        # 协议字段表格
        self.debug_table = QTableWidget()
        self.debug_table.setColumnCount(4)
        self.debug_table.setHorizontalHeaderLabels(['字段名', '类型', '值', '说明'])
        self.debug_table.setColumnWidth(0, 120)
        self.debug_table.setColumnWidth(1, 60)
        self.debug_table.setColumnWidth(2, 150)
        self.debug_table.setColumnWidth(3, 100)
        self.debug_table.setMinimumHeight(150)
        debug_v.addWidget(self.debug_table)

        # 发送结果显示
        debug_result_h = QHBoxLayout()
        debug_result_h.addWidget(QLabel('发送 HEX:'))
        self.debug_send_hex = QTextEdit()
        self.debug_send_hex.setReadOnly(True)
        self.debug_send_hex.setMaximumHeight(60)
        self.debug_send_hex.setStyleSheet('font-family: monospace;')
        debug_v.addWidget(self.debug_send_hex)

        debug_group.setObjectName('debug_group')
        debug_group.setLayout(debug_v)
        self.serial_debug_group = debug_group
        debug_group.setVisible(False)  # 默认隐藏
        self.main_splitter.addWidget(debug_group)

        # 帧解析区域
        parse_group = QGroupBox('帧解析')
        parse_v = QVBoxLayout()

        parse_h = QHBoxLayout()
        parse_h.addWidget(QLabel('协议:'))
        self.protocol_cb = QComboBox()
        self.protocol_cb.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.protocol_cb.addItem('无')
        self.protocol_cb.currentTextChanged.connect(self.on_protocol_changed)
        parse_h.addWidget(self.protocol_cb)

        self.btn_load_protocol = QPushButton('加载协议')
        self.btn_load_protocol.clicked.connect(self.load_protocol)
        parse_h.addWidget(self.btn_load_protocol)

        self.btn_scan_protocols_parse = QPushButton('扫描协议文件夹')
        self.btn_scan_protocols_parse.clicked.connect(self.scan_protocols_folder_for_parse)
        parse_h.addWidget(self.btn_scan_protocols_parse)

        # 协议文件夹路径输入
        self.protocol_folder_edit_parse = QLineEdit()
        self.protocol_folder_edit_parse.setPlaceholderText('协议文件夹路径')
        self.protocol_folder_edit_parse.setFixedWidth(150)
        parse_h.addWidget(self.protocol_folder_edit_parse)

        # 添加多协议自动解析选项
        self.chk_multi_protocol = QCheckBox('多协议自动解析')
        self.chk_multi_protocol.setToolTip('自动识别加载的多个协议')
        parse_h.addWidget(self.chk_multi_protocol)

        parse_h.addStretch()
        parse_v.addLayout(parse_h)

        # 已加载协议列表
        self.protocols_loaded = []  # 存储已加载的协议定义

        # 协议内容显示
        self.protocol_content = QTextEdit()
        self.protocol_content.setReadOnly(True)
        self.protocol_content.setMinimumHeight(60)
        self.protocol_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.protocol_content.setPlaceholderText('协议内容将显示在这里...')
        parse_v.addWidget(QLabel('协议内容:'))
        parse_v.addWidget(self.protocol_content)

        # 解析结果
        self.parse_result = QTextEdit()
        self.parse_result.setReadOnly(True)
        self.parse_result.setMinimumHeight(80)
        self.parse_result.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        parse_v.addWidget(QLabel('解析结果:'))
        parse_v.addWidget(self.parse_result)

        # 弹出独立窗口按钮
        parse_btn_h = QHBoxLayout()
        self.btn_popup_parse = QPushButton('弹出演示波器窗口')
        self.btn_popup_parse.clicked.connect(self.popup_oscillo_window)
        parse_btn_h.addWidget(self.btn_popup_parse)

        self.btn_popup_protocol = QPushButton('弹出帧解析窗口')
        self.btn_popup_protocol.clicked.connect(self.popup_protocol_window)
        parse_btn_h.addWidget(self.btn_popup_protocol)
        parse_btn_h.addStretch()
        parse_v.addLayout(parse_btn_h)

        parse_group.setObjectName('parse_group')
        parse_group.setLayout(parse_v)
        self.serial_parse_group = parse_group
        parse_group.setVisible(False)  # 默认隐藏
        self.main_splitter.addWidget(parse_group)

        # 隐藏原有的示波器和帧解析区域（可选显示）
        # 如果需要恢复显示，取消下面的注释
        # v.addWidget(oscillo_group)
        # v.addWidget(parse_group)

        # 改为添加简单的提示标签
        self.tip_label = QLabel('提示：点击上方按钮弹出示波器或帧解析独立窗口')
        self.tip_label.setStyleSheet('color: #888; padding: 5px;')
        v.addWidget(self.tip_label)

        # 串口示波器区域（保留但默认不添加到布局）
        if MATPLOTLIB_AVAILABLE:
            oscillo_group = QGroupBox('串口示波器')
            oscillo_v = QVBoxLayout()

            # 示波器控制
            oscillo_ctrl_h = QHBoxLayout()
            self.chk_oscillo_enable = QCheckBox('启用示波器')
            self.chk_oscillo_enable.stateChanged.connect(self.on_oscillo_enable_changed)
            oscillo_ctrl_h.addWidget(self.chk_oscillo_enable)

            oscillo_ctrl_h.addWidget(QLabel('显示点数:'))
            self.oscillo_points = QSpinBox()
            self.oscillo_points.setRange(10, 500)
            self.oscillo_points.setValue(100)
            oscillo_ctrl_h.addWidget(self.oscillo_points)

            self.btn_clear_oscillo = QPushButton('清空波形')
            self.btn_clear_oscillo.clicked.connect(self.clear_oscillo)
            self.btn_clear_oscillo.setEnabled(False)
            oscillo_ctrl_h.addWidget(self.btn_clear_oscillo)

            oscillo_ctrl_h.addStretch()
            oscillo_v.addLayout(oscillo_ctrl_h)

            # 示波器图表
            self.oscillo_figure = Figure(figsize=(8, 3), facecolor='#1e1e1e')
            self.oscillo_canvas = FigureCanvasQTAgg(self.oscillo_figure)
            self.oscillo_ax = self.oscillo_figure.add_subplot(111)
            self.oscillo_ax.set_facecolor('#2d2d2d')
            self.oscillo_ax.set_xlabel('Sample', color='#aaa')
            self.oscillo_ax.set_ylabel('Value', color='#aaa')
            self.oscillo_ax.tick_params(colors='#aaa')
            for spine in self.oscillo_ax.spines.values():
                spine.set_color('#555')
            self.oscillo_line, = self.oscillo_ax.plot([], [], color='#00ff00', linewidth=1)
            self.oscillo_ax.set_xlim(0, 100)
            self.oscillo_ax.set_ylim(0, 256)
            self.oscillo_figure.tight_layout()

            self.oscillo_canvas.setMinimumHeight(150)
            oscillo_v.addWidget(self.oscillo_canvas)

            # 示波器数据
            self.oscillo_data = []
            self.oscillo_max_points = 100

            oscillo_group.setObjectName('oscillo_group')
            oscillo_group.setLayout(oscillo_v)
            self.serial_oscillo_group = oscillo_group
            oscillo_group.setVisible(False)  # 默认隐藏
            self.main_splitter.addWidget(oscillo_group)
        else:
            # 如果没有 matplotlib，显示提示
            self.oscillo_tip = QLabel('提示: 请安装 matplotlib 和 numpy 以启用示波器功能\npip install matplotlib numpy')
            self.oscillo_tip.setStyleSheet('color: #888; padding: 10px;')
            self.main_splitter.addWidget(self.oscillo_tip)

        # 将splitter添加到主布局
        v.addWidget(self.main_splitter)

        # 创建串口调试标签页（带滚动条）
        serial_widget = QWidget()
        serial_widget.setLayout(v)
        self.scroll_serial = QScrollArea()
        self.scroll_serial.setWidget(serial_widget)
        self.scroll_serial.setWidgetResizable(True)
        self.scroll_serial.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_serial.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tabs.addTab(self.scroll_serial, '串口调试')

        # 初始化串口
        self.serial = None
        self.serial_thread = None
        self.recv_timer = None  # 接收数据处理定时器
        self.running = False
        self.send_counter = 0
        self.recv_counter = 0
        self.loop_timer = None

        # 串口拔插检测定时器
        self.port_check_timer = QTimer()
        self.port_check_timer.timeout.connect(self.check_ports_change)
        self.port_check_timer.start(1000)  # 每秒检测一次
        self.last_ports = []  # 上一次的串口列表

        # 初始化示波器数据
        if MATPLOTLIB_AVAILABLE:
            self.oscillo_data = []
            self.oscillo_max_points = 100
            self.oscillo_timer = None

        # 初始化独立窗口
        self.oscillo_window = None
        self.protocol_window = None

        # 初始化解析变量数据
        self.parsed_variable_data = {}

        if self.serial_available:
            self.refresh_ports()

    def _toggle_section(self, section_name, state):
        """切换串口调试各模块的显示/隐藏"""
        # 支持布尔值和Qt.Checked状态
        if isinstance(state, bool):
            visible = state
        else:
            visible = (state == Qt.Checked)

        section_map = {
            'config': getattr(self, 'serial_config_group', None),
            'send': getattr(self, 'serial_send_group', None),
            'recv': getattr(self, 'serial_recv_group', None),
            'terminal': getattr(self, 'serial_terminal_group', None),
            'debug': getattr(self, 'serial_debug_group', None),
            'parse': getattr(self, 'serial_parse_group', None),
            'oscillo': getattr(self, 'serial_oscillo_group', None),
        }

        group = section_map.get(section_name)
        if group:
            group.setVisible(visible)

    def refresh_ports(self):
        """刷新可用串口列表"""
        if not self.serial_available:
            return
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            self.serial_port_cb.clear()
            for port in ports:
                self.serial_port_cb.addItem(port.device)
            # 更新当前串口列表
            self.last_ports = [p.device for p in ports]
        except Exception as e:
            log.exception('refresh_ports failed')

    def check_ports_change(self):
        """检测串口拔插变化"""
        if not self.serial_available:
            return
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            current_ports = [p.device for p in ports]

            # 检测串口变化
            removed_ports = set(self.last_ports) - set(current_ports)
            added_ports = set(current_ports) - set(self.last_ports)

            if removed_ports or added_ports:
                # 刷新串口列表
                self.serial_port_cb.blockSignals(True)
                old_text = self.serial_port_cb.currentText()
                self.serial_port_cb.clear()
                for port in ports:
                    self.serial_port_cb.addItem(port.device)
                # 尝试保持原来的选择
                if old_text in current_ports:
                    self.serial_port_cb.setCurrentText(old_text)
                self.serial_port_cb.blockSignals(False)

                # 检测当前打开的串口是否被拔出
                if self.serial and self.serial.is_open:
                    current_port = self.serial.port
                    if current_port not in current_ports:
                        # 当前串口被拔出
                        QMessageBox.warning(self, '串口拔出',
                            f'串口 {current_port} 已被拔出，串口已关闭。')
                        self.close_serial()

            self.last_ports = current_ports

        except Exception as e:
            log.exception('check_ports_change failed')

    def toggle_serial(self):
        """打开或关闭串口"""
        if not self.serial_available:
            QMessageBox.warning(self, '错误', '请安装 pyserial: pip install pyserial')
            return

        if self.serial and self.serial.is_open:
            self.close_serial()
        else:
            self.open_serial()

    def open_serial(self):
        """打开串口"""
        if not self.serial_available:
            return

        import serial
        # 优先使用自定义路径
        custom_port = self.custom_port_edit.text().strip()
        if custom_port:
            port = custom_port
        else:
            port = self.serial_port_cb.currentText()

        if not port:
            QMessageBox.warning(self, '错误', '请选择或输入串口')
            return

        try:
            baudrate = int(self.baudrate_cb.currentText())
            stopbits_map = {'1': serial.STOPBITS_ONE, '1.5': serial.STOPBITS_ONE_POINT_FIVE, '2': serial.STOPBITS_TWO}
            stopbits = stopbits_map[self.stopbits_cb.currentText()]
            parity_map = {'无': serial.PARITY_NONE, '奇校验': serial.PARITY_ODD, '偶校验': serial.PARITY_EVEN}
            parity = parity_map[self.parity_cb.currentText()]

            self.serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                stopbits=stopbits,
                parity=parity,
                timeout=0.001,  # 减少超时时间，提高响应速度
                write_timeout=0.1
            )

            self.running = True
            self.serial_thread = QThread()
            self.serial_thread.run = self.read_serial
            self.serial_thread.start()

            # 启动定时器在主线程中处理接收数据
            self.recv_timer = QTimer()
            self.recv_timer.timeout.connect(self.check_recv_buffer)
            self.recv_timer.start(5)  # 每5ms检查一次，提高响应速度

            self.btn_open_serial.setText('关闭串口')
            self.btn_send.setEnabled(True)
            if hasattr(self, 'btn_debug_send'):
                self.btn_debug_send.setEnabled(True)
            log.info(f'Serial port {port} opened')

        except Exception as e:
            QMessageBox.critical(self, '错误', f'打开串口失败: {e}')
            log.exception('open_serial failed')

    def close_serial(self):
        """关闭串口"""
        self.running = False

        # 停止接收定时器
        if hasattr(self, 'recv_timer') and self.recv_timer:
            self.recv_timer.stop()
            self.recv_timer = None

        if self.serial_thread:
            self.serial_thread.quit()
            self.serial_thread.wait(1000)
            self.serial_thread = None

        if self.serial:
            try:
                self.serial.close()
            except:
                pass
            self.serial = None

        self.btn_open_serial.setText('打开串口')
        self.btn_send.setEnabled(False)
        if hasattr(self, 'btn_debug_send'):
            self.btn_debug_send.setEnabled(False)

        if self.loop_timer:
            self.loop_timer.stop()
            self.loop_timer = None
        self.chk_loop_send.setChecked(False)

        # 停止示波器
        if MATPLOTLIB_AVAILABLE:
            if self.oscillo_timer:
                self.oscillo_timer.stop()
                self.oscillo_timer = None
            if hasattr(self, 'chk_oscillo_enable'):
                self.chk_oscillo_enable.setChecked(False)

        log.info('Serial port closed')

    def read_serial(self):
        """串口读取线程"""
        import time
        self.terminal_buffer = b''  # 终端缓冲区
        while self.running:
            if self.serial and self.serial.is_open:
                try:
                    # 读取数据，使用更小的超时确保及时响应
                    data = self.serial.read(8192)  # 增加读取缓冲区
                    if data:
                        # 追加到缓冲区
                        self.terminal_buffer += data
                    else:
                        # 无数据时短暂休眠，减少CPU占用
                        time.sleep(0.001)  # 减少休眠时间
                except Exception:
                    pass
            else:
                time.sleep(0.01)

    def check_recv_buffer(self):
        """在主线程中检查并处理接收缓冲区"""
        data = b''
        if hasattr(self, 'terminal_buffer') and self.terminal_buffer:
            # 取走所有缓冲数据
            data = self.terminal_buffer
            self.terminal_buffer = b''

        if not data:
            return

        if self.rb_hex_recv.isChecked():
            text = ' '.join(f'{b:02X}' for b in data)
        else:
            try:
                encoding = self.encoding_cb.currentText()
                try:
                    text = data.decode(encoding, errors='replace')
                except:
                    text = data.decode('utf-8', errors='replace')
            except:
                text = str(data)

        self.recv_text.append(text)

        # 如果终端模式启用，也显示在终端区（使用终端编码）
        if hasattr(self, 'chk_terminal_mode') and self.chk_terminal_mode.isChecked():
            # 传递原始字节数据给终端显示（让append_to_terminal处理解码）
            self.append_to_terminal(data)

        # 如果独立终端窗口打开，也发送数据到该窗口
        if hasattr(self, 'terminal_window') and self.terminal_window and self.terminal_window.isVisible():
            self.terminal_window.append_to_terminal(data)

        if self.chk_auto_scroll.isChecked():
            cursor = self.recv_text.textCursor()
            cursor.movePosition(cursor.End)
            self.recv_text.setTextCursor(cursor)

        if self.chk_auto_parse.isChecked():
            self.parse_frame(data)

        # 更新示波器数据
        if MATPLOTLIB_AVAILABLE:
            for b in data:
                self.add_oscillo_data(b)

            # 更新独立示波器窗口数据
            if hasattr(self, 'oscillo_window') and self.oscillo_window and self.oscillo_window.isVisible():
                self.oscillo_window.receive_serial_data(data)

    def send_data(self):
        """发送数据"""
        if not self.serial or not self.serial.is_open:
            return

        text = self.send_text.toPlainText()
        if not text:
            return

        try:
            if self.rb_hex_send.isChecked():
                data = bytes.fromhex(text.replace(' ', ''))
            else:
                encoding = self.send_encoding_cb.currentText()
                try:
                    data = text.encode(encoding)
                except:
                    data = text.encode('utf-8')

            self.serial.write(data)
            self.send_counter += len(data)
            self.send_count.setText(str(self.send_counter))

        except Exception as e:
            QMessageBox.critical(self, '错误', f'发送失败: {e}')
            log.exception('send_data failed')

    def on_loop_send_changed(self, state):
        """循环发送选项改变"""
        if state == Qt.Checked:
            if self.serial and self.serial.is_open:
                self.loop_timer = QTimer()
                self.loop_timer.timeout.connect(self.send_data)
                self.loop_timer.start(self.loop_interval.value())
                self.loop_interval.setEnabled(True)
        else:
            if self.loop_timer:
                self.loop_timer.stop()
                self.loop_timer = None
            self.loop_interval.setEnabled(False)

    # ========== 协议调试功能 ==========
    def scan_protocols_folder(self):
        """扫描协议文件夹，添加所有JSON协议文件到下拉列表"""
        # 如果输入框有路径则使用，否则弹出文件夹选择对话框
        folder_path = self.protocol_folder_edit.text().strip()
        if not folder_path:
            folder_path = QFileDialog.getExistingDirectory(
                self, '选择协议文件夹', ''
            )
            if not folder_path:
                return
            self.protocol_folder_edit.setText(folder_path)

        if not os.path.isdir(folder_path):
            QMessageBox.warning(self, '警告', '请输入有效的文件夹路径')
            return

        # 扫描文件夹中的所有JSON文件
        json_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith('.json'):
                    json_files.append(os.path.join(root, file))

        if not json_files:
            QMessageBox.information(self, '提示', '未找到任何JSON协议文件')
            return

        # 加载所有协议文件
        loaded_count = 0
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    protocol = json.load(f)

                # 保存协议配置
                if not hasattr(self, 'debug_protocols'):
                    self.debug_protocols = {}
                if not hasattr(self, 'debug_protocols_paths'):
                    self.debug_protocols_paths = {}

                struct_name = protocol.get('structName', os.path.basename(file_path))
                # 避免重复添加
                if struct_name not in self.debug_protocols:
                    self.debug_protocols[struct_name] = protocol
                    self.debug_protocols_paths[struct_name] = file_path
                    self.debug_protocol_cb.addItem(struct_name)
                    loaded_count += 1
            except Exception as e:
                log.warning(f'加载协议文件失败 {file_path}: {e}')

        if loaded_count > 0:
            # 自动选择第一个协议并加载表格
            if self.debug_protocol_cb.count() > 0:
                first_protocol = self.debug_protocol_cb.itemText(0)
                self.debug_protocol_cb.setCurrentText(first_protocol)
            QMessageBox.information(self, '完成', f'成功加载 {loaded_count} 个协议文件')
        else:
            QMessageBox.information(self, '提示', '没有新的协议文件需要加载')

    def load_debug_protocol(self):
        """加载协议文件到调试表格"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, '选择协议文件', '', 'JSON Files (*.json);;All Files (*)'
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                protocol = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, '错误', f'加载协议文件失败: {e}')
            return

        # 保存协议配置
        if not hasattr(self, 'debug_protocols'):
            self.debug_protocols = {}
        if not hasattr(self, 'debug_protocols_paths'):
            self.debug_protocols_paths = {}

        struct_name = protocol.get('structName', 'Unknown')
        self.debug_protocols[struct_name] = protocol
        self.debug_protocols_paths[struct_name] = file_path
        self.debug_protocol_cb.addItem(struct_name)
        self.debug_protocol_cb.setCurrentText(struct_name)

        # 填充表格
        self.populate_debug_table(protocol)

    def populate_debug_table(self, protocol):
        """填充调试表格"""
        self.debug_table.setRowCount(0)
        struct_name = protocol.get('structName', '')
        fields = protocol.get('fields', [])

        for field in fields:
            fname = field.get('name', '')
            ftype = field.get('type', 'int')
            length = field.get('length', 0)

            row = self.debug_table.rowCount()
            self.debug_table.insertRow(row)

            # 字段名
            name_item = QTableWidgetItem(fname)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.debug_table.setItem(row, 0, name_item)

            # 类型
            type_str = ftype
            if ftype == 'char' and length > 0:
                type_str = f'char[{length}]'
            type_item = QTableWidgetItem(type_str)
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            self.debug_table.setItem(row, 1, type_item)

            # 值（可编辑）
            default_value = ''
            if ftype == 'int' or ftype == 'uint8' or ftype == 'uint16' or ftype == 'int8' or ftype == 'int16':
                default_value = '0'
            elif ftype == 'float':
                default_value = '0.0'
            elif ftype == 'bool':
                default_value = '0'
            elif ftype == 'char':
                default_value = ''

            value_item = QTableWidgetItem(default_value)
            self.debug_table.setItem(row, 2, value_item)

            # 说明
            comment_item = QTableWidgetItem('')
            comment_item.setFlags(comment_item.flags() & ~Qt.ItemIsEditable)
            self.debug_table.setItem(row, 3, comment_item)

        # 保存当前协议
        self.current_debug_protocol = protocol

        # 启用发送按钮
        self.btn_debug_send.setEnabled(bool(self.serial and self.serial.is_open))

    def clear_debug_table(self):
        """清空调试表格"""
        self.debug_table.setRowCount(0)
        self.debug_send_hex.clear()

    def send_debug_packet(self):
        """从表格数据生成并发送数据包"""
        if not hasattr(self, 'current_debug_protocol'):
            QMessageBox.warning(self, '警告', '请先加载协议文件')
            return

        if not self.serial or not self.serial.is_open:
            QMessageBox.warning(self, '警告', '请先打开串口')
            return

        protocol = self.current_debug_protocol
        fields = protocol.get('fields', [])
        header = protocol.get('header', 0xAA)
        footer = protocol.get('footer', 0x55)
        verify = protocol.get('verify', 'none')
        align = protocol.get('align', 1)

        # 收集数据
        field_values = []
        for i, field in enumerate(fields):
            fname = field.get('name', '')
            ftype = field.get('type', 'int')
            length = field.get('length', 0)

            try:
                if i < self.debug_table.rowCount():
                    value_str = self.debug_table.item(i, 2).text()
                else:
                    value_str = '0'

                if ftype == 'int' or ftype == 'uint8' or ftype == 'uint16' or ftype == 'int8' or ftype == 'int16':
                    value = int(value_str)
                elif ftype == 'float':
                    value = float(value_str)
                elif ftype == 'bool':
                    value = 1 if value_str in ['1', 'True', 'true'] else 0
                elif ftype == 'char':
                    value = value_str.encode('utf-8')[:length] if length > 0 else value_str.encode('utf-8')
                    # 填充到指定长度
                    if len(value) < length:
                        value = value + b'\x00' * (length - len(value))
                else:
                    value = 0

                field_values.append((fname, ftype, value))
            except ValueError:
                QMessageBox.warning(self, '错误', f'字段 {fname} 的值格式错误')
                return

        # 构建数据包
        packet = self._build_packet(protocol, field_values)

        # 显示HEX
        hex_str = ' '.join(f'{b:02X}' for b in packet)
        self.debug_send_hex.setText(hex_str)

        # 发送数据
        try:
            self.serial.write(packet)
            self.send_counter += 1
            self.send_count.setText(str(self.send_counter))
        except Exception as e:
            QMessageBox.critical(self, '错误', f'发送失败: {e}')

    def _build_packet(self, protocol, field_values):
        """构建数据包"""
        import struct

        # 获取 header/footer 整数值
        header_val = protocol.get('header', 0xAA)
        if isinstance(header_val, str):
            if header_val.startswith('0x') or header_val.startswith('0X'):
                header_int = int(header_val, 16)
            else:
                header_int = int(header_val)
        else:
            header_int = int(header_val)

        footer_val = protocol.get('footer', 0x55)
        if isinstance(footer_val, str):
            if footer_val.startswith('0x') or footer_val.startswith('0X'):
                footer_int = int(footer_val, 16)
            else:
                footer_int = int(footer_val)
        else:
            footer_int = int(footer_val)

        verify = protocol.get('verify', 'none')
        align = protocol.get('align', 1)

        # 处理 header_len, footer_len, data_len
        header_len = protocol.get('header_len', 1)
        footer_len = protocol.get('footer_len', 1)
        has_data_len = protocol.get('data_len', False)

        # 根据 header_len 取 header 的不同字节（小端序）
        header_bytes = []
        for i in range(header_len):
            header_bytes.append((header_int >> (i * 8)) & 0xFF)
        packet = bytes(header_bytes)

        # 如果有 data_len 字段，先添加占位（2字节）
        if has_data_len:
            packet += bytes(2)

        # 先添加所有字段数据
        payload_start = len(packet)
        for fname, ftype, value in field_values:
            if ftype == 'int':
                packet += struct.pack('<i', int(value))
            elif ftype == 'uint8':
                packet += struct.pack('<B', int(value) & 0xFF)
            elif ftype == 'uint16':
                packet += struct.pack('<H', int(value) & 0xFFFF)
            elif ftype == 'int8':
                packet += struct.pack('<b', int(value))
            elif ftype == 'int16':
                packet += struct.pack('<h', int(value))
            elif ftype == 'float':
                packet += struct.pack('<f', float(value))
            elif ftype == 'bool':
                packet += struct.pack('<?', bool(value))
            elif ftype == 'char':
                packet += bytes(value)

        # 计算实际数据长度并更新 data_len 字段
        if has_data_len:
            payload_length = len(packet) - payload_start
            # 更新 data_len 位置
            data_len_bytes = payload_length.to_bytes(2, 'little')
            packet = packet[:payload_start] + data_len_bytes + packet[payload_start:]

        # 计算校验
        if verify == 'sum':
            checksum = sum(packet[1:]) & 0xFF
            packet += bytes([checksum])
        elif verify == 'xor':
            checksum = 0
            for b in packet[1:]:
                checksum ^= b
            packet += bytes([checksum])
        elif verify == 'crc8':
            checksum = self._calc_crc8(packet[1:])
            packet += bytes([checksum])
        elif verify == 'crc16':
            checksum = self._calc_crc16(packet[1:])
            # CRC16 是 2 字节，需要分开高低字节
            packet += bytes([checksum & 0xFF, (checksum >> 8) & 0xFF])
        else:
            # 无校验
            pass

        # 添加 footer（根据 footer_len 取不同字节）
        footer_bytes = []
        for i in range(footer_len):
            footer_bytes.append((footer_int >> (i * 8)) & 0xFF)
        packet += bytes(footer_bytes)

        return packet

    def _calc_crc8(self, data):
        """计算CRC8"""
        crc = 0
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x07
                else:
                    crc <<= 1
            crc &= 0xFF
        return crc

    def _calc_crc16(self, data):
        """计算CRC16 (Modbus)"""
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF

    def on_debug_protocol_changed(self, protocol_name):
        """协议选择改变"""
        if hasattr(self, 'debug_protocols') and protocol_name in self.debug_protocols:
            protocol = self.debug_protocols[protocol_name]
            self.populate_debug_table(protocol)

    def on_debug_loop_changed(self, state):
        """调试循环发送改变"""
        if state == Qt.Checked:
            if self.serial and self.serial.is_open:
                self.debug_timer = QTimer()
                self.debug_timer.timeout.connect(self.send_debug_packet)
                self.debug_timer.start(self.debug_interval.value())
        else:
            if hasattr(self, 'debug_timer') and self.debug_timer:
                self.debug_timer.stop()
                self.debug_timer = None

    def on_terminal_mode_changed(self, state):
        """终端模式切换"""
        if state == Qt.Checked:
            self.terminal_input.setEnabled(True)
            self.terminal_display.append('\n=== 终端模式已启用 ===')
            self.terminal_display.append(f'提示符: {self.terminal_prompt.text()}')
            self.terminal_display.append('输入命令后按回车发送\n')
            # 聚焦到输入框
            self.terminal_input.setFocus()
        else:
            self.terminal_input.setEnabled(False)

    def send_terminal_command(self):
        """发送终端命令"""
        if not self.serial or not self.serial.is_open:
            QMessageBox.warning(self, '错误', '请先打开串口')
            return

        command = self.terminal_input.text()
        if not command:
            return

        # 显示命令（带提示符）
        prompt = self.terminal_prompt.text()
        self.terminal_display.append(f'<span style="color: #00ff00;">{prompt}{command}</span>')

        # 发送命令 + 回车（使用终端编码）
        try:
            encoding = self.terminal_encoding_cb.currentText() or 'UTF-8'
            data = (command + '\r\n').encode(encoding, errors='replace')
            self.serial.write(data)
            self.serial.flush()  # 确保数据立即发送
            self.send_counter += 1
            self.send_count.setText(str(self.send_counter))
        except Exception as e:
            self.terminal_display.append(f'<span style="color: #ff0000;">发送错误: {e}</span>')

        # 清空输入框
        self.terminal_input.clear()

    def clear_terminal(self):
        """清空终端显示"""
        self.terminal_display.clear()

    def run_diagnosis(self):
        """运行诊断，显示串口状态和发送测试命令"""
        if not self.serial or not self.serial.is_open:
            QMessageBox.warning(self, '错误', '请先打开串口')
            return

        self.terminal_display.append('<span style="color: #ffff00;">=== 串口诊断 ===</span>')

        # 显示串口配置
        self.terminal_display.append(f'波特率: {self.serial.baudrate}')
        self.terminal_display.append(f'数据位: {self.serial.bytesize}')
        self.terminal_display.append(f'停止位: {self.serial.stopbits}')
        self.terminal_display.append(f'校验位: {self.serial.parity}')
        self.terminal_display.append(f'超时: {self.serial.timeout}')

        # 发送测试命令
        self.terminal_display.append('')
        self.terminal_display.append('<span style="color: #00ff00;">发送测试命令...</span>')

        try:
            enc = self.terminal_encoding_cb.currentText()
            # 发送简单命令测试
            test_cmd = 'echo ABC123\r\n'
            self.serial.write(test_cmd.encode(enc, errors='replace'))
            self.terminal_display.append(f'已发送: {repr(test_cmd)}')
        except Exception as e:
            self.terminal_display.append(f'<span style="color: #ff0000;">发送失败: {e}</span>')

    def config_linux_terminal(self):
        """配置Linux串口终端参数"""
        if not self.serial or not self.serial.is_open:
            QMessageBox.warning(self, '错误', '请先打开串口')
            return

        # 发送stty命令配置终端
        commands = [
            'stty sane\r\n',  # 恢复默认设置
            'stty -echo\r\n',  # 关闭回显
            'stty -echoe\r\n',  # 关闭回显显示
            'stty -echok\r\n',  # 关闭换行回显
            'stty -echonl\r\n',  # 关闭换行回显
            'stty -icanon\r\n',  # 关闭规范模式
            'stty min 0 time 1\r\n',  # 设置超时
            'echo -e "\\[?2004l\\"\r\n',  # 关闭bracketed paste模式
        ]

        try:
            encoding = self.terminal_encoding_cb.currentText() or 'UTF-8'
            for cmd in commands:
                data = cmd.encode(encoding, errors='replace')
                self.serial.write(data)
                self.serial.flush()
                import time
                time.sleep(0.15)
            self.terminal_display.append('<span style="color: #00ff00;">已发送终端配置命令（关闭回显和bracketed paste）</span>')
        except Exception as e:
            self.terminal_display.append(f'<span style="color: #ff0000;">配置失败: {e}</span>')

    def append_to_terminal(self, data):
        """追加文本到终端显示"""
        import re

        # 检查是否启用HEX显示
        show_hex = hasattr(self, 'chk_terminal_hex') and self.chk_terminal_hex.isChecked()

        if show_hex:
            # HEX模式：直接显示原始字节
            hex_str = ' '.join(f'{b:02X}' for b in data)
            self.terminal_display.append(f'<span style="color: #888888;">{hex_str}</span>')
        else:
            # 文本模式：解码显示
            # 优先使用选择的编码
            enc = getattr(self, 'terminal_encoding_cb', None)
            encoding = enc.currentText() if enc else 'UTF-8'

            try:
                cleaned = data.decode(encoding, errors='replace')
            except:
                cleaned = data.decode('utf-8', errors='replace')

            # 移除所有ANSI转义序列（包括颜色和 bracketed paste 等）
            # 匹配格式: ESC [ ... 字母 或 ESC [ ? ... 字母
            # ESC 可以是 \033 或 \x1b
            cleaned = re.sub(r'\x1b\[[?0-9;]*[a-zA-Z]', '', cleaned)
            cleaned = re.sub(r'\033\[[?0-9;]*[a-zA-Z]', '', cleaned)

            # 移除其他转义序列
            cleaned = re.sub(r'\x1b\]0;.*?\x07', '', cleaned)  # OSC 序列
            cleaned = re.sub(r'\033\]0;.*?\x07', '', cleaned)

            # 处理退格键
            cleaned = cleaned.replace('\x08', '')

            # 处理回车和换行的组合
            cleaned = cleaned.replace('\r\n', '\n')
            cleaned = cleaned.replace('\r', '\n')

            # 清理多余的空行
            cleaned = re.sub(r'\n\n+', '\n', cleaned)

            # 移除其他控制字符（保留换行和制表符）
            cleaned = re.sub(r'[\x00-\x07\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)

            self.terminal_display.append(cleaned)

        # 自动滚动到底部
        scrollbar = self.terminal_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_recv(self):
        """清空接收区"""
        self.recv_text.clear()
        self.recv_counter = 0
        self.recv_count.setText('0')
        self.parse_result.clear()

    def scan_protocols_folder_for_parse(self):
        """扫描协议文件夹，添加所有JSON协议文件到帧解析下拉列表"""
        # 如果输入框有路径则使用，否则弹出文件夹选择对话框
        folder_path = self.protocol_folder_edit_parse.text().strip()
        if not folder_path:
            folder_path = QFileDialog.getExistingDirectory(
                self, '选择协议文件夹', ''
            )
            if not folder_path:
                return
            self.protocol_folder_edit_parse.setText(folder_path)

        if not os.path.isdir(folder_path):
            QMessageBox.warning(self, '警告', '请输入有效的文件夹路径')
            return

        # 扫描文件夹中的所有JSON文件
        json_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith('.json'):
                    json_files.append(os.path.join(root, file))

        if not json_files:
            QMessageBox.information(self, '提示', '未找到任何JSON协议文件')
            return

        # 加载所有协议文件
        loaded_count = 0
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    proto_data = json.load(f)

                # 保存到协议列表
                if not hasattr(self, 'protocols_loaded'):
                    self.protocols_loaded = []

                display_name = os.path.basename(file_path)
                # 避免重复添加
                existing_paths = [proto['path'] for proto in self.protocols_loaded]
                if file_path not in existing_paths:
                    self.protocols_loaded.append({
                        'path': file_path,
                        'name': display_name,
                        'data': proto_data
                    })
                    # 添加到协议选择下拉框
                    if hasattr(self, 'protocol_cb'):
                        self.protocol_cb.addItem(display_name)
                    loaded_count += 1
            except Exception as e:
                log.warning(f'加载协议文件失败 {file_path}: {e}')

        if loaded_count > 0:
            # 自动选择第一个协议
            if hasattr(self, 'protocol_cb') and self.protocol_cb.count() > 0:
                first_protocol = self.protocol_cb.itemText(0)
                self.protocol_cb.setCurrentText(first_protocol)
            QMessageBox.information(self, '完成', f'成功加载 {loaded_count} 个协议文件')
        else:
            QMessageBox.information(self, '提示', '没有新的协议文件需要加载')

    def load_protocol(self):
        """加载协议文件"""
        p, _ = QFileDialog.getOpenFileName(self, '选择协议文件', '', 'JSON Files (*.json)')
        if p:
            # 加载协议内容并显示
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 解析 JSON
                    import json
                    proto_data = json.loads(content)
                self.protocol_content.setPlainText(content)

                # 保存到协议列表
                if not hasattr(self, 'protocols_loaded'):
                    self.protocols_loaded = []

                # 提取协议名称
                proto_name = proto_data.get('structName', os.path.basename(p))
                # 提取文件名作为显示名称
                display_name = os.path.basename(p)

                # 检查是否已存在
                existing_paths = [proto['path'] for proto in self.protocols_loaded]
                if p not in existing_paths:
                    self.protocols_loaded.append({
                        'path': p,
                        'name': display_name,
                        'data': proto_data
                    })

            except Exception as e:
                self.protocol_content.setPlainText(f'加载失败: {e}')
                return

            # 添加到下拉框
            self.current_protocol_path = p
            # 检查是否已存在
            existing = [self.protocol_cb.itemText(i) for i in range(self.protocol_cb.count())]
            if p not in existing:
                self.protocol_cb.addItem(display_name)
            self.protocol_cb.setCurrentText(display_name)

    def on_protocol_changed(self, text):
        """协议选择改变时更新内容显示"""
        if text == '无':
            self.protocol_content.clear()
            return

        # 优先从 protocols_loaded 中查找
        if hasattr(self, 'protocols_loaded'):
            for proto in self.protocols_loaded:
                if proto.get('name') == text:
                    # 找到协议，显示内容
                    import json
                    content = json.dumps(proto.get('data', {}), indent=2, ensure_ascii=False)
                    self.protocol_content.setPlainText(content)
                    return

        # 如果是文件路径，尝试加载内容
        if os.path.isfile(text):
            try:
                with open(text, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.protocol_content.setPlainText(content)
            except Exception as e:
                self.protocol_content.setPlainText(f'加载失败: {e}')
        else:
            self.protocol_content.clear()

    def parse_frame(self, data):
        """解析帧数据，支持多协议"""
        if not hasattr(self, 'protocols_loaded') or not self.protocols_loaded:
            return

        # 检查是否启用多协议自动解析
        if hasattr(self, 'chk_multi_protocol') and self.chk_multi_protocol.isChecked():
            self._parse_multi_protocol(data)
        else:
            # 单协议解析 - 通过名称查找
            current_protocol = self.protocol_cb.currentText()
            if current_protocol != '无':
                for proto in self.protocols_loaded:
                    if proto['name'] == current_protocol:
                        result = self._decode_packet(data, proto['data'])
                        if result:
                            self._show_parse_result(result, proto['name'])
                        break

    def _parse_single_protocol(self, data, protocol_name):
        """单协议解析"""
        for proto in self.protocols_loaded:
            if proto['name'] == protocol_name:
                result = self._decode_packet(data, proto['data'])
                if result:
                    self._show_parse_result(result, proto['name'])
                break

    def _parse_multi_protocol(self, data):
        """多协议自动解析"""
        results = []
        for proto in self.protocols_loaded:
            result = self._decode_packet(data, proto['data'])
            if result:
                results.append((proto['name'], result))

        if results:
            output = []
            for name, result in results:
                output.append(f"协议: {name}")
                for k, v in result.items():
                    output.append(f"  {k}: {v}")
                output.append("")
            self.parse_result.setPlainText("\n".join(output))

    def _decode_packet(self, data, proto_data):
        """根据协议解析数据"""
        try:
            header = proto_data.get('header')
            header_len = proto_data.get('header_len', 1)
            footer = proto_data.get('footer')
            footer_len = proto_data.get('footer_len', 1)
            data_len_enabled = proto_data.get('data_len', True)
            align = proto_data.get('align', 1)  # 获取对齐参数
            fields = proto_data.get('fields', [])
            struct_name = proto_data.get('structName', 'Unknown')

            # 计算字段总长度（考虑对齐）
            field_size = 0
            for f in fields:
                ftype = f.get('type', 'int')
                fsize = 0
                if ftype == 'int' or ftype == 'float':
                    fsize = 4
                elif ftype == 'uint8' or ftype == 'int8':
                    fsize = 1
                elif ftype == 'uint16' or ftype == 'int16':
                    fsize = 2
                elif ftype == 'bool':
                    fsize = 1
                elif ftype == 'char':
                    fsize = f.get('length', 32)
                # 应用对齐
                if align > 1:
                    padding = (align - (field_size % align)) % align
                    field_size += padding
                field_size += fsize

            # 计算数据包最小长度
            data_len_size = 1 if data_len_enabled else 0
            min_len = header_len + data_len_size + field_size + 1 + footer_len  # header + data_len + payload + checksum + footer

            # 检查是否有帧头
            if header is not None:
                if len(data) < header_len:
                    return None
                # 检查帧头（检查第一个字节即可，因为多字节header通常是高字节在前）
                if header_len == 1:
                    if data[0] != header:
                        return None
                else:
                    # 多字节header，检查最高字节
                    expected_high_byte = (header >> ((header_len - 1) * 8)) & 0xFF
                    if data[0] != expected_high_byte:
                        return None

            # 检查数据长度
            if len(data) < min_len:
                return None

            # 检查帧尾
            if footer is not None:
                if footer_len == 1:
                    if data[-1] != footer:
                        return None
                else:
                    # 多字节footer，检查最后一个字节
                    expected_last_byte = (footer >> ((footer_len - 1) * 8)) & 0xFF
                    if data[-(footer_len)] != expected_last_byte:
                        return None

            # 解析字段（跳过帧头 + data_len）
            offset = header_len + data_len_size
            field_offset = 0  # 字段数据偏移（不含填充）
            result = {'structName': struct_name}

            for f in fields:
                fname = f.get('name', 'unknown')
                ftype = f.get('type', 'int')

                # 计算对齐填充
                if align > 1:
                    padding = (align - (field_offset % align)) % align
                    offset += padding

                if len(data) < offset + 4:
                    break

                if ftype == 'int':
                    value = int.from_bytes(data[offset:offset+4], 'little', signed=False)
                    result[fname] = value
                    offset += 4
                    field_offset += 4
                elif ftype == 'uint8':
                    result[fname] = data[offset]
                    offset += 1
                    field_offset += 1
                elif ftype == 'int8':
                    value = data[offset]
                    if value >= 128:
                        value -= 256
                    result[fname] = value
                    offset += 1
                    field_offset += 1
                elif ftype == 'uint16':
                    value = int.from_bytes(data[offset:offset+2], 'little', signed=False)
                    result[fname] = value
                    offset += 2
                    field_offset += 2
                elif ftype == 'int16':
                    value = int.from_bytes(data[offset:offset+2], 'little', signed=True)
                    result[fname] = value
                    offset += 2
                    field_offset += 2
                elif ftype == 'float':
                    import struct
                    value = struct.unpack('f', data[offset:offset+4])[0]
                    result[fname] = round(value, 4)
                    offset += 4
                    field_offset += 4
                elif ftype == 'bool':
                    result[fname] = bool(data[offset])
                    offset += 1
                    field_offset += 1
                elif ftype == 'char':
                    flen = f.get('length', 32)
                    result[fname] = data[offset:offset+flen].decode('utf-8', errors='ignore').rstrip('\x00')
                    offset += flen
                    field_offset += flen

            return result

        except Exception as e:
            log.exception('decode_packet failed')
            return None

    def _show_parse_result(self, result, protocol_name):
        """显示解析结果"""
        output = [f"协议: {protocol_name}"]
        for k, v in result.items():
            output.append(f"  {k}: {v}")
        self.parse_result.setPlainText("\n".join(output))

        # 保存解析后的变量数据供示波器使用
        # 格式: {protocol_name: {field_name: [value1, value2, ...]}}
        if not hasattr(self, 'parsed_variable_data'):
            self.parsed_variable_data = {}

        if protocol_name not in self.parsed_variable_data:
            self.parsed_variable_data[protocol_name] = {}

        max_points = getattr(self, 'oscillo_max_points', 100)

        for k, v in result.items():
            if k == 'structName':
                continue
            if isinstance(v, (int, float)):
                if k not in self.parsed_variable_data[protocol_name]:
                    self.parsed_variable_data[protocol_name][k] = []
                self.parsed_variable_data[protocol_name][k].append(v)
                # 限制数据点数量
                if len(self.parsed_variable_data[protocol_name][k]) > max_points:
                    self.parsed_variable_data[protocol_name][k] = self.parsed_variable_data[protocol_name][k][-max_points:]

        # 传递解析数据到独立示波器窗口
        if hasattr(self, 'oscillo_window') and self.oscillo_window and self.oscillo_window.isVisible():
            self.oscillo_window.receive_parsed_data(protocol_name, result)

    def on_oscillo_enable_changed(self, state):
        """启用/禁用示波器"""
        if not MATPLOTLIB_AVAILABLE:
            return

        if state == Qt.Checked:
            self.oscillo_max_points = self.oscillo_points.value()
            self.oscillo_data = []
            self.btn_clear_oscillo.setEnabled(True)
            # 启动定时更新
            self.oscillo_timer = QTimer()
            self.oscillo_timer.timeout.connect(self.update_oscillo_plot)
            self.oscillo_timer.start(50)  # 20Hz 更新率
        else:
            self.btn_clear_oscillo.setEnabled(False)
            if self.oscillo_timer:
                self.oscillo_timer.stop()
                self.oscillo_timer = None

    def clear_oscillo(self):
        """清空示波器"""
        if MATPLOTLIB_AVAILABLE:
            self.oscillo_data = []
            self.oscillo_line.set_data([], [])
            self.oscillo_canvas.draw()

    def update_oscillo_plot(self):
        """更新示波器图表"""
        if not MATPLOTLIB_AVAILABLE or not self.oscillo_data:
            return

        try:
            data = np.array(self.oscillo_data)
            x = np.arange(len(data))
            self.oscillo_line.set_data(x, data)
            self.oscillo_ax.set_xlim(0, max(10, len(data)))
            self.oscillo_ax.set_ylim(0, max(256, np.max(data) * 1.1) if len(data) > 0 else 256)
            self.oscillo_canvas.draw_idle()
        except Exception as e:
            log.exception('update_oscillo_plot failed')

    def add_oscillo_data(self, value):
        """添加示波器数据"""
        import time
        if not MATPLOTLIB_AVAILABLE:
            return

        if hasattr(self, 'chk_oscillo_enable') and self.chk_oscillo_enable.isChecked():
            self.oscillo_data.append(value)
            # 记录时间戳
            if not hasattr(self, 'oscillo_data_timestamps'):
                self.oscillo_data_timestamps = []
            self.oscillo_data_timestamps.append(time.time())
            # 限制数据点数量
            max_points = self.oscillo_points.value()
            if len(self.oscillo_data) > max_points:
                self.oscillo_data = self.oscillo_data[-max_points:]
                self.oscillo_data_timestamps = self.oscillo_data_timestamps[-max_points:]

    def popup_oscillo_window(self):
        """弹出示波器独立窗口"""
        if not MATPLOTLIB_AVAILABLE:
            QMessageBox.warning(self, '提示', '请安装 matplotlib 和 numpy 以启用示波器功能')
            return

        # 创建新窗口
        if not hasattr(self, 'oscillo_window') or not self.oscillo_window:
            self.oscillo_window = OscilloWindow(self)
        self.oscillo_window.show()
        self.oscillo_window.activateWindow()

    def popup_protocol_window(self):
        """弹出帧解析独立窗口"""
        # 创建新窗口
        if not hasattr(self, 'protocol_window') or not self.protocol_window:
            self.protocol_window = ProtocolWindow(self)

        # 同步协议列表到弹出窗口
        if hasattr(self, 'protocols_loaded') and self.protocols_loaded:
            for proto in self.protocols_loaded:
                self.protocol_window.add_protocol_item(proto.get('name', ''), proto.get('data', {}), proto.get('path'))

        # 同步当前选中的协议
        if hasattr(self, 'protocol_cb'):
            current_protocol = self.protocol_cb.currentText()
            if current_protocol != '无':
                self.protocol_window.set_current_protocol(current_protocol)

        self.protocol_window.show()
        self.protocol_window.activateWindow()

    def popup_terminal_window(self):
        """弹出终端独立窗口"""
        # 创建新窗口
        if not hasattr(self, 'terminal_window') or not self.terminal_window:
            self.terminal_window = TerminalWindow(self)
        self.terminal_window.show()
        self.terminal_window.activateWindow()


def main():
    log.debug('main start')
    try:
        app = QApplication(sys.argv)
        log.debug('QApplication created')
    except Exception:
        log.exception('Failed to create QApplication')
        raise
    p = default_json_path()
    editor = JsonEditor(p)
    editor.show()
    try:
        rc = app.exec_()
        log.debug('app exited rc=%s', rc)
        sys.exit(rc)
    except Exception:
        log.exception('app.exec_ failed')
        raise


if __name__ == '__main__':
    main()
