/**
 * sm3_avx512.c — Hybrid SM3 compress for x86-64 AVX-512
 *
 * =====================================================================
 * Hybrid split (assignment requirement: SIMD regs + general-purpose regs)
 * =====================================================================
 *
 *   [ZMM / SIMD]
 *     - 64-byte block load + per-dword big-endian byte swap (vpshufb)
 *     - Message expansion W[16..67] with 3-wide vector ILP
 *       (W[j] depends on W[j-3], so at most 3 consecutive words are
 *        independent; we compute them in one XMM with lane-wise P1/rol)
 *     - Bulk W'[0..63] = W[j] ^ W[j+4] as 4 x 16-lane ZMM XORs
 *
 *   [GPR]
 *     - 64 compression rounds A..H via sm3_compress_rounds_gpr_wp()
 *       (same round core as the reference path — bit-identical)
 *
 * Runtime: only called when sm3_cpu_has_avx512f() is true (XCR0 + CPUID).
 * Build: always compiled under /arch:AVX512 (or -mavx512f -mavx512bw) so
 * the binary contains the path even on machines that must skip it at run time.
 */
#include "sm3_internal.h"

#include <immintrin.h>
#include <string.h>

#if defined(_MSC_VER)
#  define SM3_ALIGN64 __declspec(align(64))
#  define SM3_INLINE static __forceinline
#else
#  define SM3_ALIGN64 __attribute__((aligned(64)))
#  define SM3_INLINE static inline __attribute__((always_inline))
#endif

/* ---- lane-wise helpers (128-bit, 3 active dwords) ---------------------- */

SM3_INLINE __m128i sm3_mm_rol_epi32(__m128i v, int n)
{
    /*
     * Prefer AVX-512 VL rotate when available (MSVC /arch:AVX512,
     * or GCC/Clang with -mavx512vl). Fallback is shift+or.
     */
#if defined(__AVX512VL__) || (defined(_MSC_VER) && defined(__AVX512F__))
    switch (n) {
    case 7:  return _mm_rol_epi32(v, 7);
    case 15: return _mm_rol_epi32(v, 15);
    case 23: return _mm_rol_epi32(v, 23);
    default: break;
    }
#endif
    return _mm_or_si128(_mm_slli_epi32(v, n), _mm_srli_epi32(v, 32 - n));
}

SM3_INLINE __m128i sm3_mm_p1_epi32(__m128i x)
{
    /* P1(X) = X ^ (X<<<15) ^ (X<<<23) — all 32-bit lanes */
    return _mm_xor_si128(x,
           _mm_xor_si128(sm3_mm_rol_epi32(x, 15), sm3_mm_rol_epi32(x, 23)));
}

/* ---- 1. Block load + BE decode (full ZMM) ----------------------------- */

/**
 * Load 64 message bytes and produce W[0..15] as host-endian uint32 words
 * equal to the SM3 big-endian interpretation of each 4-byte group.
 *
 * Uses one 512-bit load + vpshufb (AVX512BW) — no scalar byte loops.
 */
static void sm3_load_block_be_avx512(uint32_t W[16], const uint8_t block[64])
{
    /*
     * Shuffle control: within each 4-byte lane reverse bytes.
     * Byte index i reads from control[i] of the source.
     * Stored low-address first for loadu.
     */
    SM3_ALIGN64 static const uint8_t k_bswap[64] = {
        3,  2,  1,  0,  7,  6,  5,  4, 11, 10,  9,  8, 15, 14, 13, 12,
       19, 18, 17, 16, 23, 22, 21, 20, 27, 26, 25, 24, 31, 30, 29, 28,
       35, 34, 33, 32, 39, 38, 37, 36, 43, 42, 41, 40, 47, 46, 45, 44,
       51, 50, 49, 48, 55, 54, 53, 52, 59, 58, 57, 56, 63, 62, 61, 60
    };

    __m512i raw   = _mm512_loadu_si512((const void *)block);
    __m512i bswap = _mm512_load_si512((const void *)k_bswap);
    __m512i words = _mm512_shuffle_epi8(raw, bswap);
    _mm512_storeu_si512((void *)W, words);
}

/* ---- 2. Message expansion (3-wide SIMD ILP) --------------------------- */

/**
 * Compute W[j], W[j+1], W[j+2] in parallel (when all three exist).
 *
 * SM3 schedule:
 *   W[j] = P1(W[j-16] ^ W[j-9] ^ (W[j-3]<<<15)) ^ (W[j-13]<<<7) ^ W[j-6]
 *
 * W[j+3] needs W[j], so the independent window length is 3.
 */
static void sm3_expand3_avx512(uint32_t W[68], int j)
{
    __m128i m16 = _mm_setr_epi32((int)W[j - 16], (int)W[j - 15], (int)W[j - 14], 0);
    __m128i m9  = _mm_setr_epi32((int)W[j -  9], (int)W[j -  8], (int)W[j -  7], 0);
    __m128i m3  = _mm_setr_epi32((int)W[j -  3], (int)W[j -  2], (int)W[j -  1], 0);
    __m128i m13 = _mm_setr_epi32((int)W[j - 13], (int)W[j - 12], (int)W[j - 11], 0);
    __m128i m6  = _mm_setr_epi32((int)W[j -  6], (int)W[j -  5], (int)W[j -  4], 0);

    __m128i t = _mm_xor_si128(m16, m9);
    t = _mm_xor_si128(t, sm3_mm_rol_epi32(m3, 15));
    t = sm3_mm_p1_epi32(t);
    t = _mm_xor_si128(t, sm3_mm_rol_epi32(m13, 7));
    t = _mm_xor_si128(t, m6);

    /* Extract three lanes (lane 3 is unused padding). */
    SM3_ALIGN64 uint32_t tmp[4];
    _mm_store_si128((__m128i *)tmp, t);
    W[j]     = tmp[0];
    W[j + 1] = tmp[1];
    W[j + 2] = tmp[2];
}

/** Scalar one-step expand (tail when length not multiple of 3). */
static void sm3_expand1_avx512(uint32_t W[68], int j)
{
    uint32_t x = W[j - 16] ^ W[j - 9] ^ sm3_rol32(W[j - 3], 15);
    __m128i xv = _mm_cvtsi32_si128((int)x);
    uint32_t p1 = (uint32_t)_mm_cvtsi128_si32(sm3_mm_p1_epi32(xv));
    W[j] = p1 ^ sm3_rol32(W[j - 13], 7) ^ W[j - 6];
}

/**
 * Full schedule W[0..15] -> W[0..67].
 * 52 new words: 17 groups of 3 (j=16..66) + final W[67].
 */
static void sm3_expand_avx512(uint32_t W[68])
{
    int j;
    for (j = 16; j <= 64; j += 3) {
        sm3_expand3_avx512(W, j);
    }
    /* j = 67 remaining (16 + 17*3 = 67). */
    sm3_expand1_avx512(W, 67);
}

/* ---- 3. Bulk W' on ZMM ------------------------------------------------ */

/**
 * W'[j] = W[j] ^ W[j+4], j = 0..63.
 * Four 512-bit XORs (16 x u32 each). W[64..67] exist after expansion.
 */
static void sm3_wprime_avx512(uint32_t Wprime[64], const uint32_t W[68])
{
    int i;
    for (i = 0; i < 64; i += 16) {
        __m512i a = _mm512_loadu_si512((const void *)(W + i));
        __m512i b = _mm512_loadu_si512((const void *)(W + i + 4));
        _mm512_storeu_si512((void *)(Wprime + i), _mm512_xor_si512(a, b));
    }
}

/* ---- 4. Public compress: SIMD schedule + GPR rounds ------------------- */

void sm3_compress_avx512(uint32_t state[8], const uint8_t block[SM3_BLOCK_SIZE])
{
    SM3_ALIGN64 uint32_t W[68];
    SM3_ALIGN64 uint32_t Wprime[64];

    /* Zero tail padding words used only for alignment convenience. */
    memset(W + 16, 0, (68 - 16) * sizeof(uint32_t));

    sm3_load_block_be_avx512(W, block);
    sm3_expand_avx512(W);
    sm3_wprime_avx512(Wprime, W);

    /* General-purpose register compression (shared with ref). */
    sm3_compress_rounds_gpr_wp(state, W, Wprime);
}
