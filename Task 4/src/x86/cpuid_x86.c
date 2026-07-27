/**
 * cpuid_x86.c — Runtime CPU feature detection for AVX2 / AVX512F.
 */
#include "sm3.h"

#if defined(_MSC_VER)
#  include <intrin.h>
#elif defined(__GNUC__) || defined(__clang__)
#  include <cpuid.h>
#endif

static int g_probed = 0;
static int g_has_avx2 = 0;
static int g_has_avx512f = 0;

#if defined(_MSC_VER)
static void do_cpuid(int leaf, int subleaf, int regs[4])
{
    __cpuidex(regs, leaf, subleaf);
}

static unsigned long long do_xgetbv(unsigned int idx)
{
    return _xgetbv(idx);
}
#elif defined(__GNUC__) || defined(__clang__)
static void do_cpuid(int leaf, int subleaf, int regs[4])
{
    unsigned int a, b, c, d;
    __cpuid_count((unsigned int)leaf, (unsigned int)subleaf, a, b, c, d);
    regs[0] = (int)a;
    regs[1] = (int)b;
    regs[2] = (int)c;
    regs[3] = (int)d;
}

static unsigned long long do_xgetbv(unsigned int idx)
{
    unsigned int eax, edx;
    __asm__ volatile("xgetbv" : "=a"(eax), "=d"(edx) : "c"(idx));
    return ((unsigned long long)edx << 32) | eax;
}
#else
static void do_cpuid(int leaf, int subleaf, int regs[4])
{
    (void)leaf;
    (void)subleaf;
    regs[0] = regs[1] = regs[2] = regs[3] = 0;
}
static unsigned long long do_xgetbv(unsigned int idx)
{
    (void)idx;
    return 0;
}
#endif

static void probe_once(void)
{
    int regs[4];
    int max_leaf;
    int osxsave;
    unsigned long long xcr0;

    if (g_probed) {
        return;
    }
    g_probed = 1;

    do_cpuid(0, 0, regs);
    max_leaf = regs[0];
    if (max_leaf < 1) {
        return;
    }

    do_cpuid(1, 0, regs);
    /* ECX bit 27: OSXSAVE; bit 28: AVX */
    osxsave = (regs[2] >> 27) & 1;
    if (!osxsave || !((regs[2] >> 28) & 1)) {
        return;
    }

    xcr0 = do_xgetbv(0);
    /* XMM (bit0) + YMM (bit1) must be enabled by OS */
    if ((xcr0 & 0x6ull) != 0x6ull) {
        return;
    }

    if (max_leaf >= 7) {
        do_cpuid(7, 0, regs);
        /* EBX bit 5: AVX2 */
        if (regs[1] & (1 << 5)) {
            g_has_avx2 = 1;
        }
        /* AVX512F needs Opmask+ZMM OS enable: XCR0 bits 5,6,7 */
        if ((xcr0 & 0xE0ull) == 0xE0ull) {
            /* EBX bit 16: AVX512F */
            if (regs[1] & (1 << 16)) {
                g_has_avx512f = 1;
            }
        }
    }
}

int sm3_cpu_has_avx2(void)
{
    probe_once();
    return g_has_avx2;
}

int sm3_cpu_has_avx512f(void)
{
    probe_once();
    return g_has_avx512f;
}

int sm3_cpu_has_neon(void)
{
    return 0;
}
