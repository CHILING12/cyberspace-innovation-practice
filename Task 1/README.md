# Task 1：Bitcoin 测试网络交易与区块解析

## 任务说明

本实验在 Bitcoin Testnet4 上发送测试交易，并直接从原始字节解析交易和完整区块。程序同时检查 txid、wtxid、Merkle 根、工作量证明和本实验涉及的两类 Script。

原题要求：

> Send a tx on Bitcoin testnet, parse the tx data down to every bit, parse a whole block, and calculate each byte with script.

> `data/` 中是已经公开的测试网密钥，只能用于无价值测试网络，不能用于主网或生产钱包。

## 完成内容

- 构造并广播 Testnet4 交易
- 解析 Legacy、SegWit 交易和完整区块
- 输出每个字节的偏移、十六进制值、二进制值和字段名称
- 计算 txid、wtxid、weight、vsize、Merkle 根和 PoW
- 实现 secp256k1、BIP143、DER、low-S 等计算
- 检查 P2WPKH 和实验使用的 `P2WSH(OP_TRUE)`
- 保存运行数据、测试结果和可视化图片

## 主要结果

| 项目 | 结果 |
| --- | --- |
| P2WSH 合并交易 | 已在 Testnet4 高度 `144878` 确认 |
| P2WPKH 签名交易 | 节点已接受；记录结果时尚未确认 |
| 签名交易解析 | `223/223` 字节完成映射 |
| 完整区块解析 | `4045/4045` 字节完成映射，共 14 笔交易 |
| Script 检查 | P2WSH 5 个输入和 P2WPKH 输入均通过 |
| Merkle 根与 PoW | 重算结果通过 |
| 自动化测试 | 6 项通过 |

交易链接：

- [P2WSH 合并交易](https://mempool.space/testnet4/tx/4aa330ae4ecf52c82f38d22149b2b7da79f928e1cdad47bb33b553c093a25f7a)
- [P2WPKH 签名交易](https://mempool.space/testnet4/tx/ad00f80a9c85264ebf3ca4299d61cca06efba0487223d4e6caa9d9e58e9ac105)

## 文件

```text
Task 1/
├── code/       # 交易、区块、密码学、测试和绘图程序
├── data/       # 测试网钱包数据
├── output/     # 原始数据、解析结果和图片
└── report/
    ├── main.tex
    └── main.pdf
```

主要程序：

- `code/bitcoin_codec.py`：协议解析、密码学和 Script 计算
- `code/wallet_tool.py`：钱包、UTXO、交易构造和广播
- `code/claim_op_true_utxos.py`：合并教学用 P2WSH UTXO
- `code/chain_analyzer.py`：下载并解析交易和区块
- `code/test_bitcoin_codec.py`：自动化测试

## 运行

在本目录执行：

```powershell
python -m pip install -r code/requirements.txt
python -m unittest discover -s code -p "test_*.py" -v
python code/visualize_results.py
```

重新分析已确认交易：

```powershell
python code/chain_analyzer.py `
  --network testnet4 `
  --txid 4aa330ae4ecf52c82f38d22149b2b7da79f928e1cdad47bb33b553c093a25f7a `
  --output output/recheck_funding
```

`wallet_tool.py` 和 `claim_op_true_utxos.py` 默认只构造交易，只有添加 `--broadcast` 才会向测试网络发送。

## 实验报告

- [PDF 报告](report/main.pdf)
- [LaTeX 源文件](report/main.tex)

报告中包含协议与密码学原理、交易构造过程、逐字节解析、区块检查和完整结果。
