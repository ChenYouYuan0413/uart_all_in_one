import struct
PACKET_SIZE = 16
PACKET_HEADER_LEN = 2
PACKET_HEADER = 0xa5ff
PACKET_FOOTER_LEN = 2
PACKET_FOOTER = 0xffbb
PACKET_DATA_LEN_ENABLED = 1
PACKET_TOTAL_SIZE = 22
FMT = '<ffff'
def send_Verify(buf):
    crc = 0
    for b in buf:
        crc ^= b
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
        crc &= 0xFFFF
    return crc & 0xFF

def encode(obj):
    payload = struct.pack(FMT, obj['err_of_pix'], obj['keep_1'], obj['keep_2'], obj['keep_3'])
    if len(payload) != PACKET_SIZE:
        raise ValueError('packed size mismatch')
    checksum = send_Verify(payload)
    header_bytes = bytes([(PACKET_HEADER >> 8) & 0xFF, (PACKET_HEADER >> 0) & 0xFF])
    data_len_bytes = bytes([PACKET_SIZE])
    footer_bytes = bytes([(PACKET_FOOTER >> 8) & 0xFF, (PACKET_FOOTER >> 0) & 0xFF])
    return header_bytes + data_len_bytes + payload + bytes([checksum]) + footer_bytes

def recive_Verify(buf):
    if len(buf) != PACKET_TOTAL_SIZE:
        return False
    if buf[0] != (PACKET_HEADER >> 8):
    if buf[len - 2] != (PACKET_FOOTER >> 8):
        return False
    payload = buf[3:3+PACKET_SIZE]
    checksum = buf[19]
    return send_Verify(payload) == checksum

def decode(buf):
    if len(buf) != PACKET_TOTAL_SIZE:
        raise ValueError('buffer size mismatch')
    payload = buf[3:3+PACKET_SIZE]
    vals = struct.unpack(FMT, payload)
    obj = {}
    obj['err_of_pix'] = vals[0]
    obj['keep_1'] = vals[1]
    obj['keep_2'] = vals[2]
    obj['keep_3'] = vals[3]
    return obj