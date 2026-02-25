"""共享工具函数"""

from PyQt5.QtWidgets import QWidget


def apply_theme_to_widget(widget, theme_name='dark', matplotlib_figure=None, matplotlib_ax=None):
    """应用主题到窗口

    Args:
        widget: 要应用主题的窗口
        theme_name: 主题名称 ('dark' 或 'light')
        matplotlib_figure: matplotlib Figure 对象 (可选)
        matplotlib_ax: matplotlib Axes 对象 (可选)
    """
    if theme_name == 'dark':
        widget.setStyleSheet('''
            QWidget { background-color: #1e1e1e; color: #d4d4d4; }
            QPushButton { background-color: #3c3c3c; border: 1px solid #555; padding: 5px; }
            QPushButton:hover { background-color: #4c4c4c; }
            QCheckBox { color: #d4d4d4; }
            QLabel { color: #d4d4d4; }
            QTableWidget { background-color: #252526; color: #d4d4d4; gridline-color: #3c3c3c; }
            QHeaderView::section { background-color: #3c3c3c; color: #d4d4d4; }
            QSpinBox { background-color: #3c3c3c; color: #d4d4d4; border: 1px solid #555; }
            QComboBox { background-color: #3c3c3c; color: #d4d4d4; border: 1px solid #555; }
            QLineEdit { background-color: #3c3c3c; color: #d4d4d4; border: 1px solid #555; }
            QTextEdit { background-color: #252526; color: #d4d4d4; border: 1px solid #3c3c3c; }
        ''')
        if matplotlib_figure and matplotlib_ax:
            matplotlib_figure.patch.set_facecolor('#1e1e1e')
            matplotlib_ax.set_facecolor('#252526')
            matplotlib_ax.tick_params(colors='#d4d4d4')
            matplotlib_ax.xaxis.label.set_color('#d4d4d4')
            matplotlib_ax.yaxis.label.set_color('#d4d4d4')
            matplotlib_ax.title.set_color('#d4d4d4')
            matplotlib_ax.spines['bottom'].set_color('#d4d4d4')
            matplotlib_ax.spines['left'].set_color('#d4d4d4')
            matplotlib_ax.spines['top'].set_visible(False)
            matplotlib_ax.spines['right'].set_visible(False)
            matplotlib_ax.grid(True, alpha=0.3)
    else:
        widget.setStyleSheet('')
        if matplotlib_figure and matplotlib_ax:
            matplotlib_figure.patch.set_facecolor('white')
            matplotlib_ax.set_facecolor('#f5f5f5')
            matplotlib_ax.grid(True, alpha=0.3)


def get_theme_from_parent(parent_window, default='dark'):
    """从父窗口获取主题设置

    Args:
        parent_window: 父窗口对象
        default: 默认主题

    Returns:
        主题名称字符串
    """
    if parent_window and hasattr(parent_window, 'loaded_theme'):
        return parent_window.loaded_theme
    return default
