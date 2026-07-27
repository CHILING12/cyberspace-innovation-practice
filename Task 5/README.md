# 第五次作业：基于 TenSEAL CKKS 的密文卷积

本目录是《网络安全创新创业实践》第五次作业的完整交付，包含实验要求、课程参考资料、可运行代码、自动化测试、实验数据、结果图片，以及中文 LaTeX 实验报告和最终 PDF。

## 1. 作业要求

> 作业 5：选择任一开源全同态加密库（CPU 或 GPU 均可），使用单输入单输出 `4×4` 输入和 `3×3` 卷积核（步长 1、无填充），实现密文卷积并验证结果正确性。

本实现将要求严格解释为：

- 输入通道数和输出通道数均为 1；
- 输入张量形状为 `[1, 1, 4, 4]`；
- 卷积核形状为 `[1, 1, 3, 3]`；
- 步长 `stride=1`，填充 `padding=0`；
- 采用 CNN `Conv2D` 的二维互相关语义，即不翻转卷积核；
- 输出张量形状为 `[1, 1, 2, 2]`；
- 输入在服务器计算期间始终保持密文状态，服务器评估上下文不得包含私钥；
- 由于 CKKS 属于近似同态加密，使用预先确定的绝对误差阈值 `1e-3` 判断正确性。

## 2. 技术方案

实验选用以下开源技术：

- **TenSEAL 0.3.16**：提供加密向量、`im2col_encoding` 和 `conv2d_im2col` 接口；
- **Microsoft SEAL**：TenSEAL 使用的底层同态加密后端；
- **CKKS**：支持近似实数运算和 SIMD 批处理的同态加密方案；
- **NumPy/Matplotlib**：用于明文参考计算、误差统计和结果可视化。

客户端生成 CKKS 上下文和密钥，并保留私钥。客户端对输入进行 im2col 编码和加密后，只向服务器发送不含私钥的公开评估上下文及密文输入。服务器持有明文卷积核，执行密文与明文之间的线性乘加并返回输出密文，最后由客户端解密。

该安全边界保护的是**客户端输入**。卷积核作为服务器端明文模型参数使用，因此本实验不宣称提供模型参数隐私。

主要 CKKS 参数如下：

| 参数 | 取值 |
| --- | --- |
| 多项式模数次数 | `8192` |
| 系数模数位长链 | `[60, 40, 40, 60]` |
| 系数模数总位长 | `200 bit` |
| 全局缩放因子 | `2^40` |
| 目标经典安全级别 | `128 bit` |
| Galois Keys | 已生成，用于槽旋转 |
| Bootstrapping | 不使用，单层线性卷积无需刷新密文 |

## 3. 实验数据与参考结果

固定输入矩阵为：

```text
X = [[ 1,  2,  3,  4],
     [ 5,  6,  7,  8],
     [ 9, 10, 11, 12],
     [13, 14, 15, 16]]
```

固定卷积核为：

```text
K = [[ 1, -1,  2],
     [ 0,  3, -2],
     [ 2,  1, -1]]
```

独立明文实现和逐项手算得到参考输出：

```text
Y = [[26, 31],
     [46, 51]]
```

最终保存的 CKKS 解密输出为：

```text
[[26.000003036778416, 31.000004199480824],
 [46.000006376746114, 51.000006842397156]]
```

## 4. 目录结构

```text
第五次作业/
|-- README.md                         # 本文件：整个作业的总览与复现说明
|-- 实验要求.txt                       # 作业原始要求
|-- 参考资料/                          # 课程课件与 FHE 参考材料
|-- code/
|   |-- README.md                     # 代码目录简要说明
|   |-- requirements.txt              # 固定版本的 Python 依赖
|   |-- fhe_convolution.py            # 密文卷积主程序和实验驱动
|   |-- test_fhe_convolution.py       # 5 项自动化测试
|   |-- visualize_results.py          # 根据 JSON 证据生成结果图片
|   `-- output/
|       |-- experiment_results.json   # 10 次实验的完整机器可读证据
|       `-- figures/
|           |-- encrypted_convolution_result.png
|           `-- runtime_validation.png
`-- report/
    |-- main.tex                      # 完整中文 LaTeX 报告源码
    `-- main.pdf                      # 编译并逐页检查后的最终报告
```

`report/` 中的 `.aux`、`.log`、`.out` 和 `.toc` 文件是 XeLaTeX 编译产生的辅助文件。

## 5. 环境与复现方法

已验证环境：

- Windows 11；
- Python 3.12.9；
- TenSEAL 0.3.16；
- Matplotlib 3.10.3；
- NumPy 2.2.6。

在 PowerShell 中进入代码目录：

```powershell
cd "D:\实验报告\网络安全创新创业实践\第五次作业\code"
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

执行 10 次密文卷积实验并保存 JSON 证据：

```powershell
python fhe_convolution.py --trials 10 --output output/experiment_results.json
```

执行语法检查和自动化测试：

```powershell
python -m py_compile fhe_convolution.py test_fhe_convolution.py visualize_results.py
python -m unittest -v
```

根据实验 JSON 重新生成报告图片：

```powershell
python visualize_results.py
```

如需重新编译报告，在 `report` 目录中执行两遍 XeLaTeX，以稳定目录、引用和页码：

```powershell
cd ..\report
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

CKKS 加密含随机采样，因此重新运行后密文哈希、末位近似误差和耗时可能变化；参考输出、形状、误差阈值和正确性结论应保持不变。

## 6. 最终实验结果

当前 `experiment_results.json` 保存了 2026 年 7 月 24 日完成的 10 次实验，关键结果如下：

| 验证项目 | 结果 |
| --- | ---: |
| 通过误差阈值的实验 | `10/10` |
| 不同输入密文 SHA-256 数量 | `10/10` |
| 全部试验最大绝对误差 | `6.88152024252986e-06` |
| 全部槽位平均绝对误差 | `5.10567868330369e-06` |
| 预设绝对误差阈值 | `1e-3` |
| 服务器上下文含私钥 | `False` |
| 最终正确性判定 | `PASS` |

本次采样的中位耗时：

| 阶段 | 中位耗时 |
| --- | ---: |
| 客户端 im2col、加密与序列化 | `10.402 ms` |
| 服务器加载、密文卷积与序列化 | `14.575 ms` |
| 客户端加载与解密 | `2.328 ms` |

上下文和密钥初始化耗时为 `1337.975 ms`。服务器公开评估上下文约为 `35.5 MB`，主要开销来自完整 Galois Key 集；生产实现可仅生成实际需要的旋转密钥以减少传输与存储开销。

## 7. 测试覆盖

`test_fhe_convolution.py` 包含以下 5 项回归测试：

1. 手算明文参考结果必须等于 `[[26, 31], [46, 51]]`；
2. 密文卷积解密结果必须在误差阈值内匹配明文结果；
3. 服务器公开评估上下文不得含有私钥；
4. 相同输入的两次 CKKS 加密必须得到不同的序列化密文；
5. 非法输入形状和错误步长必须被拒绝。

最终回归结果为：

```text
Ran 5 tests
OK
```

## 8. 报告内容

`report/main.pdf` 共 26 页，主要包含：

- 作业原文、任务解释与验收标准；
- 课程资料学习、开源库比较和选型依据；
- RLWE、CKKS、同态线性运算和密钥安全边界；
- 四个输出元素的逐项手算与 im2col 推导；
- 客户端/服务器分离的实现思路及核心代码；
- 参数选择、误差判据、10 次运行结果和性能数据；
- 运行截图、矩阵与误差可视化；
- 自动化测试、局限、改进方向和复现方法；
- 三个 Python 文件的完整源码附录；
- CKKS、TenSEAL、Microsoft SEAL、HE Standard 等参考文献。

最终 PDF 已使用 XeLaTeX 编译，并通过 26 页逐页渲染检查；未发现乱码、裁切、重叠、缺失引用或 LaTeX 版式告警。

## 9. 提交说明

建议提交以下内容：

- `report/main.pdf`：最终实验报告；
- `report/main.tex`：LaTeX 源文件；
- `code/`：完整程序、测试、结果 JSON 和图片；
- 根目录 `README.md` 与 `实验要求.txt`。

提交前需要在报告封面补充姓名、学号和班级。
