#include <stdint.h>
#include <string.h>

static const int PACKET_SIZE = 12;
static const unsigned char PACKET_HEADER = 0xAA;
static const unsigned char PACKET_FOOTER = 0x55;

/* 计算简单 8-bit 校验和 */
static inline uint8_t send_Verify(const unsigned char *buf, int len) {
    uint32_t s = 0;
    for (int i = 0; i < len; ++i) s += buf[i];
    return (uint8_t)(s & 0xFF);
}

typedef struct {
    float my;
    int32_t name;
    float target;
} CyyPacket_header;

void encode(const CyyPacket_header *in, unsigned char *out) {
    unsigned char *p = out;
    *p++ = PACKET_HEADER;
    memcpy(p, &in->my, sizeof(float)); p += sizeof(float);
    memcpy(p, &in->name, sizeof(int32_t)); p += sizeof(int32_t);
    memcpy(p, &in->target, sizeof(float)); p += sizeof(float);
    uint8_t checksum = send_Verify(out + 1, PACKET_SIZE);
    *p++ = checksum;
    *p++ = PACKET_FOOTER;
}