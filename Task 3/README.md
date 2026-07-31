# Task 3：对称密码算法的软件实现与优化

## 任务说明

本实验使用 C 语言实现 AES、SM4、GIFT-128 和 TWINE-128，并比较标量、循环展开、T-table 和专用指令等优化方法。在分组密码基础上还实现了 CTR、GCM 和 XTS 三种工作模式。

## 实现内容

| 算法 | 分组长度 | 密钥长度 | 主要版本 |
| --- | ---: | ---: | --- |
| AES | 128 bit | 128/256 bit | 标量、循环展开、T-table、AES-NI |
| SM4 | 128 bit | 128 bit | 标量、循环展开、T-table |
| GIFT-128 | 128 bit | 128 bit | 标量及 SIMD 实验路径 |
| TWINE-128 | 64 bit | 128 bit | 标量及 SIMD 实验路径 |

测试包括标准向量、加解密往返、不同实现的一致性、GCM 标签错误处理和 XTS 边界长度。

## 主要结果

16 MiB 数据下记录的最佳结果：

| 算法 | 版本 | cpb | GB/s |
| --- | --- | ---: | ---: |
| AES-128 | V6（AES-NI） | 1.13 | 2.645 |
| SM4 | V1（循环展开） | 25.01 | 0.120 |
| GIFT-128 | V0（标量） | 1199.27 | 0.003 |
| TWINE-128 | V0（标量） | 502.01 | 0.006 |

本次测试中，AES-NI 的提升最明显；SM4 T-table 与标量版本接近；GCM 的主要开销来自 GHASH，使用 PCLMULQDQ 后有明显改善。24 项正确性测试均通过。

## 文件

```text
Task 3/
├── README.md
├── REPORT.md
├── LICENSE
└── src/
    ├── common.c / common.h
    ├── aes.c / aes.h
    ├── sm4.c / sm4.h
    ├── gift128.c / gift128.h
    ├── twine.c / twine.h
    ├── modes.c / modes.h
    ├── benchmark.c
    └── Makefile
```

## 编译与运行

```bash
make -C src all
make -C src test
make -C src bench
```

需要使用 AES-NI、PCLMULQDQ、AVX2 等路径时，CPU 和编译器必须支持相应指令集。

## 实验报告

[REPORT.md](REPORT.md) 包含算法原理、各优化方法、工作模式实现、性能测试、安全性讨论和参考文献。
