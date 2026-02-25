import struct
PACKET_SIZE = 12
PACKET_HEADER = 0xAA
PACKET_FOOTER = 0x55
PACKET_TOTAL_SIZE = PACKET_SIZE + 3
FMT = '<fif'
def recive_Verify(buf):
    if len(buf) != PACKET_TOTAL_SIZE:
        return False
    if buf[0] != PACKET_HEADER or buf[-1] != PACKET_FOOTER:
        return False
    payload = buf[1:1+PACKET_SIZE]
    checksum = buf[1+PACKET_SIZE]
    return (sum(payload) & 0xFF) == checksum

def decode(buf):
    if len(buf) != PACKET_TOTAL_SIZE:
        raise ValueError('buffer size mismatch')
    payload = buf[1:1+PACKET_SIZE]
    vals = struct.unpack(FMT, payload)
    obj = {}
    obj['my'] = vals[0]
    obj['name'] = vals[1]
    obj['target'] = vals[2]
    return obj