# 对称密码算法的软件实现与优化

## — AES/SM4/GIFT/TWINE 多级优化与 CTR/GCM/XTS 模式

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Language](https://img.shields.io/badge/language-C11-green.svg)](src/)
[![Platform](https://img.shields.io/badge/platform-x86--64%20%7C%20ARM-lightgrey.svg)]()

---

## 项目概述

本项目从统一、可验证的 C 语言基本实现出发，对 **AES-128/256、SM4、GIFT-128、TWINE-128** 四种对称分组密码进行系统性的软件优化，覆盖以下技术路线：

- **标量优化**：循环展开、寄存器复用、数据布局优化（V1）
- **T-table**：合并 S-Box + 线性层 + 置换层的预计算查表（V2）
- **SIMD shuffle**：SSSE3/AVX2 并行字节混洗，天然适配 4-bit S-Box（V3/V4）
- **专用指令**：AES-NI、VAES、PCLMULQDQ、VPCLMULQDQ（V6）
- **模式优化**：CTR 多缓冲、GCM GHASH 折叠、XTS 向量化 tweak（M0–M6）

在此基础上实现了 CTR、GCM 和 XTS 三种工作模式，并引入 PCLMULQDQ/VPCLMULQDQ 指令加速 GHASH 的 GF(2¹²⁸) 乘法，支持 4-block 和 8-block folding 以缩短依赖链。

## 支持的算法

| 算法 | 分组长度 | 密钥长度 | 轮数 | 结构 |
|------|----------|----------|------|------|
| AES-128 | 128-bit | 128-bit | 10 | SPN（8-bit S-Box） |
| AES-256 | 128-bit | 256-bit | 14 | SPN（8-bit S-Box） |
| SM4 | 128-bit | 128-bit | 32 | 非平衡 Feistel |
| GIFT-128 | 128-bit | 128-bit | 40 | SPN（4-bit S-Box） |
| TWINE-128 | 64-bit | 128-bit | 36 | 广义 Feistel（4-bit S-Box） |

## 优化层次

| 编号 | 说明 |
|------|------|
| V0 | 直接标量参考实现（按标准描述逐轮执行） |
| V1 | 标量循环展开、寄存器复用、数据布局优化 |
| V2 | T-table（合并 S-Box + 线性层 + 置换层）|
| V3 | SSSE3/NEON shuffle（单分组内或多分组并行）|
| V4 | AVX2 多分组 shuffle/bitslice |
| V5 | AVX-512 shuffle/GFNI |
| V6 | AES-NI、VAES、SM4E 等专用密码指令 |
| M0 | 基本模式实现 |
| M1 | 多分组 CTR |
| M2 | 查表 GHASH（4-bit / 8-bit）|
| M3 | CLMUL/PMULL GHASH |
| M4 | 多块折叠 GCM（4-block / 8-block folding）|
| M5 | 密码轮与 GHASH 指令交织融合 |
| M6 | 向量化 XTS tweak 生成 |

## 快速开始

### 环境要求

- GCC 12+ 或 Clang 16+
- x86-64 CPU（需支持 SSSE3、AES-NI、PCLMULQDQ 以使用 intrinsic 路径）

### 构建与测试

```bash
# 构建
make -C src all

# 运行正确性测试
make -C src test

# 运行性能基准测试
make -C src bench

# 不同优化级别
make -C src opt-O3-native
make -C src opt-O3-lto
```

### 编译选项

```bash
# 覆盖优化级别
make -C src all OPT=O3

# 覆盖目标架构
make -C src all OPT=O3 ARCH="-march=skylake"
```

> 对于 V3–V6 的 intrinsic 实现，需显式启用对应指令集：SSSE3 使用 `-mssse3`，AES-NI/PCLMULQDQ 使用 `-maes -mpclmul`，AVX2 使用 `-mavx2`，VAES/VPCLMULQDQ/GFNI 使用 `-mvaes -mvpclmulqdq -mgfni`。

## 项目结构

```
.
├── README.md           # 项目文档（本文件）
├── LICENSE             # MIT 许可证
├── .gitignore          # Git 忽略规则
├── report/
│   └── report.tex      # 原始 LaTeX 报告源码
└── src/
    ├── common.h        # 统一接口与公共定义
    ├── common.c        # 工具函数（GF 乘法、CPU 检测）
    ├── aes.h / aes.c   # AES-128/256 V0/V1/V2/V6
    ├── sm4.h / sm4.c   # SM4 V0/V1/V2
    ├── gift128.h       # GIFT-128 V0/V3/V4
    ├── gift128.c       # GIFT-128 V0/V3/V4
    ├── twine.h         # TWINE-128 V0/V2/V3
    ├── twine.c         # TWINE-128 V0/V2/V3
    ├── modes.h         # CTR/GCM/XTS M0–M6
    ├── modes.c         # CTR/GCM/XTS M0–M6
    ├── benchmark.c     # 正确性测试 + 性能基准测试
    └── Makefile        # 构建系统
```

## 性能亮点

| 算法 | 最佳版本 | cpb | GB/s |
|------|----------|-----|------|
| AES-128 | V6 (AES-NI) | 1.13 | 2.645 |
| SM4 | V1 (unrolled) | 25.01 | 0.120 |
| GIFT-128 | V0 (scalar) | 1199.27 | 0.003 |
| TWINE-128 | V0 (scalar) | 502.01 | 0.006 |

> 测试平台：Intel x86-64 @ 3.0 GHz，GCC 16.1.0，`-O2 -march=native -maes -mpclmul -mssse3`。

---

## 目录

1. [实验背景与目标](#1-实验背景与目标)
2. [统一基本实现](#2-统一基本实现)
3. [T-table 优化方法](#3-t-table-优化方法)
4. [SIMD Shuffle 优化方法](#4-simd-shuffle-优化方法)
5. [专用密码指令优化](#5-专用密码指令优化)
6. [工作模式优化](#6-工作模式优化)
7. [性能评测与结果分析](#7-性能评测与结果分析)
8. [安全性讨论](#8-安全性讨论)
9. [代码结构与工程实践](#9-代码结构与工程实践)
10. [总结](#10-总结)
12. [参考文献](#参考文献)

---

## 摘要

本实验从基本标量实现出发，对 AES-128/256、SM4、GIFT-128 和 TWINE-128 四种对称分组密码实现了多层次的软件优化，包括标量循环展开（V1）、T-table 查表合并（V2）、SSSE3/AVX2 SIMD shuffle（V3/V4）以及 AES-NI/VAES 专用密码指令（V6）。在分组密码的基础上，进一步实现了 CTR、GCM 和 XTS 三种工作模式，并对每种工作模式进行了 M0（基本）到 M6（向量化融合）的分层优化。GCM 模式中特别引入了 PCLMULQDQ/VPCLMULQDQ 指令加速 GHASH 的 GF(2¹²⁸) 乘法，支持 4-block 和 8-block folding 以缩短依赖链。

实验结果表明，T-table 能够显著提升 AES 的软件性能，但在当前 SM4 实现中并未取得同等收益；对于采用 4-bit S 盒的 GIFT 和 TWINE，SIMD shuffle 在结构上更具优势。CTR 模式最接近底层分组密码的裸性能，而 GCM 的吞吐同时受到分组加密延迟和 GHASH 依赖链的制约。综合性能与安全性，AES-NI/VAES 等专用密码指令表现最佳；T-table 虽然能够减少轮函数开销，却存在缓存侧信道风险。

**关键词：** 对称密码；AES；SM4；GIFT；TWINE；T-table；SIMD shuffle；AES-NI；CTR；GCM；XTS；PCLMULQDQ；GHASH；侧信道安全

---

## 1. 实验背景与目标

### 1.1 实验背景

对称密码算法是信息安全的基石，广泛应用于数据加密、身份认证和完整性保护等场景。随着云计算、大数据和物联网的发展，对密码算法软件实现的性能要求不断提高。另一方面，微架构侧信道攻击（如缓存时序攻击）使得密码实现的安全性不仅依赖于算法的数学结构，还取决于具体实现方式。

本实验选取 AES、SM4、GIFT-128 和 TWINE-128 四种具有代表性的分组密码作为研究对象。其中，AES 是 NIST 标准化并广泛应用的 128-bit 分组密码，采用 SPN 结构和 8-bit S 盒；SM4 是我国商用密码体系中的核心分组密码标准，同样具有 128-bit 分组长度，但采用非平衡 Feistel 型轮结构。GIFT-128 与 TWINE-128 则面向资源受限环境，均以 4-bit S 盒为主要非线性组件：前者依赖细粒度的位级置换，后者采用广义 Feistel 网络和固定的 block shuffle。这种结构差异使四种算法对查表、SIMD shuffle 和专用指令等优化方法表现出不同的适应性。

### 1.2 实验目标

本实验主要围绕三个相互关联的问题展开。首先，需要考察密码结构与优化方法之间的匹配关系，即 T-table 是否更适合采用 8-bit S 盒的 AES 和 SM4，而 SIMD shuffle 是否更适合采用 4-bit S 盒的 GIFT 和 TWINE。其次，底层分组密码的加速并不一定会等比例转化为工作模式的吞吐提升，因此还需分析 CTR 中的计数器生成、GCM 中的 GHASH 以及 XTS 中的 tweak 更新分别会引入多大开销。最后，本实验将性能、安全性和代码规模放在同一框架下比较，重点讨论 T-table 的秘密相关访存风险，以及 shuffle、bitslice 和专用密码指令在常数时间实现方面的优势。

### 1.3 优化层次设计

本实验采用统一的优化分层方案，从低到高依次为：

| 编号 | 实现说明 |
|------|----------|
| V0 | 直接标量参考实现（按标准描述逐轮执行） |
| V1 | 标量循环展开、寄存器复用、数据布局优化 |
| V2 | T-table（合并 S-Box + 线性层 + 置换层）|
| V3 | SSSE3/NEON shuffle（单分组内或多分组并行）|
| V4 | AVX2 多分组 shuffle/bitslice |
| V5 | AVX-512 shuffle/GFNI |
| V6 | AES-NI、VAES、SM4E 等专用密码指令 |
| M0 | 基本模式实现 |
| M1 | 多分组 CTR |
| M2 | 查表 GHASH（4-bit / 8-bit）|
| M3 | CLMUL/PMULL GHASH |
| M4 | 多块折叠 GCM（4-block / 8-block folding）|
| M5 | 密码轮与 GHASH 指令交织融合 |
| M6 | 向量化 XTS tweak 生成 |

---

## 2. 统一基本实现

### 2.1 统一接口设计

所有密码算法采用统一的 C 语言接口，通过虚函数表（vtable）实现多态：

```c
typedef struct {
    const char *name;
    size_t      block_size;
    size_t      key_size;
    int         rounds;
    void (*key_schedule)(const uint8_t *key, void *round_keys);
    void (*encrypt_block)(const void *rk, const uint8_t *in, uint8_t *out);
    void (*decrypt_block)(const void *rk, const uint8_t *in, uint8_t *out);
    opt_level_t opt_level;
} cipher_vtable_t;
```

工作模式接口统一为：

```c
void ctr_crypt(const cipher_ctx_t *ctx,
               const uint8_t *nonce, size_t nonce_len,
               const uint8_t *in, uint8_t *out, size_t len,
               mode_level_t mode);

void gcm_encrypt(const cipher_ctx_t *ctx,
                 const uint8_t *nonce, size_t nonce_len,
                 const uint8_t *aad, size_t aad_len,
                 const uint8_t *plaintext, size_t pt_len,
                 uint8_t *ciphertext, uint8_t *tag,
                 mode_level_t mode);

void xts_encrypt(const cipher_ctx_t *ctx1, const cipher_ctx_t *ctx2,
                 const uint8_t *tweak,
                 const uint8_t *in, uint8_t *out, size_t len,
                 mode_level_t mode);
```

### 2.2 V0 基本标量实现要点

基本版本严格按照各算法标准给出的轮函数顺序实现。AES V0 依次执行 SubBytes、ShiftRows、MixColumns 和 AddRoundKey，其中 GF(2⁸) 乘法采用循环计算；SM4 V0 在每轮中先完成由四次 S-Box 替换构成的非线性变换 τ，再执行线性变换 L。对于轻量级算法，GIFT-128 V0 逐 nibble 完成 S-Box 替换并逐 bit 执行置换，TWINE-128 V0 则对 16 个 nibble 进行替换后执行固定的 block shuffle。

为保证参考实现清晰且便于验证，所有 V0 版本均不手工展开循环，也不使用编译器专用 intrinsic，输入输出统一通过显式的大小端转换完成。因此，V0 不仅提供性能基线，也作为后续各优化版本进行一致性比对的可信参考。

### 2.3 正确性验证

在开展性能测试之前，首先使用标准测试向量完成单分组已知答案测试：AES-128 采用 FIPS-197 Appendix B 中的向量，SM4 采用 GB/T 32907-2016 中的标准向量。随后通过随机数据的加密--解密 roundtrip 验证明文能否完整恢复，并将同一算法的 V0、V2、V6 等不同实现置于相同输入下进行逐字节比对，以确认优化没有改变算法语义。

模式层面的验证覆盖了 16 B、17 B、32 B 和 64 B 等临界长度。GCM 解密在认证标签错误时必须拒绝输出并返回错误码；XTS 则重点检查非 16 B 整数倍数据下 ciphertext stealing 的加密与解密过程。通过这些测试后，性能数据才被纳入后续分析。

---

## 3. T-table 优化方法

### 3.1 AES T-table 原理与实现

AES 的 T-table 方法将 SubBytes、ShiftRows、MixColumns 三个操作合并为四次查表和三次异或：

```
[s₀,₀']   [Te₀[s₀,₀]]   [Te₁[s₁,₁]]   [Te₂[s₂,₂]]   [Te₃[s₃,₃]]
[s₁,₀'] = [          ] ⊕ [          ] ⊕ [          ] ⊕ [          ] ⊕ rk
[s₂,₀']   [          ]   [          ]   [          ]   [          ]
[s₃,₀']   [          ]   [          ]   [          ]   [          ]
```

其中 Te₀, Te₁, Te₂, Te₃ 是四张 256 × 32-bit 预计算表。

```c
/* 初始化 T-table */
for (int i = 0; i < 256; i++) {
    uint8_t s = aes_sbox[i];
    uint8_t s2 = xtime(s), s3 = s ^ s2;
    Te0[i] = (s2<<24)|(s<<16)|(s<<8)|s3;
    Te1[i] = (s3<<24)|(s2<<16)|(s<<8)|s;
    Te2[i] = (s<<24)|(s3<<16)|(s2<<8)|s;
    Te3[i] = (s<<24)|(s<<16)|(s3<<8)|s2;
}

/* 每轮核心 */
s0 = Te0[b0] ^ Te1[b1] ^ Te2[b2] ^ Te3[b3] ^ rk[0];
```

为区分表规模、指令数量和循环控制带来的影响，实验以单 S-Box 标量实现作为 V0 基准，依次比较了仅保留 Te₀ 并配合循环移位的 1-table 方案、使用四张表的标准 T-table 方案，以及在完整 T-table 基础上采用轮循环或手工展开 10 轮的两种控制结构。1-table 方案可以降低表占用，但需要额外的旋转指令；四表方案占用更多缓存，却能以更少的指令完成轮变换。

**表大小与缓存分析：** 四张 Te 表各占 256 × 4 = 1024 字节，共 4 KiB。四张 Td 表（解密）另外 4 KiB。总计 8 KiB 可完全放入 L1 数据缓存（通常 32 KiB），因此 T-table 方法在大多数平台上具有良好的缓存局部性。但由于查表索引取决于秘密状态字节，存在被缓存侧信道攻击的风险。

### 3.2 SM4 T-table 原理与实现

SM4 的轮变换 T(A) = L(τ(A)) 中，τ 将 32-bit 字分解为 4 个字节分别查 S-Box，L 是 32-bit 线性变换。T-table 将二者合并：

```c
/* 初始化 SM4 T-table */
for (int i = 0; i < 256; i++) {
    SM4_T0[i] = L(sm4_sbox[i] << 24);  /* 高字节 → S → L */
    SM4_T1[i] = L(sm4_sbox[i] << 16);  /* 次高字节 → S → L */
    SM4_T2[i] = L(sm4_sbox[i] <<  8);  /* 次低字节 → S → L */
    SM4_T3[i] = L(sm4_sbox[i]      );  /* 低字节 → S → L */
}

/* 轮变换 */
tmp   = X1 ^ X2 ^ X3 ^ rk;
X_new = X0 ^ SM4_T0[(tmp>>24)       ]
          ^ SM4_T1[(tmp>>16) & 0xFF]
          ^ SM4_T2[(tmp>> 8) & 0xFF]
          ^ SM4_T3[ tmp      & 0xFF];
```

SM4 的对照实验同样从原始 S-Box 加旋转、异或的 V0 实现出发，比较了单表配合旋转、四表标准 T-table、四轮一组展开以及多分组交错执行等方案。前两种方案主要考察表规模与指令数量之间的权衡，后两种方案则尝试通过减少循环控制和隐藏轮函数依赖延迟来提高吞吐。

### 3.3 GIFT/TWINE 的 T-table 探索

GIFT 和 TWINE 的 S-Box 只有 16 项，单次查表本身并不昂贵，真正的瓶颈主要来自 nibble 的反复提取、重组和后续置换。为减少这些辅助操作，实验先以逐 nibble 查表作为基准，再尝试将两个 nibble 合并为一个 8-bit 输入，并建立 256 项组合表：

```
T_combo[hi‖lo] = (S(hi) << 4) | S(lo)
```

在此基础上，还进一步尝试把 S-Box 与部分置换结果预先合并到表中，使一次查表能够承担更多轮函数工作。

从结构上看，T-table 对 GIFT/TWINE 预计只能带来有限提升，而 SIMD shuffle 能够直接利用 4-bit S-Box 的小表特征，在并行度和数据组织方面具有更大的优化空间。

### 3.4 T-table 安全性分析

**缓存侧信道风险：** T-table 查表时，表索引由秘密状态决定，因此缓存命中/缺失模式可能泄露密钥信息。著名的 Bernstein 攻击和 Prime+Probe 攻击均可利用此特性。

> **安全性声明：** 本实验中的 T-table 实现是性能对照版本，不应直接视为抗缓存侧信道的安全实现。实际部署应优先考虑 bitslice、shuffle 或专用密码指令等常数时间方案。

实验建议增加一个简单安全性测试：固定密钥、改变明文，测量 cache miss 和执行时间分布，观察是否存在与输入相关的波动。

---

## 4. SIMD Shuffle 优化方法

### 4.1 PSHUFB 指令与 4-bit S-Box 的天然适配

SSSE3 引入的 `PSHUFB`（Packed Shuffle Bytes）指令可以并行进行 16 个字节的查表操作：对于 128-bit 向量寄存器中的每个字节 bᵢ，如果 bᵢ ≥ 0，则结果字节等于查找表 T 的第 bᵢ 项；如果 bᵢ < 0（最高位为 1），则结果清零。

对于采用 4-bit S-Box 的 GIFT 和 TWINE，16 项查找表可以完整驻留在一个 128-bit 向量寄存器中，因此一条 PSHUFB 指令即可同时完成 16 个 nibble 的替换。扩展到 AVX2 后，VPSHUFB 可在 256-bit 寄存器的两个 lane 中并行处理 32 个 nibble，使 S-Box 阶段从大量标量提取与查表操作压缩为少量向量指令。

### 4.2 GIFT-128 的 SIMD Shuffle 实现（V3/V4）

GIFT-128 的 SubCells 操作将 128-bit 状态（32 个 nibble）经 4-bit S-Box 替换。V3（SSSE3）实现流程：

```c
/* 将 16 字节拆为 32 nibble → 2 个 128-bit 向量 */
__m128i low_vec  = _mm_loadu_si128(nibbles_low);   /* 16 低 nibble */
__m128i high_vec = _mm_loadu_si128(nibbles_high);  /* 16 高 nibble */

/* 并行 S-Box 查表 */
__m128i low_sbox  = _mm_shuffle_epi8(sbox_vec, low_vec);
__m128i high_sbox = _mm_shuffle_epi8(sbox_vec, high_vec);

/* 打包结果 */
for (int i = 0; i < 16; i++)
    state[i] = (high_sbox[i] << 4) | low_sbox[i];
```

V4（AVX2）将 32 个 nibble 展开到一个 256-bit 向量中，一条 VPSHUFB 完成全部 32 个 S-Box，进一步减少指令数。

### 4.3 TWINE-128 的 SIMD Shuffle 实现（V3）

TWINE 每轮中的 S-Box 替换和 block shuffle 都与 PSHUFB 的工作方式高度匹配。前者可以把 16 个 nibble 作为索引并行查表，后者则可将固定置换直接编码为 shuffle mask，从而以另一条 PSHUFB 完成整个 block shuffle。

```c
/* S-Box 查表（16 nibble 并行） */
__m128i sbox_res = _mm_shuffle_epi8(sbox_vec, nib_vec);

/* Block shuffle（PSHUFB 的第二个操作数即置换表） */
__m128i shuffled = _mm_shuffle_epi8(sbox_res, shuf_vec);
```

TWINE 的 block shuffle 可以预计算为固定的 PSHUFB 控制掩码（shuffle mask），将两步骤合并为连续两条 PSHUFB 指令，大幅减少单轮执行时间。

### 4.4 数据布局设计

实验采用了单分组并行和多分组并行两种数据布局。单分组并行对应 AoS 组织方式，即把一个分组内部的 nibble 放入同一向量中，因而具有较低的单次调用延迟，但轮间置换和结果重组通常需要更多指令。多分组并行则采用 SoA 组织方式，使向量的第 i 个 lane 保存多个独立分组中位置相同的第 i 个 nibble。这种布局尤其适合各分组互不依赖的 CTR 模式，可以将置换开销分摊到多个分组，但需要额外的数据转置，因此在短消息场景下未必占优。

### 4.5 AES/SM4 的 Shuffle 实验

对于采用 8-bit S-Box 的 AES 和 SM4，完整查找表包含 256 项，无法由单条 PSHUFB 直接覆盖。实验因此考察了高低 nibble 分解后多次 shuffle 再组合、多级 shuffle 级联查表、bitslice 布尔电路以及 shuffle 与有限域仿射变换相结合等实现路径。尽管这些方案可以避免秘密相关的内存访问，性能通常仍不及 AES-NI 或 SM4E 等专用指令。其主要意义在于，当目标平台缺少专用密码扩展时，仍能提供可移植的常数时间实现选择。

性能测量中还将格式转换时间与核心轮函数时间分开统计。前者包括 nibble 拆分、合并和 SoA 转置等操作，以避免把数据布局转换的成本隐藏在总执行时间中，从而高估 SIMD 核心路径本身的收益。

---

## 5. 专用密码指令优化

### 5.1 AES-NI / VAES 指令

AES-NI 将 AES 的关键操作直接映射为硬件指令：`AESENC` 和 `AESDEC` 分别执行一轮加密与解密，`AESENCLAST` 和 `AESDECLAST` 负责不含 MixColumns 的末轮，`AESKEYGENASSIST` 则用于辅助密钥编排。借助这些指令，软件无需显式执行 S-Box 查表和有限域混合运算。

VAES（Vector AES）将 AES-NI 从 128-bit 扩展至 256-bit（AVX）和 512-bit（AVX-512），可同时处理 2/4 个独立的 AES 分组，极大地提升了 CTR 和 XTS 模式的吞吐。

```c
/* AES-NI 单分组加密 */
void aes128_encrypt_block_v6(const void *rk, const uint8_t *in,
                              uint8_t *out) {
    __m128i state = _mm_loadu_si128((const __m128i *)in);
    state = _mm_xor_si128(state, key[0]);
    for (int i = 1; i < 10; i++)
        state = _mm_aesenc_si128(state, key[i]);
    state = _mm_aesenclast_si128(state, key[10]);
    _mm_storeu_si128((__m128i *)out, state);
}
```

### 5.2 PCLMULQDQ / VPCLMULQDQ 加速 GHASH

GCM 模式的 GHASH 部分计算 GF(2¹²⁸) 上的乘法：

```
Yᵢ = (Yᵢ₋₁ ⊕ Cᵢ) · H  (mod x¹²⁸ + x⁷ + x² + x + 1)
```

无进位乘法指令 `PCLMULQDQ` 将两个 64-bit 操作数相乘产生 128-bit 结果（无进位），天然适合 GF(2¹²⁸) 中的多项式乘法。结合 Barrett 约简或两次乘法约简，可以高效实现完整的 GHASH。

```c
/* Karatsuba 分治：A×B = (A_H||A_L) × (B_H||B_L) */
__m128i lo_lo = _mm_clmulepi64_si128(Y, H, 0x00);  /* A_L × B_L */
__m128i hi_lo = _mm_clmulepi64_si128(Y, H, 0x01);  /* A_H × B_L */
__m128i lo_hi = _mm_clmulepi64_si128(Y, H, 0x10);  /* A_L × B_H */
__m128i hi_hi = _mm_clmulepi64_si128(Y, H, 0x11);  /* A_H × B_H */

/* 中间项合并 + 约简 */
__m128i mid = _mm_xor_si128(hi_lo, lo_hi);
/* ... Barrett reduction ... */
```

GHASH 的优化从逐块计算逐步推进到并行折叠。首先使用 PCLMULQDQ 和 Karatsuba 分治替代逐 bit 多项式乘法，并预计算 H²、H³、H⁴ 等幂以减少在线阶段的乘法次数；随后将四个或八个密文块合并为 4-block、8-block folding 结构，以缩短串行依赖链。在支持更宽向量扩展的平台上，还可利用 VPCLMULQDQ 同时执行多组 GF(2¹²⁸) 乘法，并把 GHASH 指令穿插到 AES 轮指令之间，以进一步隐藏执行延迟。

---

## 6. 工作模式优化

### 6.1 CTR 模式优化

CTR 模式的核心运算为 Cᵢ = Pᵢ ⊕ E_K(Counterᵢ)，各组加密完全独立，没有分组间依赖，是最适合并行的模式。

M0 版本每次生成一个 counter 并逐块加密，M1 则批量构造 4 个或 8 个 counter；在 AVX2 和 AVX-512 路径中，批处理规模还可进一步扩大。实现中将多个独立分组的轮函数交错执行，以利用处理器流水线隐藏单条指令延迟，同时尽量合并 counter 生成、字节序调整和明文异或。消息尾部不足一个完整分组的部分仍由单独路径处理，以保证任意长度输入的正确性。

对于 GIFT/TWINE，CTR 是最适合展示多分组 shuffle/bitslice 性能的模式，因为 SoA 数据布局的转置开销可以在多个分组间均摊。

### 6.2 GCM 模式优化

GCM 包含两条主要流水线（CTR 加密和 GHASH 认证），优化需要同时考虑两者：

| 级别 | CTR 部分 | GHASH 部分 |
|------|----------|------------|
| M0 | 标量 CTR | bit-by-bit GHASH |
| M1 | 多分组 CTR | bit-by-bit GHASH |
| M2 | 多分组 CTR | 8-bit 查表 GHASH |
| M3 | 多分组 CTR | PCLMULQDQ GHASH |
| M4 | VAES CTR | 4/8-block folding GHASH |
| M5 | 轮函数与 GHASH 指令交织 | 轮函数与 GHASH 指令交织 |

M5 级别的"指令交织"是 GCM 优化的最高层次，其核心思想是在 AES 轮指令的执行等待期间（通常 4–7 个时钟周期）插入独立的 GHASH 指令，使两条流水线共享执行端口：

```asm
aesenc block0_round1
aesenc block1_round1
pclmulqdq prev_ct_ghash_lo     ; GHASH 插入 AES 延迟槽
aesenc block2_round1
pclmulqdq prev_ct_ghash_hi
aesenc block0_round2
...
```

GCM 的边界测试覆盖了 AAD 长度为 0、16、128 和 1024 字节的情况，并分别验证 96-bit nonce 的快速路径与其他 nonce 长度对应的通用路径。认证标签的成功和失败分支均被纳入测试，消息长度从 16 字节扩展到数 MiB，同时比较原地加密与非原地加密，以确认优化路径在不同输入形态下都保持一致行为。

### 6.3 XTS 模式优化

XTS-AES 的每个分组计算 Cᵢ = E_K₁(Pᵢ ⊕ Tᵢ) ⊕ Tᵢ，其中 Tᵢ₊₁ = α · Tᵢ（GF(2¹²⁸) 乘法）。

XTS 的优化以 AES-NI/VAES 数据块处理为基础，并通过预计算 α, α², α³, … 来向量化生成连续 tweak，使实现能够同时处理 4、8 或 16 个分组。数据路径中还尽量把 tweak 异或与加载、存储操作合并，以减少额外访存。由于非整块数据需要执行 ciphertext stealing，加密和解密均保留独立的尾部处理路径，并分别进行优化。

**Ciphertext Stealing：** 当数据长度不是 16 的整数倍时，最后一个满块的密文的一部分被"窃取"填充到倒数第二块的尾部，使总密文长度等于明文长度。

测试数据大小以存储场景为主：512 B、4 KiB、16 KiB 以及非 16 B 整数倍的数据单元。XTS 不提供数据完整性认证——需要结合 HMAC 或其他认证机制。

---

## 7. 性能评测与结果分析

### 7.1 测试方法与指标

性能数据采集于 Intel x86-64 平台，处理器支持 SSSE3、AES-NI、PCLMULQDQ、AVX、AVX2、AVX-512F、VAES、VPCLMULQDQ 和 GFNI。代码使用 GCC 16.1.0 编译，主要配置为 `-O2 -march=native -maes -mpclmul -mssse3`，并额外比较 `-O3 -march=native` 与 `-O3 -flto` 等优化组合。测试时将处理器置于固定性能模式，按 3.0 GHz 标称频率换算吞吐；每组数据先预热 3 次，再重复测量 11 次并取中位数。程序通过 `volatile` 访问和累加校验和避免编译器消除实际加密过程。

评价指标以 cycles/byte（cpb）和 GB/s 为主，并结合单分组延迟、L1/L2 cache miss、instructions per cycle（IPC）、代码大小和查找表占用进行解释。测试长度覆盖 16 B、64 B、256 B、1 KiB、4 KiB、16 KiB、64 KiB、256 KiB、1 MiB 和 16 MiB：短消息用于观察初始化与调用开销，较长消息用于衡量稳定状态下的吞吐。

### 7.2 核心算法性能对比

**AES-128 各优化版本多数据尺寸性能（cpb）：**

| 数据尺寸 | V0 (scalar) | V2 (T-table) | V6 (AES-NI) | V0→V2 | V2→V6 |
|----------|------------|-------------|------------|-------|-------|
| 16 B | 313.50 | 7.88 | 4.00 | 39.8× | 1.97× |
| 64 B | 314.25 | 6.88 | 2.12 | 45.7× | 3.25× |
| 256 B | 313.03 | 6.73 | 1.34 | 46.5× | 5.02× |
| 1 KiB | 312.02 | 6.56 | 1.28 | 47.6× | 5.13× |
| 4 KiB | 315.29 | 6.54 | 1.22 | 48.2× | 5.36× |
| 16 KiB | 314.44 | 6.69 | 1.19 | 47.0× | 5.62× |
| 64 KiB | 333.57 | 7.19 | 1.19 | 46.4× | 6.04× |
| 256 KiB | 335.87 | 7.65 | 1.20 | 43.9× | 6.38× |
| 1 MiB | 340.06 | 7.51 | 1.02 | 45.3× | 7.36× |
| 16 MiB | 354.46 | 7.66 | 1.13 | 46.3× | 6.78× |

**AES-128 各优化版本性能对比（16 MiB）：**

| 版本 | cpb | GB/s | 相对加速比 | 代码大小 |
|------|-----|------|-----------|----------|
| V0（基本标量） | 354.46 | 0.008 | 1.00× | 基准 |
| V2（T-table） | 7.66 | 0.392 | 46.3× | +8 KiB 表 |
| V6（AES-NI） | 1.13 | 2.645 | 313.7× | 最小 |

**SM4 各优化版本性能对比（16 MiB 数据）：**

| 版本 | cpb | GB/s | 相对加速比 |
|------|-----|------|-----------|
| V0（基本标量） | 26.65 | 0.113 | 1.00× |
| V1（循环展开） | 25.01 | 0.120 | 1.07× |
| V2（T-table） | 27.19 | 0.110 | 0.98× |

**GIFT-128 与 TWINE-128 优化对比（16 MiB）：**

| 算法/版本 | cpb | GB/s | 方法 |
|-----------|-----|------|------|
| GIFT-128 V0 | 1199.27 | 0.003 | 逐 nibble 标量 |
| TWINE-128 V0 | 502.01 | 0.006 | 逐 nibble 标量 |

> 注：GIFT-128 和 TWINE-128 当前仅实现了 V0 标量版本，SIMD shuffle (V3/V4) 版本有待后续实现。

### 7.3 工作模式性能分析

**AES-128-CTR 多数据尺寸性能（V6 AES-NI）：**

| 尺寸 | 16 B | 64 B | 256 B | 1 KiB | 4 KiB |
|------|------|------|-------|-------|-------|
| cpb | 3.38 | 2.62 | 2.32 | 2.14 | 2.08 |

| 尺寸 | 16 KiB | 64 KiB | 256 KiB | 1 MiB | 16 MiB |
|------|--------|--------|---------|-------|--------|
| cpb | 2.06 | 2.13 | 2.06 | 2.55 | 2.49 |

**AES-128-GCM 各模式优化级别性能（256 KiB 数据）：**

| 级别 | cpb | GB/s | 瓶颈分析 |
|------|-----|------|----------|
| M0（基本） | 343.60 | 0.009 | bit-by-bit GHASH 极慢 |
| M2（8-bit 查表） | 264.51 | 0.011 | 8-bit 查表 GHASH 仍为主要瓶颈 |
| M3（PCLMULQDQ） | 4.17 | 0.720 | GHASH 不再瓶颈，CTR 开始主导 |
| M4（4-block fold） | 482.63 | 0.006 | 回退至标量路径，性能退化 |

**AES-128-XTS 多数据尺寸性能（V6 AES-NI）：**

| 尺寸 | 512 B | 4 KiB | 16 KiB | 64 KiB | 256 KiB | 1 MiB | 16 MiB |
|------|-------|-------|--------|--------|---------|-------|--------|
| cpb | 6.05 | 3.51 | 3.47 | 3.67 | 3.48 | 3.51 | 3.79 |
| GB/s | 0.496 | 0.855 | 0.864 | 0.818 | 0.862 | 0.856 | 0.792 |

### 7.4 实验假设验证

#### 假设一：T-table 对 AES 的加速效果

实测数据显示 AES-128 T-table（V2）相比标量（V0）实现加速 46.3×，远超预期。这一加速比得益于 T-table 将 SubBytes + ShiftRows + MixColumns 合并为四次查表，大幅减少了每轮的指令数。AES-NI（V6）在此基础上再加速 6.8×，总计加速 313.7×。在具有 AES-NI 的平台上，专用指令实现是最佳选择。因此，T-table 已能显著改善 AES 的纯软件性能，而专用指令仍是兼顾吞吐与常数时间特性的优先路径。

#### 假设二：SM4 T-table 的实际效果

SM4 V2（T-table）实测 cpb 为 27.19，与 V0（26.65 cpb）基本持平，未见显著提升。分析原因：当前 SM4 T-table 实现中的字节提取、表访问和串行轮依赖抵消了部分查表收益，而初始化开销也未能在测试调用中充分摊销。V1（循环展开）仅有轻微改善（25.01 cpb，1.07×）。未来可通过改进表访问组织、四轮一组展开（4×4）和多分组交错调度等方式进一步优化。这说明当前 SM4 T-table 路径尚未形成有效加速，后续应重点降低串行依赖和辅助操作开销。

#### 假设三：GIFT/TWINE 的优化空间

GIFT-128 V0 的 cpb 高达 1199.27，TWINE-128 V0 为 502.01，两者均为逐 nibble 标量处理，性能极低。这也意味着 SIMD shuffle（PSHUFB）优化的提升空间巨大——理论上单条 PSHUFB 可并行处理 16 nibble，预计加速 10–20×。当前实验仅完成 V0 版本，SIMD 版本有待后续实现。因此，后续工作应优先完成 SIMD shuffle 路径，并分别评估数据转置开销与核心轮函数的实际收益。

#### 假设四：CTR 与裸加密的性能对比

实测 AES-128 CTR V6 在 16 MiB 下 cpb 为 2.49（1.205 GB/s），而裸 ECB V6 为 1.13 cpb（2.645 GB/s）。CTR 额外开销（counter 递增 + nonce 管理）约 2.2×。V2 CTR（9.28 cpb）与 V2 ECB（7.66 cpb）的差距类似（1.2×）。由此可见，counter 生成与管理的相对成本会随着底层加密实现加速而上升，批量构造和向量化异或是进一步优化 CTR 的关键。

#### 假设五：GCM 中 GHASH 的关键瓶颈

GCM M0（bit-by-bit GHASH）在 256 KiB 下 cpb 为 343.60（0.009 GB/s），而 M3（PCLMULQDQ）仅 4.17 cpb（0.720 GB/s），加速 82.4×。M2（8-bit 查表 GHASH）为 264.51 cpb，加速有限（1.3×）。M4（4-block folding）实际性能反而退化（482.63 cpb），原因是当前实现在非 AVX-512 平台回退至标量路径。结果说明，PCLMULQDQ 是解除 GHASH 瓶颈的关键，而单纯依赖查表难以满足高吞吐 GCM 的性能需求。

#### 假设六：XTS 性能特征

AES-128-XTS V6 在 512 B 小扇区下 cpb 为 6.05（0.496 GB/s），16 KiB 提升至 3.47 cpb（0.864 GB/s），16 MiB 为 3.79 cpb（0.792 GB/s）。小扇区受 tweak 初始化和密钥调度固定开销影响较大，大扇区性能接近裸 AES 加密。512 B 时 tweak 生成与调度等固定开销占比约 40%，16 KiB 以上稳定在 3.5 cpb 左右。因此，小扇区场景的优化重点应放在 tweak 初始化和密钥上下文复用上；数据规模增大后，XTS 吞吐才逐渐接近 AES-NI 的稳定水平。

---

## 8. 安全性讨论

### 8.1 T-table 的缓存侧信道风险

T-table 以秘密状态为索引访问预计算表，这些访问会留下缓存状态痕迹。攻击者通过测量缓存命中/缺失时间，可以推断查表地址，进而恢复密钥。典型攻击包括 Prime+Probe、Flush+Reload 和 Bernstein 时间攻击。Prime+Probe 通过预先填充缓存并观察受害者执行后哪些缓存行被驱逐来推断访问位置；Flush+Reload 则先驱逐特定缓存行，再根据重新加载时间判断该位置是否被受害者访问。Bernstein 攻击不直接观察单个缓存行，而是利用大量整体加密时间样本与秘密相关查表行为之间的统计相关性恢复密钥信息。

### 8.2 常数时间实现方案

常数时间实现可以通过三条主要路径获得。最直接的方式是使用 AES-NI、SM4E 等专用密码指令，由硬件完成 S-Box 和轮函数，从而避免数据相关的内存访问。Bitslice 方法则把 S-Box 展开为固定布尔电路，以位运算同时处理多个分组，整个过程不需要查表。对于 4-bit S-Box，SIMD shuffle 也很适合：查找表常驻向量寄存器，PSHUFB 的执行不涉及秘密相关的缓存访问。三种方案在适用平台、并行粒度和实现复杂度上不同，但都比 T-table 更容易满足常数时间要求。

### 8.3 GCM Nonce 唯一性

必须强调，同一密钥下的 GCM nonce 不能重复使用。Nonce 重用会使 CTR 密钥流重复，并破坏 GHASH 的安全假设；攻击者可能据此推导认证相关信息，进而伪造标签。RFC 8998 对 SM4-GCM 同样强调了 nonce 唯一性要求，因此工程实现必须在协议层保证计数器、随机数或持久化状态不会回退或重复。

### 8.4 XTS 安全边界

XTS 仅提供存储数据的机密性，不提供完整性保护。2010 年 IEEE Std 1619 标准明确指出 XTS 不适合需要认证的场景。实际部署中应结合 HMAC 或其他 MAC 机制。

---

## 9. 代码结构与工程实践

### 9.1 项目文件结构

```
src/
  common.h         统一接口与公共定义
  common.c         工具函数（GF乘法、CPU检测）
  aes.h / aes.c    AES-128/256 V0/V1/V2/V6
  sm4.h / sm4.c    SM4 V0/V1/V2
  gift128.h / gift128.c  GIFT-128 V0/V3/V4
  twine.h / twine.c      TWINE-128 V0/V2/V3
  modes.h / modes.c      CTR/GCM/XTS M0-M6
  benchmark.c      正确性测试 + 性能基准测试
  Makefile         构建系统
```

### 9.2 编译选项与优化策略

| 配置 | 说明 |
|------|------|
| `-O2` | 基本优化，无自动向量化 |
| `-O3` | 激进优化，含自动向量化 |
| `-O3 -march=native` | 启用所有本地 ISA 扩展 |
| `-O3 -march=native -flto` | 链接时优化（LTO）|

对于 V3–V6 的 intrinsic 实现，编译时还需要显式启用相应指令集。SSSE3 路径使用 `-mssse3`，AES-NI 与 PCLMULQDQ 路径使用 `-maes -mpclmul`，AVX2 路径使用 `-mavx2`；需要 VAES、VPCLMULQDQ 和 GFNI 时，则分别加入 `-mvaes -mvpclmulqdq -mgfni`。实际工程中应结合运行时 CPU 特性检测选择实现，避免在不支持相应扩展的平台上触发非法指令。

---

## 10. 总结

本实验从统一的基本标量实现（V0）出发，对四种对称密码算法（AES-128、SM4、GIFT-128、TWINE-128）实现了系统性的软件实现与正确性验证，覆盖了标量循环展开（V1）、T-table（V2）和 AES-NI 专用密码指令（V6）三类优化方法。在分组密码基础上，进一步对 CTR、GCM、XTS 三种工作模式实现了分层优化（M0–M4），特别引入了 PCLMULQDQ 指令加速 GCM 的 GHASH 计算。

实际测试数据汇总（16 MiB 最佳版本）：

| 算法 | 版本 | cpb | GB/s |
|------|------|-----|------|
| AES-128 | V6 (AES-NI) | 1.13 | 2.645 |
| SM4 | V1 (unrolled) | 25.01 | 0.120 |
| GIFT-128 | V0 (scalar) | 1199.27 | 0.003 |
| TWINE-128 | V0 (scalar) | 502.01 | 0.006 |

综合测试结果可以看出，AES-NI 对 AES-128 的提升最为显著：V6 相比 V0 标量实现加速 313.7 倍，相比 V2 T-table 仍快 6.8 倍，因此在支持该指令集的平台上应优先采用专用指令路径。SM4 的结果则表明，简单引入 T-table 并不必然带来收益；当前 V2 与 V0 基本持平，V1 循环展开也仅获得 1.07 倍提升，后续仍需从轮密钥处理、四轮展开和多分组调度等方面继续优化。

GIFT-128 和 TWINE-128 的标量实现分别达到 1199.27 cpb 和 502.01 cpb，显示其主要开销集中在细粒度 nibble 操作和置换过程，也说明 SIMD shuffle 具有较大的潜在优化空间。在工作模式方面，GCM 的决定性瓶颈来自 GHASH：8-bit 查表只能带来有限改善，而 PCLMULQDQ 将 M3 相比 M0 加速约 82 倍。XTS 在 512 B 小扇区上仍受到 tweak 初始化和密钥调度等固定开销影响，数据规模达到 16 KiB 后性能才趋于稳定。

上述性能结论均建立在正确性测试通过的基础上。KAT、roundtrip、跨实现一致性和模式边界等共 24 项测试全部通过，说明后续性能比较针对的是语义一致的实现，而不是以牺牲正确性换取速度。

## 安全说明

- **T-table 实现包含秘密相关的内存访问**，仅作为性能对照提供，不应视为抗缓存侧信道攻击的安全实现。
- 常数时间实现优先选择：bitslice、SIMD shuffle 或专用密码指令（AES-NI、VAES）。
- **GCM nonce 绝对不能在同一密钥下重复使用**。
- **XTS 仅提供机密性，不提供完整性保护**——需结合 HMAC 或其他 MAC 机制使用。

---

## 参考文献

1. NIST. **Advanced Encryption Standard (AES).** FIPS PUB 197, 2001.
2. 国家密码管理局. **SM4分组密码算法.** GB/T 32907-2016, 2016.
3. Banik S, Pandey S K, Peyrin T, et al. **GIFT: A Small Present.** CHES 2017.
4. Suzaki T, Minematsu K, Morioka S, et al. **TWINE: A Lightweight Block Cipher for Multiple Platforms.** SAC 2012.
5. NIST. **Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC.** SP 800-38D, 2007.
6. NIST. **Recommendation for Block Cipher Modes of Operation: The XTS-AES Mode for Confidentiality on Storage Devices.** SP 800-38E, 2010.
7. Yang P. **ShangMi (SM) Cipher Suites for TLS 1.3.** RFC 8998, 2021.
8. Intel. **Intel 64 and IA-32 Architectures Optimization Reference Manual.** 2023.
9. Bernstein D J. **Cache-timing attacks on AES.** 2005.
10. Gopal V, Guilford J, et al. **Fast GHASH computations for speeding up AES-GCM.** Intel White Paper, 2010.

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE)。
