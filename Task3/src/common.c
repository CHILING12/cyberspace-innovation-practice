/**
 * common.c — 公共工具函数实现
 */

#include "common.h"
#include <stdio.h>

/* ==========================================================================
 * GF(2^128) 乘法实现
 * ========================================================================== */

/* 不可约多项式: x^128 + x^7 + x^2 + x + 1
 * 约简常数 R = 0xE1 = 11100001b (x^7 + x^2 + x + 1 左移高位) */

/* 基本位移实现：逐位乘法 */
void gf128_mul_basic(uint8_t *z, const uint8_t *x, const uint8_t *y) {
    uint8_t v[16];
    memset(z, 0, 16);
    memcpy(v, y, 16);

    /* 标准二进制乘法：从 LSB 到 MSB 处理 x 的每个比特
     * GCM 比特序: byte 15 bit 0 = x^0, byte 0 bit 7 = x^{127} */
    for (int i = 0; i < 128; i++) {
        int byte_idx = 15 - (i / 8);
        int bit_idx  = i % 8;
        if (x[byte_idx] & (1 << bit_idx)) {
            xor_bytes_inplace(z, v, 16);
        }
        /* v = v * x (左移 = 乘以 x)，gf128_dbl 自动处理约简 */
        gf128_dbl(v, v);
    }
}

/* 4-bit 查表 GHASH —— 每 4 bit 查 16 项预计算表 */
void gf128_mul_table4(uint8_t *z, const uint8_t *x, const uint8_t *y) {
    /* 预计算表: table[i] = i * y (i = 0..15) */
    uint8_t table[16][16];
    memset(table[0], 0, 16);
    memcpy(table[1], y, 16);

    for (int i = 2; i < 16; i++) {
        if (i & 1) {
            xor_bytes(table[i], table[i - 1], y, 16);
        } else {
            gf128_dbl(table[i], table[i / 2]);
        }
    }

    memset(z, 0, 16);
    for (int i = 0; i < 16; i++) {
        uint8_t byte = x[i];
        /* 高 nibble */
        int hi = (byte >> 4) & 0x0F;
        uint8_t tmp[16];
        xor_bytes(tmp, table[hi], z, 16);
        /* z = z * 16 (在 GF(2^128) 中左移 4 bit) */
        for (int k = 0; k < 4; k++) gf128_dbl(z, z);
        /* 低 nibble */
        int lo = byte & 0x0F;
        xor_bytes(z, z, table[lo], 16);
    }
}

/* 8-bit 查表 GHASH —— 每 8 bit 查 256 项预计算表 */
void gf128_mul_table8(uint8_t *z, const uint8_t *x, const uint8_t *y) {
    uint8_t table[256][16];
    memset(table[0], 0, 16);
    memcpy(table[1], y, 16);

    for (int i = 2; i < 256; i++) {
        if (i & 1) {
            xor_bytes(table[i], table[i - 1], y, 16);
        } else {
            gf128_dbl(table[i], table[i / 2]);
        }
    }

    memset(z, 0, 16);
    for (int i = 0; i < 16; i++) {
        uint8_t byte = x[i];
        /* z = z * 256 (左移 8 bit) */
        for (int k = 0; k < 8; k++) gf128_dbl(z, z);
        xor_bytes_inplace(z, table[byte], 16);
    }
}

/* ==========================================================================
 * CPU 特性检测（x86）
 * ========================================================================== */

#if defined(__x86_64__) || defined(_M_X64) || defined(__i386__)

#include <cpuid.h>  /* GCC/Clang cpuid intrinsic */

static int g_cpu_features = 0;

void cpu_detect_features(void) {
    unsigned int eax, ebx, ecx, edx;
    g_cpu_features = 0;

    /* CPUID level 1: ECX */
    if (__get_cpuid(1, &eax, &ebx, &ecx, &edx)) {
        if (ecx & bit_SSSE3)   g_cpu_features |= CPU_FEAT_SSSE3;
        if (ecx & bit_AES)     g_cpu_features |= CPU_FEAT_AESNI;
        if (ecx & bit_PCLMUL)  g_cpu_features |= CPU_FEAT_PCLMUL;
        if (ecx & bit_AVX)     g_cpu_features |= CPU_FEAT_AVX;
        if (ecx & bit_F16C)    /* AVX2 在 level 7 */;
    }

    /* CPUID level 7: EBX */
    if (__get_cpuid_count(7, 0, &eax, &ebx, &ecx, &edx)) {
        if (ebx & bit_AVX2)    g_cpu_features |= CPU_FEAT_AVX2;
        if (ebx & bit_AVX512F) g_cpu_features |= CPU_FEAT_AVX512F;
        if (ecx & bit_VAES)    g_cpu_features |= CPU_FEAT_VAES;
        if (ecx & bit_VPCLMULQDQ) g_cpu_features |= CPU_FEAT_VPCLMUL;
        if (ecx & bit_GFNI)    g_cpu_features |= CPU_FEAT_GFNI;
    }
}

int cpu_has_feature(cpu_feature_t feature) {
    return (g_cpu_features & feature) != 0;
}

#elif defined(__aarch64__) || defined(_M_ARM64)

static int g_cpu_features = 0;

void cpu_detect_features(void) {
    g_cpu_features = 0;
    /* ARM NEON 在 AArch64 上总是可用 */
    g_cpu_features |= CPU_FEAT_NEON;

    /* 检测 ARM AES 和 PMULL */
#if defined(__ARM_FEATURE_AES)
    g_cpu_features |= CPU_FEAT_ARM_AES;
#endif
#if defined(__ARM_FEATURE_PMULL)
    g_cpu_features |= CPU_FEAT_PMULL;
#endif
}

int cpu_has_feature(cpu_feature_t feature) {
    return (g_cpu_features & feature) != 0;
}

#else

static int g_cpu_features = 0;

void cpu_detect_features(void) {
    g_cpu_features = 0;
}

int cpu_has_feature(cpu_feature_t feature) {
    (void)feature;
    return 0;
}

#endif

void cpu_print_features(void) {
    printf("CPU Features:\n");
    printf("  SSSE3:    %s\n", cpu_has_feature(CPU_FEAT_SSSE3)    ? "YES" : "NO");
    printf("  AES-NI:   %s\n", cpu_has_feature(CPU_FEAT_AESNI)    ? "YES" : "NO");
    printf("  PCLMUL:   %s\n", cpu_has_feature(CPU_FEAT_PCLMUL)   ? "YES" : "NO");
    printf("  AVX:      %s\n", cpu_has_feature(CPU_FEAT_AVX)      ? "YES" : "NO");
    printf("  AVX2:     %s\n", cpu_has_feature(CPU_FEAT_AVX2)     ? "YES" : "NO");
    printf("  AVX-512F: %s\n", cpu_has_feature(CPU_FEAT_AVX512F)  ? "YES" : "NO");
    printf("  VAES:     %s\n", cpu_has_feature(CPU_FEAT_VAES)     ? "YES" : "NO");
    printf("  VPCLMUL:  %s\n", cpu_has_feature(CPU_FEAT_VPCLMUL)  ? "YES" : "NO");
    printf("  GFNI:     %s\n", cpu_has_feature(CPU_FEAT_GFNI)     ? "YES" : "NO");
}
