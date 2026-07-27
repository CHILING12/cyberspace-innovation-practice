/**
 * Internal shared helpers for SM3 implementations.
 * Not part of the public API.
 */
#ifndef SM3_OPT_INTERNAL_H
#define SM3_OPT_INTERNAL_H

#include "sm3.h"

#include <string.h>

/* ---- 32-bit rotate / endian ------------------------------------------- */

static inline uint32_t sm3_rol32(uint32_t x, int n)
{
    return (x << n) | (x >> (32 - n));
}

static inline uint32_t sm3_load_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) |
           ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] <<  8) |
           ((uint32_t)p[3]      );
}

static inline void sm3_store_be32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >>  8);
    p[3] = (uint8_t)(v      );
}

/* ---- boolean / permutation functions ---------------------------------- */

static inline uint32_t sm3_p0(uint32_t x)
{
    return x ^ sm3_rol32(x, 9) ^ sm3_rol32(x, 17);
}

static inline uint32_t sm3_p1(uint32_t x)
{
    return x ^ sm3_rol32(x, 15) ^ sm3_rol32(x, 23);
}

static inline uint32_t sm3_ff0(uint32_t x, uint32_t y, uint32_t z)
{
    return x ^ y ^ z;
}

static inline uint32_t sm3_ff1(uint32_t x, uint32_t y, uint32_t z)
{
    return (x & y) | (x & z) | (y & z);
}

static inline uint32_t sm3_gg0(uint32_t x, uint32_t y, uint32_t z)
{
    return x ^ y ^ z;
}

static inline uint32_t sm3_gg1(uint32_t x, uint32_t y, uint32_t z)
{
    return (x & y) | ((~x) & z);
}

/* ---- IV / Tj ---------------------------------------------------------- */

static const uint32_t SM3_IV[8] = {
    0x7380166Fu, 0x4914B2B9u, 0x172442D7u, 0xDA8A0600u,
    0xA96F30BCu, 0x163138AAu, 0xE38DEE4Du, 0xB0FB0E4Eu
};

/* T_j raw constants (before rotate-by-j) */
#define SM3_T0  0x79CC4519u
#define SM3_T1  0x7A879D8Au

/* (T_j <<< (j mod 32)) — computed, avoids a hand-maintained table. */
static inline uint32_t sm3_t_rol(int j)
{
    uint32_t T = (j < 16) ? SM3_T0 : SM3_T1;
    int n = j & 31;
    if (n == 0) {
        return T;
    }
    return (T << n) | (T >> (32 - n));
}

/* ---- compression round macro (GPR path shared by all impls) ----------- */

/*
 * One SM3 round.  FF/GG selected by the caller via ff/gg arguments.
 * Updates A..H in place; consumes W and W' for this round index.
 */
#define SM3_ROUND(A, B, C, D, E, F, G, H, FF, GG, Wj, Wpj, Tjrol)           \
    do {                                                                    \
        uint32_t _ss1, _ss2, _tt1, _tt2;                                    \
        _ss1 = sm3_rol32(sm3_rol32((A), 12) + (E) + (Tjrol), 7);            \
        _ss2 = _ss1 ^ sm3_rol32((A), 12);                                   \
        _tt1 = (FF)((A), (B), (C)) + (D) + _ss2 + (Wpj);                    \
        _tt2 = (GG)((E), (F), (G)) + (H) + _ss1 + (Wj);                     \
        (D)  = (C);                                                         \
        (C)  = sm3_rol32((B), 9);                                           \
        (B)  = (A);                                                         \
        (A)  = _tt1;                                                        \
        (H)  = (G);                                                         \
        (G)  = sm3_rol32((F), 19);                                          \
        (F)  = (E);                                                         \
        (E)  = sm3_p0(_tt2);                                                \
    } while (0)

/* Scalar message expansion into W[68] (and optional Wprime[64]). */
void sm3_expand_ref(uint32_t W[68], const uint8_t block[SM3_BLOCK_SIZE]);

/* Shared 64-round compression given fully expanded W[68]. */
void sm3_compress_rounds_gpr(uint32_t state[8], const uint32_t W[68]);

/* Same rounds, but W'[j] supplied by caller (SIMD bulk path). */
void sm3_compress_rounds_gpr_wp(uint32_t state[8],
                                const uint32_t W[68],
                                const uint32_t Wprime[64]);

/* Resolve AUTO / validate availability; returns concrete impl or -1. */
int sm3_resolve_impl(sm3_impl_t impl);

/* Compress function table hook used by sm3_common. */
sm3_compress_fn sm3_select_compress(sm3_impl_t impl);

#endif /* SM3_OPT_INTERNAL_H */
