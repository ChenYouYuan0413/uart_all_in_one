#include <stdint.h>
#include <string.h>

static const int PACKET_SIZE = 20;

typedef struct {
    char aim[16];
    int32_t fire;
} WeaponPacket;

/* 简单示例 encode：将结构体按顺序复制到字节缓冲区（小端） */
void encode(const WeaponPacket *in, unsigned char *out) {
    unsigned char *p = out;
    memcpy(p, in->aim, 16); p += 16;
    memcpy(p, &in->fire, sizeof(int32_t)); p += sizeof(int32_t);
}

void decode(const unsigned char *in, WeaponPacket *out) {
    const unsigned char *p = in;
    memcpy(out->aim, p, 16); p += 16;
    memcpy(&out->fire, p, sizeof(int32_t)); p += sizeof(int32_t);
}