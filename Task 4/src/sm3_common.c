/**
 * sm3_common.c — Padding, incremental API, implementation dispatch.
 */
#include "sm3_internal.h"

/* Process-wide default: AUTO until first use resolves it. */
static sm3_impl_t g_default_impl = SM3_IMPL_AUTO;
static sm3_impl_t g_resolved_default = SM3_IMPL_REF;
static int        g_default_resolved = 0;

static sm3_impl_t pick_best_impl(void)
{
    /* Priority: arch-native SIMD first, then ref. */
#if defined(SM3_HAS_AVX512)
    if (sm3_cpu_has_avx512f()) {
        return SM3_IMPL_AVX512;
    }
#endif
#if defined(SM3_HAS_AVX2)
    if (sm3_cpu_has_avx2()) {
        return SM3_IMPL_AVX2;
    }
#endif
#if defined(SM3_HAS_NEON)
    if (sm3_cpu_has_neon()) {
        return SM3_IMPL_NEON;
    }
#endif
    return SM3_IMPL_REF;
}

int sm3_resolve_impl(sm3_impl_t impl)
{
    if (impl == SM3_IMPL_AUTO) {
        return (int)pick_best_impl();
    }

    switch (impl) {
    case SM3_IMPL_REF:
        return (int)SM3_IMPL_REF;
#if defined(SM3_HAS_AVX2)
    case SM3_IMPL_AVX2:
        return sm3_cpu_has_avx2() ? (int)SM3_IMPL_AVX2 : -1;
#endif
#if defined(SM3_HAS_AVX512)
    case SM3_IMPL_AVX512:
        return sm3_cpu_has_avx512f() ? (int)SM3_IMPL_AVX512 : -1;
#endif
#if defined(SM3_HAS_NEON)
    case SM3_IMPL_NEON:
        return sm3_cpu_has_neon() ? (int)SM3_IMPL_NEON : -1;
#endif
    default:
        return -1;
    }
}

sm3_compress_fn sm3_select_compress(sm3_impl_t impl)
{
    int r = sm3_resolve_impl(impl);
    if (r < 0) {
        return sm3_compress_ref;
    }

    switch ((sm3_impl_t)r) {
#if defined(SM3_HAS_AVX2)
    case SM3_IMPL_AVX2:
        return sm3_compress_avx2;
#endif
#if defined(SM3_HAS_AVX512)
    case SM3_IMPL_AVX512:
        return sm3_compress_avx512;
#endif
#if defined(SM3_HAS_NEON)
    case SM3_IMPL_NEON:
        return sm3_compress_neon;
#endif
    case SM3_IMPL_REF:
    default:
        return sm3_compress_ref;
    }
}

sm3_compress_fn sm3_get_compress_fn(sm3_impl_t impl)
{
    return sm3_select_compress(impl);
}

int sm3_impl_available(sm3_impl_t impl)
{
    return sm3_resolve_impl(impl) >= 0;
}

const char *sm3_impl_name(sm3_impl_t impl)
{
    switch (impl) {
    case SM3_IMPL_AUTO:   return "auto";
    case SM3_IMPL_REF:    return "ref";
    case SM3_IMPL_AVX2:   return "avx2";
    case SM3_IMPL_AVX512: return "avx512";
    case SM3_IMPL_NEON:   return "neon";
    default:              return "unknown";
    }
}

static void ensure_default_resolved(void)
{
    if (!g_default_resolved) {
        g_resolved_default = (sm3_impl_t)sm3_resolve_impl(g_default_impl);
        if ((int)g_resolved_default < 0) {
            g_resolved_default = SM3_IMPL_REF;
        }
        g_default_resolved = 1;
    }
}

int sm3_set_impl(sm3_impl_t impl)
{
    int r = sm3_resolve_impl(impl);
    if (r < 0) {
        return -1;
    }
    g_default_impl = impl;
    g_resolved_default = (sm3_impl_t)r;
    g_default_resolved = 1;
    return 0;
}

sm3_impl_t sm3_get_impl(void)
{
    ensure_default_resolved();
    return g_resolved_default;
}

const char *sm3_active_impl_desc(void)
{
    ensure_default_resolved();
    switch (g_resolved_default) {
    case SM3_IMPL_REF:
        return "ref (scalar C, GPR only)";
#if defined(SM3_HAS_AVX2)
    case SM3_IMPL_AVX2:
        return "avx2 hybrid (SIMD expand + GPR rounds)";
#endif
#if defined(SM3_HAS_AVX512)
    case SM3_IMPL_AVX512:
        return "avx512 hybrid (SIMD expand + GPR rounds)";
#endif
#if defined(SM3_HAS_NEON)
    case SM3_IMPL_NEON:
        return "neon hybrid (SIMD expand + GPR rounds)";
#endif
    default:
        return "unknown";
    }
}

void sm3_init_ex(sm3_ctx *ctx, sm3_impl_t impl)
{
    int r = sm3_resolve_impl(impl);
    if (r < 0) {
        r = (int)SM3_IMPL_REF;
    }

    ctx->total_bits = 0;
    ctx->buffer_len = 0;
    ctx->impl = r;
    memcpy(ctx->state, SM3_IV, sizeof(SM3_IV));
    memset(ctx->buffer, 0, sizeof(ctx->buffer));
}

void sm3_init(sm3_ctx *ctx)
{
    ensure_default_resolved();
    sm3_init_ex(ctx, g_resolved_default);
}

void sm3_update(sm3_ctx *ctx, const uint8_t *data, size_t len)
{
    sm3_compress_fn compress;
    size_t offset = 0;

    if (len == 0 || data == NULL) {
        return;
    }

    compress = sm3_select_compress((sm3_impl_t)ctx->impl);

    /* Fill partial buffer first. */
    if (ctx->buffer_len > 0) {
        size_t need = SM3_BLOCK_SIZE - ctx->buffer_len;
        size_t take = (len < need) ? len : need;
        memcpy(ctx->buffer + ctx->buffer_len, data, take);
        ctx->buffer_len += take;
        offset += take;
        if (ctx->buffer_len == SM3_BLOCK_SIZE) {
            compress(ctx->state, ctx->buffer);
            ctx->total_bits += (uint64_t)SM3_BLOCK_SIZE * 8u;
            ctx->buffer_len = 0;
        }
    }

    /* Full blocks from the input stream. */
    while (offset + SM3_BLOCK_SIZE <= len) {
        compress(ctx->state, data + offset);
        ctx->total_bits += (uint64_t)SM3_BLOCK_SIZE * 8u;
        offset += SM3_BLOCK_SIZE;
    }

    /* Remainder. */
    if (offset < len) {
        size_t rem = len - offset;
        memcpy(ctx->buffer, data + offset, rem);
        ctx->buffer_len = rem;
    }
}

void sm3_final(sm3_ctx *ctx, uint8_t out[SM3_DIGEST_SIZE])
{
    sm3_compress_fn compress = sm3_select_compress((sm3_impl_t)ctx->impl);
    uint64_t total_bits = ctx->total_bits + (uint64_t)ctx->buffer_len * 8u;
    size_t i;
    uint8_t pad[SM3_BLOCK_SIZE * 2];
    size_t pad_len;
    size_t n = ctx->buffer_len;

    /* Copy remaining bytes + 0x80 */
    memset(pad, 0, sizeof(pad));
    if (n > 0) {
        memcpy(pad, ctx->buffer, n);
    }
    pad[n] = 0x80;

    /*
     * If not enough room for 8-byte length (need n+1+8 <= 64),
     * use two blocks.
     */
    if (n <= 55) {
        pad_len = 56;
    } else {
        pad_len = 56 + SM3_BLOCK_SIZE;
    }

    /* Append big-endian 64-bit bit-length */
    pad[pad_len + 0] = (uint8_t)(total_bits >> 56);
    pad[pad_len + 1] = (uint8_t)(total_bits >> 48);
    pad[pad_len + 2] = (uint8_t)(total_bits >> 40);
    pad[pad_len + 3] = (uint8_t)(total_bits >> 32);
    pad[pad_len + 4] = (uint8_t)(total_bits >> 24);
    pad[pad_len + 5] = (uint8_t)(total_bits >> 16);
    pad[pad_len + 6] = (uint8_t)(total_bits >>  8);
    pad[pad_len + 7] = (uint8_t)(total_bits      );

    compress(ctx->state, pad);
    if (pad_len > 56) {
        compress(ctx->state, pad + SM3_BLOCK_SIZE);
    }

    for (i = 0; i < 8; i++) {
        sm3_store_be32(out + 4 * i, ctx->state[i]);
    }

    sm3_ctx_clear(ctx);
}

void sm3_ctx_clear(sm3_ctx *ctx)
{
    if (ctx) {
        volatile uint8_t *p = (volatile uint8_t *)ctx;
        size_t i;
        for (i = 0; i < sizeof(*ctx); i++) {
            p[i] = 0;
        }
    }
}

void sm3_digest(const uint8_t *data, size_t len, uint8_t out[SM3_DIGEST_SIZE])
{
    sm3_ctx ctx;
    sm3_init(&ctx);
    sm3_update(&ctx, data, len);
    sm3_final(&ctx, out);
}

int sm3_digest_ex(const uint8_t *data, size_t len,
                  uint8_t out[SM3_DIGEST_SIZE], sm3_impl_t impl)
{
    sm3_ctx ctx;
    if (sm3_resolve_impl(impl) < 0) {
        return -1;
    }
    sm3_init_ex(&ctx, impl);
    sm3_update(&ctx, data, len);
    sm3_final(&ctx, out);
    return 0;
}
