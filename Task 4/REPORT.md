# SM3 软件实现与 SIMD/GPR 混合优化

本实验对应题目 **“SM3 软件实现与优化：实现基于 SIMD 寄存器和通用寄存器混合的 SM3 算法优化实现，要求实现 ARM64 和 x86（AVX2/AVX512）中的两种架构指令集”**。

实验实现了纯 C 参考版本、x86-64 AVX2 混合版本、x86-64 AVX-512 混合版本和 ARM64 NEON 混合版本。各版本使用统一 API，并通过标准测试向量、随机一致性测试和性能基准进行比较。

算法依据：

- GM/T 0004-2012《SM3 密码杂凑算法》
- ISO/IEC 10118-3
- RFC 8998 中对 SM3 的相关描述

## 1. 实验目标

本项目从 SM3 算法本身出发完成软件实现和优化，主要目标包括：

1. 实现标准 SM3 杂凑算法，输出 256 bit 摘要。
2. 提供纯 C 标量实现，作为正确性基线。
3. 实现 x86-64 AVX2 优化路径。
4. 实现 x86-64 AVX-512 优化路径。
5. 实现 ARM64 NEON 优化路径。
6. 体现 SIMD 寄存器与通用寄存器 GPR 的混合使用。
7. 支持运行时 CPU 特性检测、实现自动选择和不可用路径回退。
8. 提供测试程序与性能基准程序，便于复现实验结果。

## 2. 实现思路

SM3 每个 512 bit 消息分组需要经过：

1. 大端装载 16 个 32 bit 消息字；
2. 消息扩展，生成 `W[0..67]`；
3. 生成 `W'[0..63] = W[j] ^ W[j+4]`；
4. 执行 64 轮压缩函数；
5. 将压缩结果与原状态异或。

本项目采用 **SIMD + GPR 混合优化**：

| 阶段                 | 实现方式            | 说明                                            |
| -------------------- | ------------------- | ----------------------------------------------- |
| 消息填充、分块       | 标量代码            | 控制逻辑多，并行收益小                          |
| 64 字节分组装载      | SIMD                | 可一次装载多个 32 bit 字                        |
| 大端字节序转换       | SIMD                | 可批量进行字节重排                              |
| 消息扩展 `W[16..67]` | SIMD + 少量标量辅助 | 扩展公式存在滑动依赖，但旋转、异或、P1 可向量化 |
| `W'` 生成            | SIMD                | 纯批量异或                                      |
| 64 轮压缩            | GPR                 | `A..H` 状态链式依赖强，适合通用寄存器串行执行   |
| 状态更新             | GPR                 | 数据量小，直接标量更新                          |

整体数据流：

```text
输入消息
  |
  v
填充与 64 字节分组
  |
  v
sm3_compress_ref / sm3_compress_avx2 / sm3_compress_avx512 / sm3_compress_neon
  |
  +-- SIMD：装载、大端转换、消息扩展、W' 生成
  |
  +-- GPR ：64 轮压缩函数
  |
  v
256 bit SM3 摘要
```

压缩轮函数由各实现共享 `sm3_compress_rounds_gpr_wp()`，避免不同优化路径重复实现轮函数导致静默错误。

## 3. 目录结构

```text
.
├── CMakeLists.txt                    # CMake 构建配置，按架构启用 AVX2 / AVX-512 / NEON
├── README.md                         # 项目说明文档
├── include
│   └── sm3.h                         # 对外 API、上下文结构、实现枚举
├── src
│   ├── sm3_common.c                  # 增量接口、填充、分块、实现分发
│   ├── sm3_internal.h                # 内部宏、轮函数、共享工具函数
│   ├── sm3_ref.c                     # 纯 C 参考实现
│   ├── sm3_mb.c                      # 多缓冲 API 与回退
│   ├── x86                           # x86-64 平台相关实现
│   │   ├── cpuid_x86.c               # x86 CPU 指令集检测
│   │   ├── sm3_avx2.c                # AVX2 单缓冲混合实现
│   │   ├── sm3_mb_avx2.c             # AVX2 四路多缓冲内核
│   │   └── sm3_avx512.c              # AVX-512 混合实现
│   └── arm64                         # ARM64 平台相关实现
│       ├── cpu_arm.c                 # ARM64 NEON 特性检测
│       └── sm3_neon.c                # NEON 混合实现
├── tests
│   ├── test_vectors.c                # 标准测试向量与增量接口测试
│   ├── test_impl.c                   # CPU 特性、实现选择和回退测试
│   ├── test_random.c                 # 随机消息一致性测试
│   └── test_mb.c                     # 多缓冲与参考实现交叉验证
├── bench
│   └── bench_sm3.c                   # 单缓冲 / 多缓冲吞吐基准
├── docs
│   ├── design.md                     # 混合架构设计说明
│   ├── optimization.md               # 优化思路与性能分析
│   ├── multibuffer.md                # 四路多缓冲说明
│   ├── avx512.md                     # AVX-512 路径说明
│   └── neon.md                       # NEON 路径说明
└── scripts
    ├── build.bat                     # Windows 构建脚本
    ├── run_tests.bat                 # Windows 测试脚本
    └── build_and_test.sh             # Linux / ARM64 构建测试脚本
```

## 4. 已实现的架构路径

### 4.1 基线实现：`sm3_ref`

文件：

- `src/sm3_ref.c`
- `src/sm3_internal.h`

特点：

- 使用标准 C 实现；
- 不依赖 SIMD 指令；
- 作为所有优化实现的正确性基线；
- 用于不支持 SIMD 优化路径时的回退。

### 4.2 x86-64 AVX2 混合实现

文件：

- `src/x86/sm3_avx2.c`
- `src/x86/cpuid_x86.c`

入口函数：

```c
void sm3_compress_avx2(uint32_t state[8], const uint8_t block[64]);
```

实现要点：

- 使用 `_mm256_loadu_si256` 装载 256 bit 数据；
- 使用 `_mm256_shuffle_epi8` 完成 32 bit 字内部的大端转换；
- 使用 SIMD 指令辅助 `P1`、循环左移和消息扩展；
- 使用 YMM 寄存器批量生成 `W'[j] = W[j] ^ W[j+4]`；
- 64 轮压缩调用共享 GPR 轮函数。

### 4.3 x86-64 AVX-512 实现

文件：

- `src/x86/sm3_avx512.c`
- `src/x86/cpuid_x86.c`

入口函数：

```c
void sm3_compress_avx512(uint32_t state[8], const uint8_t block[64]);
```

实现要点：

- 使用 512 bit ZMM 寄存器一次装载完整 64 字节分组；
- 使用 AVX-512 字节重排完成大端转换；
- 使用 3-wide 方式处理消息扩展；
- 使用 16 lane 向量异或批量生成 `W'`；
- 64 轮压缩调用共享 GPR 轮函数；
- 通过 CPUID + XGETBV 检查 AVX-512F 和 OS 上下文保存能力，不支持时运行时跳过。

SM3 扩展公式中 `W[j]` 依赖 `W[j-3]`：

```text
W[j] = P1(W[j-16] ^ W[j-9] ^ (W[j-3] <<< 15))
       ^ (W[j-13] <<< 7)
       ^ W[j-6]
```

因此单条消息中不能简单地一次并行生成 16 个新字。本项目在 AVX-512 和 NEON 路径中采用依赖感知的 3-wide 扩展。

### 4.4 ARM64 NEON 实现

文件：

- `src/arm64/sm3_neon.c`
- `src/arm64/cpu_arm.c`

入口函数：

```c
void sm3_compress_neon(uint32_t state[8], const uint8_t block[64]);
```

实现要点：

- 使用 `vld1q_u8` 装载 128 bit 数据；
- 使用 `vrev32q_u8` 完成 32 bit 字内部的大端转换；
- 使用 NEON 向量指令实现 `P1`、循环左移和 3-wide 消息扩展；
- 使用 `veorq_u32` 批量生成 `W'`；
- 64 轮压缩调用共享 GPR 轮函数；
- 不使用 ARMv8.2-SM 的 SM3 专用指令，保持纯软件 SIMD/GPR 混合优化路径。

## 5. 运行时实现选择

项目提供统一实现枚举：

```c
typedef enum sm3_impl {
    SM3_IMPL_AUTO   = 0,
    SM3_IMPL_REF    = 1,
    SM3_IMPL_AVX2   = 2,
    SM3_IMPL_AVX512 = 3,
    SM3_IMPL_NEON   = 4
} sm3_impl_t;
```

自动选择优先级：

| 平台     | `SM3_IMPL_AUTO` 优先级 |
| -------- | ---------------------- |
| x86-64   | AVX-512 -> AVX2 -> REF |
| ARM64    | NEON -> REF            |
| 其他平台 | REF                    |

如果某个实现未编译进库，或者当前 CPU 不支持对应指令集，则 `sm3_impl_available()` 返回 0，测试程序会将该路径标记为 `SKIP`。

## 6. 构建方法

### 6.1 Windows x86-64

推荐使用脚本：

```bat
scripts\build.bat
```

产物位于 `build\`：

```text
build\sm3.lib
build\test_vectors.exe
build\test_impl.exe
build\test_random.exe
build\test_mb.exe
build\bench_sm3.exe
```

也可手动构建：

```bat
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

### 6.2 Linux x86-64 / ARM64

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

ARM64 也可使用：

```bash
chmod +x scripts/build_and_test.sh
./scripts/build_and_test.sh
```

### 6.3 CMake 选项

| 选项                | 默认值 | 说明                          |
| ------------------- | -----: | ----------------------------- |
| `SM3_BUILD_TESTS`   |   `ON` | 构建测试程序                  |
| `SM3_BUILD_BENCH`   |   `ON` | 构建性能测试程序              |
| `SM3_ENABLE_AVX2`   |   `ON` | 在 x86-64 上启用 AVX2 路径    |
| `SM3_ENABLE_AVX512` |   `ON` | 在 x86-64 上启用 AVX-512 路径 |
| `SM3_ENABLE_NEON`   |   `ON` | 在 ARM64 上启用 NEON 路径     |

示例：

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DSM3_ENABLE_AVX512=OFF
```

## 7. API 使用

### 7.1 一次性计算摘要

```c
#include "sm3.h"

uint8_t digest[SM3_DIGEST_SIZE];
sm3_digest(data, len, digest);
```

### 7.2 显式指定实现

```c
uint8_t digest[SM3_DIGEST_SIZE];

if (sm3_impl_available(SM3_IMPL_AVX2)) {
    sm3_digest_ex(data, len, digest, SM3_IMPL_AVX2);
}
```

### 7.3 增量接口

```c
sm3_ctx ctx;
uint8_t digest[SM3_DIGEST_SIZE];

sm3_init_ex(&ctx, SM3_IMPL_AUTO);
sm3_update(&ctx, part1, part1_len);
sm3_update(&ctx, part2, part2_len);
sm3_final(&ctx, digest);
```

### 7.4 设置默认实现

```c
if (sm3_set_impl(SM3_IMPL_AVX2) == 0) {
    sm3_digest(data, len, digest);
}
```

如果指定实现不可用，`sm3_set_impl()` 返回 `-1`。

### 7.5 多缓冲（四路并行）

同时哈希 4 条**相互独立**、等长的消息时，可走 AVX2 多缓冲内核（扩展与 64 轮压缩均在 4 个 lane 上并行）：

```c
const uint8_t *msgs[4] = { m0, m1, m2, m3 };
uint8_t digests[4][SM3_DIGEST_SIZE];

sm3_mb4_digest(msgs, len, digests);

/* 任意条数：等长组优先 4 路，其余顺序处理 */
sm3_mb_digest(n, msg_list, lens, digests_n);
```

详见 [docs/multibuffer.md](docs/multibuffer.md)。

## 8. 测试、验证与性能结果

### 8.1 正确性测试

Windows：

```bat
scripts\run_tests.bat
```

或分别运行：

```bat
build\test_vectors.exe
build\test_impl.exe
build\test_random.exe
build\test_mb.exe
```

Linux / ARM64：

```bash
./build/test_vectors
./build/test_impl
./build/test_random
./build/test_mb
```

测试内容：

| 测试程序       | 测试内容                                |
| -------------- | --------------------------------------- |
| `test_vectors` | 空串、`abc`、64 字节标准消息、增量接口  |
| `test_impl`    | CPU 特性检测、实现可用性、默认实现切换  |
| `test_random`  | 2000 组随机长度消息，与参考实现交叉比较 |
| `test_mb`      | 四路多缓冲与顺序 `ref` 交叉验证         |

### 8.2 本机验证结果

#### Windows x86-64

当前开发环境：

```text
系统环境：Windows x86-64
验证日期：2026-07-23
CPU 特性：AVX2=1，AVX512F=0，NEON=0
默认实现：avx2 hybrid (SIMD expand + GPR rounds)
```

正确性结果：

| 测试项         | 结果                 |
| -------------- | -------------------- |
| `test_vectors` | `RESULT: all passed` |
| `test_impl`    | `RESULT: all passed` |
| `test_random`  | `RESULT: all passed` |

#### Ubuntu x86-64

当前开发环境：

```text
系统环境：Ubuntu x86-64
验证日期：2026-07-30
CPU 特性：AVX2=1，AVX512F=0，NEON=0
默认实现：avx2 hybrid (SIMD expand + GPR rounds)
编译器：GCC 15.2.0
```

正确性结果：

| 测试项         | 结果                 |
| -------------- | -------------------- |
| `test_vectors` | `RESULT: all passed` |
| `test_impl`    | `RESULT: all passed` |
| `test_random`  | `RESULT: all passed` |
| `test_mb`      | `RESULT: all passed` |



### 8.3 性能测试

运行：

```bash
# Linux / ARM64
./build/bench_sm3
```

```bat
:: Windows
build\bench_sm3.exe
```

#### Windows x86-64 结果

单缓冲：

|  消息长度 |          ref |         avx2 | avx512 |
| --------: | -----------: | -----------: | ------ |
|       3 B |   5.22 MiB/s |   4.83 MiB/s | SKIP   |
|      64 B |  66.97 MiB/s |  56.57 MiB/s | SKIP   |
|    1024 B | 138.17 MiB/s | 125.88 MiB/s | SKIP   |
|    8192 B | 153.18 MiB/s | 134.21 MiB/s | SKIP   |
| 1048576 B | 150.76 MiB/s | 134.30 MiB/s | SKIP   |

多缓冲（4 路并行）：

| 消息长度 | ref4（4×顺序 ref） | mb4（4 路并行） | 约加速比 |
| -------: | -----------------: | --------------: | -------: |
|    1 KiB |         ~148 MiB/s |      ~327 MiB/s |    ~2.2× |
|    8 KiB |         ~154 MiB/s |      ~380 MiB/s |    ~2.5× |
|    1 MiB |         ~154 MiB/s |      ~386 MiB/s |    ~2.5× |

（数值以 `bench_sm3.exe` 当场输出为准。）

#### Ubuntu x86-64 结果

单缓冲：

|  消息长度 |         ref |         avx2 | avx512 |
| --------: | ----------: | -----------: | -----: |
|      64 B | 38.21 MiB/s |  54.59 MiB/s |   SKIP |
|    1024 B | 74.35 MiB/s | 104.23 MiB/s |   SKIP |
|    8192 B | 78.99 MiB/s | 117.41 MiB/s |   SKIP |
| 1048576 B | 78.31 MiB/s | 116.98 MiB/s |   SKIP |

多缓冲（4 路并行）：

|  消息长度 | ref4（4×顺序 ref） | mb4（4 路并行） | 约加速比 |
| --------: | -----------------: | --------------: | -------: |
|      64 B |        37.90 MiB/s |     59.16 MiB/s |    ~1.6× |
|    1024 B |        75.34 MiB/s |    251.64 MiB/s |    ~3.3× |
|    8192 B |        77.66 MiB/s |    359.77 MiB/s |    ~4.6× |
| 1048576 B |        79.29 MiB/s |    362.52 MiB/s |    ~4.6× |

结果说明：

1. 当前机器支持 AVX2，不支持 AVX-512，因此 AVX-512 项跳过。
2. 当前机器不是 ARM64，因此 NEON 路径无法在本机运行。
3. 单缓冲 SM3 的主要瓶颈在 64 轮压缩函数的串行依赖；SIMD 单流优化主要覆盖装载、消息扩展和 `W'` 生成，因此单缓冲 AVX2 的加速幅度受限于压缩阶段的串行瓶颈。
4. **多缓冲**同时处理 4 条独立消息时，扩展与压缩均可 lane 并行，因此加速效果显著（长消息可达 ~4.6×）。

（数值以 `bench_sm3` 当场输出为准。）

### 8.4 多缓冲

| 组件                               | 说明                                       |
| ---------------------------------- | ------------------------------------------ |
| `sm3_mb4_compress_avx2`            | 4 路并行：装载/扩展/64 轮均在 SIMD lane 上 |
| `sm3_mb4_digest` / `sm3_mb_digest` | 高层 API；无 AVX2 时回退顺序 ref           |
| `test_mb`                          | 与 `sm3_ref` 位级一致验证                  |

## 9. ARM64 NEON 验证说明

本仓库已包含 ARM64 NEON 源码和 CMake 架构门控逻辑。当前验证机器是 Windows x86-64，因此无法直接运行 NEON 路径。

在 ARM64 Linux 环境中执行：

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
./build/test_vectors
./build/test_impl
./build/test_random
./build/bench_sm3
```

预期现象：

- `CPU ... NEON=1`；
- 默认实现为 `neon hybrid (SIMD expand + GPR rounds)`；
- `test_vectors`、`test_impl`、`test_random` 全部通过；
- `bench_sm3` 输出 `neon` 对应吞吐率。

## 10. 局限与后续优化方向

当前实现重点是完成题目要求的 SIMD/GPR 混合结构，并保证多实现之间的位级一致性。由于单条 SM3 消息的压缩轮存在强串行依赖，单缓冲 SIMD 优化的加速空间有限。

后续可以继续优化：

1. 将多缓冲扩展到 8 路（AVX2 双向量或 AVX-512）。
2. 软件流水：交错执行消息扩展与压缩轮，隐藏部分延迟。
3. 预计算轮常量：减少每轮中对 `T_j <<< j` 的重复计算。
4. 手写汇编调度：针对具体微架构安排寄存器和指令顺序。

## 11. 实验结论

本项目实现了完整的 SM3 软件哈希库，并在 x86-64 和 ARM64 两类架构上设计了 SIMD/GPR 混合优化路径。SIMD 主要用于可并行的数据准备阶段，GPR 主要用于存在串行依赖的压缩阶段。

当前 x86-64 环境下，参考实现与 AVX2 实现已经通过标准向量、实现选择和随机一致性测试；AVX-512 与 NEON 路径也已接入统一构建和运行时分发机制，可在对应硬件环境中继续验证。
