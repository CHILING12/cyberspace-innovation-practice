/**
 * Implementation selection / feature-probe smoke tests.
 */
#include "sm3.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

static void expect_true(const char *name, int cond)
{
    if (!cond) {
        printf("[FAIL] %s\n", name);
        failures++;
    } else {
        printf("[ OK ] %s\n", name);
    }
}

int main(void)
{
    uint8_t d0[SM3_DIGEST_SIZE], d1[SM3_DIGEST_SIZE];
    const char *msg = "sm3-opt";

    printf("SM3 impl / feature tests\n");
    printf("  AVX2    available(build+cpu): %d (cpu=%d)\n",
           sm3_impl_available(SM3_IMPL_AVX2), sm3_cpu_has_avx2());
    printf("  AVX512  available(build+cpu): %d (cpu=%d)\n",
           sm3_impl_available(SM3_IMPL_AVX512), sm3_cpu_has_avx512f());
    printf("  NEON    available(build+cpu): %d (cpu=%d)\n",
           sm3_impl_available(SM3_IMPL_NEON), sm3_cpu_has_neon());
    printf("  REF     available: %d\n", sm3_impl_available(SM3_IMPL_REF));
    printf("  AUTO    available: %d\n", sm3_impl_available(SM3_IMPL_AUTO));

    expect_true("ref always available", sm3_impl_available(SM3_IMPL_REF));
    expect_true("auto always available", sm3_impl_available(SM3_IMPL_AUTO));
    expect_true("set ref", sm3_set_impl(SM3_IMPL_REF) == 0);
    expect_true("get is ref", sm3_get_impl() == SM3_IMPL_REF);

    sm3_digest((const uint8_t *)msg, strlen(msg), d0);

    if (sm3_impl_available(SM3_IMPL_AVX2)) {
        expect_true("set avx2", sm3_set_impl(SM3_IMPL_AVX2) == 0);
        sm3_digest((const uint8_t *)msg, strlen(msg), d1);
        expect_true("avx2 matches ref digest", memcmp(d0, d1, 32) == 0);
    } else {
        expect_true("set avx2 fails when unavailable",
                    sm3_set_impl(SM3_IMPL_AVX2) == -1);
    }

    if (sm3_impl_available(SM3_IMPL_AVX512)) {
        expect_true("set avx512", sm3_set_impl(SM3_IMPL_AVX512) == 0);
        sm3_digest((const uint8_t *)msg, strlen(msg), d1);
        expect_true("avx512 matches ref digest", memcmp(d0, d1, 32) == 0);
    } else {
        printf("[SKIP] avx512 not available on this CPU/build\n");
    }

    if (sm3_impl_available(SM3_IMPL_NEON)) {
        expect_true("set neon", sm3_set_impl(SM3_IMPL_NEON) == 0);
        sm3_digest((const uint8_t *)msg, strlen(msg), d1);
        expect_true("neon matches ref digest", memcmp(d0, d1, 32) == 0);
    } else {
        printf("[SKIP] neon not available on this CPU/build\n");
        expect_true("set neon fails when unavailable",
                    sm3_set_impl(SM3_IMPL_NEON) == -1);
    }

    expect_true("set auto", sm3_set_impl(SM3_IMPL_AUTO) == 0);
    printf("  active: %s\n", sm3_active_impl_desc());
    printf("  compress_fn ref  = %p\n", (void *)sm3_get_compress_fn(SM3_IMPL_REF));
#if defined(SM3_HAS_AVX2)
    if (sm3_impl_available(SM3_IMPL_AVX2)) {
        printf("  compress_fn avx2 = %p\n", (void *)sm3_get_compress_fn(SM3_IMPL_AVX2));
        expect_true("compress fn differs ref/avx2",
                    sm3_get_compress_fn(SM3_IMPL_REF) !=
                    sm3_get_compress_fn(SM3_IMPL_AVX2));
    }
#endif
#if defined(SM3_HAS_NEON)
    if (sm3_impl_available(SM3_IMPL_NEON)) {
        printf("  compress_fn neon = %p\n", (void *)sm3_get_compress_fn(SM3_IMPL_NEON));
        expect_true("compress fn differs ref/neon",
                    sm3_get_compress_fn(SM3_IMPL_REF) !=
                    sm3_get_compress_fn(SM3_IMPL_NEON));
    }
#endif

    if (failures) {
        printf("RESULT: %d failure(s)\n", failures);
        return 1;
    }
    printf("RESULT: all passed\n");
    return 0;
}
