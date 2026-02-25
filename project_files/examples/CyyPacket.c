#include <stdint.h>
#include <string.h>
#include <stddef.h>

static const int PACKET_SIZE = 12;
static const unsigned char PACKET_HEADER = 0xAA;
static const unsigned char PACKET_FOOTER = 0x55;
static const int PACKET_TOTAL_SIZE = PACKET_SIZE + 3; /* header + payload + checksum + footer */

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
} CyyPacket;

/* encode -> 写入完整包：header + payload + checksum + footer */
void encode(const CyyPacket *in, unsigned char *out) {
    /* out 缓冲区至少为 PACKET_TOTAL_SIZE 字节 */
    unsigned char *p = out;
    *p++ = PACKET_HEADER;
    memcpy(p, &in->my, sizeof(float)); p += sizeof(float);
    memcpy(p, &in->name, sizeof(int32_t)); p += sizeof(int32_t);
    memcpy(p, &in->target, sizeof(float)); p += sizeof(float);
    /* 计算 payload 校验 */
    uint8_t checksum = send_Verify(out + 1, PACKET_SIZE);
    *p++ = checksum;
    *p++ = PACKET_FOOTER;
}

/* decode -> 输入完整包：检查 header/footer/checksum 后解析 payload */
int recive_Verify(const unsigned char *buf, int len) {
    if (len != PACKET_TOTAL_SIZE) return 0;
    if (buf[0] != PACKET_HEADER) return 0;
    if (buf[len-1] != PACKET_FOOTER) return 0;
    uint8_t expect = buf[1 + PACKET_SIZE];
    return send_Verify(buf + 1, PACKET_SIZE) == expect;
}

void decode(const unsigned char *in, CyyPacket *out) {
    /* 假设已通过 recive_Verify */
    const unsigned char *p = in + 1; /* skip header */
    memcpy(&out->my, p, sizeof(float)); p += sizeof(float);
    memcpy(&out->name, p, sizeof(int32_t)); p += sizeof(int32_t);
    memcpy(&out->target, p, sizeof(float)); p += sizeof(float);
}