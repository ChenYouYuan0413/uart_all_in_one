"""串口示波器窗口模块"""

import os
import re
from functools import partial
from collections import deque

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QSpinBox,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QLineEdit,
    QAbstractItemView, QHeaderView, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from .theme_utils import apply_theme_to_widget, get_theme_from_parent

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


class OscilloWindow(QWidget):
    """串口示波器独立窗口"""

    # 颜色列表
    COLORS = [
        '#00ff00', '#ff0000', '#0000ff', '#ffff00', '#ff00ff', '#00ffff',
        '#ff8800', '#88ff00', '#ff0088', '#8800ff', '#00ff88', '#ff0000',
        '#00ccff', '#ccff00', '#ff00cc', '#cc00ff', '#ffcc00', '#c0c0c0',
        '#ff6666', '#66ff66', '#6666ff', '#ffff66', '#ff66ff', '#66ffff',
        '#ff9966', '#99ff66', '#6699ff', '#9966ff', '#66ff99', '#9999ff'
    ]

    def __init__(self, parent=None):
        super().__init__()
        self.parent_window = parent
        self.setWindowTitle('串口示波器')
        self.setMinimumSize(700, 450)
        self.init_ui()

        # 应用深色主题
        self.apply_theme()

    def init_ui(self):
        v = QVBoxLayout()

        # 控制栏
        ctrl_h = QHBoxLayout()
        self.chk_enable = QCheckBox('启用')
        self.chk_enable.setChecked(True)
        self.chk_enable.stateChanged.connect(self.on_enable_changed)
        ctrl_h.addWidget(self.chk_enable)

        ctrl_h.addWidget(QLabel('显示点数:'))
        self.points_spin = QSpinBox()
        self.points_spin.setRange(10, 1000)
        self.points_spin.setValue(100)
        self.points_spin.valueChanged.connect(self.on_points_changed)
        ctrl_h.addWidget(self.points_spin)

        self.btn_clear = QPushButton('清空')
        self.btn_clear.clicked.connect(self.clear_data)
        ctrl_h.addWidget(self.btn_clear)

        # 缓存时间窗口设置
        ctrl_h.addWidget(QLabel('缓存(秒):'))
        self.cache_time_spin = QSpinBox()
        self.cache_time_spin.setRange(1, 3600)
        self.cache_time_spin.setValue(10)
        self.cache_time_spin.setSuffix(' 秒')
        ctrl_h.addWidget(self.cache_time_spin)

        # 导出按钮
        self.btn_export = QPushButton('导出数据')
        self.btn_export.clicked.connect(self.export_data)
        ctrl_h.addWidget(self.btn_export)

        ctrl_h.addStretch()

        # 显示模式选择
        ctrl_h.addWidget(QLabel('显示模式:'))
        self.display_mode_cb = QComboBox()
        self.display_mode_cb.addItems(['原始数据', '解析变量'])
        self.display_mode_cb.currentTextChanged.connect(self.on_display_mode_changed)
        ctrl_h.addWidget(self.display_mode_cb)

        v.addLayout(ctrl_h)

        # 变量选择表格（解析模式时显示）- 包含复选框、变量名和倍率
        self.var_table = QTableWidget()
        self.var_table.setColumnCount(4)
        self.var_table.setHorizontalHeaderLabels(['✓', '变量名', '倍率', '颜色'])
        # 允许拖动调整列宽 - 所有列都可交互
        self.var_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.var_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.var_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.var_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.var_table.setColumnWidth(0, 30)
        self.var_table.setColumnWidth(1, 150)
        self.var_table.setColumnWidth(2, 80)
        self.var_table.setColumnWidth(3, 50)
        # 允许拖动调整列宽
        self.var_table.horizontalHeader().setDragEnabled(True)
        self.var_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.var_table.setMaximumHeight(120)
        self.var_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.var_table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.var_table.itemChanged.connect(self.on_var_table_changed)
        self.var_table.itemSelectionChanged.connect(self.on_var_selection_changed)
        self.var_multiplier_inputs = {}  # 存储每个变量的倍率输入框 {var_name: QLineEdit}
        self.var_colors = {}  # 存储变量名对应的固定颜色

        var_table_wrapper = QWidget()
        var_table_layout = QVBoxLayout()
        var_table_layout.addWidget(QLabel('选择变量 (勾选显示/拖动表头调整列宽):'))
        var_table_layout.addWidget(self.var_table)
        # 清除按钮
        btn_clear_vars = QPushButton('清除未选中变量')
        btn_clear_vars.clicked.connect(self.clear_unchecked_vars)
        var_table_layout.addWidget(btn_clear_vars)
        var_table_wrapper.setLayout(var_table_layout)

        v.addWidget(var_table_wrapper)

        # 绘图区域
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(8, 4))
            self.canvas = FigureCanvasQTAgg(self.figure)
            self.ax = self.figure.add_subplot(111)
            self.ax.set_xlabel('Sample')
            self.ax.set_ylabel('Value')
            self.ax.grid(True)
            v.addWidget(self.canvas)

            # 绑定鼠标滚轮事件用于缩放
            self.canvas.mpl_scroll_event = None
            self.canvas.mpl_connect('scroll_event', self.on_mouse_scroll)
        else:
            self.figure = None
            self.canvas = None
            self.ax = None
            v.addWidget(QLabel('请安装 matplotlib 和 numpy 以显示图表'))

        # 数据存储
        self.enabled = True
        self.max_points = 100
        self.raw_data = deque(maxlen=self.max_points)
        self.parsed_data = {}  # {var_name: deque(maxlen=max_points)}
        self.selected_vars = set()  # 当前选中的变量集合

        # 定时更新
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(100)  # 100ms更新一次

        # 设置主布局
        self.setLayout(v)

    def on_mouse_scroll(self, event):
        """鼠标滚轮缩放"""
        if event.inaxes != self.ax:
            return

        base_scale = 1.1
        scale_factor = 1 / base_scale if event.button == 'up' else base_scale

        # 获取当前x轴范围
        xlim = self.ax.get_xlim()
        x_range = xlim[1] - xlim[0]
        x_center = (xlim[0] + xlim[1]) / 2

        # 计算新的范围
        new_x_range = x_range * scale_factor

        # 限制范围
        if new_x_range < 10:
            new_x_range = 10
        if new_x_range > self.max_points * 2:
            new_x_range = self.max_points * 2

        # 设置新的x轴范围（保持中心点不变）
        self.ax.set_xlim([x_center - new_x_range / 2, x_center + new_x_range / 2])
        self.canvas.draw_idle()

    def apply_theme(self):
        """应用主题样式"""
        theme = get_theme_from_parent(self.parent_window, 'dark')
        apply_theme_to_widget(self, theme, self.figure, self.ax)

    def on_enable_changed(self, state):
        self.enabled = state == Qt.Checked

    def on_points_changed(self, value):
        self.max_points = value
        # 重建 deque
        new_raw = deque(maxlen=value)
        for item in list(self.raw_data)[-value:]:
            new_raw.append(item)
        self.raw_data = new_raw
        # 重建 parsed_data
        for var_name in self.parsed_data:
            new_deque = deque(maxlen=value)
            for item in list(self.parsed_data[var_name])[-value:]:
                new_deque.append(item)
            self.parsed_data[var_name] = new_deque

    def clear_data(self):
        self.raw_data.clear()
        self.parsed_data.clear()
        if self.ax:
            self.ax.clear()
            self.ax.set_xlabel('Sample')
            self.ax.set_ylabel('Value')
            self.ax.grid(True)
            self.canvas.draw_idle()

    def export_data(self):
        """导出数据到CSV文件"""
        if not self.raw_data and not self.parsed_data:
            QMessageBox.warning(self, '警告', '没有数据可导出')
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, '导出数据', '', 'CSV文件 (*.csv);;所有文件 (*)')
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                # 如果有解析数据，导出解析数据
                if self.parsed_data:
                    # 获取所有变量名
                    var_names = list(self.parsed_data.keys())
                    f.write('Index,' + ','.join(var_names) + '\n')

                    # 获取最大长度
                    max_len = max(len(d) for d in self.parsed_data.values())

                    for i in range(max_len):
                        row = [str(i)]
                        for var_name in var_names:
                            if i < len(self.parsed_data[var_name]):
                                row.append(str(self.parsed_data[var_name][i]))
                            else:
                                row.append('')
                        f.write(','.join(row) + '\n')
                else:
                    # 导出原始数据
                    f.write('Index,Value\n')
                    for i, val in enumerate(self.raw_data):
                        f.write(f'{i},{val}\n')

            QMessageBox.information(self, '成功', f'数据已导出到:\n{file_path}')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'导出失败: {e}')

    def on_display_mode_changed(self, mode):
        """切换显示模式"""
        if mode == '解析变量':
            self.var_table.setVisible(True)
        else:
            self.var_table.setVisible(False)
        self.update_plot()

    def clear_unchecked_vars(self):
        """清除未选中的变量数据"""
        # 获取所有当前选中的变量
        checked_vars = set()
        for row in range(self.var_table.rowCount()):
            item = self.var_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                name_item = self.var_table.item(row, 1)
                if name_item:
                    var_name = name_item.text()
                    checked_vars.add(var_name)

        # 清除未选中变量的数据
        vars_to_remove = []
        for var_name in self.parsed_data:
            if var_name not in checked_vars:
                vars_to_remove.append(var_name)

        for var_name in vars_to_remove:
            del self.parsed_data[var_name]

        self.update_plot()

    def on_var_table_changed(self, item):
        """变量表格勾选状态改变"""
        if item.column() == 0:  # 复选框列
            row = item.row()
            name_item = self.var_table.item(row, 1)
            if not name_item:
                return
            var_name = name_item.text()
            if item.checkState() == Qt.Checked:
                self.selected_vars.add(var_name)
                # 如果数据中还没有这个变量，初始化
                if var_name not in self.parsed_data:
                    self.parsed_data[var_name] = deque(maxlen=self.max_points)
            else:
                self.selected_vars.discard(var_name)
            self.update_plot()

    def on_var_selection_changed(self):
        """变量选中状态改变（用于倍率输入）"""
        pass  # 可扩展

    def update_plot(self):
        """更新图表"""
        if not self.enabled or not self.ax or not self.canvas:
            return

        mode = self.display_mode_cb.currentText()

        try:
            self.ax.clear()
            self.ax.set_xlabel('Sample')
            self.ax.set_ylabel('Value')
            self.ax.grid(True)

            if mode == '原始数据':
                # 原始数据模式
                if self.raw_data:
                    x = list(range(len(self.raw_data)))
                    y = list(self.raw_data)
                    self.ax.plot(x, y, 'b-', linewidth=1, label='Raw Data')
                    self.ax.legend(loc='upper right')
            else:
                # 解析变量模式
                handles = []
                legend_labels = []

                # 遍历所有变量，获取倍率并绘制
                for row in range(self.var_table.rowCount()):
                    item = self.var_table.item(row, 0)
                    if not item or item.checkState() != Qt.Checked:
                        continue

                    name_item = self.var_table.item(row, 1)
                    if not name_item:
                        continue
                    var_name = name_item.text()
                    multiplier_edit = self.var_multiplier_inputs.get(var_name)
                    multiplier = 1.0
                    if multiplier_edit:
                        try:
                            multiplier = float(multiplier_edit.text())
                        except:
                            multiplier = 1.0

                    if var_name in self.parsed_data and self.parsed_data[var_name]:
                        x = list(range(len(self.parsed_data[var_name])))
                        y = [v * multiplier for v in self.parsed_data[var_name]]

                        # 获取固定颜色
                        color = self.var_colors.get(var_name, '#00ff00')

                        line, = self.ax.plot(x, y, color=color, linewidth=1, label=var_name)
                        handles.append(line)

                        display_name = var_name
                        if multiplier != 1:
                            display_name += f' (×{multiplier})'
                        legend_labels.append(display_name)

                if handles:
                    self.ax.legend(handles, legend_labels, loc='upper right', fontsize=8)
            self.canvas.draw_idle()
        except:
            pass

    def get_color_by_name(self, name):
        """根据变量名生成固定颜色"""
        if name in self.var_colors:
            return self.var_colors[name]

        # 使用哈希生成固定索引
        hash_val = hash(name) % len(self.COLORS)
        color = self.COLORS[hash_val]
        self.var_colors[name] = color
        return color

    def add_data(self, data, protocol_data=None):
        """添加数据到示波器

        Args:
            data: 原始数据值
            protocol_data: 解析后的数据字典 {'var_name': value}
        """
        if not self.enabled:
            return

        # 添加原始数据
        self.raw_data.append(data)

        # 添加解析数据
        if protocol_data:
            for var_name, value in protocol_data.items():
                if var_name not in self.parsed_data:
                    self.parsed_data[var_name] = deque(maxlen=self.max_points)
                self.parsed_data[var_name].append(value)

                # 如果变量不在表格中，添加
                if var_name not in self.var_multiplier_inputs:
                    self._add_var_to_table(var_name)

    def receive_serial_data(self, data_bytes):
        """接收串口数据（供主窗口调用）

        Args:
            data_bytes: 串口接收的字节数据
        """
        if not self.enabled:
            return

        # 将每个字节作为原始数据添加
        for b in data_bytes:
            self.add_data(b)

    def receive_parsed_data(self, protocol_name, parsed_dict):
        """接收解析后的数据（供主窗口调用）

        Args:
            protocol_name: 协议名称
            parsed_dict: 解析后的数据字典 {'var_name': value}
        """
        if not self.enabled:
            return

        # 添加解析数据
        for var_name, value in parsed_dict.items():
            if var_name not in self.parsed_data:
                self.parsed_data[var_name] = deque(maxlen=self.max_points)
            self.parsed_data[var_name].append(value)

            # 如果变量不在表格中，添加
            if var_name not in self.var_multiplier_inputs:
                self._add_var_to_table(var_name)

    def _add_var_to_table(self, var_name):
        """添加变量到表格"""
        row = self.var_table.rowCount()
        self.var_table.insertRow(row)

        # 复选框
        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        chk_item.setCheckState(Qt.Unchecked)
        self.var_table.setItem(row, 0, chk_item)

        # 变量名
        name_item = QTableWidgetItem(var_name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.var_table.setItem(row, 1, name_item)

        # 倍率输入
        multiplier_edit = QLineEdit('1.0')
        multiplier_edit.setFixedWidth(60)
        multiplier_edit.setStyleSheet('background-color: #3c3c3c; color: #d4d4d4; border: 1px solid #555;')
        multiplier_edit.textChanged.connect(partial(self._on_multiplier_changed, var_name))
        self.var_table.setCellWidget(row, 2, multiplier_edit)
        self.var_multiplier_inputs[var_name] = multiplier_edit

        # 颜色预览
        color = self.get_color_by_name(var_name)
        color_item = QTableWidgetItem(color)
        color_item.setBackground(QColor(color))
        color_item.setFlags(color_item.flags() & ~Qt.ItemIsEditable)
        self.var_table.setItem(row, 3, color_item)

    def _on_multiplier_changed(self, var_name, text):
        """倍率改变时更新图表"""
        self.update_plot()

    def set_data_from_protocol(self, protocol_data):
        """从协议解析设置变量列表"""
        # 清空表格
        self.var_table.setRowCount(0)
        self.var_multiplier_inputs.clear()
        self.var_colors.clear()

        if not protocol_data:
            return

        fields = protocol_data.get('fields', [])
        for field in fields:
            var_name = field.get('name', '')
            if var_name:
                self._add_var_to_table(var_name)

        # 更新绘图
        self.update_plot()
