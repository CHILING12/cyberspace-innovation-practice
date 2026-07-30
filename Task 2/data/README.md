# 数据与证据

本目录保存报告引用的基准测试明细、汇总结果、汇编输出、核心补丁、
默认测试记录和来源说明。

- `benchmark_detail_30.csv`：30 轮基准测试的逐轮记录；
- `benchmark_summary_30.csv`：按实验对象汇总的统计量；
- `benchmark_results_30.json`：结构化结果与区间估计；
- `default_tests_all_four_versions.txt`：四个版本的默认测试记录；
- `pr1257_*.s`：PR #1257 修改前后的汇编证据；
- `pr1446_*.txt`、`pr1446_core_diff.patch`：PR #1446 的路径与补丁证据；
- `pr1058_core_diff.patch`：PR #1058 的核心补丁；
- `revision_source_notes.md`：提交版本、来源和实验说明。

上游仓库工作树体积较大，未直接放入提交包。其精确准备方式见
`repo/README.md`。
