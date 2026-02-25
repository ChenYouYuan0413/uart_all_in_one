#!/usr/bin/env python3
"""
简单的串口数据结构代码生成器（示例版）
支持：整型(int32)、浮点(float32)、定长字符串(char[n])
输入：JSON 文件，输出：在指定目录生成示例 C 和 Python 解析函数模板
用法：python generator.py examples/struct_definition.json --lang c --out examples/
"""

import json
import os
import sys
import argparse
import struct

PRIMITIVE_MAP = {
    'int': 'int32_t',
    'uint8': 'uint8_t',
    'uint16': 'uint16_t',
    'int8': 'int8_t',
    'int16': 'int16_t',
    'float': 'float',
    'bool': 'uint8_t',
    'char': 'char'  # 需要 length
}

PY_STRUCT_PACK_MAP = {
    'int': 'i',
    'uint8': 'B',
    'uint16': 'H',
    'int8': 'b',
    'int16': 'h',
    'float': 'f',
    'bool': '?',
}


def load_def(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    # 去除可能的 BOM
    if text.startswith('\ufeff'):
        text = text.lstrip('\ufeff')
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # 打印文件片段并提示错误位置，便于调试
        lines = text.splitlines()
        print(f'Error parsing JSON file: {path}')
        print(f'JSONDecodeError: {e.msg} (line {e.lineno}, col {e.colno})')
        start = max(0, e.lineno - 3)
        end = min(len(lines), e.lineno + 2)
        for i in range(start, end):
            ln = i + 1
            marker = '>>' if ln == e.lineno else '  '
            print(f"{marker} {ln:4d}: {lines[i]}")
        raise


def calc_packet_size(defn):
    """计算数据包长度（字节）。"""
    size = 0
    for f in defn['fields']:
        if f['type'] == 'int':
            size += 4
        elif f['type'] == 'uint8' or f['type'] == 'int8':
            size += 1
        elif f['type'] == 'uint16' or f['type'] == 'int16':
            size += 2
        elif f['type'] == 'float':
            size += 4
        elif f['type'] == 'bool':
            size += 1
        elif f['type'] == 'char':
            size += f.get('length', 32)
        else:
            # 可扩展类型处理
            raise ValueError('未知字段类型: ' + f.get('type', ''))
    return size


def get_verify_type(defn):
    """获取校验类型，默认为sum"""
    return defn.get('verify', 'sum')


def get_align(defn):
    """获取字节对齐，默认为4"""
    return defn.get('align', 4)


def gen_c_verify_func(verify_type):
    """生成C语言的校验函数"""
    lines = []
    if verify_type == 'none':
        lines.append('/* 无校验 */')
        lines.append('static inline uint8_t send_Verify(const unsigned char *buf, int len) {')
        lines.append('    return 0;')
        lines.append('}')
    elif verify_type == 'crc8':
        lines.append('/* CRC8 校验 */')
        lines.append('static const uint8_t CRC8_TABLE[256] = {')
        # 生成 CRC8 查表
        lines.append('    0x00, 0x07, 0x0E, 0x09, 0x1C, 0x1B, 0x12, 0x15,')
        lines.append('    0x38, 0x3F, 0x36, 0x31, 0x24, 0x23, 0x2A, 0x2D,')
        lines.append('    0x70, 0x77, 0x7E, 0x79, 0x6C, 0x6B, 0x62, 0x65,')
        lines.append('    0x48, 0x4F, 0x46, 0x41, 0x54, 0x53, 0x5A, 0x5D,')
        lines.append('    0xE0, 0xE7, 0xEE, 0xE9, 0xFC, 0xFB, 0xF2, 0xF5,')
        lines.append('    0xD8, 0xDF, 0xD6, 0xD1, 0xC4, 0xC3, 0xCA, 0xCD,')
        lines.append('    0x90, 0x97, 0x9E, 0x99, 0x8C, 0x8B, 0x82, 0x85,')
        lines.append('    0xA8, 0xAF, 0xA6, 0xA1, 0xB4, 0xB3, 0xBA, 0xBD,')
        lines.append('    0xDC, 0xDB, 0xD2, 0xD5, 0xC8, 0xCF, 0xC6, 0xC1,')
        lines.append('    0xEC, 0xEB, 0xE2, 0xE5, 0xF8, 0xFF, 0xF6, 0xF1,')
        lines.append('    0xAC, 0xAB, 0xA2, 0xA5, 0xB8, 0xBF, 0xB6, 0xB1,')
        lines.append('    0x9C, 0x9B, 0x92, 0x95, 0x88, 0x8F, 0x86, 0x81,')
        lines.append('    0x3C, 0x3B, 0x32, 0x35, 0x28, 0x2F, 0x26, 0x21,')
        lines.append('    0x0C, 0x0B, 0x02, 0x05, 0x18, 0x1F, 0x16, 0x11,')
        lines.append('    0x4C, 0x4B, 0x42, 0x45, 0x58, 0x5F, 0x56, 0x51,')
        lines.append('    0x7C, 0x7B, 0x72, 0x75, 0x68, 0x6F, 0x66, 0x61,')
        lines.append('    0xAD, 0xAA, 0xA3, 0xA4, 0xB9, 0xBE, 0xB7, 0xB0,')
        lines.append('    0x9D, 0x9A, 0x93, 0x94, 0x89, 0x8E, 0x87, 0x80,')
        lines.append('    0xDD, 0xDA, 0xD3, 0xD4, 0xC9, 0xCE, 0xC7, 0xC0,')
        lines.append('    0xED, 0xEA, 0xE3, 0xE4, 0xF9, 0xFE, 0xF7, 0xF0,')
        lines.append('    0x11, 0x16, 0x1F, 0x18, 0x0D, 0x0A, 0x03, 0x04,')
        lines.append('    0x29, 0x2E, 0x27, 0x20, 0x35, 0x32, 0x3B, 0x3C,')
        lines.append('    0x61, 0x66, 0x6F, 0x68, 0x7D, 0x7A, 0x73, 0x74,')
        lines.append('    0x59, 0x5E, 0x57, 0x50, 0x45, 0x42, 0x4B, 0x4C,')
        lines.append('    0xC5, 0xC2, 0xCB, 0xCC, 0xD9, 0xDE, 0xD7, 0xD0,')
        lines.append('    0xFD, 0xFA, 0xF3, 0xF4, 0xE9, 0xEE, 0xE7, 0xE0,')
        lines.append('    0xA5, 0xA2, 0xAB, 0xAC, 0xB9, 0xBE, 0xB7, 0xB0,')
        lines.append('    0x9D, 0x9A, 0x93, 0x94, 0x89, 0x8E, 0x87, 0x80,')
        lines.append('    0x75, 0x72, 0x7B, 0x7C, 0x69, 0x6E, 0x67, 0x60,')
        lines.append('    0x4D, 0x4A, 0x43, 0x44, 0x59, 0x5E, 0x57, 0x50,')
        lines.append('    0x05, 0x02, 0x0B, 0x0C, 0x19, 0x1E, 0x17, 0x10,')
        lines.append('    0x3D, 0x3A, 0x33, 0x34, 0x29, 0x2E, 0x27, 0x20')
        lines.append('};')
        lines.append('static inline uint8_t send_Verify(const unsigned char *buf, int len) {')
        lines.append('    uint8_t crc = 0;')
        lines.append('    for (int i = 0; i < len; i++) {')
        lines.append('        crc = CRC8_TABLE[crc ^ buf[i]];')
        lines.append('    }')
        lines.append('    return crc;')
        lines.append('}')
    elif verify_type == 'crc16':
        lines.append('/* CRC16 校验 */')
        lines.append('static const uint16_t CRC16_TABLE[256] = {')
        # 生成 CRC16 查表 (简略版本)
        lines.append('    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,')
        lines.append('    0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,')
        lines.append('    0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,')
        lines.append('    0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,')
        lines.append('    0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,')
        lines.append('    0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,')
        lines.append('    0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,')
        lines.append('    0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,')
        lines.append('    0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,')
        lines.append('    0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,')
        lines.append('    0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,')
        lines.append('    0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xAB3B, 0xBB1A,')
        lines.append('    0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,')
        lines.append('    0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,')
        lines.append('    0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,')
        lines.append('    0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,')
        lines.append('    0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,')
        lines.append('    0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,')
        lines.append('    0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,')
        lines.append('    0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,')
        lines.append('    0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,')
        lines.append('    0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,')
        lines.append('    0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,')
        lines.append('    0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,')
        lines.append('    0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,')
        lines.append('    0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,')
        lines.append('    0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,')
        lines.append('    0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,')
        lines.append('    0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,')
        lines.append('    0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,')
        lines.append('    0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,')
        lines.append('    0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0')
        lines.append('};')
        lines.append('static inline uint8_t send_Verify(const unsigned char *buf, int len) {')
        lines.append('    uint16_t crc = 0;')
        lines.append('    for (int i = 0; i < len; i++) {')
        lines.append('        crc = (crc << 8) ^ CRC16_TABLE[((crc >> 8) ^ buf[i]) & 0xFF];')
        lines.append('    }')
        lines.append('    return (uint8_t)(crc & 0xFF);')
        lines.append('}')
    elif verify_type == 'xor':
        lines.append('/* 异或校验 (XOR) */')
        lines.append('static inline uint8_t send_Verify(const unsigned char *buf, int len) {')
        lines.append('    uint8_t xor_val = 0;')
        lines.append('    for (int i = 0; i < len; ++i) xor_val ^= buf[i];')
        lines.append('    return xor_val;')
        lines.append('}')
    else:  # sum (default)
        lines.append('/* 求和校验 (Sum) */')
        lines.append('static inline uint8_t send_Verify(const unsigned char *buf, int len) {')
        lines.append('    uint32_t s = 0;')
        lines.append('    for (int i = 0; i < len; ++i) s += buf[i];')
        lines.append('    return (uint8_t)(s & 0xFF);')
        lines.append('}')
    return lines


def gen_c(defn):
    name = defn['structName']
    fields = defn['fields']
    packet_size = calc_packet_size(defn)
    align = get_align(defn)
    # 获取 header_len 和 header 值
    header_len = defn.get('header_len', 1)
    header_val = defn.get('header', 0xAA)
    footer_val = defn.get('footer', 0x55)

    # 生成 struct
    lines = []
    lines.append('#include <stdint.h>')
    lines.append('#include <string.h>')
    lines.append('#include <stddef.h>')
    lines.append('')
    lines.append(f'static const int PACKET_SIZE = {packet_size};')
    lines.append(f'static const int PACKET_HEADER_LEN = {header_len};')
    lines.append(f'static const uint{header_len*8}_t PACKET_HEADER = {hex(header_val)};')
    lines.append(f'static const unsigned char PACKET_FOOTER = {hex(footer_val)};')
    # 新格式: header(n bytes) + data_len(1 byte) + payload + checksum(1 byte) + footer(1 byte)
    lines.append(f'static const int PACKET_TOTAL_SIZE = {header_len} + 1 + PACKET_SIZE + 2; /* header + data_len + payload + checksum + footer */')
    lines.append('')
    # 字节对齐
    lines.append(f'#pragma pack(push, {align})')
    lines.append('')
    # 生成校验函数
    verify_type = get_verify_type(defn)
    lines.extend(gen_c_verify_func(verify_type))
    lines.append('')
    lines.append('typedef struct {')
    for f in fields:
        t = f['type']
        if t == 'char':
            l = f.get('length', 32)
            lines.append(f'    {PRIMITIVE_MAP[t]} {f["name"]}[{l}];')
        else:
            lines.append(f'    {PRIMITIVE_MAP[t]} {f["name"]};')
    lines.append(f'}} {name};')
    lines.append('')
    lines.append('#pragma pack(pop)')
    lines.append('')
    # 生成 encode 函数：输出完整包 [HEADER][DATA_LEN][payload][CHECKSUM][FOOTER]
    lines.append('/* encode -> 写入完整包：header + data_len + payload + checksum + footer */')
    lines.append(f'void encode(const {name} *in, unsigned char *out) {{')
    lines.append('    /* out 缓冲区至少为 PACKET_TOTAL_SIZE 字节 */')
    lines.append('    unsigned char *p = out;')
    # 写入 header (支持多字节)
    if header_len == 1:
        lines.append('    *p++ = (unsigned char)PACKET_HEADER;')
    else:
        lines.append(f'    /* 写入 {header_len} 字节 header */')
        for i in range(header_len):
            shift = (header_len - 1 - i) * 8
            lines.append(f'    *p++ = (unsigned char)(PACKET_HEADER >> {shift});')
    # 写入 data_len
    lines.append(f'    *p++ = (unsigned char)PACKET_SIZE;')
    for f in fields:
        if f['type'] == 'int':
            lines.append(f'    memcpy(p, &in->{f["name"]}, sizeof(int32_t)); p += sizeof(int32_t);')
        elif f['type'] == 'float':
            lines.append(f'    memcpy(p, &in->{f["name"]}, sizeof(float)); p += sizeof(float);')
        elif f['type'] == 'bool':
            lines.append(f'    memcpy(p, &in->{f["name"]}, sizeof(uint8_t)); p += sizeof(uint8_t);')
        elif f['type'] == 'char':
            l = f.get('length', 32)
            lines.append(f'    memcpy(p, in->{f["name"]}, {l}); p += {l};')
        else:
            lines.append(f'    /* unknown field type: {f.get("type")} */')
    lines.append('    /* 计算 payload 校验 (不包括 header, data_len, checksum, footer) */')
    lines.append(f'    uint8_t checksum = send_Verify(out + {header_len} + 1, PACKET_SIZE);')
    lines.append('    *p++ = checksum;')
    lines.append('    *p++ = PACKET_FOOTER;')
    lines.append('}')
    lines.append('')
    # 生成 decode：验证头尾与校验后填充结构体
    header_check = f'(buf[0] != (unsigned char)PACKET_HEADER)' if header_len == 1 else f'(buf[0] != (unsigned char)(PACKET_HEADER >> { (header_len-1)*8 }))'
    lines.append(f'/* decode -> 输入完整包：检查 header/footer/checksum 后解析 payload */')
    lines.append(f'int recive_Verify(const unsigned char *buf, int len) {{')
    lines.append(f'    if (len != PACKET_TOTAL_SIZE) return 0;')
    lines.append(f'    if ({header_check}) return 0;')
    lines.append('    if (buf[len-1] != PACKET_FOOTER) return 0;')
    lines.append(f'    uint8_t expect = buf[{header_len} + 1 + PACKET_SIZE];')
    lines.append(f'    return send_Verify(buf + {header_len} + 1, PACKET_SIZE) == expect;')
    lines.append('}')
    lines.append('')
    lines.append(f'void decode(const unsigned char *in, {name} *out) {{')
    lines.append(f'    /* 假设已通过 recive_Verify，跳过 header({header_len}字节) + data_len(1字节) */')
    lines.append(f'    const unsigned char *p = in + {header_len} + 1;')
    for f in fields:
        if f['type'] == 'int':
            lines.append(f'    memcpy(&out->{f["name"]}, p, sizeof(int32_t)); p += sizeof(int32_t);')
        elif f['type'] == 'float':
            lines.append(f'    memcpy(&out->{f["name"]}, p, sizeof(float)); p += sizeof(float);')
        elif f['type'] == 'bool':
            lines.append(f'    memcpy(&out->{f["name"]}, p, sizeof(uint8_t)); p += sizeof(uint8_t);')
        elif f['type'] == 'char':
            l = f.get('length', 32)
            lines.append(f'    memcpy(out->{f["name"]}, p, {l}); p += {l};')
        else:
            lines.append(f'    /* unknown field type: {f.get("type")} */')
    lines.append('}')
    return '\n'.join(lines)


def gen_c_send(defn):
    name = defn['structName']
    fields = defn['fields']
    packet_size = calc_packet_size(defn)
    verify_type = get_verify_type(defn)
    align = get_align(defn)
    header_len = defn.get('header_len', 1)
    header_val = defn.get('header', 0xAA)
    footer_val = defn.get('footer', 0x55)
    footer_len = defn.get('footer_len', 1)
    data_len_enabled = defn.get('data_len', True)

    # 计算数据包总长度
    if data_len_enabled:
        data_len_size = 1
    else:
        data_len_size = 0
    total_size = header_len + data_len_size + packet_size + 1 + footer_len

    lines = []
    lines.append('#include <stdint.h>')
    lines.append('#include <string.h>')
    lines.append('')
    lines.append(f'static const int PACKET_SIZE = {packet_size};')
    lines.append(f'static const int PACKET_HEADER_LEN = {header_len};')
    lines.append(f'static const uint{header_len*8}_t PACKET_HEADER = {hex(header_val)};')
    lines.append(f'static const int PACKET_FOOTER_LEN = {footer_len};')
    lines.append(f'static const uint{footer_len*8}_t PACKET_FOOTER = {hex(footer_val)};')
    lines.append(f'static const int PACKET_DATA_LEN_ENABLED = {1 if data_len_enabled else 0};')
    lines.append(f'static const int PACKET_TOTAL_SIZE = {total_size};')
    lines.append('')
    # 字节对齐
    lines.append(f'#pragma pack(push, {align})')
    lines.append('')
    # send_Verify
    lines.extend(gen_c_verify_func(verify_type))
    lines.append('')
    # recive_Verify (也包含在发送端，便于对回包校验)
    data_offset = header_len + (1 if data_len_enabled else 0)
    checksum_offset = header_len + (1 if data_len_enabled else 0) + packet_size
    footer_check_offset = f'len - {footer_len}'
    lines.append('static inline int recive_Verify(const unsigned char *buf, int len) {')
    lines.append(f'    if (len != PACKET_TOTAL_SIZE) return 0;')
    if header_len == 1:
        lines.append('    if (buf[0] != (unsigned char)PACKET_HEADER) return 0;')
    else:
        lines.append(f'    if (buf[0] != (unsigned char)(PACKET_HEADER >> { (header_len-1)*8 })) return 0;')
    # Footer check (support multi-byte)
    if footer_len == 1:
        lines.append('    if (buf[len-1] != (unsigned char)PACKET_FOOTER) return 0;')
    else:
        lines.append(f'    if (buf[{footer_check_offset}] != (unsigned char)(PACKET_FOOTER >> { (footer_len-1)*8 })) return 0;')
    lines.append(f'    uint8_t expect = buf[{checksum_offset}];')
    lines.append(f'    return send_Verify(buf + {data_offset}, PACKET_SIZE) == expect;')
    lines.append('}')
    lines.append('')
    # struct
    lines.append('typedef struct {')
    for f in fields:
        t = f['type']
        if t == 'char':
            l = f.get('length', 32)
            lines.append(f'    {PRIMITIVE_MAP[t]} {f["name"]}[{l}];')
        else:
            lines.append(f'    {PRIMITIVE_MAP[t]} {f["name"]};')
    lines.append(f'}} {name};')
    lines.append('')
    lines.append('#pragma pack(pop)')
    lines.append('')
    # encode
    lines.append(f'void encode(const {name} *in, unsigned char *out) {{')
    lines.append('    unsigned char *p = out;')
    # 写入 header (支持多字节)
    if header_len == 1:
        lines.append('    *p++ = (unsigned char)PACKET_HEADER;')
    else:
        lines.append(f'    /* 写入 {header_len} 字节 header */')
        for i in range(header_len):
            shift = (header_len - 1 - i) * 8
            lines.append(f'    *p++ = (unsigned char)(PACKET_HEADER >> {shift});')
    # 条件写入 data_len
    if data_len_enabled:
        lines.append(f'    *p++ = (unsigned char)PACKET_SIZE;')
    for f in fields:
        if f['type'] == 'int':
            lines.append(f'    memcpy(p, &in->{f["name"]}, sizeof(int32_t)); p += sizeof(int32_t);')
        elif f['type'] == 'float':
            lines.append(f'    memcpy(p, &in->{f["name"]}, sizeof(float)); p += sizeof(float);')
        elif f['type'] == 'bool':
            lines.append(f'    memcpy(p, &in->{f["name"]}, sizeof(uint8_t)); p += sizeof(uint8_t);')
        elif f['type'] == 'char':
            l = f.get('length', 32)
            lines.append(f'    memcpy(p, in->{f["name"]}, {l}); p += {l};')
        else:
            lines.append(f'    /* unknown field type: {f.get("type")} */')
    # 计算校验和的位置
    data_offset = header_len + (1 if data_len_enabled else 0)
    lines.append(f'    uint8_t checksum = send_Verify(out + {data_offset}, PACKET_SIZE);')
    lines.append('    *p++ = checksum;')
    # 写入 footer (支持多字节)
    if footer_len == 1:
        lines.append('    *p++ = (unsigned char)PACKET_FOOTER;')
    else:
        lines.append(f'    /* 写入 {footer_len} 字节 footer */')
        for i in range(footer_len):
            shift = (footer_len - 1 - i) * 8
            lines.append(f'    *p++ = (unsigned char)(PACKET_FOOTER >> {shift});')
    lines.append('}')
    lines.append('')
    # decode (发送端也能解析收到的数据)
    data_offset = header_len + (1 if data_len_enabled else 0)
    lines.append(f'void decode(const unsigned char *in, {name} *out) {{')
    lines.append(f'    const unsigned char *p = in + {data_offset};  /* skip header + data_len (if enabled) */')
    for f in fields:
        if f['type'] == 'int':
            lines.append(f'    memcpy(&out->{f["name"]}, p, sizeof(int32_t)); p += sizeof(int32_t);')
        elif f['type'] == 'float':
            lines.append(f'    memcpy(&out->{f["name"]}, p, sizeof(float)); p += sizeof(float);')
        elif f['type'] == 'bool':
            lines.append(f'    memcpy(&out->{f["name"]}, p, sizeof(uint8_t)); p += sizeof(uint8_t);')
        elif f['type'] == 'char':
            l = f.get('length', 32)
            lines.append(f'    memcpy(out->{f["name"]}, p, {l}); p += {l};')
        else:
            lines.append(f'    /* unknown field type: {f.get("type")} */')
    lines.append('}')
    return '\n'.join(lines)


def gen_c_recv(defn):
    name = defn['structName']
    fields = defn['fields']
    packet_size = calc_packet_size(defn)
    verify_type = get_verify_type(defn)
    align = get_align(defn)
    header_len = defn.get('header_len', 1)
    header_val = defn.get('header', 0xAA)
    footer_val = defn.get('footer', 0x55)
    footer_len = defn.get('footer_len', 1)
    data_len_enabled = defn.get('data_len', True)

    # 计算数据包总长度
    if data_len_enabled:
        data_len_size = 1
    else:
        data_len_size = 0
    total_size = header_len + data_len_size + packet_size + 1 + footer_len

    lines = []
    lines.append('#include <stdint.h>')
    lines.append('#include <string.h>')
    lines.append('')
    lines.append(f'static const int PACKET_SIZE = {packet_size};')
    lines.append(f'static const int PACKET_HEADER_LEN = {header_len};')
    lines.append(f'static const uint{header_len*8}_t PACKET_HEADER = {hex(header_val)};')
    lines.append(f'static const int PACKET_FOOTER_LEN = {footer_len};')
    lines.append(f'static const uint{footer_len*8}_t PACKET_FOOTER = {hex(footer_val)};')
    lines.append(f'static const int PACKET_DATA_LEN_ENABLED = {1 if data_len_enabled else 0};')
    lines.append(f'static const int PACKET_TOTAL_SIZE = {total_size};')
    lines.append('')
    # 字节对齐
    lines.append(f'#pragma pack(push, {align})')
    lines.append('')
    # send_Verify 和 recive_Verify（接收端也需发送功能以回应）
    lines.extend(gen_c_verify_func(verify_type))
    lines.append('')
    lines.append('int recive_Verify(const unsigned char *buf, int len) {')
    lines.append(f'    if (len != PACKET_TOTAL_SIZE) return 0;')
    lines.append(f'    if (buf[0] != (unsigned char)(PACKET_HEADER >> { (header_len-1)*8 })) return 0;')
    lines.append('    if (buf[len-1] != PACKET_FOOTER) return 0;')
    lines.append(f'    uint8_t expect = buf[{header_len} + 1 + PACKET_SIZE];')
    lines.append(f'    return send_Verify(buf + {header_len} + 1, PACKET_SIZE) == expect;')
    lines.append('}')
    lines.append('')
    # struct and decode
    lines.append(f'typedef struct {{')
    for f in fields:
        t = f['type']
        if t == 'char':
            l = f.get('length', 32)
            lines.append(f'    {PRIMITIVE_MAP[t]} {f["name"]}[{l}];')
        else:
            lines.append(f'    {PRIMITIVE_MAP[t]} {f["name"]};')
    lines.append(f'}} {name};')
    lines.append('')
    # decode
    lines.append(f'void decode(const unsigned char *in, {name} *out) {{')
    lines.append(f'    const unsigned char *p = in + {header_len} + 1;  /* skip header + data_len */')
    for f in fields:
        if f['type'] == 'int':
            lines.append(f'    memcpy(&out->{f["name"]}, p, sizeof(int32_t)); p += sizeof(int32_t);')
        elif f['type'] == 'float':
            lines.append(f'    memcpy(&out->{f["name"]}, p, sizeof(float)); p += sizeof(float);')
        elif f['type'] == 'bool':
            lines.append(f'    memcpy(&out->{f["name"]}, p, sizeof(uint8_t)); p += sizeof(uint8_t);')
        elif f['type'] == 'char':
            l = f.get('length', 32)
            lines.append(f'    memcpy(out->{f["name"]}, p, {l}); p += {l};')
        else:
            lines.append(f'    /* unknown field type: {f.get("type")} */')
    lines.append('}')
    lines.append('')
    # 同时生成 encode，便于接收端也能回复
    lines.append(f'void encode(const {name} *in, unsigned char *out) {{')
    lines.append('    unsigned char *p = out;')
    # 写入 header (支持多字节)
    if header_len == 1:
        lines.append('    *p++ = (unsigned char)PACKET_HEADER;')
    else:
        lines.append(f'    /* 写入 {header_len} 字节 header */')
        for i in range(header_len):
            shift = (header_len - 1 - i) * 8
            lines.append(f'    *p++ = (unsigned char)(PACKET_HEADER >> {shift});')
    # 写入 data_len
    lines.append(f'    *p++ = (unsigned char)PACKET_SIZE;')
    for f in fields:
        if f['type'] == 'int':
            lines.append(f'    memcpy(p, &in->{f["name"]}, sizeof(int32_t)); p += sizeof(int32_t);')
        elif f['type'] == 'float':
            lines.append(f'    memcpy(p, &in->{f["name"]}, sizeof(float)); p += sizeof(float);')
        elif f['type'] == 'bool':
            lines.append(f'    memcpy(p, &in->{f["name"]}, sizeof(uint8_t)); p += sizeof(uint8_t);')
        elif f['type'] == 'char':
            l = f.get('length', 32)
            lines.append(f'    memcpy(p, in->{f["name"]}, {l}); p += {l};')
        else:
            lines.append(f'    /* unknown field type: {f.get("type")} */')
    lines.append(f'    uint8_t checksum = send_Verify(out + {header_len} + 1, PACKET_SIZE);')
    lines.append('    *p++ = checksum;')
    lines.append('    *p++ = PACKET_FOOTER;')
    lines.append('}')
    return '\n'.join(lines)


def gen_cpp_send(defn):
    # 目前与 C 相同，仅改扩展名与稍微不同的 includes
    txt = gen_c_send(defn)
    txt = txt.replace('#include <stdint.h>', '#include <cstdint>')
    txt = txt.replace('#include <string.h>', '#include <cstring>')
    return txt


def gen_cpp_recv(defn):
    txt = gen_c_recv(defn)
    txt = txt.replace('#include <stdint.h>', '#include <cstdint>')
    txt = txt.replace('#include <string.h>', '#include <cstring>')
    return txt


def gen_python_verify_func(verify_type):
    """生成Python的校验函数"""
    lines = []
    if verify_type == 'none':
        lines.append('def send_Verify(buf):')
        lines.append('    return 0')
    elif verify_type == 'crc8':
        lines.append('def send_Verify(buf):')
        lines.append('    crc = 0')
        lines.append('    for b in buf:')
        lines.append('        crc ^= b')
        lines.append('        for _ in range(8):')
        lines.append('            if crc & 0x80:')
        lines.append('                crc = (crc << 1) ^ 0x07')
        lines.append('            else:')
        lines.append('                crc = crc << 1')
        lines.append('        crc &= 0xFF')
        lines.append('    return crc')
    elif verify_type == 'crc16':
        lines.append('def send_Verify(buf):')
        lines.append('    crc = 0')
        lines.append('    for b in buf:')
        lines.append('        crc ^= b')
        lines.append('        for _ in range(8):')
        lines.append('            if crc & 0x8000:')
        lines.append('                crc = (crc << 1) ^ 0x1021')
        lines.append('            else:')
        lines.append('                crc = crc << 1')
        lines.append('        crc &= 0xFFFF')
        lines.append('    return crc & 0xFF')
    elif verify_type == 'xor':
        lines.append('def send_Verify(buf):')
        lines.append('    result = 0')
        lines.append('    for b in buf:')
        lines.append('        result ^= b')
        lines.append('    return result')
    else:  # sum (default)
        lines.append('def send_Verify(buf):')
        lines.append('    return sum(buf) & 0xFF')
    return lines


def gen_python_send(defn):
    name = defn['structName']
    fields = defn['fields']
    verify_type = get_verify_type(defn)
    header_len = defn.get('header_len', 1)
    header_val = defn.get('header', 0xAA)
    footer_val = defn.get('footer', 0x55)
    footer_len = defn.get('footer_len', 1)
    data_len_enabled = defn.get('data_len', True)

    lines = []
    lines.append('import struct')
    fmt_parts = []
    for f in fields:
        if f['type'] == 'int':
            fmt_parts.append('i')
        elif f['type'] == 'float':
            fmt_parts.append('f')
        elif f['type'] == 'bool':
            fmt_parts.append('?')
        else:
            l = f.get('length', 32)
            fmt_parts.append(f'{l}s')
    fmt = '<' + ''.join(fmt_parts)
    packet_size = struct.calcsize(fmt)

    # 计算数据包总长度
    if data_len_enabled:
        data_len_size = 1
    else:
        data_len_size = 0
    total_size = header_len + data_len_size + packet_size + 1 + footer_len

    lines.append(f'PACKET_SIZE = {packet_size}')
    lines.append(f'PACKET_HEADER_LEN = {header_len}')
    lines.append(f'PACKET_HEADER = {hex(header_val)}')
    lines.append(f'PACKET_FOOTER_LEN = {footer_len}')
    lines.append(f'PACKET_FOOTER = {hex(footer_val)}')
    lines.append(f'PACKET_DATA_LEN_ENABLED = {1 if data_len_enabled else 0}')
    lines.append(f'PACKET_TOTAL_SIZE = {total_size}')
    lines.append(f"FMT = '{fmt}'")

    # 校验函数
    lines.extend(gen_python_verify_func(verify_type))
    lines.append('')

    # encode
    pack_args = []
    for f in fields:
        if f['type'] == 'char':
            l = f.get('length', 32)
            pack_args.append(f"obj['{f['name']}'].encode('utf-8')[:{l}].ljust({l}, b'\\x00')")
        elif f['type'] == 'bool':
            pack_args.append(f"bool(obj['{f['name']}'])")
        else:
            pack_args.append(f"obj['{f['name']}']")
    lines.append('def encode(obj):')
    lines.append('    payload = struct.pack(FMT, ' + ', '.join(pack_args) + ')')
    lines.append('    if len(payload) != PACKET_SIZE:')
    lines.append("        raise ValueError('packed size mismatch')")
    lines.append('    checksum = send_Verify(payload)')
    # 构建 header 字节
    if header_len == 1:
        lines.append('    header_bytes = bytes([PACKET_HEADER])')
    else:
        header_bytes = 'bytes(['
        for i in range(header_len):
            shift = (header_len - 1 - i) * 8
            header_bytes += f'(PACKET_HEADER >> {shift}) & 0xFF, '
        header_bytes = header_bytes.rstrip(', ') + '])'
        lines.append(f'    header_bytes = {header_bytes}')
    # 条件写入 data_len
    if data_len_enabled:
        lines.append('    data_len_bytes = bytes([PACKET_SIZE])')
        data_len_part = 'data_len_bytes + '
    else:
        data_len_part = ''
    # 构建 footer 字节
    if footer_len == 1:
        lines.append('    footer_bytes = bytes([PACKET_FOOTER])')
    else:
        footer_bytes = 'bytes(['
        for i in range(footer_len):
            shift = (footer_len - 1 - i) * 8
            footer_bytes += f'(PACKET_FOOTER >> {shift}) & 0xFF, '
        footer_bytes = footer_bytes.rstrip(', ') + '])'
        lines.append(f'    footer_bytes = {footer_bytes}')
    lines.append(f'    return header_bytes + {data_len_part}payload + bytes([checksum]) + footer_bytes')
    lines.append('')
    # decode + recive_Verify (发送端也能解析回复)
    data_offset = header_len + (1 if data_len_enabled else 0)
    checksum_offset = header_len + (1 if data_len_enabled else 0) + packet_size
    footer_check_offset = f'len - {footer_len}'
    lines.append('def recive_Verify(buf):')
    lines.append('    if len(buf) != PACKET_TOTAL_SIZE:')
    lines.append('        return False')
    if header_len == 1:
        lines.append('    if buf[0] != PACKET_HEADER:')
    else:
        lines.append(f'    if buf[0] != (PACKET_HEADER >> { (header_len-1)*8 }):')
    if footer_len == 1:
        lines.append('        return False')
    else:
        lines.append(f'    if buf[{footer_check_offset}] != (PACKET_FOOTER >> { (footer_len-1)*8 }):')
        lines.append('        return False')
    lines.append(f'    payload = buf[{data_offset}:{data_offset}+PACKET_SIZE]')
    lines.append(f'    checksum = buf[{checksum_offset}]')
    lines.append('    return send_Verify(payload) == checksum')
    lines.append('')
    lines.append('def decode(buf):')
    lines.append('    if len(buf) != PACKET_TOTAL_SIZE:')
    lines.append("        raise ValueError('buffer size mismatch')")
    lines.append(f'    payload = buf[{data_offset}:{data_offset}+PACKET_SIZE]')
    lines.append('    vals = struct.unpack(FMT, payload)')
    lines.append('    obj = {}')
    idx = 0
    for f in fields:
        if f['type'] == 'char':
            lines.append(f"    obj['{f['name']}'] = vals[{idx}].rstrip(b'\\x00').decode('utf-8', errors='ignore')")
        elif f['type'] == 'bool':
            lines.append(f"    obj['{f['name']}'] = bool(vals[{idx}])")
        else:
            lines.append(f"    obj['{f['name']}'] = vals[{idx}]")
        idx += 1
    lines.append('    return obj')
    return '\n'.join(lines)


def gen_python_recv(defn):
    name = defn['structName']
    fields = defn['fields']
    verify_type = get_verify_type(defn)
    header_len = defn.get('header_len', 1)
    header_val = defn.get('header', 0xAA)
    footer_val = defn.get('footer', 0x55)
    footer_len = defn.get('footer_len', 1)
    data_len_enabled = defn.get('data_len', True)

    lines = []
    lines.append('import struct')
    fmt_parts = []
    for f in fields:
        if f['type'] == 'int':
            fmt_parts.append('i')
        elif f['type'] == 'float':
            fmt_parts.append('f')
        elif f['type'] == 'bool':
            fmt_parts.append('?')
        else:
            l = f.get('length', 32)
            fmt_parts.append(f'{l}s')
    fmt = '<' + ''.join(fmt_parts)
    packet_size = struct.calcsize(fmt)

    # 计算数据包总长度
    if data_len_enabled:
        data_len_size = 1
    else:
        data_len_size = 0
    total_size = header_len + data_len_size + packet_size + 1 + footer_len

    lines.append(f'PACKET_SIZE = {packet_size}')
    lines.append(f'PACKET_HEADER_LEN = {header_len}')
    lines.append(f'PACKET_HEADER = {hex(header_val)}')
    lines.append(f'PACKET_FOOTER_LEN = {footer_len}')
    lines.append(f'PACKET_FOOTER = {hex(footer_val)}')
    lines.append(f'PACKET_DATA_LEN_ENABLED = {1 if data_len_enabled else 0}')
    lines.append(f'PACKET_TOTAL_SIZE = {total_size}')
    lines.append(f"FMT = '{fmt}'")
    # recv side also contains encode/send_Verify to allow sending responses
    lines.extend(gen_python_verify_func(verify_type))
    lines.append('')
    lines.append('def encode(obj):')
    pack_args = []
    for f in fields:
        if f['type'] == 'char':
            l = f.get('length', 32)
            pack_args.append(f"obj['{f['name']}'].encode('utf-8')[:{l}].ljust({l}, b'\\x00')")
        elif f['type'] == 'bool':
            pack_args.append(f"bool(obj['{f['name']}'])")
        else:
            pack_args.append(f"obj['{f['name']}']")
    lines.append('    payload = struct.pack(FMT, ' + ', '.join(pack_args) + ')')
    lines.append('    if len(payload) != PACKET_SIZE:')
    lines.append("        raise ValueError('packed size mismatch')")
    lines.append('    checksum = send_Verify(payload)')
    # 构建 header 字节
    if header_len == 1:
        lines.append('    header_bytes = bytes([PACKET_HEADER])')
    else:
        header_bytes = 'bytes(['
        for i in range(header_len):
            shift = (header_len - 1 - i) * 8
            header_bytes += f'(PACKET_HEADER >> {shift}) & 0xFF, '
        header_bytes = header_bytes.rstrip(', ') + '])'
        lines.append(f'    header_bytes = {header_bytes}')
    # 条件写入 data_len
    if data_len_enabled:
        lines.append('    data_len_bytes = bytes([PACKET_SIZE])')
        data_len_part = 'data_len_bytes + '
    else:
        data_len_part = ''
    # 构建 footer 字节
    if footer_len == 1:
        lines.append('    footer_bytes = bytes([PACKET_FOOTER])')
    else:
        footer_bytes = 'bytes(['
        for i in range(footer_len):
            shift = (footer_len - 1 - i) * 8
            footer_bytes += f'(PACKET_FOOTER >> {shift}) & 0xFF, '
        footer_bytes = footer_bytes.rstrip(', ') + '])'
        lines.append(f'    footer_bytes = {footer_bytes}')
    lines.append(f'    return header_bytes + {data_len_part}payload + bytes([checksum]) + footer_bytes')
    lines.append('')
    data_offset = header_len + (1 if data_len_enabled else 0)
    checksum_offset = header_len + (1 if data_len_enabled else 0) + packet_size
    footer_check_offset = f'len - {footer_len}'
    lines.append('def recive_Verify(buf):')
    lines.append('    if len(buf) != PACKET_TOTAL_SIZE:')
    lines.append('        return False')
    if header_len == 1:
        lines.append('    if buf[0] != PACKET_HEADER:')
    else:
        lines.append(f'    if buf[0] != (PACKET_HEADER >> { (header_len-1)*8 }):')
    if footer_len == 1:
        lines.append('        return False')
    else:
        lines.append(f'    if buf[{footer_check_offset}] != (PACKET_FOOTER >> { (footer_len-1)*8 }):')
        lines.append('        return False')
    lines.append(f'    payload = buf[{data_offset}:{data_offset}+PACKET_SIZE]')
    lines.append(f'    checksum = buf[{checksum_offset}]')
    lines.append('    return send_Verify(payload) == checksum')
    lines.append('')
    lines.append('def decode(buf):')
    lines.append('    if len(buf) != PACKET_TOTAL_SIZE:')
    lines.append("        raise ValueError('buffer size mismatch')")
    lines.append(f'    payload = buf[{data_offset}:{data_offset}+PACKET_SIZE]')
    lines.append('    vals = struct.unpack(FMT, payload)')
    lines.append('    obj = {}')
    idx = 0
    for f in fields:
        if f['type'] == 'char':
            lines.append(f"    obj['{f['name']}'] = vals[{idx}].rstrip(b'\\x00').decode('utf-8', errors='ignore')")
        elif f['type'] == 'bool':
            lines.append(f"    obj['{f['name']}'] = bool(vals[{idx}])")
        else:
            lines.append(f"    obj['{f['name']}'] = vals[{idx}]")
        idx += 1
    lines.append('    return obj')
    return '\n'.join(lines)


def write_out(text, path):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print('Wrote', path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('json', help='struct definition json')
    ap.add_argument('--lang', default='python', choices=['python', 'c', 'cpp'], help='target language (deprecated)')
    ap.add_argument('--send-lang', default=None, choices=['python','c','cpp'], help='send side language')
    ap.add_argument('--recv-lang', default=None, choices=['python','c','cpp'], help='recv side language')
    ap.add_argument('--out', default='.', help='output directory')
    args = ap.parse_args()

    defn = load_def(args.json)
    os.makedirs(args.out, exist_ok=True)
    base = defn['structName']
    # determine send/recv languages
    send_lang = args.send_lang or args.lang
    recv_lang = args.recv_lang or args.lang

    # send side
    if send_lang == 'c':
        txt = gen_c_send(defn)
        write_out(txt, os.path.join(args.out, base + '_send.c'))
    elif send_lang == 'cpp':
        txt = gen_cpp_send(defn)
        write_out(txt, os.path.join(args.out, base + '_send.cpp'))
    else:
        txt = gen_python_send(defn)
        write_out(txt, os.path.join(args.out, base + '_send.py'))

    # recv side
    if recv_lang == 'c':
        txt = gen_c_recv(defn)
        write_out(txt, os.path.join(args.out, base + '_recv.c'))
    elif recv_lang == 'cpp':
        txt = gen_cpp_recv(defn)
        write_out(txt, os.path.join(args.out, base + '_recv.cpp'))
    else:
        txt = gen_python_recv(defn)
        write_out(txt, os.path.join(args.out, base + '_recv.py'))


if __name__ == '__main__':
    main()
