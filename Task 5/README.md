# Task 5：基于 TenSEAL CKKS 的密文卷积

## 任务说明

使用开源全同态加密库，对单通道 `4×4` 输入和 `3×3` 卷积核执行步长为 1、无填充的密文卷积。本实验选择 TenSEAL 0.3.16 和 CKKS，输出形状为 `2×2`。

## 实现流程

1. 客户端创建 CKKS 上下文和密钥；
2. 客户端使用 im2col 编码输入并加密；
3. 服务器加载不含私钥的评估上下文；
4. 服务器使用明文卷积核计算密文结果；
5. 客户端解密，并与普通卷积结果比较。

本实验保护客户端输入。卷积核是服务器端的明文参数。

主要参数：

| 参数 | 值 |
| --- | --- |
| 多项式模数次数 | `8192` |
| 系数模数位长链 | `[60, 40, 40, 60]` |
| 全局缩放因子 | `2^40` |
| 误差阈值 | `1e-3` |

## 结果

普通卷积结果：

```text
[[26, 31],
 [46, 51]]
```

10 次 CKKS 实验均通过误差检查，最大绝对误差为 `6.88152024252986e-06`。服务器使用的上下文不含私钥。

本次记录的中位耗时：

| 阶段 | 时间 |
| --- | ---: |
| im2col、加密和序列化 | `10.402 ms` |
| 服务器加载、计算和序列化 | `14.575 ms` |
| 客户端加载和解密 | `2.328 ms` |

CKKS 加密包含随机采样，重新运行后密文哈希、末位误差和耗时会有变化。

## 文件

```text
Task 5/
├── code/
│   ├── fhe_convolution.py
│   ├── test_fhe_convolution.py
│   ├── visualize_results.py
│   └── output/
└── report/
    ├── main.tex
    └── main.pdf
```

## 运行

```powershell
cd code
python -m pip install -r requirements.txt
python fhe_convolution.py --trials 10 --output output/experiment_results.json
python -m unittest -v
python visualize_results.py
```

## 实验报告

- [PDF 报告](report/main.pdf)
- [LaTeX 源文件](report/main.tex)

报告中包含 CKKS 原理、参数选择、卷积推导、客户端与服务器流程、误差分析和测试结果。
