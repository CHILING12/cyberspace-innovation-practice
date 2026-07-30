# 作业 5：TenSEAL CKKS 密文卷积

本目录实现单输入、单输出的 `4x4` 输入与 `3x3` 卷积核密文卷积，步长为 1、无填充，输出为 `2x2`。

程序分为客户端和服务器两部分：

- 客户端上下文持有 CKKS 私钥，负责输入加密和结果解密；
- 服务器只获得不含私钥的公开评估上下文、密文输入和明文卷积核；
- 服务器使用 TenSEAL 的 `im2col_encoding` 和 `conv2d_im2col` 完成密文线性乘加；
- 使用普通卷积结果、误差阈值、密钥隔离和密文随机性检查实验结果。

## 运行

```powershell
python -m pip install -r requirements.txt
python fhe_convolution.py --trials 10 --output output/experiment_results.json
python -m unittest -v
python visualize_results.py
```

实验使用 CKKS 参数 `N=8192`、系数模数位长链 `[60, 40, 40, 60]`、全局缩放因子 `2^40`。测试中的误差阈值为 `1e-3`。
