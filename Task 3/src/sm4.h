/**
 * sm4.h — SM4 分组密码实现（GB/T 32907-2016）
 *
 * 提供以下优化版本：
 *   V0: 基本标量实现（S-Box 数组 + rotate/xor）
 *   V1: 循环展开、寄存器优化
 *   V2: T-table（四张 256 项 32-bit 表）
 */

#ifndef SM4_H
#define SM4_H

#include "common.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SM4_BLOCKLEN    16
#define SM4_KEYLEN      16
#define SM4_NR          32

/* SM4 轮密钥结构 */
typedef struct {
    uint32_t rk[SM4_NR];
} sm4_round_keys_t;

/* ==========================================================================
 * V0: 基本标量实现
 * ========================================================================== */

extern const cipher_vtable_t sm4_v0_vtable;

void sm4_key_schedule_v0(const uint8_t *key, void *round_keys);
void sm4_encrypt_block_v0(const void *rk, const uint8_t *in, uint8_t *out);
void sm4_decrypt_block_v0(const void *rk, const uint8_t *in, uint8_t *out);

/* SM4 S-Box */
extern const uint8_t sm4_sbox[256];

/* ==========================================================================
 * V1: 循环展开
 * ========================================================================== */

extern const cipher_vtable_t sm4_v1_vtable;

void sm4_encrypt_block_v1(const void *rk, const uint8_t *in, uint8_t *out);
void sm4_decrypt_block_v1(const void *rk, const uint8_t *in, uint8_t *out);

/* ==========================================================================
 * V2: T-table
 * ========================================================================== */

extern const cipher_vtable_t sm4_v2_vtable;

/* SM4 T-table: 4 张 256 项 32-bit 表 */
extern const uint32_t *SM4_T0;
extern const uint32_t *SM4_T1;
extern const uint32_t *SM4_T2;
extern const uint32_t *SM4_T3;

void sm4_encrypt_block_v2(const void *rk, const uint8_t *in, uint8_t *out);
void sm4_decrypt_block_v2(const void *rk, const uint8_t *in, uint8_t *out);

/* 1-table + rotate 变体 */
void sm4_encrypt_block_v2_1table(const void *rk, const uint8_t *in, uint8_t *out);

/* 四轮一组展开 */
void sm4_encrypt_block_v2_4x4(const void *rk, const uint8_t *in, uint8_t *out);

/* 多分组交错执行 */
void sm4_encrypt_nblocks_v2(const void *rk,
                             const uint8_t *in, uint8_t *out, size_t n);

#ifdef __cplusplus
}
#endif

#endif /* SM4_H */
