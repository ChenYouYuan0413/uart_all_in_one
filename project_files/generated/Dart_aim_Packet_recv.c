#include <stdint.h>
#include <string.h>

static const int PACKET_SIZE = 16;
static const unsigned char PACKET_HEADER = 0xAA;
static const unsigned char PACKET_FOOTER = 0x55;

/* 计算简单 8-bit 校验和 */
static inline uint8_t send_Verify(const unsigned char *buf, int len) {
    uint32_t s = 0;
    for (int i = 0; i < len; ++i) s += buf[i];
    return (uint8_t)(s & 0xFF);
}

int recive_Verify(const unsigned char *buf, int len) {
    if (len != PACKET_SIZE + 3) return 0;
    if (buf[0] != PACKET_HEADER) return 0;
    if (buf[len-1] != PACKET_FOOTER) return 0;
    uint8_t expect = buf[1 + PACKET_SIZE];
    return send_Verify(buf + 1, PACKET_SIZE) == expect;
}

typedef struct {
    float err_of_pix;
    float keep_1;
    float keep_2;
    float keep_3;
} Dart_aim_Packet;

void decode(const unsigned char *in, Dart_aim_Packet *out) {
    const unsigned char *p = in + 1;
    memcpy(&out->err_of_pix, p, sizeof(float)); p += sizeof(float);
    memcpy(&out->keep_1, p, sizeof(float)); p += sizeof(float);
    memcpy(&out->keep_2, p, sizeof(float)); p += sizeof(float);
    memcpy(&out->keep_3, p, sizeof(float)); p += sizeof(float);
}

void encode(const Dart_aim_Packet *in, unsigned char *out) {
    unsigned char *p = out;
    *p++ = PACKET_HEADER;
    memcpy(p, &in->err_of_pix, sizeof(float)); p += sizeof(float);
    memcpy(p, &in->keep_1, sizeof(float)); p += sizeof(float);
    memcpy(p, &in->keep_2, sizeof(float)); p += sizeof(float);
    memcpy(p, &in->keep_3, sizeof(float)); p += sizeof(float);
    uint8_t checksum = send_Verify(out + 1, PACKET_SIZE);
    *p++ = checksum;
    *p++ = PACKET_FOOTER;
}