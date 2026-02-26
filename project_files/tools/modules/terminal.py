"""串口终端窗口模块"""

import re

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QComboBox, QCheckBox, QScrollArea
)
from PyQt5.QtCore import Qt

from .theme_utils import apply_theme_to_widget, get_theme_from_parent


class TerminalWindow(QWidget):
    """串口终端独立窗口"""

    def __init__(self, parent=None):
        super().__init__()
        self.parent_window = parent
        self.setWindowTitle('串口终端')
        self.setMinimumSize(600, 400)
        self.init_ui()

        # 应用深色主题
        self.apply_theme()

    def init_ui(self):
        v = QVBoxLayout()

        # 控制栏
        ctrl_h = QHBoxLayout()

        ctrl_h.addWidget(QLabel('提示符:'))
        self.terminal_prompt = QLineEdit('root@localhost:~$ ')
        self.terminal_prompt.setFixedWidth(120)
        ctrl_h.addWidget(self.terminal_prompt)

        ctrl_h.addWidget(QLabel('编码:'))
        self.terminal_encoding_cb = QComboBox()
        self.terminal_encoding_cb.addItems(['UTF-8', 'GBK', 'GB2312', 'ASCII', 'Latin-1'])
        self.terminal_encoding_cb.setCurrentText('UTF-8')
        self.terminal_encoding_cb.setFixedWidth(80)
        ctrl_h.addWidget(self.terminal_encoding_cb)

        # HEX显示选项
        self.chk_terminal_hex = QCheckBox('显示HEX')
        ctrl_h.addWidget(self.chk_terminal_hex)

        # 本地回显选项
        self.chk_local_echo = QCheckBox('本地回显')
        self.chk_local_echo.setChecked(True)
        ctrl_h.addWidget(self.chk_local_echo)

        ctrl_h.addStretch()

        # 清空按钮
        self.btn_clear = QPushButton('清空')
        self.btn_clear.clicked.connect(self.clear_terminal)
        ctrl_h.addWidget(self.btn_clear)

        v.addLayout(ctrl_h)

        # 终端显示区
        self.terminal_display = QTextEdit()
        self.terminal_display.setReadOnly(True)
        self.terminal_display.setStyleSheet('''
            QTextEdit {
                background-color: #0c0c0c;
                color: #cccccc;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }
        ''')
        v.addWidget(self.terminal_display)

        # 发送区
        send_h = QHBoxLayout()

        self.terminal_input = QLineEdit()
        self.terminal_input.setPlaceholderText('输入命令...')
        self.terminal_input.setStyleSheet('''
            QLineEdit {
                background-color: #1e1e1e;
                color: #cccccc;
                font-family: 'Consolas', 'Courier New', monospace;
                border: 1px solid #3c3c3c;
                padding: 4px;
            }
        ''')
        self.terminal_input.returnPressed.connect(self.send_terminal_command)
        send_h.addWidget(self.terminal_input)

        self.btn_send = QPushButton('发送')
        self.btn_send.clicked.connect(self.send_terminal_command)
        send_h.addWidget(self.btn_send)

        v.addLayout(send_h)

        # 设置主布局
        self.setLayout(v)

    def apply_theme(self, theme_name=None):
        """应用主题样式"""
        if theme_name and '亮' in theme_name:
            theme = 'light'
        elif theme_name and '暗' in theme_name:
            theme = 'dark'
        else:
            theme = get_theme_from_parent(self.parent_window, 'dark')
        apply_theme_to_widget(self, theme)

    def clear_terminal(self):
        self.terminal_display.clear()

    def send_terminal_command(self):
        """发送终端命令"""
        cmd = self.terminal_input.text()
        if not cmd:
            return

        # 显示输入的命令
        prompt = self.terminal_prompt.text()
        self.terminal_display.append(f'<span style="color: #00ff00;">{prompt}</span><span style="color: #cccccc;">{cmd}</span>')
        self.terminal_input.clear()

        # 发送到父窗口（串口）
        if self.parent_window and hasattr(self.parent_window, 'send_data'):
            # 添加换行
            cmd_bytes = cmd.encode(self.terminal_encoding_cb.currentText(), errors='replace')
            cmd_bytes += b'\r\n'
            self.parent_window.send_data(cmd_bytes)

    def receive_data(self, data):
        """接收数据并显示"""
        if not data:
            return

        encoding = self.terminal_encoding_cb.currentText()

        if self.chk_terminal_hex.isChecked():
            # HEX 模式显示
            hex_str = ' '.join(f'{b:02X}' for b in data)
            self.terminal_display.append(f'<span style="color: #888888;">{hex_str}</span>')
        else:
            # 文本模式显示
            try:
                cleaned = data.decode(encoding, errors='replace')
            except:
                cleaned = data.decode('utf-8', errors='replace')

            # 移除ANSI转义序列
            cleaned = re.sub(r'\x1b\[[?0-9;]*[a-zA-Z]', '', cleaned)
            cleaned = re.sub(r'\033\[[?0-9;]*[a-zA-Z]', '', cleaned)
            cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')

            self.terminal_display.append(cleaned)

        scrollbar = self.terminal_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
