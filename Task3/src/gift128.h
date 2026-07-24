/**
 * gift128.h — GIFT-128 轻量级分组密码实现
 *
 * GIFT-128: 128-bit 分组, 128-bit 密钥, 40 轮
 * 结构: 基于 SPN + 4-bit S-Box + bit permutation
 *
 * 优化版本:
 *   V0: 基本标量（逐 nibble 操作）
 *   V3: SSSE3 PSHUFB shuffle（16 nibble 并行 S-Box）
 *   V4: AVX2 VPSHUFB（32 nibble 并行 S-Box, 多分组）
 */

#ifndef GIFT128_H
#define GIFT128_H

#include "common.h"

#ifdef __cplusplus
extern "C" {
#endif

#define GIFT128_BLOCKLEN   16
#define GIFT128_KEYLEN     16
#define GIFT128_NR          40

typedef struct {
    uint32_t rk[4 * GIFT128_NR];  /* 每轮 4 个 32-bit 轮密钥字 */
} gift128_round_keys_t;

/* GIFT 4-bit S-Box */
extern const uint8_t gift_sbox[16];
extern const uint8_t gift_inv_sbox[16];

/* GIFT bit permutation */
extern const uint8_t gift_perm[128];

/* ==========================================================================
 * V0: 基本标量实现
 * ========================================================================== */

extern const cipher_vtable_t gift128_v0_vtable;

void gift128_key_schedule_v0(const uint8_t *key, void *round_keys);
void gift128_encrypt_block_v0(const void *rk, const uint8_t *in, uint8_t *out);
void gift128_decrypt_block_v0(const void *rk, const uint8_t *in, uint8_t *out);

/* ==========================================================================
 * V3: SSSE3 PSHUFB shuffle
 * ========================================================================== */

extern const cipher_vtable_t gift128_v3_vtable;

/* 单分组内并行：16 nibble 同时查表 */
void gift128_encrypt_block_v3(const void *rk, const uint8_t *in, uint8_t *out);

/* 多分组并行 (SoA): 处理 8/16 个独立分组 */
void gift128_encrypt_nblocks_v3(const void *rk,
                                 const uint8_t *in, uint8_t *out, size_t n);

/* ==========================================================================
 * V4: AVX2 VPSHUFB (32 nibble 并行)
 * ========================================================================== */

extern const cipher_vtable_t gift128_v4_vtable;

void gift128_encrypt_block_v4(const void *rk, const uint8_t *in, uint8_t *out);
void gift128_encrypt_nblocks_v4(const void *rk,
                                 const uint8_t *in, uint8_t *out, size_t n);

#ifdef __cplusplus
}
#endif

#endif /* GIFT128_H */
