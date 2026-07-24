/**
 * Random-length cross-check: every available SIMD path must match ref.
 */
#include "sm3.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static uint32_t xorshift32(uint32_t *s)
{
    uint32_t x = *s;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *s = x;
    return x;
}

static int failures = 0;

static void check_pair(const char *tag, const uint8_t *msg, size_t len,
                       sm3_impl_t a, sm3_impl_t b)
{
    uint8_t da[SM3_DIGEST_SIZE], db[SM3_DIGEST_SIZE];
    if (!sm3_impl_available(a) || !sm3_impl_available(b)) {
        return;
    }
    sm3_digest_ex(msg, len, da, a);
    sm3_digest_ex(msg, len, db, b);
    if (memcmp(da, db, SM3_DIGEST_SIZE) != 0) {
        printf("[FAIL] %s len=%zu %s vs %s\n", tag, len,
               sm3_impl_name(a), sm3_impl_name(b));
        failures++;
    }
}

int main(void)
{
    uint32_t seed = (uint32_t)time(NULL) ^ 0xA5A5A5A5u;
    uint8_t *buf;
    size_t i;
    const size_t max_len = 4096;
    const int iters = 2000;
    int t;

    printf("SM3 random consistency (seed=%u, iters=%d)\n", seed, iters);
    printf("CPU AVX2=%d AVX512F=%d NEON=%d\n",
           sm3_cpu_has_avx2(), sm3_cpu_has_avx512f(), sm3_cpu_has_neon());

    buf = (uint8_t *)malloc(max_len);
    if (!buf) {
        fprintf(stderr, "oom\n");
        return 1;
    }

    /* Boundary lengths */
    {
        size_t boundaries[] = {0, 1, 3, 55, 56, 63, 64, 65, 127, 128, 255, 256, 1024, 4096};
        size_t bi;
        for (bi = 0; bi < sizeof(boundaries) / sizeof(boundaries[0]); bi++) {
            size_t n = boundaries[bi];
            size_t j;
            if (n > max_len) {
                continue;
            }
            for (j = 0; j < n; j++) {
                buf[j] = (uint8_t)(j * 17 + bi);
            }
#if defined(SM3_HAS_AVX2)
            check_pair("boundary", buf, n, SM3_IMPL_REF, SM3_IMPL_AVX2);
#endif
#if defined(SM3_HAS_AVX512)
            check_pair("boundary", buf, n, SM3_IMPL_REF, SM3_IMPL_AVX512);
#endif
#if defined(SM3_HAS_NEON)
            check_pair("boundary", buf, n, SM3_IMPL_REF, SM3_IMPL_NEON);
#endif
        }
    }

    for (t = 0; t < iters; t++) {
        size_t len = xorshift32(&seed) % (max_len + 1);
        size_t j;
        for (j = 0; j < len; j++) {
            buf[j] = (uint8_t)xorshift32(&seed);
        }

        /* multi-update vs one-shot on ref */
        {
            sm3_ctx ctx;
            uint8_t one[SM3_DIGEST_SIZE], multi[SM3_DIGEST_SIZE];
            size_t off = 0;
            sm3_digest_ex(buf, len, one, SM3_IMPL_REF);
            sm3_init_ex(&ctx, SM3_IMPL_REF);
            while (off < len) {
                size_t chunk = (xorshift32(&seed) % 97) + 1;
                if (off + chunk > len) {
                    chunk = len - off;
                }
                sm3_update(&ctx, buf + off, chunk);
                off += chunk;
            }
            sm3_final(&ctx, multi);
            if (memcmp(one, multi, SM3_DIGEST_SIZE) != 0) {
                printf("[FAIL] multi-update len=%zu\n", len);
                failures++;
            }
        }

#if defined(SM3_HAS_AVX2)
        check_pair("random", buf, len, SM3_IMPL_REF, SM3_IMPL_AVX2);
#endif
#if defined(SM3_HAS_AVX512)
        check_pair("random", buf, len, SM3_IMPL_REF, SM3_IMPL_AVX512);
#endif
#if defined(SM3_HAS_NEON)
        check_pair("random", buf, len, SM3_IMPL_REF, SM3_IMPL_NEON);
#endif

        if ((t + 1) % 500 == 0) {
            printf("  ... %d/%d\n", t + 1, iters);
        }
    }

    free(buf);

    if (failures) {
        printf("RESULT: %d failure(s)\n", failures);
        return 1;
    }
    printf("RESULT: all passed\n");
    return 0;
}
