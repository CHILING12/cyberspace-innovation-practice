/**
 * Standard SM3 test vectors (GM/T 0004 / common published vectors).
 */
#include "sm3.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static int failures = 0;

static void to_hex(const uint8_t *in, size_t n, char *out)
{
    static const char *hd = "0123456789abcdef";
    size_t i;
    for (i = 0; i < n; i++) {
        out[2 * i]     = hd[in[i] >> 4];
        out[2 * i + 1] = hd[in[i] & 0xf];
    }
    out[2 * n] = '\0';
}

static int parse_hex(const char *hex, uint8_t *out, size_t out_len)
{
    size_t n = strlen(hex);
    size_t i;
    if (n != out_len * 2) {
        return -1;
    }
    for (i = 0; i < out_len; i++) {
        unsigned int v;
        if (sscanf(hex + 2 * i, "%2x", &v) != 1) {
            return -1;
        }
        out[i] = (uint8_t)v;
    }
    return 0;
}

static void expect_digest(const char *name, const void *msg, size_t len,
                          const char *hex_expected, sm3_impl_t impl)
{
    uint8_t got[SM3_DIGEST_SIZE];
    uint8_t exp[SM3_DIGEST_SIZE];
    char got_hex[SM3_DIGEST_SIZE * 2 + 1];

    if (!sm3_impl_available(impl)) {
        printf("  [SKIP] %s (%s not available)\n", name, sm3_impl_name(impl));
        return;
    }

    if (parse_hex(hex_expected, exp, SM3_DIGEST_SIZE) != 0) {
        printf("  [FAIL] %s: bad expected hex\n", name);
        failures++;
        return;
    }

    if (sm3_digest_ex((const uint8_t *)msg, len, got, impl) != 0) {
        printf("  [FAIL] %s: digest_ex failed\n", name);
        failures++;
        return;
    }

    to_hex(got, SM3_DIGEST_SIZE, got_hex);
    if (memcmp(got, exp, SM3_DIGEST_SIZE) != 0) {
        printf("  [FAIL] %s [%s]\n", name, sm3_impl_name(impl));
        printf("         expected: %s\n", hex_expected);
        printf("         got:      %s\n", got_hex);
        failures++;
    } else {
        printf("  [ OK ] %s [%s]\n", name, sm3_impl_name(impl));
    }
}

/* "abc" */
static const char *VEC_ABC =
    "66c7f0f462eeedd9d1f2d46bdc10e4e24167c4875cf2f7a2297da02b8f4ba8e0";

/* empty message */
static const char *VEC_EMPTY =
    "1ab21d8355cfa17f8e61194831e81a8f22bec8c728fefb747ed035eb5082aa2b";

/*
 * 16 x "abcd" = 64 bytes (exactly one block before padding)
 * Published: 0xdebe9ff9... (common SM3 test suite)
 */
static const char *MSG_ABCD16 =
    "abcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcd";
static const char *VEC_ABCD16 =
    "debe9ff92275b8a138604889c18e5a4d6fdb70e5387e5765293dcba39c0c5732";

static void run_suite_for_impl(sm3_impl_t impl)
{
    printf("== implementation: %s ==\n", sm3_impl_name(impl));
    expect_digest("empty", "", 0, VEC_EMPTY, impl);
    expect_digest("abc", "abc", 3, VEC_ABC, impl);
    expect_digest("64*abcd", MSG_ABCD16, 64, VEC_ABCD16, impl);

    /* Incremental vs one-shot for "abc" */
    if (sm3_impl_available(impl)) {
        sm3_ctx ctx;
        uint8_t a[SM3_DIGEST_SIZE], b[SM3_DIGEST_SIZE];
        sm3_digest_ex((const uint8_t *)"abc", 3, a, impl);
        sm3_init_ex(&ctx, impl);
        sm3_update(&ctx, (const uint8_t *)"a", 1);
        sm3_update(&ctx, (const uint8_t *)"b", 1);
        sm3_update(&ctx, (const uint8_t *)"c", 1);
        sm3_final(&ctx, b);
        if (memcmp(a, b, SM3_DIGEST_SIZE) != 0) {
            printf("  [FAIL] incremental abc [%s]\n", sm3_impl_name(impl));
            failures++;
        } else {
            printf("  [ OK ] incremental abc [%s]\n", sm3_impl_name(impl));
        }
    }
    printf("\n");
}

int main(void)
{
    printf("SM3 test vectors\n");
    printf("CPU AVX2=%d AVX512F=%d NEON=%d\n",
           sm3_cpu_has_avx2(), sm3_cpu_has_avx512f(), sm3_cpu_has_neon());
    printf("Default: %s\n\n", sm3_active_impl_desc());

    run_suite_for_impl(SM3_IMPL_REF);
#if defined(SM3_HAS_AVX2)
    run_suite_for_impl(SM3_IMPL_AVX2);
#endif
#if defined(SM3_HAS_AVX512)
    run_suite_for_impl(SM3_IMPL_AVX512);
#endif
#if defined(SM3_HAS_NEON)
    run_suite_for_impl(SM3_IMPL_NEON);
#endif
    run_suite_for_impl(SM3_IMPL_AUTO);

    if (failures) {
        printf("RESULT: %d failure(s)\n", failures);
        return 1;
    }
    printf("RESULT: all passed\n");
    return 0;
}
