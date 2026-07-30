# 作业二：Bitcoin Core 中 libsecp256k1 的常数时间修复与性能改进分析

本目录是《网络空间创新创业实践》课程作业二的完整交付。作业以 Bitcoin Core 使用的
`bitcoin-core/secp256k1` 仓库为对象，从提交记录、源码差异、编译后汇编、构建包含
轨迹、上游正确性测试和配对微基准六类证据出发，分析一项常数时间修复与两项性能改进。

目录中包含可编辑的 LaTeX 报告、已编译 PDF、汇编与 Git diff、构建路径证据、30 次/版本
微基准数据、四个版本的默认测试日志、制图与实验脚本。所有结论均按证据边界表述：
库级机器码现象不等同于已完成端到端攻击验证，微基准结果也不等同于 Bitcoin Core
整体吞吐量提升。

## 1. 作业目标

课程任务要求检查 `bitcoin-core/secp256k1` 中与 Bitcoin 密码算法有关的安全修复和性能
改进，并解释修改原因、数学基础与实际效果。本作业将任务落实为以下五项可验收目标：

1. 从官方仓库的 CHANGELOG、提交记录和 PR 评审中筛选代表性案例；
2. 对常数时间案例比较修复前后的源码与 Clang 15 汇编，判断秘密值是否影响内存访问模式；
3. 对域运算案例确认构建入口确实从旧 x86_64 汇编切换到 C/int128 实现；
4. 对固定基点标量乘法案例解释 signed-digit multi-comb、预计算表和在线点加法次数的变化；
5. 使用同一编译参数、交错区组实验、默认上游测试和结构化证据验证结论。

## 2. 完成情况概览

本作业选取了三个层次不同、证据链互补的案例：

| 案例 | 类型 | 核心问题 | 本作业的验证方式 |
| --- | --- | --- | --- |
| PR #1257 | 常数时间修复 | Clang 15 是否把条件移动编译成秘密相关加载地址 | 源码差异、C 探针、修复前后完整汇编 |
| PR #1446 | 域运算性能改进 | 删除旧 x86_64 汇编后实际进入哪条实现路径 | Git diff、`gcc -H -E` 包含轨迹、ECDSA verify 微基准 |
| PR #1058 | 标量乘法性能改进 | signed-digit multi-comb 如何减少表空间与在线点运算 | Git diff、数学推导、ECDSA sign 与 EC keygen 微基准 |

主要验收结论如下：

| 验收项目 | 结果 |
| --- | --- |
| PR #1257 汇编检查 | 修复前出现“先按秘密条件选择地址，再只加载一侧”的模式；修复后双侧加载并掩码合并 |
| PR #1446 构建路径 | 合入前进入 `field_5x52_asm_impl.h`，合入后进入 `field_5x52_int128_impl.h` |
| PR #1446 ECDSA verify | 区组中位耗时变化 `-6.31%`，bootstrap 95% 区间 `[-7.60%, -2.55%]` |
| PR #1058 ECDSA sign | 区组中位耗时变化 `-11.78%`，bootstrap 95% 区间 `[-12.36%, -11.09%]` |
| PR #1058 EC keygen | 区组中位耗时变化 `-13.85%`，bootstrap 95% 区间 `[-15.05%, -12.50%]` |
| PR #1058 表与点运算 | 主预计算表约由 64 KiB 降到 22 KiB，默认在线点加入次数由 64 次降到 44 次 |
| 四个性能版本正确性 | 编译退出码与上游默认测试退出码全部为 `0` |
| 报告交付 | LaTeX 源码与已编译 PDF 均已提交 |

表中负百分比表示合入后耗时降低。

## 3. 三个案例的关键结论

### 3.1 PR #1257：Clang 15 下的常数时间条件移动

该案例关注 `secp256k1_fe_cmov` 与 `secp256k1_fe_storage_cmov` 的编译鲁棒性。
修复前的 Clang 15.0.7 汇编包含如下模式：

```asm
test   r8d, r8d
cmove  rdx, rcx
mov    rdx, qword ptr [rdx]
```

虽然这里没有普通 `jcc` 条件跳转，但 `cmove` 先根据条件选择地址，随后只加载被选中的
一侧，秘密值仍可能影响内存访问地址。修复后汇编会先从两侧取值，再用掩码合并，避免
把秘密条件直接转化为单侧加载地址。

本作业据此得出的结论是：补丁改善了条件移动在 Clang 15 下的常数时间编译鲁棒性。
该探针没有执行 dudect 统计检验，也没有完成 Bitcoin Core 端到端定时攻击，因此
README 和报告均不把它描述为已经证实可利用的密钥恢复漏洞。

### 3.2 PR #1446：删除旧 x86_64 域运算汇编

PR #1446 删除了旧的手写 x86_64 5×52 域运算汇编。本作业在前后两个版本使用相同的
`-DUSE_ASM_X86_64` 与包含目录运行 GCC 预处理包含追踪：

```text
合入前：field_5x52_impl.h -> field_5x52_asm_impl.h
合入后：field_5x52_impl.h -> field_5x52_int128_impl.h
```

这组证据只用于证明构建路径发生了变化；性能因果由独立的交错微基准支持。在本机
GCC 15.2.0、`-O2` 环境下，合入后 ECDSA verify 的区组中位耗时下降 `6.31%`。

### 3.3 PR #1058：signed-digit multi-comb

PR #1058 重构固定基点标量乘法 `secp256k1_ecmult_gen`。signed-digit 表示利用点的
正负对称性，让一个表项同时覆盖正负数字，减少预计算表项；新的 multi-comb 参数还
减少了在线循环中的点加法次数。

在默认参数下，本作业从源码变化得到：

- 主预计算表约由 `64 KiB` 降到 `22 KiB`；
- 在线点加入次数由 `64` 次降到 `44` 次；
- ECDSA sign 区组中位耗时下降 `11.78%`；
- EC keygen 区组中位耗时下降 `13.85%`。

这两项操作都调用固定基点乘法，与修改位置相符。结果是库函数微基准，不直接代表
钱包签名、交易验证或区块验证的端到端加速比例。

## 4. 实验设计

### 4.1 版本对

| 案例 | 合入前提交 | 合入后提交 | 取值方式 |
| --- | --- | --- | --- |
| PR #1257 | `464a9115b4ed` | `4a496a36fb07` | 补丁提交及其父提交 |
| PR #1446 | `07687e811d1c` | `10e6d29b60c3` | 合并提交与第一父提交 |
| PR #1058 | `d8311688bd38` | `da515074e3eb` | 合并提交与第一父提交 |

### 4.2 实验环境

最终结构化环境记录位于 `evidence/benchmark_environment_30.json`：

| 项目 | 配置 |
| --- | --- |
| 系统 | Windows 11，构建号 `10.0.26200` |
| 处理器 | 13th Gen Intel Core i7-1360P |
| Python | 3.12.13 |
| 编译器 | GCC 15.2.0；报告另使用 Clang 15.0.7 检查 PR #1257 汇编 |
| 编译参数 | `-O2 -std=c90 -fno-omit-frame-pointer` |
| 调度控制 | 固定逻辑 CPU 0，设置高优先级 |
| 未控制因素 | 动态频率、Turbo、系统中断与后台任务 |

### 4.3 微基准方法

性能实验包含 15 个四测量区组。奇数区组按 ABBA、偶数区组按 BAAB 运行，其中 A 为
before、B 为 after。每个版本、每项操作保留 30 次正式测量，正式测量前另执行一个
不计入结果的预热区组。

- PR #1446：`ecdsa_verify`，每个样本 4000 次内部迭代；
- PR #1058：`ecdsa_sign` 与 `ec_keygen`，每个样本 7000 次内部迭代；
- 每个区组分别计算 before 与 after 中位数，再计算相对变化；
- 使用 10,000 次 bootstrap 估计区组中位变化的 95% 区间；
- bootstrap 固定种子为 `20260730`。

逐次结果、汇总结果和比较结果分别保存在：

- `evidence/benchmark_detail_30.csv`；
- `evidence/benchmark_summary_30.csv`；
- `evidence/benchmark_comparison_30.csv`；
- `evidence/benchmark_results_30.json`；
- `evidence/benchmark_raw_30.txt`。

### 4.4 正确性测试

四个性能版本均使用上游 `src/tests.c` 的默认迭代次数，未设置
`SECP256K1_TEST_ITERS`。完整命令和输出位于
`evidence/default_tests_all_four_versions.txt`。

| 版本 | 编译退出码 | 测试退出码 | 记录的运行时间 |
| --- | ---: | ---: | ---: |
| `pr1446-before` | 0 | 0 | 64.186 s |
| `pr1446-after` | 0 | 0 | 63.332 s |
| `pr1058-before` | 0 | 0 | 65.059 s |
| `pr1058-after` | 0 | 0 | 64.489 s |

退出码为 `0` 说明本次记录中的编译和默认上游测试成功；表中的外层运行时间不是性能
结论的来源。

## 5. 项目目录

```text
Task 2/
|-- README.md
|-- assignment2_secp256k1_report_v4.tex
|-- report.pdf
|-- evidence/
|   |-- benchmark_comparison_30.csv
|   |-- benchmark_detail_30.csv
|   |-- benchmark_environment_30.json
|   |-- benchmark_raw_30.txt
|   |-- benchmark_results_30.json
|   |-- benchmark_summary_30.csv
|   |-- default_tests_all_four_versions.txt
|   |-- pr1058_core_diff.patch
|   |-- pr1257_actual_after_bool_win_O2.s
|   |-- pr1257_actual_before_bool_win_O2.s
|   |-- pr1446_after_include_trace.txt
|   |-- pr1446_before_include_trace.txt
|   |-- pr1446_core_diff.patch
|   |-- pr1446_path_comparison.txt
|   `-- revision_source_notes.md
|-- imgs/
|   |-- 10_pr1257_assembly_paper.png
|   |-- 12_block_changes_paper.png
|   |-- 13_bitcoin_core_call_path_paper.png
|   |-- logo1.jpg
|   `-- sdured.png
`-- scripts/
    |-- cpu_set_info.py
    |-- make_paper_figures_v4.py
    |-- pr1257_cmov_probe_bool.c
    |-- pr1446_mul_probe_v2.c
    |-- run_default_tests_all.py
    `-- run_pr_benchmarks_v3.py
```

## 6. 文件说明

### 6.1 报告文件

- `assignment2_secp256k1_report_v4.tex`：完整中文 LaTeX 报告源文件，包含正文、
  参考文献、机器码摘录、关键复现命令和证据文件索引；
- `report.pdf`：由上述 TeX 源码编译得到的提交版 PDF；
- `imgs/`：报告使用的校徽、汇编对比、性能区组变化和 Bitcoin Core 调用路径图。

### 6.2 核心证据

| 文件 | 用途 |
| --- | --- |
| `pr1257_actual_before_bool_win_O2.s` | Clang 15.0.7 修复前完整汇编 |
| `pr1257_actual_after_bool_win_O2.s` | Clang 15.0.7 修复后完整汇编 |
| `pr1446_before_include_trace.txt` | PR #1446 合入前 GCC 包含轨迹 |
| `pr1446_after_include_trace.txt` | PR #1446 合入后 GCC 包含轨迹 |
| `pr1446_path_comparison.txt` | 前后实现路径与完整预处理命令对照 |
| `pr1446_core_diff.patch` | PR #1446 核心源码差异 |
| `pr1058_core_diff.patch` | PR #1058 参数、在线函数和预计算程序差异 |
| `benchmark_detail_30.csv` | 15 区组、180 行逐次测量明细 |
| `benchmark_summary_30.csv` | 各版本耗时中位数、MAD、范围与置信区间 |
| `benchmark_comparison_30.csv` | 区组中位变化与 bootstrap 95% 区间 |
| `benchmark_raw_30.txt` | 微基准程序的逐次原始输出 |
| `benchmark_environment_30.json` | 系统、工具链、CPU 亲和性和优先级记录 |
| `default_tests_all_four_versions.txt` | 四个版本的编译命令与完整默认测试结果 |
| `revision_source_notes.md` | 图表数据来源与结论边界说明 |

### 6.3 脚本

- `cpu_set_info.py`：读取 Windows CPU Set、核心、缓存、NUMA 和效率等级信息；
- `pr1257_cmov_probe_bool.c`：调用两类条件移动函数的最小汇编探针；
- `pr1446_mul_probe_v2.c`：调用 5×52 域乘法内部函数的最小探针；
- `run_default_tests_all.py`：编译并执行四个实验版本的上游默认测试；
- `run_pr_benchmarks_v3.py`：在原实验驱动基础上增加 Windows CPU 亲和性与高优先级控制；
- `make_paper_figures_v4.py`：根据结构化 CSV 和汇编证据生成报告图。

## 7. 推荐验收流程

### 7.1 阅读主报告

先打开 `report.pdf`，再在 VS Code 中打开 `assignment2_secp256k1_report_v4.tex`。
PDF 用于查看最终排版，TeX 用于搜索结论、公式、引用和证据文件名。

### 7.2 检查文件完整性

在 `Task 2` 目录执行：

```powershell
Get-ChildItem -Recurse -File
```

当前交付应包含 29 个文件。

### 7.3 检查 Python 语法

```powershell
python -m py_compile `
  scripts/cpu_set_info.py `
  scripts/make_paper_figures_v4.py `
  scripts/run_default_tests_all.py `
  scripts/run_pr_benchmarks_v3.py
```

该命令只检查 Python 语法，不会重跑基准测试。

### 7.4 检查结构化结果

```powershell
Import-Csv evidence/benchmark_comparison_30.csv |
  Format-Table comparison, operation, median_block_relative_change_pct

Get-Content evidence/benchmark_environment_30.json -Raw |
  ConvertFrom-Json |
  Format-List
```

### 7.5 检查默认测试记录

```powershell
Select-String `
  -Path evidence/default_tests_all_four_versions.txt `
  -Pattern "=====|compile_exit_code|test_exit_code|wall_s"
```

预期四个版本的 `compile_exit_code` 和 `test_exit_code` 均为 `0`。

## 8. 重新编译报告

报告使用 XeLaTeX 和 Windows 中文字体配置。在 `Task 2` 目录执行：

```powershell
xelatex -interaction=nonstopmode -halt-on-error assignment2_secp256k1_report_v4.tex
xelatex -interaction=nonstopmode -halt-on-error assignment2_secp256k1_report_v4.tex
```

运行两遍用于稳定目录、引用和页码。输出文件为
`assignment2_secp256k1_report_v4.pdf`；仓库中的提交版文件名为 `report.pdf`。
如果需要更新提交版，可在检查新 PDF 后再明确复制或重命名，避免误覆盖已经验收的版本。

如果其他系统缺少报告指定的 Windows 中文字体，需要调整 TeX 中的 `ctex` 字体设置后再编译。

## 9. 证据快速复核

### 9.1 PR #1257 汇编

```powershell
Select-String `
  -Path evidence/pr1257_actual_before_bool_win_O2.s `
  -Pattern "cmove|mov"

Select-String `
  -Path evidence/pr1257_actual_after_bool_win_O2.s `
  -Pattern "cmove|mov"
```

复核重点不是简单统计 `cmove` 数量，而是确认修复前是否先选择地址再加载、修复后是否
双侧加载再掩码合并。

### 9.2 PR #1446 构建路径

```powershell
Get-Content evidence/pr1446_path_comparison.txt
```

应能看到合入前的 `field_5x52_asm_impl.h` 与合入后的 `field_5x52_int128_impl.h`。

### 9.3 性能结果

```powershell
Import-Csv evidence/benchmark_comparison_30.csv | Format-Table
```

负数表示合入后更快。解释结果时应同时给出区组中位变化和 bootstrap 95% 区间，
不要只引用单次最快结果。

## 10. 完整复现实验的依赖边界

本目录完整保存了报告、关键源码差异、已生成机器码、构建轨迹、测试日志、结构化性能
结果和实验脚本，但不是独立封装的 libsecp256k1 构建仓库。

以下内容未包含在课程提交目录中：

- 三个 PR 对应的完整上游源码快照；
- `builds/` 中的预计算对象文件和 benchmark 可执行文件；
- `run_pr_benchmarks_v3.py` 引用的原实验驱动 `run_pr_benchmarks_v2.py`；
- 制图脚本原研究工作区中的中间目录。

因此：

- 可以直接阅读和审计所有已提交证据；
- 可以直接进行 Python 语法检查、CSV/JSON 检查和报告编译；
- 不能在一个全新目录中直接运行 `run_pr_benchmarks_v3.py` 或
  `run_default_tests_all.py` 完整重建实验；
- 若要从零重跑，应先检出表 4.1 的上游版本、生成预计算对象文件、恢复原实验驱动，
  并把脚本中的 `repo/`、`builds/`、`evidence/revision/` 等路径调整为当前机器的真实位置。

README 保留这一边界，避免把“证据交付完整”误写成“所有构建依赖均已打包”。

## 11. VS Code 修改与 Git 同步

建议从仓库根目录打开 VS Code：

```powershell
code .
```

修改前先同步：

```powershell
git pull --ff-only
```

修改后先检查范围：

```powershell
git status
git diff -- "Task 2"
```

只提交作业二相关文件：

```powershell
git add -- "Task 2"
git commit -m "Update Task 2"
git push
```

也可以使用 VS Code 左侧“源代码管理”面板完成暂存、提交和“同步更改”。提交前应确认
没有把 `.aux`、`.log`、临时截图或未检查的新 PDF 一并加入。

## 12. 结论边界与使用限制

### 12.1 常数时间结论

- PR #1257 的结论来自给定 Clang 版本、优化参数与最小探针；
- 没有观察到普通条件跳转，不代表秘密相关内存访问不存在；
- 没有运行 dudect，也没有完成跨进程或远程攻击；
- 不应把库级机器码问题直接写成已证实可利用的 Bitcoin Core 漏洞。

### 12.2 性能结论

- 性能数据来自一台 Windows x86_64 机器、GCC 15.2.0 和 `-O2`；
- 固定 CPU 与高优先级不能消除动态频率、Turbo、中断和后台任务；
- 15 个区组适合描述本次重复性，但不是跨机器、跨编译器基准；
- 库函数微基准不能直接外推为钱包、节点或区块验证的整体提升。

### 12.3 证据结论

- 包含轨迹证明实际实现路径，不单独证明性能因果；
- Git diff 证明源码变化，不单独证明运行时效果；
- 正确性测试退出码为 0 证明本次测试通过，不等同于形式化验证；
- 图表是结构化证据的可视化，最终数字应以 CSV、JSON 和原始日志为准。

## 13. 常见问题

### 13.1 README 或证据文件在终端显示乱码

所有文本文件均按 UTF-8 保存。Windows PowerShell 5 中可显式指定：

```powershell
Get-Content README.md -Encoding UTF8
```

VS Code 右下角编码应显示 `UTF-8`。

### 13.2 XeLaTeX 找不到中文字体

报告使用 Windows 中文字体配置。请确认 XeLaTeX 与对应字体可用，或修改 TeX 导言区
的字体设置。不要改用 pdfLaTeX 编译中文报告。

### 13.3 基准脚本提示缺少模块或目录

这是第 10 节说明的复现依赖边界。课程目录保存了最终证据和实验脚本，但没有打包完整
上游源码快照、构建对象与 `run_pr_benchmarks_v2.py`。应先恢复原实验工作区并调整路径，
不要把缺少外部构建依赖误判为现有结果文件损坏。

### 13.4 GitHub 无法直接预览大 PDF

`report.pdf` 约 11.8 MB。若网页预览加载较慢，可下载文件，或在本地 VS Code、浏览器
和 PDF 阅读器中打开。

## 14. 提交清单

提交或继续修改前建议完成以下检查：

- [ ] `Task 2/README.md` 在 GitHub 与 VS Code 中均正常显示中文；
- [ ] `report.pdf` 可正常打开，题目、姓名、目录、图表和参考文献完整；
- [ ] `assignment2_secp256k1_report_v4.tex` 可由 XeLaTeX 连续编译两遍；
- [ ] `evidence/` 中的汇编、diff、包含轨迹、默认测试和基准数据齐全；
- [ ] 四个版本的编译与测试退出码均为 `0`；
- [ ] 三组性能结果与 `benchmark_comparison_30.csv` 一致；
- [ ] 安全与性能结论保留第 12 节的适用边界；
- [ ] `git diff -- "Task 2"` 中没有临时文件或无关改动；
- [ ] 本地提交已推送到 GitHub `main` 分支。

## 15. 主要资料

- [bitcoin-core/secp256k1](https://github.com/bitcoin-core/secp256k1)
- [PR #1257：Fix constant-time cmov when compiling with Clang 15](https://github.com/bitcoin-core/secp256k1/pull/1257)
- [PR #1446：Remove x86_64 field arithmetic assembly](https://github.com/bitcoin-core/secp256k1/pull/1446)
- [PR #1058：signed-digit multi-comb](https://github.com/bitcoin-core/secp256k1/pull/1058)
- Mike Hamburg, *Fast and compact elliptic-curve cryptography*, ePrint 2012/309
- Bitcoin Core `src/key.cpp`、`src/pubkey.cpp` 与 `src/script/interpreter.cpp`

更完整的数学推导、源码引用、访问日期和参考文献条目见
`assignment2_secp256k1_report_v4.tex` 与 `report.pdf`。
