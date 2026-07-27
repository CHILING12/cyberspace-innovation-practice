/**
 * sm3_mb.c — Multi-buffer SM3 API (dispatch + sequential fallback).
 *
 * When AVX2 is available, full 64-byte blocks of four equal-length messages
 * are compressed with sm3_mb4_compress_avx2. Padding / short tails use the
 * existing scalar incremental API so correctness stays identical to sm3_ref.
 */
#include "sm3_internal.h"

#include <string.h>

int sm3_mb_max_lanes(void)
{
#if defined(SM3_HAS_AVX2)
    if (sm3_cpu_has_avx2()) {
        return SM3_MB4_LANES;
    }
#endif
    return 1;
}

static void mb_digest_sequential(const uint8_t *const *msgs,
                                 const size_t *lens,
                                 size_t num,
                                 uint8_t digests[][SM3_DIGEST_SIZE])
{
    size_t i;
    for (i = 0; i < num; i++) {
        sm3_digest_ex(msgs[i], lens[i], digests[i], SM3_IMPL_REF);
    }
}

#if defined(SM3_HAS_AVX2)
static void mb4_digest_avx2(const uint8_t *const msgs[SM3_MB4_LANES],
                            size_t len,
                            uint8_t digests[SM3_MB4_LANES][SM3_DIGEST_SIZE])
{
    uint32_t state[SM3_MB4_LANES][8];
    size_t off;
    size_t nfull;
    int lane;

    for (lane = 0; lane < SM3_MB4_LANES; lane++) {
        memcpy(state[lane], SM3_IV, sizeof(SM3_IV));
    }

    nfull = len / SM3_BLOCK_SIZE;
    for (off = 0; off < nfull; off++) {
        const uint8_t *blocks[SM3_MB4_LANES];
        for (lane = 0; lane < SM3_MB4_LANES; lane++) {
            blocks[lane] = msgs[lane] + off * SM3_BLOCK_SIZE;
        }
        sm3_mb4_compress_avx2(state, blocks);
    }

    /* Remainder + padding via scalar incremental API (shared correctness). */
    for (lane = 0; lane < SM3_MB4_LANES; lane++) {
        sm3_ctx ctx;
        size_t rem = len % SM3_BLOCK_SIZE;
        size_t base = nfull * SM3_BLOCK_SIZE;

        sm3_init_ex(&ctx, SM3_IMPL_REF);
        memcpy(ctx.state, state[lane], sizeof(ctx.state));
        ctx.total_bits = (uint64_t)base * 8u;
        ctx.buffer_len = 0;
        if (rem > 0) {
            sm3_update(&ctx, msgs[lane] + base, rem);
        }
        sm3_final(&ctx, digests[lane]);
    }
}
#endif

void sm3_mb4_digest(const uint8_t *const msgs[SM3_MB4_LANES],
                    size_t len,
                    uint8_t digests[SM3_MB4_LANES][SM3_DIGEST_SIZE])
{
#if defined(SM3_HAS_AVX2)
    if (sm3_cpu_has_avx2()) {
        mb4_digest_avx2(msgs, len, digests);
        return;
    }
#endif
    {
        size_t lens[SM3_MB4_LANES];
        int i;
        for (i = 0; i < SM3_MB4_LANES; i++) {
            lens[i] = len;
        }
        mb_digest_sequential(msgs, lens, SM3_MB4_LANES, digests);
    }
}

void sm3_mb_digest(size_t num,
                   const uint8_t *const *msgs,
                   const size_t *lens,
                   uint8_t digests[][SM3_DIGEST_SIZE])
{
    size_t i = 0;

    if (num == 0 || msgs == NULL || lens == NULL || digests == NULL) {
        return;
    }

#if defined(SM3_HAS_AVX2)
    if (sm3_cpu_has_avx2()) {
        while (i + SM3_MB4_LANES <= num) {
            size_t k;
            int same = 1;
            for (k = 1; k < SM3_MB4_LANES; k++) {
                if (lens[i + k] != lens[i]) {
                    same = 0;
                    break;
                }
            }
            if (same) {
                const uint8_t *batch[SM3_MB4_LANES];
                for (k = 0; k < SM3_MB4_LANES; k++) {
                    batch[k] = msgs[i + k];
                }
                mb4_digest_avx2(batch, lens[i], &digests[i]);
                i += SM3_MB4_LANES;
                continue;
            }
            /* Different lengths: one sequential, then retry grouping. */
            sm3_digest_ex(msgs[i], lens[i], digests[i], SM3_IMPL_REF);
            i++;
        }
    }
#endif

    for (; i < num; i++) {
        sm3_digest_ex(msgs[i], lens[i], digests[i], SM3_IMPL_REF);
    }
}
