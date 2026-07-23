/**
 * sm3_ref.c — Pure C SM3 reference implementation (GPR only).
 *
 * Correctness baseline for all SIMD hybrid paths.
 */
#include "sm3_internal.h"

void sm3_expand_ref(uint32_t W[68], const uint8_t block[SM3_BLOCK_SIZE])
{
    int j;

    for (j = 0; j < 16; j++) {
        W[j] = sm3_load_be32(block + 4 * j);
    }

    for (j = 16; j < 68; j++) {
        uint32_t x = W[j - 16] ^ W[j - 9] ^ sm3_rol32(W[j - 3], 15);
        W[j] = sm3_p1(x) ^ sm3_rol32(W[j - 13], 7) ^ W[j - 6];
    }
}

void sm3_compress_rounds_gpr_wp(uint32_t state[8],
                                const uint32_t W[68],
                                const uint32_t Wprime[64])
{
    uint32_t A = state[0];
    uint32_t B = state[1];
    uint32_t C = state[2];
    uint32_t D = state[3];
    uint32_t E = state[4];
    uint32_t F = state[5];
    uint32_t G = state[6];
    uint32_t H = state[7];
    int j;

    for (j = 0; j < 16; j++) {
        SM3_ROUND(A, B, C, D, E, F, G, H,
                  sm3_ff0, sm3_gg0, W[j], Wprime[j], sm3_t_rol(j));
    }

    for (j = 16; j < 64; j++) {
        SM3_ROUND(A, B, C, D, E, F, G, H,
                  sm3_ff1, sm3_gg1, W[j], Wprime[j], sm3_t_rol(j));
    }

    state[0] ^= A;
    state[1] ^= B;
    state[2] ^= C;
    state[3] ^= D;
    state[4] ^= E;
    state[5] ^= F;
    state[6] ^= G;
    state[7] ^= H;
}

void sm3_compress_rounds_gpr(uint32_t state[8], const uint32_t W[68])
{
    uint32_t Wprime[64];
    int j;
    for (j = 0; j < 64; j++) {
        Wprime[j] = W[j] ^ W[j + 4];
    }
    sm3_compress_rounds_gpr_wp(state, W, Wprime);
}

void sm3_compress_ref(uint32_t state[8], const uint8_t block[SM3_BLOCK_SIZE])
{
    uint32_t W[68];
    sm3_expand_ref(W, block);
    sm3_compress_rounds_gpr(state, W);
}
