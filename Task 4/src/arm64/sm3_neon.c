/**
 * sm3_neon.c — Hybrid SM3 compress for ARM64 NEON
 *
 * =====================================================================
 * Hybrid split (same assignment model as x86 AVX2/AVX512)
 * =====================================================================
 *
 *   [NEON / SIMD  128-bit = 4 x u32]
 *     - 64-byte block load + per-dword big-endian byte swap (vrev32)
 *     - Message expansion W[16..67] with 3-wide vector ILP
 *       (W[j] depends on W[j-3]; at most 3 consecutive new words)
 *     - Bulk W'[0..63] = W[j] ^ W[j+4] as 4-lane XOR loops
 *
 *   [GPR / general-purpose 32-bit regs]
 *     - 64 compression rounds A..H via sm3_compress_rounds_gpr_wp()
 *       (identical core to ref / x86 hybrids — bit-identical digests)
 *
 * Built only when targeting ARM64 (see CMakeLists.txt). On ARMv8-A
 * 64-bit, NEON is a baseline feature — sm3_cpu_has_neon() returns 1.
 *
 * Not using ARMv8.2-SM crypto extensions (sm3ss1 / sm3tt*) so the path
 * stays a pure software SIMD+GPR mix, matching the course requirement.
 */
#include "sm3_internal.h"

#if defined(__aarch64__) || defined(_M_ARM64)

#include <arm_neon.h>
#include <string.h>

#if defined(_MSC_VER)
#  define SM3_ALIGN16 __declspec(align(16))
#else
#  define SM3_ALIGN16 __attribute__((aligned(16)))
#endif

/* ---- NEON helpers ----------------------------------------------------- */

static inline uint32x4_t sm3_vrolq_n_u32(uint32x4_t v, const int n)
{
    /* Compile-time n in 1..31 */
    return vorrq_u32(vshlq_n_u32(v, n), vshrq_n_u32(v, 32 - n));
}

static inline uint32x4_t sm3_vp1_u32(uint32x4_t x)
{
    /* P1(X) = X ^ (X<<<15) ^ (X<<<23) */
    return veorq_u32(x,
           veorq_u32(sm3_vrolq_n_u32(x, 15), sm3_vrolq_n_u32(x, 23)));
}

/* ---- 1. Block load + BE decode ---------------------------------------- */

/**
 * Load 64 message bytes → W[0..15] as host uint32 words matching SM3
 * big-endian lane interpretation.
 *
 * vrev32q_u8 reverses bytes inside each 32-bit lane of a 16-byte chunk.
 */
static void sm3_load_block_be_neon(uint32_t W[16], const uint8_t block[64])
{
    uint8x16_t b0 = vld1q_u8(block +  0);
    uint8x16_t b1 = vld1q_u8(block + 16);
    uint8x16_t b2 = vld1q_u8(block + 32);
    uint8x16_t b3 = vld1q_u8(block + 48);

    uint32x4_t w0 = vreinterpretq_u32_u8(vrev32q_u8(b0));
    uint32x4_t w1 = vreinterpretq_u32_u8(vrev32q_u8(b1));
    uint32x4_t w2 = vreinterpretq_u32_u8(vrev32q_u8(b2));
    uint32x4_t w3 = vreinterpretq_u32_u8(vrev32q_u8(b3));

    vst1q_u32(W +  0, w0);
    vst1q_u32(W +  4, w1);
    vst1q_u32(W +  8, w2);
    vst1q_u32(W + 12, w3);
}

/* ---- 2. Message expansion (3-wide NEON ILP) --------------------------- */

/**
 * Compute W[j], W[j+1], W[j+2] in three active lanes of a uint32x4_t.
 *
 *   W[j] = P1(W[j-16] ^ W[j-9] ^ (W[j-3]<<<15))
 *          ^ (W[j-13]<<<7) ^ W[j-6]
 */
static void sm3_expand3_neon(uint32_t W[68], int j)
{
    SM3_ALIGN16 uint32_t buf[4];
    uint32x4_t m16, m9, m3, m13, m6, t;

    buf[0] = W[j - 16]; buf[1] = W[j - 15]; buf[2] = W[j - 14]; buf[3] = 0;
    m16 = vld1q_u32(buf);
    buf[0] = W[j - 9];  buf[1] = W[j - 8];  buf[2] = W[j - 7];  buf[3] = 0;
    m9 = vld1q_u32(buf);
    buf[0] = W[j - 3];  buf[1] = W[j - 2];  buf[2] = W[j - 1];  buf[3] = 0;
    m3 = vld1q_u32(buf);
    buf[0] = W[j - 13]; buf[1] = W[j - 12]; buf[2] = W[j - 11]; buf[3] = 0;
    m13 = vld1q_u32(buf);
    buf[0] = W[j - 6];  buf[1] = W[j - 5];  buf[2] = W[j - 4];  buf[3] = 0;
    m6 = vld1q_u32(buf);

    t = veorq_u32(m16, m9);
    t = veorq_u32(t, sm3_vrolq_n_u32(m3, 15));
    t = sm3_vp1_u32(t);
    t = veorq_u32(t, sm3_vrolq_n_u32(m13, 7));
    t = veorq_u32(t, m6);

    W[j]     = vgetq_lane_u32(t, 0);
    W[j + 1] = vgetq_lane_u32(t, 1);
    W[j + 2] = vgetq_lane_u32(t, 2);
}

/** Single-word expand for the schedule tail (W[67]). */
static void sm3_expand1_neon(uint32_t W[68], int j)
{
    uint32_t x = W[j - 16] ^ W[j - 9] ^ sm3_rol32(W[j - 3], 15);
    uint32x4_t xv = vdupq_n_u32(x);
    uint32_t p1 = vgetq_lane_u32(sm3_vp1_u32(xv), 0);
    W[j] = p1 ^ sm3_rol32(W[j - 13], 7) ^ W[j - 6];
}

/**
 * Full schedule: W[0..15] → W[0..67].
 * 52 new words = 17×3 (j=16..66) + W[67].
 */
static void sm3_expand_neon(uint32_t W[68])
{
    int j;
    for (j = 16; j <= 64; j += 3) {
        sm3_expand3_neon(W, j);
    }
    sm3_expand1_neon(W, 67);
}

/* ---- 3. Bulk W' on NEON ----------------------------------------------- */

/** W'[j] = W[j] ^ W[j+4], j = 0..63 (16 iterations × 4 lanes). */
static void sm3_wprime_neon(uint32_t Wprime[64], const uint32_t W[68])
{
    int i;
    for (i = 0; i < 64; i += 4) {
        uint32x4_t a = vld1q_u32(W + i);
        uint32x4_t b = vld1q_u32(W + i + 4);
        vst1q_u32(Wprime + i, veorq_u32(a, b));
    }
}

/* ---- 4. Public compress: NEON schedule + GPR rounds ------------------- */

void sm3_compress_neon(uint32_t state[8], const uint8_t block[SM3_BLOCK_SIZE])
{
    SM3_ALIGN16 uint32_t W[68];
    SM3_ALIGN16 uint32_t Wprime[64];

    memset(W + 16, 0, (68 - 16) * sizeof(uint32_t));

    sm3_load_block_be_neon(W, block);
    sm3_expand_neon(W);
    sm3_wprime_neon(Wprime, W);

    sm3_compress_rounds_gpr_wp(state, W, Wprime);
}

#else /* !ARM64 */

/* Should never be linked on non-ARM64 builds (CMake excludes this file). */
void sm3_compress_neon(uint32_t state[8], const uint8_t block[SM3_BLOCK_SIZE])
{
    sm3_compress_ref(state, block);
}

#endif /* ARM64 */
