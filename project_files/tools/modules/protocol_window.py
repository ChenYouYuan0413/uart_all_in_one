"""帧解析窗口模块"""

import os
import json

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTextEdit, QCheckBox, QScrollArea, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt

from .theme_utils import apply_theme_to_widget, get_theme_from_parent


class ProtocolWindow(QWidget):
    """帧解析独立窗口"""

    def __init__(self, parent=None):
        super().__init__()
        self.parent_window = parent
        self.setWindowTitle('帧解析')
        self.setMinimumSize(500, 400)
        self.init_ui()

        # 应用深色主题
        self.apply_theme()

    def init_ui(self):
        v = QVBoxLayout()

        # 控制栏
        ctrl_h = QHBoxLayout()
        ctrl_h.addWidget(QLabel('协议:'))
        self.protocol_cb = QComboBox()
        self.protocol_cb.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.protocol_cb.addItem('无')
        ctrl_h.addWidget(self.protocol_cb)

        self.btn_load = QPushButton('加载协议')
        self.btn_load.clicked.connect(self.load_protocol)
        ctrl_h.addWidget(self.btn_load)

        self.btn_custom = QPushButton('自定义协议')
        self.btn_custom.clicked.connect(self.custom_protocol)
        ctrl_h.addWidget(self.btn_custom)

        self.chk_multi = QCheckBox('多协议自动解析')
        ctrl_h.addWidget(self.chk_multi)

        ctrl_h.addStretch()

        # 解析按钮
        self.btn_parse = QPushButton('手动解析')
        self.btn_parse.clicked.connect(self.manual_parse)
        ctrl_h.addWidget(self.btn_parse)

        v.addLayout(ctrl_h)

        # 手动输入区
        input_h = QHBoxLayout()
        input_h.addWidget(QLabel('输入(HEX):'))
        self.input_hex = QTextEdit()
        self.input_hex.setPlaceholderText('输入十六进制数据，如: 7B 01 02 03...')
        self.input_hex.setMaximumHeight(60)
        input_h.addWidget(self.input_hex)
        v.addLayout(input_h)

        # 解析结果显示区
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(2)
        self.result_table.setHorizontalHeaderLabels(['字段', '值'])
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        v.addWidget(QLabel('解析结果:'))
        v.addWidget(self.result_table)

        # 原始协议内容显示
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.protocol_content = QTextEdit()
        self.protocol_content.setReadOnly(True)
        self.protocol_content.setMaximumHeight(150)
        scroll.setWidget(self.protocol_content)
        v.addWidget(QLabel('协议内容:'))
        v.addWidget(scroll)

        self.current_protocol_data = None
        self.protocols_list = []  # 存储多协议

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

    def load_protocol(self):
        """加载协议文件"""
        # 获取示例目录
        if self.parent_window and hasattr(self.parent_window, 'examples_dir'):
            default_dir = self.parent_window.examples_dir
        else:
            default_dir = os.path.join(os.path.dirname(__file__), '..', 'examples')

        file_path, _ = QFileDialog.getOpenFileName(
            self, '选择协议文件', default_dir, 'JSON文件 (*.json);;所有文件 (*)')
        if not file_path:
            return

        self._load_protocol_file(file_path)

    def _load_protocol_file(self, file_path):
        """加载协议文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.protocol_content.setPlainText(content)

            # 解析JSON
            proto_data = json.loads(content)
            name = proto_data.get('structName', os.path.basename(file_path))

            # 添加到下拉框
            existing = [self.protocol_cb.itemText(i) for i in range(self.protocol_cb.count())]
            if name not in existing:
                self.protocol_cb.addItem(name)
            self.protocol_cb.setCurrentText(name)

            # 保存当前协议数据
            self.current_protocol_data = proto_data

            # 保存到父窗口
            if self.parent_window and hasattr(self.parent_window, 'protocols_loaded'):
                # 检查是否已存在
                found = False
                for p in self.parent_window.protocols_loaded:
                    if p.get('name') == name:
                        p['data'] = proto_data
                        p['path'] = file_path
                        found = True
                        break
                if not found:
                    self.parent_window.protocols_loaded.append({
                        'path': file_path,
                        'name': name,
                        'data': proto_data
                    })

            # 更新示波器变量列表
            if self.parent_window and hasattr(self.parent_window, 'oscillo_window') and self.parent_window.oscillo_window:
                self.parent_window.oscillo_window.set_data_from_protocol(proto_data)

        except Exception as e:
            QMessageBox.warning(self, '错误', f'加载协议失败: {e}')

    def custom_protocol(self):
        """自定义协议"""
        # 打开协议编辑器
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle('自定义协议')
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout()

        # 协议内容编辑
        layout.addWidget(QLabel('协议内容 (JSON):'))
        editor = QTextEdit()
        default_proto = '''{
  "structName": "Custom_Packet",
  "fields": [
    {"name": "header", "type": "uint8"},
    {"name": "data1", "type": "uint16"},
    {"name": "data2", "type": "int16"},
    {"name": "checksum", "type": "uint8"}
  ],
  "verify": "xor",
  "header": 123,
  "header_len": 1
}'''
        editor.setPlainText(default_proto)
        layout.addWidget(editor)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.setLayout(layout)

        if dialog.exec_():
            try:
                content = editor.toPlainText()
                proto_data = json.loads(content)
                name = proto_data.get('structName', 'Custom_Packet')

                # 显示内容
                self.protocol_content.setPlainText(content)
                self.protocol_cb.addItem(name)
                self.protocol_cb.setCurrentText(name)
                self.current_protocol_data = proto_data

            except json.JSONDecodeError as e:
                QMessageBox.warning(self, '错误', f'JSON格式错误: {e}')

    def manual_parse(self):
        """手动解析输入的HEX数据"""
        if not self.current_protocol_data:
            QMessageBox.warning(self, '警告', '请先加载协议')
            return

        hex_str = self.input_hex.toPlainText().strip()
        if not hex_str:
            QMessageBox.warning(self, '警告', '请输入十六进制数据')
            return

        # 解析HEX字符串
        try:
            # 移除空格和其他分隔符
            hex_str = hex_str.replace(' ', '').replace(',', '').replace('0x', '').replace('0X', '')
            data = bytes.fromhex(hex_str)
        except ValueError:
            QMessageBox.warning(self, '错误', '无效的十六进制数据')
            return

        # 使用父窗口的解码函数解析
        if self.parent_window and hasattr(self.parent_window, '_decode_packet'):
            try:
                # 获取当前字节序设置
                endian = 'little'
                if self.parent_window and hasattr(self.parent_window, 'get_current_endian'):
                    endian = self.parent_window.get_current_endian()
                result = self.parent_window._decode_packet(data, self.current_protocol_data, endian)
                self._display_result(result)
            except Exception as e:
                QMessageBox.warning(self, '解析错误', f'解析失败: {e}')
        else:
            QMessageBox.warning(self, '错误', '无法解析：父窗口没有_decode_packet方法')

    def _display_result(self, result):
        """显示解析结果"""
        self.result_table.setRowCount(0)

        if not result:
            QMessageBox.warning(self, '解析失败', '未能解析数据，请检查：\n1. 协议是否正确加载\n2. 字节序是否匹配\n3. 数据格式是否正确')
            return

        for field_name, value in result.items():
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)

            name_item = QTableWidgetItem(str(field_name))
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.result_table.setItem(row, 0, name_item)

            value_item = QTableWidgetItem(str(value))
            value_item.setFlags(value_item.flags() & ~Qt.ItemIsEditable)
            self.result_table.setItem(row, 1, value_item)

    def add_protocol_item(self, name, data, path=None):
        """添加协议到下拉列表"""
        existing = [self.protocol_cb.itemText(i) for i in range(self.protocol_cb.count())]
        if name not in existing and name:
            self.protocol_cb.addItem(name)

    def set_current_protocol(self, protocol_name):
        """设置当前选中的协议并加载其数据"""
        if not protocol_name or protocol_name == '无':
            return

        # 设置下拉框选中项
        index = self.protocol_cb.findText(protocol_name)
        if index >= 0:
            self.protocol_cb.setCurrentIndex(index)

        # 如果父窗口有协议数据，从父窗口获取
        if self.parent_window and hasattr(self.parent_window, 'protocols_loaded'):
            for proto in self.parent_window.protocols_loaded:
                if proto.get('name') == protocol_name:
                    self.current_protocol_data = proto.get('data')
                    # 显示协议内容
                    import json
                    content = json.dumps(proto.get('data', {}), indent=2, ensure_ascii=False)
                    self.protocol_content.setPlainText(content)
                    break
