/**
 * Multi-buffer correctness: sm3_mb4 / sm3_mb vs sequential sm3_ref.
 */
#include "sm3.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int failures = 0;

static uint32_t rng(uint32_t *s)
{
    uint32_t x = *s;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *s = x;
    return x;
}

static void expect_eq(const char *tag, const uint8_t a[32], const uint8_t b[32])
{
    if (memcmp(a, b, 32) != 0) {
        printf("[FAIL] %s\n", tag);
        failures++;
    }
}

int main(void)
{
    uint32_t seed = (uint32_t)time(NULL) ^ 0x4D42534Du;
    int t;
    size_t lens_eq[] = {0, 1, 3, 55, 56, 63, 64, 65, 128, 1023, 1024, 4096};
    size_t n_eq = sizeof(lens_eq) / sizeof(lens_eq[0]);
    size_t ei;

    printf("SM3 multi-buffer tests\n");
    printf("CPU AVX2=%d  mb_max_lanes=%d\n",
           sm3_cpu_has_avx2(), sm3_mb_max_lanes());

    /* Equal-length batches */
    for (ei = 0; ei < n_eq; ei++) {
        size_t len = lens_eq[ei];
        uint8_t *bufs[SM3_MB4_LANES];
        const uint8_t *msgs[SM3_MB4_LANES];
        uint8_t got[SM3_MB4_LANES][SM3_DIGEST_SIZE];
        uint8_t exp[SM3_MB4_LANES][SM3_DIGEST_SIZE];
        int lane;
        char tag[64];

        for (lane = 0; lane < SM3_MB4_LANES; lane++) {
            size_t j;
            bufs[lane] = (uint8_t *)malloc(len ? len : 1);
            if (!bufs[lane]) {
                fprintf(stderr, "oom\n");
                return 1;
            }
            for (j = 0; j < len; j++) {
                bufs[lane][j] = (uint8_t)(rng(&seed) + (unsigned)lane * 17u);
            }
            msgs[lane] = bufs[lane];
            sm3_digest_ex(msgs[lane], len, exp[lane], SM3_IMPL_REF);
        }

        sm3_mb4_digest(msgs, len, got);
        for (lane = 0; lane < SM3_MB4_LANES; lane++) {
            sprintf(tag, "mb4 equal len=%zu lane=%d", len, lane);
            expect_eq(tag, got[lane], exp[lane]);
        }

        for (lane = 0; lane < SM3_MB4_LANES; lane++) {
            free(bufs[lane]);
        }
        printf("  [ OK ] mb4 equal-length len=%zu\n", len);
    }

    /* sm3_mb_digest mixed lengths */
    {
        const size_t num = 7;
        uint8_t *bufs[7];
        const uint8_t *msgs[7];
        size_t lens[7];
        uint8_t got[7][SM3_DIGEST_SIZE];
        uint8_t exp[7][SM3_DIGEST_SIZE];
        size_t i;

        for (i = 0; i < num; i++) {
            size_t j;
            lens[i] = (size_t)(rng(&seed) % 2000u);
            bufs[i] = (uint8_t *)malloc(lens[i] ? lens[i] : 1);
            if (!bufs[i]) {
                fprintf(stderr, "oom\n");
                return 1;
            }
            for (j = 0; j < lens[i]; j++) {
                bufs[i][j] = (uint8_t)rng(&seed);
            }
            msgs[i] = bufs[i];
            sm3_digest_ex(msgs[i], lens[i], exp[i], SM3_IMPL_REF);
        }

        sm3_mb_digest(num, msgs, lens, got);
        for (i = 0; i < num; i++) {
            char tag[32];
            sprintf(tag, "mb mixed i=%zu len=%zu", i, lens[i]);
            expect_eq(tag, got[i], exp[i]);
        }
        for (i = 0; i < num; i++) {
            free(bufs[i]);
        }
        printf("  [ OK ] sm3_mb_digest mixed (num=%zu)\n", num);
    }

    /* Random equal-length stress */
    for (t = 0; t < 200; t++) {
        size_t len = (size_t)(rng(&seed) % 8193u);
        uint8_t *bufs[SM3_MB4_LANES];
        const uint8_t *msgs[SM3_MB4_LANES];
        uint8_t got[SM3_MB4_LANES][SM3_DIGEST_SIZE];
        uint8_t exp[SM3_MB4_LANES][SM3_DIGEST_SIZE];
        int lane;

        for (lane = 0; lane < SM3_MB4_LANES; lane++) {
            size_t j;
            bufs[lane] = (uint8_t *)malloc(len ? len : 1);
            if (!bufs[lane]) {
                fprintf(stderr, "oom\n");
                return 1;
            }
            for (j = 0; j < len; j++) {
                bufs[lane][j] = (uint8_t)rng(&seed);
            }
            msgs[lane] = bufs[lane];
            sm3_digest_ex(msgs[lane], len, exp[lane], SM3_IMPL_REF);
        }
        sm3_mb4_digest(msgs, len, got);
        for (lane = 0; lane < SM3_MB4_LANES; lane++) {
            if (memcmp(got[lane], exp[lane], 32) != 0) {
                printf("[FAIL] stress t=%d len=%zu lane=%d\n", t, len, lane);
                failures++;
            }
        }
        for (lane = 0; lane < SM3_MB4_LANES; lane++) {
            free(bufs[lane]);
        }
    }
    printf("  [ OK ] mb4 random stress (200)\n");

    if (failures) {
        printf("RESULT: %d failure(s)\n", failures);
        return 1;
    }
    printf("RESULT: all passed\n");
    return 0;
}
