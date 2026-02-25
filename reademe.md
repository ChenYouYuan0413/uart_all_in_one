# 串口通信一站式工具

一个功能完整的串口通信工具，支持代码生成、串口调试、帧解析和示波器功能。

## 功能特性

### 1. 代码生成器
- 支持生成 **C**、**C++**、**Python** 三种语言的串口通信代码
- 自动生成 `encode()` 编码函数和 `decode()` 解码函数
- 支持多种校验方式：无校验、CRC8、CRC16、Sum求和、XOR异或
- 支持字节对齐配置（1/2/4/8字节）
- 支持自定义帧头帧尾

### 2. 串口调试
- 支持常见的波特率设置（9600~921600）
- 支持数据位、停止位、校验位配置
- 支持 ASCII 和 HEX 模式收发
- 支持中文编码（GBK/UTF-8/GB2312）
- 支持循环发送功能
- 实时发送/接收计数

### 3. 帧解析
- 支持多协议同时解析
- 加载多个 JSON 协议文件
- 自动识别协议并解析数据

### 4. 串口示波器
- 实时显示接收数据波形
- 可配置显示点数（10~500）
- 深色主题界面

## 安装

### 环境要求
- Python 3.7+
- Windows 7+ 或 Ubuntu 16.04+

### 安装依赖

```bash
# 克隆项目
git clone <repository-url>
cd uart_all_in_one

# 安装依赖
pip install -r requirements.txt

# 或逐个安装
pip install PyQt5 pyserial matplotlib numpy
```

## 使用方法

### 1. 启动工具

```bash
python project_files/tools/qt_json_editor.py
```

### 2. 结构体配置

1. 在"结构体配置"标签页中：
   - 设置结构体名称（structName）
   - 添加字段：选择类型（int/float/char/bool），设置名称和长度
   - 选择校验方式：无校验/CRC8/CRC16/求和校验/异或校验
   - 设置字节对齐：1/2/4/8 字节
   - 配置帧头帧尾（可选）

2. 点击"保存"保存 JSON 文件
3. 点击"生成代码"生成对应语言的代码

### 3. 串口调试

1. 切换到"串口调试"标签页
2. 选择串口和波特率
3. 点击"打开串口"
4. 发送数据：
   - 在发送区输入内容
   - 选择发送模式（ASCII/HEX）
   - 选择编码（GBK/UTF-8）
   - 点击"发送"按钮
5. 接收数据会自动显示在接收区

### 4. 帧解析

1. 在帧解析区域点击"加载协议"
2. 选择已有的 JSON 协议文件
3. 可以加载多个协议
4. 勾选"多协议自动解析"自动识别所有协议
5. 接收数据时会自动解析并显示结果

### 5. 串口示波器

1. 在串口调试区域下方找到"串口示波器"
2. 勾选"启用示波器"
3. 设置显示点数
4. 接收数据时会实时显示波形
5. 点击"清空波形"可重置

## 代码生成说明

### 生成的文件

- `{StructName}_send.c` - C语言发送端代码
- `{StructName}_recv.c` - C语言接收端代码
- `{StructName}_send.cpp` - C++发送端代码
- `{StructName}_recv.cpp` - C++接收端代码
- `{StructName}_send.py` - Python发送端代码
- `{StructName}_recv.py` - Python接收端代码

### 生成的函数

| 函数 | 说明 |
|------|------|
| `encode()` | 编码：将结构体数据转换为字节流 |
| `decode()` | 解码：将字节流转换为结构体数据 |
| `send_Verify()` | 计算校验值 |
| `recive_Verify()` | 验证数据完整性 |

### 数据包格式

```
[HEADER][payload][checksum][FOOTER]
  1字节   N字节     1字节    1字节
```

## 打包发布

### 使用打包脚本

```bash
# 安装打包依赖
pip install pyinstaller

# 打包成 Windows exe
python project_files/tools/build.py win

# 打包成 Linux 可执行文件
python project_files/tools/build.py linux

# 清理构建文件
python project_files/tools/build.py clean
```

打包后的文件位于 `dist` 目录下。

## 协议文件格式

JSON 协议文件格式示例：

```json
{
  "structName": "MyPacket",
  "fields": [
    {"name": "id", "type": "int"},
    {"name": "value", "type": "float"},
    {"name": "name", "type": "char", "length": 32}
  ],
  "header": 170,
  "footer": 85,
  "verify": "sum",
  "align": 4
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| structName | string | 结构体名称 |
| fields | array | 字段列表 |
| fields[].name | string | 字段名称 |
| fields[].type | string | 字段类型：int/float/char/bool |
| fields[].length | int | 字段长度（仅char类型需要） |
| header | int | 帧头（0-255） |
| footer | int | 帧尾（0-255） |
| verify | string | 校验方式：none/crc8/crc16/sum/xor |
| align | int | 字节对齐：1/2/4/8 |

## 常见问题

### 1. 串口打不开
- 检查串口是否被其他程序占用
- 确认串口名称正确

### 2. 接收数据乱码
- 尝试切换编码方式（GBK/UTF-8）
- 确认发送端和接收端使用相同的编码

### 3. 帧解析失败
- 确认协议文件格式正确
- 确认帧头帧尾设置正确

### 4. 示波器不显示
- 确保已安装 matplotlib 和 numpy
- 确认已启用示波器

## 项目结构

```
uart_all_in_one/
├── project_files/
│   ├── tools/
│   │   ├── qt_json_editor.py    # 主程序
│   │   ├── generator.py         # 代码生成器
│   │   └── build.py             # 打包脚本
│   ├── examples/
│   │   └── struct_definition.json  # 示例协议
│   └── generated/                   # 生成的代码
├── requirements.txt
└── reademe.md
```

## 许可证

MIT License

## 更新日志

### v1.0.0 (2024-xx-xx)
- 初始版本
- 支持代码生成（C/C++/Python）
- 支持串口调试
- 支持帧解析
- 支持串口示波器
