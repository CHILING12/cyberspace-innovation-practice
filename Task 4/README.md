# Task 4：SM3 软件实现与 SIMD/GPR 混合优化

## 任务说明

本实验实现 SM3 的纯 C 参考版本，并在 x86-64 和 ARM64 平台上编写 AVX2、AVX-512、NEON 优化路径。程序支持运行时选择、增量摘要接口和四路多缓冲。

## 实现内容

| 实现 | 平台 | 说明 |
| --- | --- | --- |
| `sm3_ref` | 通用 C | 参考实现 |
| `sm3_avx2` | x86-64 | SIMD 处理装载与扩展，GPR 执行压缩 |
| `sm3_avx512` | x86-64 | AVX-512 与 GPR 混合实现 |
| `sm3_neon` | ARM64 | NEON 与 GPR 混合实现 |
| `sm3_mb4` | x86-64 AVX2 | 四条独立消息并行 |

测试程序覆盖标准向量、增量接口、CPU 特性检测、随机消息和多缓冲一致性。

## 文件

```text
Task 4/
├── README.md
├── REPORT.md
├── CMakeLists.txt
├── include/
├── src/
├── tests/
├── bench/
├── docs/
└── scripts/
```

## 编译

Windows：

```bat
scripts\build.bat
```

Linux 或 ARM64：

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

## 测试与性能

```bash
./build/test_vectors
./build/test_impl
./build/test_random
./build/test_mb
./build/bench_sm3
```

Windows x86-64 和 Ubuntu x86-64 上的正确性测试均已通过。测试机器支持 AVX2，不支持 AVX-512；NEON 路径需要在 ARM64 环境中运行。

Ubuntu x86-64 上，1 MiB 单缓冲 AVX2 约为 `116.98 MiB/s`，四路多缓冲约为 `362.52 MiB/s`。具体数值会随 CPU 和编译选项变化。

## 实验报告

[REPORT.md](REPORT.md) 记录了 SM3 算法、混合优化方法、各架构实现、API、测试过程和性能结果。
