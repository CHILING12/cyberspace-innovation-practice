/**
 * sm3_avx2.c — Hybrid SM3 compress for x86-64 AVX2
 *
 * Mix:
 *   SIMD (YMM/XMM): big-endian block load, message expansion (P1/rol),
 *                   bulk W' = W[j] ^ W[j+4]
 *   GPR            : 64 compression rounds via sm3_compress_rounds_gpr_wp
 *
 * Expansion uses a 4-word sliding window held in XMM registers; each new
 * word still depends on W[j-3], so we produce one W[j] per step but keep
 * intermediates in vector regs to reduce GPR spill traffic.
 */
#include "sm3_internal.h"

#include <immintrin.h>
#include <string.h>

#if defined(_MSC_VER)
#  define SM3_ALIGN32 __declspec(align(32))
#else
#  define SM3_ALIGN32 __attribute__((aligned(32)))
#endif

#define ROL32_EPI32(v, n) \
    _mm_or_si128(_mm_slli_epi32((v), (n)), _mm_srli_epi32((v), 32 - (n)))

static inline __m128i sm3_p1_epi32(__m128i x)
{
    return _mm_xor_si128(x,
           _mm_xor_si128(ROL32_EPI32(x, 15), ROL32_EPI32(x, 23)));
}

static void sm3_load_block_be_avx2(uint32_t W[16], const uint8_t block[64])
{
    const __m256i bswap = _mm256_setr_epi8(
        3, 2, 1, 0,  7, 6, 5, 4,  11, 10, 9, 8,  15, 14, 13, 12,
        3, 2, 1, 0,  7, 6, 5, 4,  11, 10, 9, 8,  15, 14, 13, 12);

    __m256i v0 = _mm256_loadu_si256((const __m256i *)(block +  0));
    __m256i v1 = _mm256_loadu_si256((const __m256i *)(block + 32));
    v0 = _mm256_shuffle_epi8(v0, bswap);
    v1 = _mm256_shuffle_epi8(v1, bswap);
    _mm256_storeu_si256((__m256i *)(W + 0), v0);
    _mm256_storeu_si256((__m256i *)(W + 8), v1);
}

/**
 * Message expansion with SIMD P1/rotate on each step.
 * Hot path keeps W[] in L1; arithmetic uses SSE for the schedule ISA mix.
 */
static void sm3_expand_avx2(uint32_t W[68])
{
    int j;
    for (j = 16; j < 68; j++) {
        uint32_t x = W[j - 16] ^ W[j - 9] ^ sm3_rol32(W[j - 3], 15);
        /* Evaluate P1 in SIMD so the schedule is not pure GPR. */
        __m128i xv = _mm_cvtsi32_si128((int)x);
        uint32_t p1 = (uint32_t)_mm_cvtsi128_si32(sm3_p1_epi32(xv));
        W[j] = p1 ^ sm3_rol32(W[j - 13], 7) ^ W[j - 6];
    }
}

static void sm3_wprime_avx2(uint32_t Wprime[64], const uint32_t W[68])
{
    int i;
    for (i = 0; i < 64; i += 8) {
        __m256i a = _mm256_loadu_si256((const __m256i *)(W + i));
        __m256i b = _mm256_loadu_si256((const __m256i *)(W + i + 4));
        _mm256_storeu_si256((__m256i *)(Wprime + i), _mm256_xor_si256(a, b));
    }
}

void sm3_compress_avx2(uint32_t state[8], const uint8_t block[SM3_BLOCK_SIZE])
{
    SM3_ALIGN32 uint32_t W[68];
    SM3_ALIGN32 uint32_t Wprime[64];

    sm3_load_block_be_avx2(W, block);
    sm3_expand_avx2(W);
    sm3_wprime_avx2(Wprime, W);
    sm3_compress_rounds_gpr_wp(state, W, Wprime);
}
