/**
 * twine.h — TWINE 轻量级分组密码实现
 *
 * TWINE: 64-bit 分组, 80/128-bit 密钥, 36 轮
 * 结构: 广义 Feistel (GFN) + 4-bit S-Box + block shuffle
 *
 * 优化版本:
 *   V0: 基本标量
 *   V2: T-table（组合 nibble 表）
 *   V3: SSSE3 PSHUFB shuffle（利用 block shuffle 结构）
 */

#ifndef TWINE_H
#define TWINE_H

#include "common.h"

#ifdef __cplusplus
extern "C" {
#endif

#define TWINE_BLOCKLEN      8
#define TWINE128_KEYLEN    16
#define TWINE80_KEYLEN     10
#define TWINE_NR            36

typedef struct {
    uint8_t rk[TWINE_NR * 2];   /* 每轮 2 字节轮密钥 */
} twine_round_keys_t;

/* TWINE 4-bit S-Box */
extern const uint8_t twine_sbox[16];

/* TWINE block shuffle 表（16 个 nibble 的置换） */
extern const uint8_t twine_shuffle[16];

/* ==========================================================================
 * V0: 基本标量实现
 * ========================================================================== */

extern const cipher_vtable_t twine128_v0_vtable;

void twine128_key_schedule_v0(const uint8_t *key, void *round_keys);
void twine128_encrypt_block_v0(const void *rk, const uint8_t *in, uint8_t *out);
void twine128_decrypt_block_v0(const void *rk, const uint8_t *in, uint8_t *out);

/* ==========================================================================
 * V2: T-table（组合 nibble 表）
 * ========================================================================== */

extern const cipher_vtable_t twine128_v2_vtable;

/* 256 项组合表：把 2 个 nibble 的 S-Box 结果合并成 1 个字节 */
extern const uint8_t twine_ttable[256];

void twine128_encrypt_block_v2(const void *rk, const uint8_t *in, uint8_t *out);
void twine128_decrypt_block_v2(const void *rk, const uint8_t *in, uint8_t *out);

/* ==========================================================================
 * V3: SSSE3 PSHUFB shuffle
 * ========================================================================== */

extern const cipher_vtable_t twine128_v3_vtable;

/* 使用 PSHUFB 做 16 个 nibble 的 S-Box + block shuffle */
void twine128_encrypt_block_v3(const void *rk, const uint8_t *in, uint8_t *out);

/* 多分组并行 (SoA 布局) */
void twine128_encrypt_nblocks_v3(const void *rk,
                                  const uint8_t *in, uint8_t *out, size_t n);

#ifdef __cplusplus
}
#endif

#endif /* TWINE_H */
