/**
 * common.h — 对称密码算法软件实现：统一接口与公共定义
 *
 * 本文件定义所有密码算法和模式的统一接口，支持：
 *   - 分组密码：AES-128/256、SM4、GIFT-128、TWINE-128
 *   - 优化层次：V0（标量）→ V6（专用指令）
 *   - 工作模式：CTR、GCM、XTS（M0 → M6）
 */

#ifndef COMMON_H
#define COMMON_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ==========================================================================
 * 基本类型与常量
 * ========================================================================== */

#define AES_BLOCK_SIZE      16
#define SM4_BLOCK_SIZE      16
#define GIFT128_BLOCK_SIZE  16
#define TWINE_BLOCK_SIZE     8

#define AES128_KEY_SIZE     16
#define AES256_KEY_SIZE     32
#define SM4_KEY_SIZE        16
#define GIFT128_KEY_SIZE    16
#define TWINE128_KEY_SIZE   16
#define TWINE80_KEY_SIZE    10

#define AES128_ROUNDS       10
#define AES256_ROUNDS       14
#define SM4_ROUNDS          32
#define GIFT128_ROUNDS      40
#define TWINE_ROUNDS        36

/* 最大轮密钥空间 */
#define MAX_ROUND_KEYS      32
#define MAX_ROUND_KEY_SIZE   (MAX_ROUND_KEYS * 16)

/* ==========================================================================
 * 密码算法上下文（统一接口）
 * ========================================================================== */

/**
 * 密码算法标识
 */
typedef enum {
    CIPHER_AES_128 = 0,
    CIPHER_AES_256,
    CIPHER_SM4,
    CIPHER_GIFT_128,
    CIPHER_TWINE_128,
    CIPHER_TWINE_80,
    CIPHER_COUNT
} cipher_id_t;

/**
 * 优化版本标识
 * V0: 基本标量参考实现
 * V1: 标量循环展开、寄存器优化
 * V2: T-table
 * V3: SSSE3/NEON shuffle
 * V4: AVX2 多分组 shuffle/bitslice
 * V5: AVX-512 shuffle/GFNI
 * V6: AES-NI、VAES、SM4E 等专用密码指令
 */
typedef enum {
    OPT_V0 = 0,  /* 基本标量 */
    OPT_V1 = 1,  /* 循环展开 */
    OPT_V2 = 2,  /* T-table */
    OPT_V3 = 3,  /* SSSE3 shuffle */
    OPT_V4 = 4,  /* AVX2 shuffle/bitslice */
    OPT_V5 = 5,  /* AVX-512 */
    OPT_V6 = 6,  /* 专用指令 (AES-NI/VAES) */
    OPT_COUNT
} opt_level_t;

/**
 * 工作模式标识
 * M0: 基本模式
 * M1: 多分组 CTR
 * M2: 查表 GHASH
 * M3: CLMUL/PMULL GHASH
 * M4: 多块折叠 GCM
 * M5: 密码轮与 GHASH 融合
 * M6: 向量化 XTS tweak
 */
typedef enum {
    MODE_M0 = 0,  /* 基本模式 */
    MODE_M1 = 1,  /* 多分组并行 */
    MODE_M2 = 2,  /* 查表 GHASH */
    MODE_M3 = 3,  /* CLMUL GHASH */
    MODE_M4 = 4,  /* 多块折叠 */
    MODE_M5 = 5,  /* 交织融合 */
    MODE_M6 = 6,  /* 向量化 tweak */
    MODE_COUNT
} mode_level_t;

/* ==========================================================================
 * 分组密码抽象接口
 * ========================================================================== */

/**
 * 轮密钥结构（前向声明）
 */
struct cipher_ctx;

/**
 * 分组密码虚函数表
 */
typedef struct {
    const char *name;
    cipher_id_t id;
    size_t      block_size;
    size_t      key_size;
    int         rounds;

    /* 密钥编排 */
    void (*key_schedule)(const uint8_t *key, void *round_keys);

    /* 分组加密 / 解密 */
    void (*encrypt_block)(const void *round_keys, const uint8_t *in, uint8_t *out);
    void (*decrypt_block)(const void *round_keys, const uint8_t *in, uint8_t *out);

    /* 多分组加密（用于 CTR 批量处理） */
    void (*encrypt_nblocks)(const void *round_keys,
                            const uint8_t *in, uint8_t *out, size_t n);

    /* 优化级别 */
    opt_level_t opt_level;
} cipher_vtable_t;

/**
 * 通用密码上下文 —— 组合 vtable 与轮密钥
 */
typedef struct cipher_ctx {
    const cipher_vtable_t *vtable;
    uint8_t                round_keys[MAX_ROUND_KEY_SIZE];
    size_t                 round_key_size;
} cipher_ctx_t;

/* 便利宏 */
#define cipher_block_size(ctx)  ((ctx)->vtable->block_size)
#define cipher_name(ctx)        ((ctx)->vtable->name)
#define cipher_rounds(ctx)      ((ctx)->vtable->rounds)

static inline void cipher_key_schedule(cipher_ctx_t *ctx, const uint8_t *key) {
    ctx->vtable->key_schedule(key, ctx->round_keys);
}

static inline void cipher_encrypt_block(const cipher_ctx_t *ctx,
                                         const uint8_t *in, uint8_t *out) {
    ctx->vtable->encrypt_block(ctx->round_keys, in, out);
}

static inline void cipher_decrypt_block(const cipher_ctx_t *ctx,
                                         const uint8_t *in, uint8_t *out) {
    ctx->vtable->decrypt_block(ctx->round_keys, in, out);
}

/* ==========================================================================
 * 工作模式接口
 * ========================================================================== */

/* ---- CTR 模式 ---- */

/**
 * CTR 模式加密（同时也是解密）
 *
 * @param ctx         已初始化的密码上下文
 * @param nonce       nonce（大小等于 block_size / 2）
 * @param nonce_len   nonce 长度（字节）
 * @param counter_init 初始计数器值（通常为 0 或 1）
 * @param in          明文/密文输入
 * @param out         密文/明文输出
 * @param len         数据长度（字节）
 * @param mode        模式优化级别
 */
void ctr_crypt(const cipher_ctx_t *ctx,
               const uint8_t *nonce, size_t nonce_len,
               uint32_t counter_init,
               const uint8_t *in, uint8_t *out, size_t len,
               mode_level_t mode);

/**
 * CTR 多消息批量处理（multi-buffer）
 */
void ctr_crypt_multi(const cipher_ctx_t *ctx,
                     const uint8_t **nonces, size_t nonce_len,
                     const uint8_t **in, uint8_t **out,
                     const size_t *lens, size_t n_msgs,
                     mode_level_t mode);

/* ---- GCM 模式 ---- */

#define GCM_BLOCK_SIZE      16
#define GCM_TAG_SIZE        16
#define GCM_DEFAULT_TAG_LEN 16

/**
 * GCM 认证加密
 *
 * @param ctx         已初始化的密码上下文
 * @param key         GHASH 密钥 H = E_K(0^128)（内部计算）
 * @param nonce       nonce（推荐 96 bit / 12 字节）
 * @param nonce_len   nonce 长度
 * @param aad         附加认证数据
 * @param aad_len     AAD 长度
 * @param plaintext   明文
 * @param pt_len      明文长度
 * @param ciphertext  密文输出（可与 plaintext 相同，原地加密）
 * @param tag         认证标签输出（16 字节）
 * @param mode        模式优化级别
 */
void gcm_encrypt(const cipher_ctx_t *ctx,
                 const uint8_t *nonce, size_t nonce_len,
                 const uint8_t *aad, size_t aad_len,
                 const uint8_t *plaintext, size_t pt_len,
                 uint8_t *ciphertext, uint8_t *tag,
                 mode_level_t mode);

/**
 * GCM 认证解密
 *
 * @return 0 表示认证成功，-1 表示标签不匹配
 */
int gcm_decrypt(const cipher_ctx_t *ctx,
                const uint8_t *nonce, size_t nonce_len,
                const uint8_t *aad, size_t aad_len,
                const uint8_t *ciphertext, size_t ct_len,
                const uint8_t *tag,
                uint8_t *plaintext,
                mode_level_t mode);

/* ---- XTS 模式 ---- */

#define XTS_BLOCK_SIZE  16
#define XTS_TWEAK_SIZE  16

/**
 * XTS-AES 加密
 *
 * @param ctx1        数据加密密钥 K1 的上下文
 * @param ctx2        tweak 加密密钥 K2 的上下文
 * @param tweak       16 字节 tweak 值
 * @param in          明文输入
 * @param out         密文输出
 * @param len         数据长度（字节，>= 16）
 * @param mode        模式优化级别
 */
void xts_encrypt(const cipher_ctx_t *ctx1, const cipher_ctx_t *ctx2,
                 const uint8_t *tweak,
                 const uint8_t *in, uint8_t *out, size_t len,
                 mode_level_t mode);

/**
 * XTS-AES 解密
 */
void xts_decrypt(const cipher_ctx_t *ctx1, const cipher_ctx_t *ctx2,
                 const uint8_t *tweak,
                 const uint8_t *in, uint8_t *out, size_t len,
                 mode_level_t mode);

/* ==========================================================================
 * GF(2^128) 乘法（用于 GHASH）
 * ========================================================================== */

/**
 * GF(2^128) 乘法：Z = X * Y  (mod x^128 + x^7 + x^2 + x + 1)
 * 基本位移实现
 */
void gf128_mul_basic(uint8_t *z, const uint8_t *x, const uint8_t *y);

/**
 * GF(2^128) 乘法：4-bit 查表
 */
void gf128_mul_table4(uint8_t *z, const uint8_t *x, const uint8_t *y);

/**
 * GF(2^128) 乘法：8-bit 查表
 */
void gf128_mul_table8(uint8_t *z, const uint8_t *x, const uint8_t *y);

/* ---- PCLMULQDQ / VPCLMULQDQ 加速 (x86) ---- */
#if defined(__x86_64__) || defined(_M_X64) || defined(__i386__)
/**
 * 使用 PCLMULQDQ 的 GF(2^128) 乘法
 * 需要 CPU 支持 PCLMULQDQ 指令
 */
void gf128_mul_pclmul(uint8_t *z, const uint8_t *x, const uint8_t *y);

/**
 * 4-block folding GHASH 使用 VPCLMULQDQ
 */
void ghash_4block_folding(uint8_t *y, const uint8_t *h,
                           const uint8_t *data, size_t n_blocks);

/**
 * 8-block folding GHASH 使用 VPCLMULQDQ
 */
void ghash_8block_folding(uint8_t *y, const uint8_t *h,
                           const uint8_t *data, size_t n_blocks);
#endif

/* ==========================================================================
 * 辅助工具函数
 * ========================================================================== */

/* 字节序转换 */
static inline uint32_t load32_be(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] <<  8) |  (uint32_t)p[3];
}

static inline uint32_t load32_le(const uint8_t *p) {
    return ((uint32_t)p[3] << 24) | ((uint32_t)p[2] << 16) |
           ((uint32_t)p[1] <<  8) |  (uint32_t)p[0];
}

static inline void store32_be(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >>  8);
    p[3] = (uint8_t)(v);
}

static inline void store32_le(uint8_t *p, uint32_t v) {
    p[3] = (uint8_t)(v >> 24);
    p[2] = (uint8_t)(v >> 16);
    p[1] = (uint8_t)(v >>  8);
    p[0] = (uint8_t)(v);
}

static inline uint64_t load64_be(const uint8_t *p) {
    return ((uint64_t)load32_be(p) << 32) | load32_be(p + 4);
}

static inline void store64_be(uint8_t *p, uint64_t v) {
    store32_be(p,     (uint32_t)(v >> 32));
    store32_be(p + 4, (uint32_t)(v));
}

/* XOR n 字节 */
static inline void xor_bytes(uint8_t *dst, const uint8_t *a, const uint8_t *b, size_t n) {
    for (size_t i = 0; i < n; i++) dst[i] = a[i] ^ b[i];
}

static inline void xor_bytes_inplace(uint8_t *dst, const uint8_t *src, size_t n) {
    for (size_t i = 0; i < n; i++) dst[i] ^= src[i];
}

/* 左移 1 bit（用于 XTS tweak 的 GF(2^128) 乘法（α = 2）） */
static inline void gf128_dbl(uint8_t *out, const uint8_t *in) {
    uint8_t carry = 0;
    for (int i = 15; i >= 0; i--) {
        uint8_t b = in[i];
        out[i] = (uint8_t)((b << 1) | carry);
        carry = (uint8_t)(b >> 7);
    }
    if (carry) {
        out[15] ^= 0x87;  /* 不可约多项式 x^128 + x^7 + x^2 + x + 1 */
    }
}

/* 右移 1 bit */
static inline void gf128_shr(uint8_t *out, const uint8_t *in) {
    uint8_t carry = 0;
    for (int i = 0; i < 16; i++) {
        uint8_t b = in[i];
        out[i] = (uint8_t)((b >> 1) | (carry << 7));
        carry = (uint8_t)(b & 1);
    }
}

/* 递增计数器（大端序） */
static inline void ctr_increment_be(uint8_t *counter, size_t len) {
    for (size_t i = len; i > 0; i--) {
        if (++counter[i - 1] != 0) break;
    }
}

/* ==========================================================================
 * SIMD 与 CPU 特性检测
 * ========================================================================== */

typedef enum {
    CPU_FEAT_SSSE3    = (1 << 0),
    CPU_FEAT_AESNI    = (1 << 1),
    CPU_FEAT_PCLMUL   = (1 << 2),
    CPU_FEAT_AVX      = (1 << 3),
    CPU_FEAT_AVX2     = (1 << 4),
    CPU_FEAT_AVX512F  = (1 << 5),
    CPU_FEAT_VAES     = (1 << 6),
    CPU_FEAT_VPCLMUL  = (1 << 7),
    CPU_FEAT_GFNI     = (1 << 8),
    CPU_FEAT_NEON     = (1 << 9),
    CPU_FEAT_ARM_AES  = (1 << 10),
    CPU_FEAT_PMULL    = (1 << 11),
} cpu_feature_t;

/**
 * 检测 CPU 特性
 */
int cpu_has_feature(cpu_feature_t feature);
void cpu_detect_features(void);
void cpu_print_features(void);

#ifdef __cplusplus
}
#endif

#endif /* COMMON_H */
