# 示例：如何使用 generator.py 生成的 Python 模块
# 先用命令行生成：
# python ..\tools\generator.py struct_definition.json --lang python --out .

# 假设已生成 SensorPacket.py
try:
    from SensorPacket import encode, decode
except Exception:
    print('请先运行 generator.py 生成 SensorPacket.py')

if 'encode' in globals():
    obj = {'id': 123, 'value': 4.56, 'name': 'temp'}
    b = encode(obj)
    print('Encoded bytes:', b)
    o2 = decode(b)
    print('Decoded:', o2)
