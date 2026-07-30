# Task 6：CKKS 密文卷积的旋转次数与稀疏优化

## 任务说明

本实验在 Task 5 的基础上分析 TenSEAL 密文卷积中的旋转—累加过程，并测试固定稀疏卷积核带来的改进。

在单密文二叉归约模型中，合并 `n` 个有效项至少需要 `ceil(log2(n))` 层旋转—累加。通用 `3×3` 卷积有 9 个乘加项，需要 4 次旋转；删除固定卷积核中的一个零权重后，剩余 8 个有效项，需要 3 次旋转。

## 结果

| 项目 | 通用方案 | 稀疏方案 |
| --- | ---: | ---: |
| 有效乘加项 | 9 | 8 |
| 逻辑打包槽数 | 64 | 32 |
| CKKS 密文数 | 1 | 1 |
| 推导旋转数 | 4 | 3 |
| 最大绝对误差 | `6.807e-6` | `6.813e-6` |
| 服务器求值中位数 | `9.452 ms` | `7.746 ms` |

两种方案均满足 `1e-3` 的误差要求。逻辑槽数减少不等于物理密文数量减少，本实验的两种方案都使用一个 CKKS 密文。

## 文件

```text
Task 6/
├── README.md
├── REPORT.md
└── code/
    ├── requirements.txt
    ├── rotation_experiment.py
    ├── test_rotation_experiment.py
    └── output/
```

## 运行

```powershell
cd code
py -3.13 -m pip install -r requirements.txt
py -3.13 -m unittest -v
py -3.13 rotation_experiment.py --trials 5
```

## 实验报告

[REPORT.md](REPORT.md) 包含问题定义、旋转次数推导、TenSEAL 源码对应、对照实验和结果讨论。
