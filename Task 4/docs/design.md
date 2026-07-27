# SM3 混合架构设计（x86 + ARM64）

## 1. 目标

在 **x86-64** 与 **ARM64** 上实现 SM3，并提供：

1. **参考路径**：纯通用寄存器（GPR），保证正确。
2. **SIMD 混合路径**：
   - x86：AVX2 / AVX-512（见 [avx512.md](avx512.md)）
   - ARM64：NEON（见 [neon.md](neon.md)）
3. **统一 API**，运行时按能力选择实现（`AUTO` / `set_impl`）。

同一仓库、同一测试向量；CMake 按架构只链接本机 SIMD 目标。

## 2. 算法角色划分

| 阶段 | 并行性 | 放置 |
|------|--------|------|
| 消息填充 / 分块 | 低 | 标量 `sm3_common.c` |
| 分组装载 + 大端转换 | 中高 | SIMD |
| 消息扩展 `W[16..67]` | 中（有滑动依赖） | SIMD |
| `W′[j]=W[j]⊕W[j+4]` | 高 | SIMD 批量 |
| 64 轮压缩 | 低（A..H 链依赖） | **GPR** |
| 状态异或写回 | 低 | GPR |

这是作业要求的「SIMD 寄存器和通用寄存器混合」的核心解释。

## 3. 数据流

```
              ┌─────────────────────────────────────┐
 update() ──► │ buffer + padding (scalar)           │
              └─────────────────┬───────────────────┘
                                │ 64-byte blocks
                                ▼
              ┌─────────────────────────────────────┐
              │ sm3_compress_{ref,avx2,avx512,neon} │
              │   expand  → W[68]  (+ W' optional)  │
              │   rounds  → sm3_compress_rounds_gpr │
              └─────────────────┬───────────────────┘
                                ▼
                           state[8]
```

所有实现共享 `sm3_compress_rounds_gpr_wp()`，避免 SIMD 路径单独写轮函数导致静默错误。

## 4. AVX2 路径

- **装载**：`_mm256_loadu_si256` ×2 + `shuffle_epi8` 字节翻转。
- **扩展**：逐步 + SIMD `P1`。
- **W′**：YMM 8×u32 批量异或。
- **压缩**：标量 64 轮。

## 5. AVX-512 路径（阶段 4，详见 docs/avx512.md）

- 装载：**单次** `_mm512_loadu_si512` + `vpshufb` 大端解码。
- 扩展：**3-wide** SIMD（`W[j..j+2]` 并行；`W[j]` 依赖 `W[j-3]`）。
- W′：四次 `_mm512_xor_si512`（16×u32）。
- 压缩：与 ref/AVX2 相同的 `sm3_compress_rounds_gpr_wp`。
- 无 AVX512F：目标仍可编译，**运行时** 跳过。

## 6. NEON 路径（ARM64，详见 docs/neon.md）

- 装载：4× `vld1q_u8` + `vrev32q_u8`。
- 扩展：**3-wide** NEON（与 AVX-512 相同依赖窗口）。
- W′：4×u32 `veorq_u32` 循环。
- 压缩：共用 GPR 轮函数。
- ARM64 上 NEON 为基线能力，`sm3_cpu_has_neon()==1`。
- **不使用** ARMv8.2-SM 专用 SM3 指令。

## 7. API 选择

- `SM3_IMPL_REF` / `AVX2` / `AVX512` / `NEON` / `AUTO`
- `AUTO` 优先级（在已编译进库的前提下）：
  - x86：AVX512F → AVX2 → REF
  - ARM64：NEON → REF

## 8. 正确性策略

1. 标准测试向量（空串、`abc`、64×`abcd`）。
2. 边界长度（55/56/63/64/65…）。
3. 随机长度 0..4096 × 多实现交叉对比。
4. 增量 `update` 分片 vs 一次性 `digest`。

## 9. 非目标

- 多缓冲（multi-buffer）并行哈希多条消息（可作为加分扩展）
- 手写全汇编压缩
- OpenSSL 引擎对接
- ARMv8.2-SM / Intel 专用 SM3 指令作为主路径
