# ARM64 NEON 混合实现说明

## 1. 目标

在 **ARM64（ARMv8-A 64 位）** 上提供与 `sm3_ref` **位级一致** 的混合路径：

| 部分 | 实现 |
|------|------|
| 分组装载 + 大端 | NEON `vld1q` + `vrev32q_u8` |
| 消息扩展 `W[16..67]` | NEON 3-wide（同 x86 AVX-512 的依赖窗口） |
| `W′[j]=W[j]⊕W[j+4]` | NEON 4×u32 批量异或 |
| 64 轮压缩 | **GPR**（`sm3_compress_rounds_gpr_wp`，与 ref/x86 共用） |

**不使用** ARMv8.2-SM 的 `sm3*` 专用加密指令，以满足作业「SIMD 寄存器 + 通用寄存器混合」的软件优化要求。

## 2. 文件与构建

| 项 | 值 |
|----|-----|
| 源文件 | `src/arm64/sm3_neon.c` |
| CPU 探测 | `src/arm64/cpu_arm.c`（`sm3_cpu_has_neon()==1`） |
| 入口 | `sm3_compress_neon` |
| CMake | 目标为 ARM64（`CMAKE_SYSTEM_PROCESSOR` 为 `aarch64`/`arm64`）且 `SM3_ENABLE_NEON=ON` |
| 宏 | `SM3_HAS_NEON=1` |
| 选择子 | `SM3_IMPL_NEON` |

在 x86 主机上配置时 **不会** 编译本文件，避免缺少 `arm_neon.h`。

## 3. 数据流

```
 block[64]
     │  vld1q_u8 ×4 + vrev32q_u8
     ▼
 W[0..15]
     │  3-wide NEON expand (P1 / <<<15 / <<<7)
     ▼
 W[0..67]
     │  veorq_u32  16× (4-lane)
     ▼
 W'[0..63]
     │  sm3_compress_rounds_gpr_wp
     ▼
 state[8]
```

## 4. 3-wide 扩展

与 AVX-512 路径相同的依赖分析：`W[j]` 依赖 `W[j-3]`，故一次最多并行 3 个新词。

- `j = 16, 19, …, 64`：`sm3_expand3_neon`
- `j = 67`：`sm3_expand1_neon`（SIMD 上算 `P1`）

## 5. 与 x86 对照

| 项目 | AVX2 | AVX-512 | NEON |
|------|------|---------|------|
| 向量宽 | 256-bit | 512-bit | **128-bit** |
| 装载 | 2×YMM pshufb | 1×ZMM | 4×128B + vrev32 |
| 扩展并行 | 逐步 + P1 | 3-wide | **3-wide** |
| W′ 宽度 | 8×u32 | 16×u32 | **4×u32** |
| 压缩 | 共用 GPR | 共用 GPR | **共用 GPR** |

## 6. 在 Ubuntu ARM64 上验收

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
./build/test_vectors    # 应跑 neon 套件，非 SKIP
./build/test_random     # ref vs neon
./build/test_impl
./build/bench_sm3
```

期望：

- `CPU ... NEON=1`
- `Default: neon hybrid ...`
- 向量 / 随机全部 PASS
- bench 出现 `neon` 一行

## 7. 完成检查表

- [x] `SM3_IMPL_NEON` API
- [x] `src/arm64/sm3_neon.c` 混合实现
- [x] `src/arm64/cpu_arm.c`
- [x] CMake 架构门控（ARM64 编 NEON，x86 不编）
- [x] 分发 / 测试 / bench 挂接
- [x] 本设计文档
- [ ] 真机上运行测试（须在 ARM64 环境执行）
