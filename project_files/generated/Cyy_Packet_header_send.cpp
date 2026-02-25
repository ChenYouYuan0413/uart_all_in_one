#include <cstdint>
#include <cstring>

static const int PACKET_SIZE = 12;
static const unsigned char PACKET_HEADER = 0xAA;
static const unsigned char PACKET_FOOTER = 0x55;

/* 计算简单 8-bit 校验和 */
static inline uint8_t send_Verify(const unsigned char *buf, int len) {
    uint32_t s = 0;
    for (int i = 0; i < len; ++i) s += buf[i];
    return (uint8_t)(s & 0xFF);
}

static inline int recive_Verify(const unsigned char *buf, int len) {
    if (len != PACKET_SIZE + 3) return 0;
    if (buf[0] != PACKET_HEADER) return 0;
    if (buf[len-1] != PACKET_FOOTER) return 0;
    uint8_t expect = buf[1 + PACKET_SIZE];
    return send_Verify(buf + 1, PACKET_SIZE) == expect;
}

typedef struct {
    float my;
    int32_t name;
    float target;
} Cyy_Packet_header;

void encode(const Cyy_Packet_header *in, unsigned char *out) {
    unsigned char *p = out;
    *p++ = PACKET_HEADER;
    memcpy(p, &in->my, sizeof(float)); p += sizeof(float);
    memcpy(p, &in->name, sizeof(int32_t)); p += sizeof(int32_t);
    memcpy(p, &in->target, sizeof(float)); p += sizeof(float);
    uint8_t checksum = send_Verify(out + 1, PACKET_SIZE);
    *p++ = checksum;
    *p++ = PACKET_FOOTER;
}

void decode(const unsigned char *in, Cyy_Packet_header *out) {
    const unsigned char *p = in + 1;
    memcpy(&out->my, p, sizeof(float)); p += sizeof(float);
    memcpy(&out->name, p, sizeof(int32_t)); p += sizeof(int32_t);
    memcpy(&out->target, p, sizeof(float)); p += sizeof(float);
}