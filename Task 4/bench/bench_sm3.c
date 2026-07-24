/**
 * Throughput / latency micro-benchmark for SM3 implementations.
 */
#include "sm3.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#  define WIN32_LEAN_AND_MEAN
#  include <windows.h>
static double now_s(void)
{
    static LARGE_INTEGER freq;
    static int init = 0;
    LARGE_INTEGER c;
    if (!init) {
        QueryPerformanceFrequency(&freq);
        init = 1;
    }
    QueryPerformanceCounter(&c);
    return (double)c.QuadPart / (double)freq.QuadPart;
}
#else
#  include <time.h>
static double now_s(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}
#endif

static void bench_one(sm3_impl_t impl, size_t msg_len, int rounds)
{
    uint8_t *buf;
    uint8_t digest[SM3_DIGEST_SIZE];
    double t0, t1, elapsed, mib, mbps;
    int i;

    if (!sm3_impl_available(impl)) {
        printf("  %-10s  len=%8zu  SKIP (unavailable)\n", sm3_impl_name(impl), msg_len);
        return;
    }

    buf = (uint8_t *)malloc(msg_len ? msg_len : 1);
    if (!buf) {
        fprintf(stderr, "oom\n");
        return;
    }
    for (i = 0; i < (int)msg_len; i++) {
        buf[i] = (uint8_t)(i * 131u);
    }

    for (i = 0; i < 8; i++) {
        sm3_digest_ex(buf, msg_len, digest, impl);
    }

    t0 = now_s();
    for (i = 0; i < rounds; i++) {
        sm3_digest_ex(buf, msg_len, digest, impl);
    }
    t1 = now_s();
    elapsed = t1 - t0;
    mib = ((double)msg_len * (double)rounds) / (1024.0 * 1024.0);
    mbps = (elapsed > 0.0) ? (mib / elapsed) : 0.0;

    printf("  %-10s  len=%8zu  rounds=%6d  time=%7.4fs  thr=%10.2f MiB/s\n",
           sm3_impl_name(impl), msg_len, rounds, elapsed, mbps);

    free(buf);
}

/** Aggregate throughput of hashing 4 independent messages at once. */
static void bench_mb4(size_t msg_len, int rounds)
{
    uint8_t *bufs[SM3_MB4_LANES];
    const uint8_t *msgs[SM3_MB4_LANES];
    uint8_t digests[SM3_MB4_LANES][SM3_DIGEST_SIZE];
    double t0, t1, elapsed, mib, mbps;
    int i, lane;

    for (lane = 0; lane < SM3_MB4_LANES; lane++) {
        size_t j;
        bufs[lane] = (uint8_t *)malloc(msg_len ? msg_len : 1);
        if (!bufs[lane]) {
            fprintf(stderr, "oom\n");
            return;
        }
        for (j = 0; j < msg_len; j++) {
            bufs[lane][j] = (uint8_t)(j * 17u + (unsigned)lane * 3u);
        }
        msgs[lane] = bufs[lane];
    }

    for (i = 0; i < 4; i++) {
        sm3_mb4_digest(msgs, msg_len, digests);
    }

    t0 = now_s();
    for (i = 0; i < rounds; i++) {
        sm3_mb4_digest(msgs, msg_len, digests);
    }
    t1 = now_s();
    elapsed = t1 - t0;
    mib = ((double)msg_len * (double)rounds * (double)SM3_MB4_LANES) / (1024.0 * 1024.0);
    mbps = (elapsed > 0.0) ? (mib / elapsed) : 0.0;

    printf("  %-10s  len=%8zu  rounds=%6d  time=%7.4fs  thr=%10.2f MiB/s  (4x aggregate)\n",
           "mb4", msg_len, rounds, elapsed, mbps);

    for (lane = 0; lane < SM3_MB4_LANES; lane++) {
        free(bufs[lane]);
    }
}

/** Four sequential ref digests for fair multi-stream comparison. */
static void bench_ref4(size_t msg_len, int rounds)
{
    uint8_t *bufs[SM3_MB4_LANES];
    uint8_t digests[SM3_MB4_LANES][SM3_DIGEST_SIZE];
    double t0, t1, elapsed, mib, mbps;
    int i, lane;

    for (lane = 0; lane < SM3_MB4_LANES; lane++) {
        size_t j;
        bufs[lane] = (uint8_t *)malloc(msg_len ? msg_len : 1);
        if (!bufs[lane]) {
            fprintf(stderr, "oom\n");
            return;
        }
        for (j = 0; j < msg_len; j++) {
            bufs[lane][j] = (uint8_t)(j * 17u + (unsigned)lane * 3u);
        }
    }

    for (i = 0; i < 4; i++) {
        for (lane = 0; lane < SM3_MB4_LANES; lane++) {
            sm3_digest_ex(bufs[lane], msg_len, digests[lane], SM3_IMPL_REF);
        }
    }

    t0 = now_s();
    for (i = 0; i < rounds; i++) {
        for (lane = 0; lane < SM3_MB4_LANES; lane++) {
            sm3_digest_ex(bufs[lane], msg_len, digests[lane], SM3_IMPL_REF);
        }
    }
    t1 = now_s();
    elapsed = t1 - t0;
    mib = ((double)msg_len * (double)rounds * (double)SM3_MB4_LANES) / (1024.0 * 1024.0);
    mbps = (elapsed > 0.0) ? (mib / elapsed) : 0.0;

    printf("  %-10s  len=%8zu  rounds=%6d  time=%7.4fs  thr=%10.2f MiB/s  (4x sequential ref)\n",
           "ref4", msg_len, rounds, elapsed, mbps);

    for (lane = 0; lane < SM3_MB4_LANES; lane++) {
        free(bufs[lane]);
    }
}

int main(int argc, char **argv)
{
    size_t sizes[] = {64, 1024, 8192, 1024 * 1024};
    int default_rounds[] = {50000, 10000, 2500, 100};
    size_t n = sizeof(sizes) / sizeof(sizes[0]);
    size_t i;
    int scale = 1;

    if (argc > 1) {
        scale = atoi(argv[1]);
        if (scale < 1) {
            scale = 1;
        }
    }

    printf("SM3 benchmark\n");
    printf("CPU AVX2=%d AVX512F=%d NEON=%d  mb_max_lanes=%d\n",
           sm3_cpu_has_avx2(), sm3_cpu_has_avx512f(), sm3_cpu_has_neon(),
           sm3_mb_max_lanes());
    printf("Default impl: %s\n", sm3_active_impl_desc());
    printf("scale=%d\n\n", scale);

    printf("=== single-buffer ===\n");
    for (i = 0; i < n; i++) {
        int rounds = default_rounds[i] * scale;
        printf("Message size %zu bytes:\n", sizes[i]);
        bench_one(SM3_IMPL_REF, sizes[i], rounds);
#if defined(SM3_HAS_AVX2)
        bench_one(SM3_IMPL_AVX2, sizes[i], rounds);
#endif
#if defined(SM3_HAS_AVX512)
        bench_one(SM3_IMPL_AVX512, sizes[i], rounds);
#endif
#if defined(SM3_HAS_NEON)
        bench_one(SM3_IMPL_NEON, sizes[i], rounds);
#endif
        printf("\n");
    }

    printf("=== multi-buffer (4 independent streams) ===\n");
    for (i = 0; i < n; i++) {
        int rounds = default_rounds[i] * scale;
        printf("Message size %zu bytes:\n", sizes[i]);
        bench_ref4(sizes[i], rounds);
        bench_mb4(sizes[i], rounds);
        printf("\n");
    }

    return 0;
}
