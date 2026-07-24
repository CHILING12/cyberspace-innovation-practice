/**
 * modes.h — CTR / GCM / XTS 工作模式实现
 *
 * 模式优化层次：
 *   M0: 基本模式
 *   M1: 多分组 CTR
 *   M2: 查表 GHASH
 *   M3: CLMUL/PMULL GHASH
 *   M4: 多块折叠 GCM
 *   M5: 密码轮与 GHASH 融合（指令交织）
 *   M6: 向量化 XTS tweak
 */

#ifndef MODES_H
#define MODES_H

#include "common.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ==========================================================================
 * CTR 模式
 * ========================================================================== */

/**
 * CTR M0: 基本逐块实现
 */
void ctr_crypt_m0(const cipher_ctx_t *ctx,
                  const uint8_t *nonce, size_t nonce_len,
                  uint32_t counter_init,
                  const uint8_t *in, uint8_t *out, size_t len);

/**
 * CTR M1: 多分组并行（一次构造 4/8/16 个 counter）
 */
void ctr_crypt_m1(const cipher_ctx_t *ctx,
                  const uint8_t *nonce, size_t nonce_len,
                  uint32_t counter_init,
                  const uint8_t *in, uint8_t *out, size_t len);

/* ==========================================================================
 * GCM 模式
 * ========================================================================== */

/**
 * GCM M0: 基本 CTR + bit-by-bit GHASH
 */
void gcm_encrypt_m0(const cipher_ctx_t *ctx,
                     const uint8_t *nonce, size_t nonce_len,
                     const uint8_t *aad, size_t aad_len,
                     const uint8_t *plaintext, size_t pt_len,
                     uint8_t *ciphertext, uint8_t *tag);

int gcm_decrypt_m0(const cipher_ctx_t *ctx,
                    const uint8_t *nonce, size_t nonce_len,
                    const uint8_t *aad, size_t aad_len,
                    const uint8_t *ciphertext, size_t ct_len,
                    const uint8_t *tag,
                    uint8_t *plaintext);

/**
 * GCM M2: 8-bit 查表 GHASH
 */
void gcm_encrypt_m2(const cipher_ctx_t *ctx,
                     const uint8_t *nonce, size_t nonce_len,
                     const uint8_t *aad, size_t aad_len,
                     const uint8_t *plaintext, size_t pt_len,
                     uint8_t *ciphertext, uint8_t *tag);

/**
 * GCM M3: PCLMULQDQ GHASH
 */
void gcm_encrypt_m3(const cipher_ctx_t *ctx,
                     const uint8_t *nonce, size_t nonce_len,
                     const uint8_t *aad, size_t aad_len,
                     const uint8_t *plaintext, size_t pt_len,
                     uint8_t *ciphertext, uint8_t *tag);

/**
 * GCM M4: 4-block / 8-block folding
 */
void gcm_encrypt_m4(const cipher_ctx_t *ctx,
                     const uint8_t *nonce, size_t nonce_len,
                     const uint8_t *aad, size_t aad_len,
                     const uint8_t *plaintext, size_t pt_len,
                     uint8_t *ciphertext, uint8_t *tag);

/**
 * GCM M5: AES 轮与 GHASH 指令交织
 */
void gcm_encrypt_m5(const cipher_ctx_t *ctx,
                     const uint8_t *nonce, size_t nonce_len,
                     const uint8_t *aad, size_t aad_len,
                     const uint8_t *plaintext, size_t pt_len,
                     uint8_t *ciphertext, uint8_t *tag);

/* ==========================================================================
 * XTS 模式
 * ========================================================================== */

/**
 * XTS M0: 基本实现
 */
void xts_encrypt_m0(const cipher_ctx_t *ctx1, const cipher_ctx_t *ctx2,
                     const uint8_t *tweak,
                     const uint8_t *in, uint8_t *out, size_t len);

void xts_decrypt_m0(const cipher_ctx_t *ctx1, const cipher_ctx_t *ctx2,
                     const uint8_t *tweak,
                     const uint8_t *in, uint8_t *out, size_t len);

/**
 * XTS M6: 向量化 tweak 生成 + 多分组并行
 */
void xts_encrypt_m6(const cipher_ctx_t *ctx1, const cipher_ctx_t *ctx2,
                     const uint8_t *tweak,
                     const uint8_t *in, uint8_t *out, size_t len);

void xts_decrypt_m6(const cipher_ctx_t *ctx1, const cipher_ctx_t *ctx2,
                     const uint8_t *tweak,
                     const uint8_t *in, uint8_t *out, size_t len);

#ifdef __cplusplus
}
#endif

#endif /* MODES_H */
