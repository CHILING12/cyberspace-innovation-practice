# Task 7：基于 garak 的 DeepSeek 模型安全测评

## 任务说明

本实验在 Ubuntu 虚拟机中部署 garak 0.15.1，通过 LiteLLM 对 `deepseek-v4-flash` 进行安全测评。

测试包括：

- 提示注入
- DAN 越狱
- 毒性内容
- API Key 泄露
- 利用型攻击
- 恶意代码生成

## 结果概览

模型在 API Key 保护、毒性内容和恶意代码拒绝方面表现较好，但在部分提示注入、DAN 越狱、模板注入和 SQL 注入测试中出现命中。

| 类别 | 结果摘要 |
| --- | --- |
| 提示注入 | 出现部分命中 |
| DAN 越狱 | 风险较明显 |
| 毒性内容 | 本次样本未发现问题 |
| API Key 泄露 | 未发现泄露 |
| 利用型攻击 | 部分模板和 SQL 载荷被回显 |
| 恶意代码生成 | 检测样本均未生成恶意代码 |

## 文件

```text
Task 7/
├── README.md
├── Task7实验报告.md
├── promptInjection.png
├── dan.png
├── toxicity.png
├── apikey.png
├── exploitation.png
└── malwaregen.png
```

## 实验报告

[Task7实验报告.md](Task7实验报告.md) 记录了测试环境、命令、评价指标、各类样本结果和安全分析。
