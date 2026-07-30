# 课程作业2第三次修订版：源码与证据

主报告题目：**Bitcoin Core 中 libsecp256k1 的常数时间修复与性能改进分析**

## 目录

- `report.pdf`：已编译、已逐页检查的提交版 PDF。
- `assignment2_secp256k1_report_v4.tex`：报告 LaTeX 源文件。
- `imgs/`：山大标识和报告实际使用的三张论文风格插图。
- `evidence/`：汇编、Git diff、包含轨迹、默认测试日志和 15 区组微基准数据。
- `scripts/`：汇编探针、基准测试、默认测试和制图脚本。

## 编译

在本目录执行：

```powershell
xelatex assignment2_secp256k1_report_v4.tex
xelatex assignment2_secp256k1_report_v4.tex
```

报告使用 XeLaTeX 与 Windows 中文字体配置。若在其他系统编译，需要调整
`ctex` 字体设置。证据文件均为本次报告所引用的原始输出或结构化结果。
