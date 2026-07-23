/**
 * cpu_arm.c — ARM64 feature probes (and stubs for x86-only queries).
 *
 * On ARMv8-A 64-bit (ARM64), NEON is mandatory in the baseline
 * architecture, so sm3_cpu_has_neon() is always 1 when this
 * translation unit is built.
 */
#include "sm3.h"

int sm3_cpu_has_neon(void)
{
    return 1;
}

int sm3_cpu_has_avx2(void)
{
    return 0;
}

int sm3_cpu_has_avx512f(void)
{
    return 0;
}
