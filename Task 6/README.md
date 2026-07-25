# CKKS 密文卷积旋转次数最优性分析

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![TenSEAL](https://img.shields.io/badge/TenSEAL-0.3.16-green.svg)](https://github.com/OpenMined/TenSEAL)

在 TenSEAL CKKS 同态加密卷积中，分析"打包→旋转→累加"方案的旋转（rotation）操作是否达到理论最小值，并给出稀疏优化证明。

---

## 目录

1. [项目背景](#1-项目背景)
2. [核心问题](#2-核心问题)
3. [技术方案](#3-技术方案)
4. [实验结果](#4-实验结果)
5. [核心结论](#5-核心结论)
6. [项目结构](#6-项目结构)
7. [快速复现](#7-快速复现)
8. [参考文献](#8-参考文献)
9. [许可证](#9-许可证)

---

## 1. 项目背景

CKKS 全同态加密支持在密文上直接进行向量化线性运算。在二维卷积中，密文元素需要跨槽位旋转以对齐计算位置。一次旋转（`rotate_vector`）需消耗 Galois Key 且计算开销数十倍于密文乘法，因此**最小化旋转次数**是 CKKS 卷积性能优化的核心问题。

本项目在 [Task 5](../task5/)（TenSEAL CKKS 密文卷积正确性验证）的基础上，系统分析当前实现中的旋转策略是否已达理论最优。

## 2. 核心问题

> **在 4×4 输入、3×3 卷积核的 CKKS 密文卷积中，"打包→旋转→累加"方案使用的旋转次数是否等于理论最小值？**

固定输入和卷积核：

$$
X = \begin{bmatrix}
1&2&3&4\\
5&6&7&8\\
9&10&11&12\\
13&14&15&16
\end{bmatrix}
\qquad
K = \begin{bmatrix}
1&-1&2\\
0&3&-2\\
2&1&-1
\end{bmatrix}
\qquad
Y = X * K = \begin{bmatrix}
26&31\\
46&51
\end{bmatrix}
$$

考察两个层次：

| 层次 | 说明 | 有效项数 |
|------|------|----------|
| 通用 3×3 卷积 | 不利用卷积核具体数值，支持任意核 | 9 |
| 稀疏固定卷积核 | 利用 $K[1,0]=0$ 删除零权重 | 8 |

## 3. 技术方案

### 3.1 TenSEAL 二叉旋转累加

TenSEAL 的 `enc_matmul_plain` 采用二叉归约（binary reduction），而非逐元素旋转：

1. **补齐至 2 的幂**：核长度 9 → 16（$2^4$）
2. **按列扫描打包**：4 个滑窗 × 16 项 = 64 槽
3. **逐级归约**：每次旋转将槽间距减半，累加项数翻倍

```
64 槽 ──[rot 32]──▶ 合并为 32 槽
32 槽 ──[rot 16]──▶ 合并为 16 槽
16 槽 ──[rot  8]──▶ 合并为  8 槽
 8 槽 ──[rot  4]──▶ 合并为  4 槽（输出）
```

旋转序列 `[32, 16, 8, 4]`，共 **4 次**。

### 3.2 理论下界

二叉归约一次旋转至多将累加项数翻倍。$n$ 项归约至 1 项的最小旋转次数：

$$R_{\min}(n) = \lceil \log_2 n \rceil$$

| 场景 | $n$ | $R_{\min}$ |
|------|-----|------------|
| 通用 3×3 卷积 | 9 | $\lceil \log_2 9 \rceil = 4$ |
| 稀疏卷积核 | 8 | $\lceil \log_2 8 \rceil = 3$ |

### 3.3 稀疏优化

固定卷积核 $K[1,0] = 0$，第 3 个核位置（0-indexed）对任意输入的乘积恒为零。删除该位置后：

- 有效乘积项：9 → **8**
- 补齐至 $2^3 = 8$，刚好无需补零
- 密文向量：64 → **32**（减少 50%）
- 旋转序列：`[16, 8, 4]`，共 **3** 次

### 3.4 实验约束

- 不修改 Task 5 任何代码，通过 `sys.path` 导入复用
- 客户端持有私钥，服务器仅持有公开评估上下文
- CKKS 参数：$N=8192$，系数模数 $[60,40,40,60]$，全局缩放 $2^{40}$

## 4. 实验结果

### 4.1 通用 3×3 卷积

| 指标 | 数值 |
|------|------|
| 打包方式 | `im2col_encoding` + `conv2d_im2col` |
| 密文向量大小 | 64 |
| 旋转序列 | `[32, 16, 8, 4]` |
| 实际旋转次数 | **4** |
| 理论下界 | **4** |
| 达到最优 | ✅ |
| 最大绝对误差 | $6.88 \times 10^{-6}$ |

### 4.2 稀疏固定卷积核

| 指标 | 数值 |
|------|------|
| 打包方式 | 去零 + `enc_matmul_encoding` + `enc_matmul_plain` |
| 非零核元素 | 8 |
| 密文向量大小 | 32 |
| 旋转序列 | `[16, 8, 4]` |
| 实际旋转次数 | **3** |
| 理论下界 | **3** |
| 达到最优 | ✅ |
| 最大绝对误差 | $6.83 \times 10^{-6}$ |

### 4.3 运行输出

```text
CKKS ROTATION EXPERIMENT
========================

[Generic 3x3 convolution]
packed vector size : 64
rotation steps     : [32, 16, 8, 4]
actual rotations   : 4
theoretical minimum: 4
reaches minimum    : True
maximum error      : 6.877227e-06

[Sparse fixed-kernel convolution]
nonzero terms      : 8
packed vector size : 32
rotation steps     : [16, 8, 4]
actual rotations   : 3
theoretical minimum: 3
reaches minimum    : True
maximum error      : 6.830322e-06

[Conclusion]
Generic 3x3 convolution: 4 rotations, matching ceil(log2(9)) = 4.
Fixed sparse kernel: 3 rotations after removing the zero coefficient,
matching ceil(log2(8)) = 3.
```

### 4.4 对比总结

| 分析对象 | 有效项 | 打包长度 | 旋转次数 | 理论下界 | 最优 |
|----------|--------|----------|----------|----------|:----:|
| 通用 3×3 卷积 | 9 | 64 | 4 | 4 | ✅ |
| 稀疏固定卷积核 | 8 | 32 | 3 | 3 | ✅ |

## 5. 核心结论

**结论一：通用卷积已达理论最优。**
TenSEAL 的 `im2col_encoding + conv2d_im2col` 路径对任意 3×3 卷积核使用 4 次旋转，等于二叉归约模型下 $\lceil \log_2 9 \rceil = 4$ 的理论下界。

**结论二：稀疏优化可进一步降低。**
利用 $K[1,0] = 0$ 删除零权重后，旋转次数从 4 降至 3，密文存储减半。若在模型剪枝或结构化稀疏场景中，该方法可推广至任意稀疏卷积核。

**结论三：一般性 $n$ 项归约公式。**
在 TenSEAL 二叉归约框架下，$n$ 项线性乘加的理论最小旋转次数为 $\lceil \log_2 n \rceil$，可通过零权重剔除和 2-幂补齐逼近。

### 为什么不是 8 次旋转？

直觉上 3×3 卷积核 9 个位置减去中心需要 8 次旋转。但 TenSEAL 实际采用 im2col 展平 + 矩阵乘法 + 二叉归约，4 次旋转即可覆盖全部数据——比直觉方案快一倍。

## 6. 项目结构

```text
Task 6/
├── README.md
├── LICENSE
├── .gitignore
└── code/
    ├── rotation_experiment.py            # 旋转分析主程序
    └── output/
        └── rotation_experiment_results.json  # 实验证据
```

## 7. 快速复现

### 环境

| 依赖 | 版本 |
|------|------|
| Python | 3.13 |
| TenSEAL | 0.3.16 |
| NumPy | ≥2.0 |

> TenSEAL 0.3.16 在 PyPI 上仅提供到 Python 3.13（cp313）的 Windows wheel。

### 运行

```powershell
# 安装依赖
pip install tenseal==0.3.16 numpy

# 运行实验
cd code
python rotation_experiment.py
```

实验输出终端统计结果，并将完整的机器可读证据写入 `output/rotation_experiment_results.json`。

## 8. 参考文献

1. Cheon, J. H., Kim, A., Kim, M., & Song, Y. (2017). *Homomorphic encryption for arithmetic of approximate numbers.* ASIACRYPT 2017.
2. OpenMined. (2025). *TenSEAL: A library for encrypted tensor operations using homomorphic encryption.* https://github.com/OpenMined/TenSEAL
3. Microsoft SEAL. (2025). *Microsoft SEAL (release 4.1).* https://github.com/Microsoft/SEAL

## 9. 许可证

本项目基于 [MIT License](LICENSE) 发布。

---

<p align="center">
  <sub>《网络安全创新创业实践》· 第六次作业 · 2026</sub>
</p>
