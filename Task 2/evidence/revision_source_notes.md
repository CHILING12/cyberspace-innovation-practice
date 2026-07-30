# 修订版图表与证据说明

- 图10：`10_pr1257_clang15_assembly.png`
  - 目的：说明 PR #1257 前后 Clang 15.0.7 机器码差异。
  - 数据：`pr1257_actual_before_bool_win_O2.s`、`pr1257_actual_after_bool_win_O2.s`。
  - 结论边界：修复前观察到 `cmove` 选择指针后仅加载一侧，属于秘密相关内存访问；未观察到普通 `jcc` 条件跳转，不据此声称已经完成端到端定时攻击。

- 图11：`11_pr1446_build_path_proof.png`
  - 目的：证明合入前 benchmark 确实启用了旧 x86_64 域运算汇编路径。
  - 数据：GCC 15.2.0 相同 `-DUSE_ASM_X86_64` 编译命令与 `-H` 包含轨迹；合入前包含 `field_5x52_asm_impl.h`，合入后包含 `field_5x52_int128_impl.h`。
  - 结论边界：证明实现路径，不单独证明性能因果；性能结论另由配对实验支持。

- 图12：`12_benchmark_distributions_30.png`
  - 目的：展示 30 次交错微基准的分布、中心与离散程度。
  - 数据：`benchmark_detail_30.csv`、`benchmark_summary_30.csv`、`benchmark_comparison_30.csv`。
  - 统计：15 个四测量区组，奇数 ABBA、偶数 BAAB；每个版本保留 30 次；菱形为中位数、误差线为 MAD；区组相对改变量给出 10,000 次 bootstrap 95% 区间。

- 图13：`13_bitcoin_core_call_path.png`
  - 目的：把库级修改映射到 Bitcoin Core 的具体签名与验签调用路径。
  - 数据：Bitcoin Core `src/key.cpp`、`src/pubkey.cpp`、`src/script/interpreter.cpp`，访问日期 2026-07-30。
  - 结论边界：调用路径证明“相关性”，不等同于 Bitcoin Core 端到端性能提升测量。

- 图14：`14_multicomb_worked_example.png`
  - 目的：用 8 位标量给出 multi-comb 重组的可手算示例，并说明 signed-digit 使表项减半的原因。
  - 数据：Mike Hamburg, *Fast and compact elliptic-curve cryptography*, ePrint 2012/309, §3.3；secp256k1 PR #1058。
