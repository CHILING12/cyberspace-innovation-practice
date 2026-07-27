/**
 * sm3_mb_avx2.c — 4-way multi-buffer SM3 on AVX2
 *
 * Unlike the single-buffer hybrid (SIMD expand + scalar rounds), multi-buffer
 * hashes four *independent* messages at once so that:
 *   - message expansion is fully lane-parallel (no W[j-3] cross-lane hazard)
 *   - the 64 compression rounds are fully lane-parallel (A..H per lane)
 *
 * Data layout: each __m128i holds one 32-bit word for 4 messages
 *   lane0 = msgs[0], lane1 = msgs[1], lane2 = msgs[2], lane3 = msgs[3]
 */
#include "sm3_internal.h"

#include <immintrin.h>
#include <string.h>

#define L SM3_MB4_LANES

static inline __m128i mb_rol(__m128i x, int n)
{
    return _mm_or_si128(_mm_slli_epi32(x, n), _mm_srli_epi32(x, 32 - n));
}

static inline __m128i mb_p0(__m128i x)
{
    return _mm_xor_si128(x, _mm_xor_si128(mb_rol(x, 9), mb_rol(x, 17)));
}

static inline __m128i mb_p1(__m128i x)
{
    return _mm_xor_si128(x, _mm_xor_si128(mb_rol(x, 15), mb_rol(x, 23)));
}

static inline __m128i mb_ff0(__m128i x, __m128i y, __m128i z)
{
    return _mm_xor_si128(x, _mm_xor_si128(y, z));
}

static inline __m128i mb_ff1(__m128i x, __m128i y, __m128i z)
{
    return _mm_or_si128(_mm_and_si128(x, y),
           _mm_or_si128(_mm_and_si128(x, z), _mm_and_si128(y, z)));
}

static inline __m128i mb_gg0(__m128i x, __m128i y, __m128i z)
{
    return _mm_xor_si128(x, _mm_xor_si128(y, z));
}

static inline __m128i mb_gg1(__m128i x, __m128i y, __m128i z)
{
    /* (x & y) | (~x & z) */
    return _mm_or_si128(_mm_and_si128(x, y), _mm_andnot_si128(x, z));
}

static inline __m128i mb_add3(__m128i a, __m128i b, __m128i c)
{
    return _mm_add_epi32(_mm_add_epi32(a, b), c);
}

static inline __m128i mb_add4(__m128i a, __m128i b, __m128i c, __m128i d)
{
    return _mm_add_epi32(_mm_add_epi32(a, b), _mm_add_epi32(c, d));
}

/** Load word j (big-endian) from four blocks into one vector. */
static inline __m128i mb_load_be_word(const uint8_t *const blocks[L], int j)
{
    const int off = 4 * j;
    return _mm_setr_epi32(
        (int)sm3_load_be32(blocks[0] + off),
        (int)sm3_load_be32(blocks[1] + off),
        (int)sm3_load_be32(blocks[2] + off),
        (int)sm3_load_be32(blocks[3] + off));
}

/**
 * One SM3 round, 4 lanes in parallel.
 * FF/GG are function pointers replaced by macros at call sites for inlining.
 */
#define MB_ROUND(A, B, C, D, E, F, G, H, FF, GG, Wj, Wpj, Tj)                 \
    do {                                                                      \
        __m128i _ss1, _ss2, _tt1, _tt2;                                       \
        __m128i _t = _mm_set1_epi32((int)(Tj));                               \
        _ss1 = mb_rol(mb_add3(mb_rol((A), 12), (E), _t), 7);                  \
        _ss2 = _mm_xor_si128(_ss1, mb_rol((A), 12));                          \
        _tt1 = mb_add4((FF)((A), (B), (C)), (D), _ss2, (Wpj));                \
        _tt2 = mb_add4((GG)((E), (F), (G)), (H), _ss1, (Wj));                 \
        (D) = (C);                                                            \
        (C) = mb_rol((B), 9);                                                 \
        (B) = (A);                                                            \
        (A) = _tt1;                                                           \
        (H) = (G);                                                            \
        (G) = mb_rol((F), 19);                                                \
        (F) = (E);                                                            \
        (E) = mb_p0(_tt2);                                                    \
    } while (0)

void sm3_mb4_compress_avx2(uint32_t state_lane[L][8],
                           const uint8_t *const blocks[L])
{
    __m128i W[68];
    __m128i A, B, C, D, E, F, G, H;
    int j;

    /* ---- load + expand (fully parallel across 4 messages) ---- */
    for (j = 0; j < 16; j++) {
        W[j] = mb_load_be_word(blocks, j);
    }
    for (j = 16; j < 68; j++) {
        __m128i t = _mm_xor_si128(W[j - 16], W[j - 9]);
        t = _mm_xor_si128(t, mb_rol(W[j - 3], 15));
        t = mb_p1(t);
        t = _mm_xor_si128(t, mb_rol(W[j - 13], 7));
        W[j] = _mm_xor_si128(t, W[j - 6]);
    }

    /* ---- pack state: state_lane[lane][s] -> vector S ---- */
    A = _mm_setr_epi32((int)state_lane[0][0], (int)state_lane[1][0],
                       (int)state_lane[2][0], (int)state_lane[3][0]);
    B = _mm_setr_epi32((int)state_lane[0][1], (int)state_lane[1][1],
                       (int)state_lane[2][1], (int)state_lane[3][1]);
    C = _mm_setr_epi32((int)state_lane[0][2], (int)state_lane[1][2],
                       (int)state_lane[2][2], (int)state_lane[3][2]);
    D = _mm_setr_epi32((int)state_lane[0][3], (int)state_lane[1][3],
                       (int)state_lane[2][3], (int)state_lane[3][3]);
    E = _mm_setr_epi32((int)state_lane[0][4], (int)state_lane[1][4],
                       (int)state_lane[2][4], (int)state_lane[3][4]);
    F = _mm_setr_epi32((int)state_lane[0][5], (int)state_lane[1][5],
                       (int)state_lane[2][5], (int)state_lane[3][5]);
    G = _mm_setr_epi32((int)state_lane[0][6], (int)state_lane[1][6],
                       (int)state_lane[2][6], (int)state_lane[3][6]);
    H = _mm_setr_epi32((int)state_lane[0][7], (int)state_lane[1][7],
                       (int)state_lane[2][7], (int)state_lane[3][7]);

    for (j = 0; j < 16; j++) {
        __m128i Wj  = W[j];
        __m128i Wpj = _mm_xor_si128(W[j], W[j + 4]);
        MB_ROUND(A, B, C, D, E, F, G, H, mb_ff0, mb_gg0, Wj, Wpj, sm3_t_rol(j));
    }
    for (j = 16; j < 64; j++) {
        __m128i Wj  = W[j];
        __m128i Wpj = _mm_xor_si128(W[j], W[j + 4]);
        MB_ROUND(A, B, C, D, E, F, G, H, mb_ff1, mb_gg1, Wj, Wpj, sm3_t_rol(j));
    }

    /* state ^= working vars (per lane) */
    {
        __m128i s0 = _mm_setr_epi32((int)state_lane[0][0], (int)state_lane[1][0],
                                    (int)state_lane[2][0], (int)state_lane[3][0]);
        __m128i s1 = _mm_setr_epi32((int)state_lane[0][1], (int)state_lane[1][1],
                                    (int)state_lane[2][1], (int)state_lane[3][1]);
        __m128i s2 = _mm_setr_epi32((int)state_lane[0][2], (int)state_lane[1][2],
                                    (int)state_lane[2][2], (int)state_lane[3][2]);
        __m128i s3 = _mm_setr_epi32((int)state_lane[0][3], (int)state_lane[1][3],
                                    (int)state_lane[2][3], (int)state_lane[3][3]);
        __m128i s4 = _mm_setr_epi32((int)state_lane[0][4], (int)state_lane[1][4],
                                    (int)state_lane[2][4], (int)state_lane[3][4]);
        __m128i s5 = _mm_setr_epi32((int)state_lane[0][5], (int)state_lane[1][5],
                                    (int)state_lane[2][5], (int)state_lane[3][5]);
        __m128i s6 = _mm_setr_epi32((int)state_lane[0][6], (int)state_lane[1][6],
                                    (int)state_lane[2][6], (int)state_lane[3][6]);
        __m128i s7 = _mm_setr_epi32((int)state_lane[0][7], (int)state_lane[1][7],
                                    (int)state_lane[2][7], (int)state_lane[3][7]);
        A = _mm_xor_si128(A, s0);
        B = _mm_xor_si128(B, s1);
        C = _mm_xor_si128(C, s2);
        D = _mm_xor_si128(D, s3);
        E = _mm_xor_si128(E, s4);
        F = _mm_xor_si128(F, s5);
        G = _mm_xor_si128(G, s6);
        H = _mm_xor_si128(H, s7);
    }

    {
        uint32_t tmp[4];
        int lane;
        _mm_storeu_si128((__m128i *)tmp, A);
        for (lane = 0; lane < L; lane++) state_lane[lane][0] = tmp[lane];
        _mm_storeu_si128((__m128i *)tmp, B);
        for (lane = 0; lane < L; lane++) state_lane[lane][1] = tmp[lane];
        _mm_storeu_si128((__m128i *)tmp, C);
        for (lane = 0; lane < L; lane++) state_lane[lane][2] = tmp[lane];
        _mm_storeu_si128((__m128i *)tmp, D);
        for (lane = 0; lane < L; lane++) state_lane[lane][3] = tmp[lane];
        _mm_storeu_si128((__m128i *)tmp, E);
        for (lane = 0; lane < L; lane++) state_lane[lane][4] = tmp[lane];
        _mm_storeu_si128((__m128i *)tmp, F);
        for (lane = 0; lane < L; lane++) state_lane[lane][5] = tmp[lane];
        _mm_storeu_si128((__m128i *)tmp, G);
        for (lane = 0; lane < L; lane++) state_lane[lane][6] = tmp[lane];
        _mm_storeu_si128((__m128i *)tmp, H);
        for (lane = 0; lane < L; lane++) state_lane[lane][7] = tmp[lane];
    }
}
