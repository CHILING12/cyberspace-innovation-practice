/**
 * aes.h — AES-128/256 实现
 *
 * 提供以下优化版本：
 *   V0: 基本标量，按 FIPS-197 逐轮实现
 *   V1: 循环展开、寄存器复用
 *   V2: T-table (Te0-Te3, Td0-Td3)
 *   V6: AES-NI / VAES 专用指令
 */

#ifndef AES_H
#define AES_H

#include "common.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ==========================================================================
 * AES 轮密钥结构
 * ========================================================================== */

#define AES128_NR 10
#define AES256_NR 14
#define AES_MAXNR 14
#define AES_BLOCKLEN 16

/* 轮密钥：Nr+1 个 128-bit 字 */
typedef struct {
    uint32_t rk[4 * (AES_MAXNR + 1)];
    int      rounds;
} aes_round_keys_t;

/* ==========================================================================
 * V0: 基本标量实现
 * ========================================================================== */

extern const cipher_vtable_t aes128_v0_vtable;
extern const cipher_vtable_t aes256_v0_vtable;

void aes128_key_schedule_v0(const uint8_t *key, void *round_keys);
void aes128_encrypt_block_v0(const void *rk, const uint8_t *in, uint8_t *out);
void aes128_decrypt_block_v0(const void *rk, const uint8_t *in, uint8_t *out);

/* ==========================================================================
 * V1: 循环展开 + 寄存器优化
 * ========================================================================== */

extern const cipher_vtable_t aes128_v1_vtable;
extern const cipher_vtable_t aes256_v1_vtable;

void aes128_encrypt_block_v1(const void *rk, const uint8_t *in, uint8_t *out);
void aes128_decrypt_block_v1(const void *rk, const uint8_t *in, uint8_t *out);

/* ==========================================================================
 * V2: T-table 实现
 * ========================================================================== */

extern const cipher_vtable_t aes128_v2_vtable;
extern const cipher_vtable_t aes256_v2_vtable;

/* 预计算的 T-table */
extern const uint32_t *Te0;
extern const uint32_t *Te1;
extern const uint32_t *Te2;
extern const uint32_t *Te3;
extern const uint32_t *Td0;
extern const uint32_t *Td1;
extern const uint32_t *Td2;
extern const uint32_t *Td3;

void aes128_encrypt_block_v2(const void *rk, const uint8_t *in, uint8_t *out);
void aes128_decrypt_block_v2(const void *rk, const uint8_t *in, uint8_t *out);

/* 1-table + 旋转变体（用于对比分析） */
void aes128_encrypt_block_v2_1table(const void *rk, const uint8_t *in, uint8_t *out);

/* 全轮展开变体 */
void aes128_encrypt_block_v2_unrolled(const void *rk, const uint8_t *in, uint8_t *out);

/* ==========================================================================
 * V6: AES-NI / VAES 专用指令
 * ========================================================================== */

extern const cipher_vtable_t aes128_v6_vtable;
extern const cipher_vtable_t aes256_v6_vtable;

/* 单分组 AES-NI */
void aes128_encrypt_block_v6(const void *rk, const uint8_t *in, uint8_t *out);
void aes128_decrypt_block_v6(const void *rk, const uint8_t *in, uint8_t *out);

/* 多分组 AES-NI（利用流水线） */
void aes128_encrypt_nblocks_v6(const void *rk,
                                const uint8_t *in, uint8_t *out, size_t n);

/* VAES-256 (AVX-512) 多分组 */
void aes128_encrypt_nblocks_vaes(const void *rk,
                                  const uint8_t *in, uint8_t *out, size_t n);

/* ==========================================================================
 * AES S-Box（公开，供其他模块验证使用）
 * ========================================================================== */

extern const uint8_t aes_sbox[256];
extern const uint8_t aes_inv_sbox[256];

#ifdef __cplusplus
}
#endif

#endif /* AES_H */
