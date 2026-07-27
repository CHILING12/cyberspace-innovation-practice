# 多缓冲（Multi-buffer）优化说明

## 1. 动机

单缓冲混合路径中，64 轮压缩对 \(A..H\) 存在串行依赖，SIMD 难以加速；消息扩展又受 \(W[j]\!\leftarrow\!W[j-3]\) 限制。  
**多缓冲**同时处理 \(N\) 条**相互独立**的消息：第 \(k\) 条消息的状态与 \(W\) 仅占用向量第 \(k\) 个 lane，从而：

- 扩展在 lane 间无交叉依赖，可满宽并行；
- 压缩轮对每条消息仍串行，但 **4 条消息的轮函数同步执行**，有效吞吐按 lane 数放大。

## 2. 本实现

| 项 | 说明 |
|----|------|
| 宽度 | **4 路**（`SM3_MB4_LANES`，对应 SSE/AVX 的 4×u32） |
| 内核 | `sm3_mb4_compress_avx2`（`src/x86/sm3_mb_avx2.c`） |
| API | `sm3_mb4_digest` / `sm3_mb_digest` / `sm3_mb_max_lanes` |
| 回退 | 无 AVX2 时退化为顺序 `sm3_digest_ex(..., REF)` |
| 填充 | 整块走 4 路 SIMD；尾块与填充走标量增量接口，保证与 ref 一致 |

数据布局：每个 `__m128i` 的 4 个 32 位 lane 分别对应 4 条消息的同一逻辑字。

## 3. 使用示例

```c
const uint8_t *msgs[4] = { m0, m1, m2, m3 };
uint8_t out[4][SM3_DIGEST_SIZE];

/* 四条等长消息 */
sm3_mb4_digest(msgs, len, out);

/* 任意条数；等长组优先走 4 路 */
size_t n = ...;
const uint8_t *list[...];
size_t lens[...];
uint8_t digs[...][32];
sm3_mb_digest(n, list, lens, digs);
```

## 4. 与单缓冲对比

| | 单缓冲 AVX2 | 多缓冲 mb4 |
|--|-------------|------------|
| 消息数 | 1 | 4（独立） |
| 扩展 | 有限向量化 | 满 4-lane 并行 |
| 压缩 | GPR 串行 | **4 路 SIMD 并行** |
| 适用 | 单流 API | 批处理 / 多连接 |

## 5. 验证

```bat
build\test_mb.exe
build\bench_sm3.exe
```

`bench` 中 `ref4` 为 4 次顺序 ref 的合计吞吐，`mb4` 为多缓冲合计吞吐，二者可直接比较加速比。
