# 课程作业2：Bitcoin Core 中 libsecp256k1 的常数时间修复与性能改进分析

报告人：安泊仰、李汶峰、赵孙梦元、孙名璋

## 目录结构

```text
.
├─ code/       实验探针、基准测试与回归测试脚本
├─ data/       实验结果、汇编、补丁和来源记录
├─ report.pdf  最终报告 PDF
├─ .gitignore
└─ README.md
```

## 直接查看

最终报告位于当前目录下的 `report.pdf`，在 GitHub 文件列表中点击即可查看。

## 项目内容

- `code/`：PR #1257 与 PR #1446 的 C 探针、基准测试脚本和默认测试脚本；
- `data/`：基准测试明细、汇总数据、汇编输出、核心补丁和测试记录；
- `report.pdf`：课程作业最终报告。

## 复现实验

1. 按 `data/repo/README.md` 准备六个上游源码工作树；
2. 将 GCC 放入 `PATH`，如需指定编译器可设置环境变量 `CC`；
3. 在项目根目录运行：

```powershell
python .\code\run_pr_benchmarks_v3.py
python .\code\run_default_tests_all.py
```

实验脚本默认从 `data/repo/` 读取源码工作树，将构建产物写入
`builds/`，结果写入 `data/`。报告采用的原始结果已随项目提供，
不重新运行也可以检查。

## 数据检查

```powershell
Import-Csv .\data\benchmark_comparison_30.csv | Format-Table
Get-Content .\data\benchmark_environment_30.json -Raw | ConvertFrom-Json
Select-String `
  -Path .\data\default_tests_all_four_versions.txt `
  -Pattern "=====|compile_exit_code|test_exit_code|wall_s"
```

## VS Code 与 Git 同步

从仓库根目录打开：

```powershell
code .
```

修改前执行：

```powershell
git pull --ff-only
```

修改后检查并提交：

```powershell
git status
git diff -- "Task 2"
git add -- "Task 2"
git commit -m "Update Task 2"
git push
```
