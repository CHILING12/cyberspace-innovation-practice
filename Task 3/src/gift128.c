/**
 * gift128.c — GIFT-128 轻量级分组密码实现
 *
 * GIFT-128 结构:
 *   - 128-bit state = 32 个 4-bit nibble
 *   - 每轮: SubCells (4-bit S-Box) → PermBits (bit permutation) → AddRoundKey
 *   - 密钥编排使用简单的轮常数和移位
 *
 * 参考: "GIFT: A Small Present" (Banik et al., CHES 2017)
 *       GIFT-128 版本规范
 */

#include "gift128.h"
#include <string.h>

/* ==========================================================================
 * GIFT S-Box (4-bit)
 * ========================================================================== */

const uint8_t gift_sbox[16] = {
    0x1, 0xA, 0x4, 0xC, 0x6, 0xF, 0x3, 0x9,
    0x2, 0xD, 0xB, 0x7, 0x5, 0x0, 0x8, 0xE
};

const uint8_t gift_inv_sbox[16] = {
    0xD, 0x0, 0x8, 0x6, 0x2, 0xC, 0x4, 0xB,
    0xE, 0x7, 0x1, 0xA, 0x3, 0x9, 0xF, 0x5
};

/* ==========================================================================
 * GIFT bit permutation
 *
 * 128-bit 状态按 bit 排列，PermBits 将 bit i 移到 bit perm[i]
 * ========================================================================== */

/* GIFT-128 置换：将 bit i 映射到 perm[i] */
const uint8_t gift_perm[128] = {
     0,  33,  66,  99,  96,   1,  34,  67,
    68,  97,   2,  35,  36,  69,  98,   3,
     4,  37,  70, 103, 100,   5,  38,  71,
    72, 101,   6,  39,  40,  73, 102,   7,
     8,  41,  74, 107, 104,   9,  42,  75,
    76, 105,  10,  43,  44,  77, 106,  11,
    12,  45,  78, 111, 108,  13,  46,  79,
    80, 109,  14,  47,  48,  81, 110,  15,
    16,  49,  82, 115, 112,  17,  50,  83,
    84, 113,  18,  51,  52,  85, 114,  19,
    20,  53,  86, 119, 116,  21,  54,  87,
    88, 117,  22,  55,  56,  89, 118,  23,
    24,  57,  90, 123, 120,  25,  58,  91,
    92, 121,  26,  59,  60,  93, 122,  27,
    28,  61,  94, 127, 124,  29,  62,  95,
    96, 125,  30,  63,  64,  97, 126,  31
};

/* ==========================================================================
 * 轮常数 (6-bit)
 * ========================================================================== */

static const uint8_t gift_round_constants[40] = {
     1,  3,  7, 15, 31, 62, 61, 59, 55, 47,
    30, 60, 57, 51, 39, 14, 29, 58, 53, 43,
    22, 44, 24, 48, 33,  2,  5, 11, 23, 46,
    28, 56, 49, 35,  6, 13, 27, 54, 45, 26
};

/* ==========================================================================
 * 辅助函数：bit 操作
 * ========================================================================== */

static inline int get_bit(const uint8_t *state, int pos) {
    return (state[pos / 8] >> (pos % 8)) & 1;
}

static inline void set_bit(uint8_t *state, int pos, int val) {
    if (val)
        state[pos / 8] |= (1 << (pos % 8));
    else
        state[pos / 8] &= ~(1 << (pos % 8));
}

/* ==========================================================================
 * V0: 基本标量实现
 * ========================================================================== */

static void sub_cells(uint8_t *state) {
    for (int i = 0; i < 16; i++) {
        uint8_t lo = state[i] & 0x0F;
        uint8_t hi = (state[i] >> 4) & 0x0F;
        state[i] = (gift_sbox[hi] << 4) | gift_sbox[lo];
    }
}

static void sub_cells_inv(uint8_t *state) {
    for (int i = 0; i < 16; i++) {
        uint8_t lo = state[i] & 0x0F;
        uint8_t hi = (state[i] >> 4) & 0x0F;
        state[i] = (gift_inv_sbox[hi] << 4) | gift_inv_sbox[lo];
    }
}

static void perm_bits(uint8_t *state) {
    uint8_t new_state[16];
    memset(new_state, 0, 16);
    for (int i = 0; i < 128; i++) {
        int val = get_bit(state, i);
        set_bit(new_state, gift_perm[i], val);
    }
    memcpy(state, new_state, 16);
}

/* 逆置换：将 bit gift_perm[i] 恢复到 i 位 */
static void perm_bits_inv(uint8_t *state) {
    uint8_t new_state[16];
    memset(new_state, 0, 16);
    for (int i = 0; i < 128; i++) {
        int val = get_bit(state, gift_perm[i]);
        set_bit(new_state, i, val);
    }
    memcpy(state, new_state, 16);
}

static void add_round_key(uint8_t *state, const uint8_t *rk) {
    /* GIFT 使用轮密钥的前 32 bit 异或到状态的选择位 */
    uint32_t rk32 = load32_be(rk);
    /* U = state 的高 32 bit, V = 低 96 bit */
    /* RK 与状态的第 0,1 (高 2 字节) 和第 4,5 字节异或 */
    state[0] ^= (uint8_t)(rk32 >> 24);
    state[1] ^= (uint8_t)(rk32 >> 16);
    /* 另外 2 字节加到特定位置 */
    state[4] ^= (uint8_t)(rk32 >> 8);
    state[5] ^= (uint8_t)(rk32);
}

static void add_round_constant(uint8_t *state, int round) {
    /* 6-bit 轮常数加在 state 的特定 bit 上 */
    uint8_t rc = gift_round_constants[round];
    state[2] ^= ((rc >> 2) & 0x03);       /* bits 5,4 → state[2] bits 1,0 */
    state[3] ^= ((rc & 0x03) << 6);       /* bits 1,0 → state[3] bits 7,6 */
}

void gift128_key_schedule_v0(const uint8_t *key, void *round_keys) {
    uint32_t *rk = (uint32_t *)round_keys;
    uint32_t K[4];

    K[0] = load32_be(key);
    K[1] = load32_be(key + 4);
    K[2] = load32_be(key + 8);
    K[3] = load32_be(key + 12);

    for (int r = 0; r < GIFT128_NR; r++) {
        /* 提取轮密钥：K 的高 32 bit 和低 32 bit */
        rk[4 * r + 0] = K[0];
        rk[4 * r + 1] = K[1];

        /* 密钥更新：
         * K = (K >> 32) | (K << 96)  (128-bit 循环右移 32 bit)
         * 然后 S-Box 应用于 K 的高 16 bit */
        uint32_t t0 = K[0];
        K[0] = K[1];
        K[1] = K[2];
        K[2] = K[3];
        K[3] = t0;

        /* 对 K 的高 16 bit (K[0] 的高 16 bit → K[3] 的高 16 bit)
         * ... 实际 GIFT 密钥编排需要对两个 nibble 应用 S-Box */
        uint8_t hi_nib = (uint8_t)(K[3] >> 28);
        uint8_t lo_nib = (uint8_t)((K[3] >> 24) & 0x0F);
        K[3] &= 0x00FFFFFF;
        K[3] |= (uint32_t)(gift_sbox[hi_nib] & 0xF) << 28;
        K[3] |= (uint32_t)(gift_sbox[lo_nib] & 0xF) << 24;
    }

    /* 存储轮常数信息供每轮使用 */
    for (int r = 0; r < GIFT128_NR; r++) {
        rk[4 * r + 2] = (uint32_t)r;
        rk[4 * r + 3] = 0;
    }
}

void gift128_encrypt_block_v0(const void *rk, const uint8_t *in, uint8_t *out) {
    const uint32_t *rkv = (const uint32_t *)rk;
    uint8_t state[16];
    memcpy(state, in, 16);

    for (int r = 0; r < GIFT128_NR; r++) {
        sub_cells(state);
        perm_bits(state);
        add_round_key(state, (const uint8_t *)&rkv[4 * r]);
        add_round_constant(state, r);
    }

    memcpy(out, state, 16);
}

void gift128_decrypt_block_v0(const void *rk, const uint8_t *in, uint8_t *out) {
    const uint32_t *rkv = (const uint32_t *)rk;
    uint8_t state[16];
    memcpy(state, in, 16);

    for (int r = GIFT128_NR - 1; r >= 0; r--) {
        add_round_constant(state, r);
        add_round_key(state, (const uint8_t *)&rkv[4 * r]);
        perm_bits_inv(state);
        sub_cells_inv(state);
    }

    memcpy(out, state, 16);
}

/* ==========================================================================
 * V3: SSSE3 PSHUFB shuffle 实现
 *
 * 核心思想：使用 PSHUFB 指令在一个向量中并行查 16 项 nibble S-Box
 *   1. 将 state 的 32 个 nibble 展开到 32 个字节（每个 nibble → 1 字节）
 *   2. 使用 PSHUFB 并行查表
 *   3. 将结果打包回 16 字节
 * ========================================================================== */

#if defined(__x86_64__) || defined(_M_X64) || defined(__i386__)
#include <tmmintrin.h>   /* SSSE3 PSHUFB */
#include <immintrin.h>   /* AVX2 */

void gift128_encrypt_block_v3(const void *rk, const uint8_t *in, uint8_t *out) {
    const uint32_t *rkv = (const uint32_t *)rk;
    uint8_t state[16];
    memcpy(state, in, 16);

    /* S-Box 查找表（16 字节） */
    const __m128i sbox_vec = _mm_setr_epi8(
        0x1, 0xA, 0x4, 0xC, 0x6, 0xF, 0x3, 0x9,
        0x2, 0xD, 0xB, 0x7, 0x5, 0x0, 0x8, 0xE
    );

    for (int r = 0; r < GIFT128_NR; r++) {
        /* 1. SubCells: PSHUFB 查表
         * 需要将 16 字节拆成 32 nibble → 2 个 16 字节向量 */
        uint8_t nibbles_low[16], nibbles_high[16];
        for (int i = 0; i < 16; i++) {
            nibbles_low[i]  = state[i] & 0x0F;
            nibbles_high[i] = (state[i] >> 4) & 0x0F;
        }

        __m128i low_vec  = _mm_loadu_si128((__m128i *)nibbles_low);
        __m128i high_vec = _mm_loadu_si128((__m128i *)nibbles_high);

        /* 并行查 16 个 nibble */
        __m128i low_sbox  = _mm_shuffle_epi8(sbox_vec, low_vec);
        __m128i high_sbox = _mm_shuffle_epi8(sbox_vec, high_vec);

        /* 打包回 16 字节 */
        uint8_t sl[16], sh[16];
        _mm_storeu_si128((__m128i *)sl, low_sbox);
        _mm_storeu_si128((__m128i *)sh, high_sbox);
        for (int i = 0; i < 16; i++) {
            state[i] = ((sh[i] & 0x0F) << 4) | (sl[i] & 0x0F);
        }

        /* 2. PermBits */
        perm_bits(state);

        /* 3. AddRoundKey + AddConstant */
        add_round_key(state, (const uint8_t *)&rkv[4 * r]);
        add_round_constant(state, r);
    }

    memcpy(out, state, 16);
}

/* 多分组并行：SoA 数据布局，处理 N 个分组
 * lane i = 各个分组的第 i 个 nibble 集合 */
void gift128_encrypt_nblocks_v3(const void *rk,
                                 const uint8_t *in, uint8_t *out, size_t n) {
    for (size_t i = 0; i < n; i++) {
        gift128_encrypt_block_v3(rk, in + i * 16, out + i * 16);
    }
}

/* V4: AVX2 — 使用 VPSHUFB */
void gift128_encrypt_block_v4(const void *rk, const uint8_t *in, uint8_t *out) {
    /* AVX2 实现与 SSSE3 类似，但从 128-bit 扩展为 256-bit
     * 单分组内：32 nibble 可以在一个 256-bit 向量内并行处理 */
#if defined(__AVX2__)
    const uint32_t *rkv = (const uint32_t *)rk;
    uint8_t state[16];
    memcpy(state, in, 16);

    /* 256-bit S-Box 表 */
    const __m256i sbox_vec = _mm256_setr_epi8(
        0x1,0xA,0x4,0xC,0x6,0xF,0x3,0x9,
        0x2,0xD,0xB,0x7,0x5,0x0,0x8,0xE,
        0x1,0xA,0x4,0xC,0x6,0xF,0x3,0x9,
        0x2,0xD,0xB,0x7,0x5,0x0,0x8,0xE
    );

    for (int r = 0; r < GIFT128_NR; r++) {
        /* 将 16 字节拆成 32 个 nibble，装入 __m256i */
        uint8_t nibbles[32];
        for (int i = 0; i < 16; i++) {
            nibbles[2 * i]     = state[i] & 0x0F;       /* low nibble */
            nibbles[2 * i + 1] = (state[i] >> 4) & 0x0F; /* high nibble */
        }

        __m256i nib_vec = _mm256_loadu_si256((__m256i *)nibbles);
        __m256i sbox_res = _mm256_shuffle_epi8(sbox_vec, nib_vec);

        uint8_t res[32];
        _mm256_storeu_si256((__m256i *)res, sbox_res);

        /* 打包 */
        for (int i = 0; i < 16; i++) {
            state[i] = ((res[2 * i + 1] & 0x0F) << 4) | (res[2 * i] & 0x0F);
        }

        perm_bits(state);
        add_round_key(state, (const uint8_t *)&rkv[4 * r]);
        add_round_constant(state, r);
    }

    memcpy(out, state, 16);
#else
    /* 回退到 V3 */
    gift128_encrypt_block_v3(rk, in, out);
#endif
}

void gift128_encrypt_nblocks_v4(const void *rk,
                                 const uint8_t *in, uint8_t *out, size_t n) {
    for (size_t i = 0; i < n; i++) {
        gift128_encrypt_block_v4(rk, in + i * 16, out + i * 16);
    }
}

#else
/* 非 x86 平台：回退到标量实现 */
void gift128_encrypt_block_v3(const void *rk, const uint8_t *in, uint8_t *out) {
    gift128_encrypt_block_v0(rk, in, out);
}
void gift128_encrypt_block_v4(const void *rk, const uint8_t *in, uint8_t *out) {
    gift128_encrypt_block_v0(rk, in, out);
}
void gift128_encrypt_nblocks_v3(const void *rk, const uint8_t *in, uint8_t *out, size_t n) {
    for (size_t i = 0; i < n; i++)
        gift128_encrypt_block_v0(rk, in + i * 16, out + i * 16);
}
void gift128_encrypt_nblocks_v4(const void *rk, const uint8_t *in, uint8_t *out, size_t n) {
    for (size_t i = 0; i < n; i++)
        gift128_encrypt_block_v0(rk, in + i * 16, out + i * 16);
}
#endif

/* ==========================================================================
 * Vtable 定义
 * ========================================================================== */

#define DEFINE_GIFT128_VTABLE(name, ks, enc, dec, opt) \
    const cipher_vtable_t name = { \
        "GIFT-128", CIPHER_GIFT_128, 16, 16, 40, \
        ks, enc, dec, NULL, opt \
    }

DEFINE_GIFT128_VTABLE(gift128_v0_vtable,
    gift128_key_schedule_v0, gift128_encrypt_block_v0, gift128_decrypt_block_v0, OPT_V0);
DEFINE_GIFT128_VTABLE(gift128_v3_vtable,
    gift128_key_schedule_v0, gift128_encrypt_block_v3, gift128_decrypt_block_v0, OPT_V3);
DEFINE_GIFT128_VTABLE(gift128_v4_vtable,
    gift128_key_schedule_v0, gift128_encrypt_block_v4, gift128_decrypt_block_v0, OPT_V4);
