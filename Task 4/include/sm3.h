/**
 * sm3.h — SM3 cryptographic hash (GM/T 0004-2012 / ISO/IEC 10118-3)
 *
 * Portable API + selectable implementations:
 *   - SM3_IMPL_REF     pure C (general-purpose registers only)
 *   - SM3_IMPL_AVX2    x86 hybrid: SIMD schedule + GPR compression
 *   - SM3_IMPL_AVX512  x86 hybrid: wider SIMD schedule + GPR compression
 *   - SM3_IMPL_NEON    ARM64 hybrid: NEON schedule + GPR compression
 *   - SM3_IMPL_AUTO    runtime pick of the best available on this CPU
 *
 * Layout: common ref/padding + src/x86/* + src/arm64/* (one tree, per-arch build).
 */
#ifndef SM3_OPT_SM3_H
#define SM3_OPT_SM3_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SM3_DIGEST_SIZE 32
#define SM3_BLOCK_SIZE  64

typedef struct sm3_ctx {
    uint64_t total_bits;          /* message length so far, in bits */
    uint32_t state[8];            /* chaining value A..H */
    uint8_t  buffer[SM3_BLOCK_SIZE];
    size_t   buffer_len;          /* bytes pending in buffer (0..63) */
    int      impl;                /* sm3_impl_t snapshot at init/set */
} sm3_ctx;

/**
 * Implementation selectors.
 * Query availability with sm3_impl_available().
 */
typedef enum sm3_impl {
    SM3_IMPL_AUTO   = 0,
    SM3_IMPL_REF    = 1,
    SM3_IMPL_AVX2   = 2,
    SM3_IMPL_AVX512 = 3,
    SM3_IMPL_NEON   = 4
} sm3_impl_t;

/* ---- one-shot --------------------------------------------------------- */

/** Hash `len` bytes at `data` into `out[32]` using the current default impl. */
void sm3_digest(const uint8_t *data, size_t len, uint8_t out[SM3_DIGEST_SIZE]);

/** Same as sm3_digest but with an explicit implementation. Returns 0 on success. */
int  sm3_digest_ex(const uint8_t *data, size_t len,
                   uint8_t out[SM3_DIGEST_SIZE], sm3_impl_t impl);

/* ---- incremental API -------------------------------------------------- */

void sm3_init(sm3_ctx *ctx);
void sm3_init_ex(sm3_ctx *ctx, sm3_impl_t impl);
void sm3_update(sm3_ctx *ctx, const uint8_t *data, size_t len);
void sm3_final(sm3_ctx *ctx, uint8_t out[SM3_DIGEST_SIZE]);

/** Wipe context (best-effort; not a full secure-memory guarantee). */
void sm3_ctx_clear(sm3_ctx *ctx);

/* ---- implementation control ------------------------------------------- */

/**
 * Set process-wide default implementation for sm3_init / sm3_digest.
 * Returns 0 on success, -1 if `impl` is unavailable on this CPU/build.
 * SM3_IMPL_AUTO always succeeds and resolves to the best available.
 */
int  sm3_set_impl(sm3_impl_t impl);

/** Current process-wide default (resolved; never returns SM3_IMPL_AUTO). */
sm3_impl_t sm3_get_impl(void);

/** Non-zero if this build + CPU can run `impl` (AUTO always true). */
int  sm3_impl_available(sm3_impl_t impl);

/** Stable name: "ref", "avx2", "avx512", "neon", or "auto". */
const char *sm3_impl_name(sm3_impl_t impl);

/** Human-readable description of the active default. */
const char *sm3_active_impl_desc(void);

/* ---- CPU feature probes ----------------------------------------------- */

int sm3_cpu_has_avx2(void);
int sm3_cpu_has_avx512f(void);
int sm3_cpu_has_neon(void);

/* ---- low-level block compress (for tests / instrumentation) ----------- */

typedef void (*sm3_compress_fn)(uint32_t state[8], const uint8_t block[SM3_BLOCK_SIZE]);

sm3_compress_fn sm3_get_compress_fn(sm3_impl_t impl);

void sm3_compress_ref(uint32_t state[8], const uint8_t block[SM3_BLOCK_SIZE]);

#if defined(SM3_HAS_AVX2)
void sm3_compress_avx2(uint32_t state[8], const uint8_t block[SM3_BLOCK_SIZE]);
#endif

#if defined(SM3_HAS_AVX512)
void sm3_compress_avx512(uint32_t state[8], const uint8_t block[SM3_BLOCK_SIZE]);
#endif

#if defined(SM3_HAS_NEON)
void sm3_compress_neon(uint32_t state[8], const uint8_t block[SM3_BLOCK_SIZE]);
#endif

/* ---- multi-buffer (parallel independent messages) --------------------- */

/** Parallel lane count used by the AVX2 multi-buffer kernel. */
#define SM3_MB4_LANES 4

/**
 * Maximum hardware multi-buffer width available in this build+CPU.
 * Returns 4 when AVX2 multi-buffer is usable, otherwise 1 (scalar only).
 */
int sm3_mb_max_lanes(void);

/**
 * Hash exactly four independent messages of equal length `len`.
 * On AVX2: 4-lane SIMD for full blocks (expand + compression rounds).
 * Otherwise: sequential digests (correctness-preserving fallback).
 * digests[i] receives the SM3 digest of msgs[i].
 */
void sm3_mb4_digest(const uint8_t *const msgs[SM3_MB4_LANES],
                    size_t len,
                    uint8_t digests[SM3_MB4_LANES][SM3_DIGEST_SIZE]);

/**
 * Hash `num` independent messages (arbitrary lengths).
 * Groups of four equal-length streams use multi-buffer when possible;
 * remaining messages use the sequential path.
 * digests must provide space for num * SM3_DIGEST_SIZE bytes as digests[num][32].
 */
void sm3_mb_digest(size_t num,
                   const uint8_t *const *msgs,
                   const size_t *lens,
                   uint8_t digests[][SM3_DIGEST_SIZE]);

#if defined(SM3_HAS_AVX2)
/**
 * Compress one 64-byte block for four messages in parallel (AVX2).
 * state_lane[lane][0..7] is A..H for that message; blocks[lane] is 64 bytes.
 */
void sm3_mb4_compress_avx2(uint32_t state_lane[SM3_MB4_LANES][8],
                           const uint8_t *const blocks[SM3_MB4_LANES]);
#endif

#ifdef __cplusplus
}
#endif

#endif /* SM3_OPT_SM3_H */
