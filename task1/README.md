# 作业一：Bitcoin 测试网络交易、逐位解析与完整区块审计

本目录是《网络安全创新创业实践》课程作业一的完整交付。项目在 Bitcoin Testnet4 上真实构造并广播测试交易，同时使用自行实现的协议与密码学代码，对原始交易和完整区块进行逐字节、逐字段和逐位审计。目录中包含源代码、测试网络钱包、链上广播证据、原始数据、解析结果、可视化图片、自动化测试，以及完整中文 LaTeX 报告。

> 安全提示：`data/` 中的 JSON 文件包含测试网络私钥。它们只可用于 Bitcoin 测试网络，不能用于主网，不能接收真实 BTC，也不应作为任何生产钱包的密钥材料。项目中的测试网络密钥已经随作业文件公开，不再具有保密性。

## 1. 原始作业要求

课程截图中的 Project 原文为：

> **Project: send a tx on Bitcoin testnet, and parse the tx data down to every bit && parse a whole block, try to calc each byte with script.**

本项目将该要求严格化为以下五项可验收目标：

1. 在公开 Bitcoin 测试网络上构造并广播至少一笔真实交易，保存 raw transaction、本地 txid、节点返回 txid、广播时间和浏览器链接；
2. 不依赖区块浏览器的解码结果，自行从原始字节反序列化交易，并为每个字节给出十六进制值、8 位二进制值和所属协议字段；
3. 从 80 字节区块头开始完整解析一个区块，覆盖区块中的全部交易，重算区块哈希、难度目标、工作量证明和 Merkle 根；
4. 对实验涉及的锁定与解锁条件执行 Script 审计，覆盖 `P2WSH(SHA256(OP_TRUE))` 和 `P2WPKH` 两条路径；
5. 提供完整源代码、自动化测试、链上证据、运行结果、可视化图片和中文实验报告，使结论可复现、可审计。

这里的“逐位解析”不是把整段数据简单转换成二进制字符串，而是先严格确定每个协议字段的字节边界，再把每个字节展开为 8 位，并将字节偏移、十六进制、二进制和字段名逐行对应。

## 2. 完成情况概览

本作业完成了两笔相互关联的 Testnet4 交易：

1. **启动资金交易（父交易）**：花费 5 个链上锁定条件明确为 `P2WSH(OP_TRUE)` 的公开教学 UTXO，将总计 `1650 sat` 合并为课程发送钱包的 `1000 sat` P2WPKH 输出，并支付 `650 sat` 手续费；
2. **课程签名交易（子交易）**：由课程测试钱包使用自己的 secp256k1 私钥，按 BIP143 构造签名摘要，使用 RFC 6979 确定性 nonce 和 low-S ECDSA 签名，将 `400 sat` 发送到接收地址，产生 `318 sat` 找零并支付 `282 sat` 手续费。

主要验收结论如下：

| 验收项目 | 结果 |
| --- | --- |
| 父交易广播 | 节点返回 txid 与本地重算 txid 完全一致 |
| 父交易确认状态 | 已在 Testnet4 高度 `144878` 确认 |
| 子交易广播 | 节点返回 txid 与本地重算 txid 完全一致 |
| 子交易最终采样状态 | mempool 已接受，保存证据时尚未确认 |
| 课程签名交易解析 | `223/223` 字节全部映射，无遗漏、无重叠 |
| 完整区块解析 | `4045/4045` 字节全部映射，共 14 笔交易 |
| P2WSH Script | 5/5 个 `OP_TRUE` 输入均满足 witness program 且 CleanStack 为真 |
| P2WPKH Script | BIP143、DER、ECDSA、low-S、HASH160 与 CleanStack 全部通过 |
| Merkle 根 | 区块头值与独立重算值一致 |
| 工作量证明 | 独立重算区块哈希满足 `hash <= target` |
| 回归测试 | 6/6 项通过 |

此外，项目还保存了一笔已确认的默认 Signet P2WPKH 交易及其完整区块，作为跨网络回归样本。该样本区块大小为 `74123 B`，包含 41 笔交易，字节覆盖、Merkle 根和 PoW 验证均通过。

## 3. 关键链上标识

### 3.1 课程地址

| 用途 | Testnet4 地址 |
| --- | --- |
| 发送与找零地址 | `tb1qw0mgkymm78hd270asxdcvhlucfhjw72t4ajxge` |
| 接收地址 | `tb1qkts77kng6xv0rxldrjjfctk5jmf5nx3ltsndlw` |
| 公开 P2WSH(OP_TRUE) 地址 | `tb1qft5p2uhsdcdc3l2ua4ap5qqfg4pjaqlp250x7us7a8qqhrxrxfsqaqh7jw` |

这些地址均属于测试网络。`tb1...` 前缀本身不能区分 Testnet4、默认 Signet 和 Mutinynet，使用时必须同时核对钱包 JSON 中的 `network` 字段和所连接的 API。

### 3.2 父交易：P2WSH(OP_TRUE) 合并

| 项目 | 值 |
| --- | --- |
| txid | `4aa330ae4ecf52c82f38d22149b2b7da79f928e1cdad47bb33b553c093a25f7a` |
| wtxid | `7ea8089a0b477ef55a2d1ae80bd24f2025ef6020b1207e224177e9ff52f8b9b7` |
| 输入 | 5 个 `330 sat` 的 P2WSH(OP_TRUE) UTXO |
| 输出 | 1 个 `1000 sat` 的 P2WPKH 输出 |
| 手续费 | `650 sat` |
| 总大小 | `263 B` |
| stripped size | `246 B` |
| weight | `1001 WU` |
| vsize | `251 vB` |
| 实际费率 | 约 `2.590 sat/vB` |
| 确认区块高度 | `144878` |
| 确认区块哈希 | `0000000000b9d2773b283332f6e1c36da7fdd7b11af12fa7f14866e0beb425ca` |

浏览器地址：<https://mempool.space/testnet4/tx/4aa330ae4ecf52c82f38d22149b2b7da79f928e1cdad47bb33b553c093a25f7a>

该交易不使用任何第三方私钥。其 witness script 只有一个字节 `0x51`，即 `OP_TRUE`：

```text
SHA256(51)
= 4ae81572f06e1b88fd5ced7a1a000945432e83e1551e6f721ee9c00b8cc33260
```

该结果与被花费输出的 v0 P2WSH witness program 一致，因此把 `51` 作为 witness script 就是链上锁定条件公开允许的完整解锁方式。程序仍会逐输入校验 witness program，并确认最终栈为真且满足 CleanStack。

### 3.3 子交易：P2WPKH ECDSA 签名

| 项目 | 值 |
| --- | --- |
| txid | `ad00f80a9c85264ebf3ca4299d61cca06efba0487223d4e6caa9d9e58e9ac105` |
| wtxid | `56508ced1dc61e19699ce54b23728fbf076b95bb737ead63074926bde6661825` |
| 输入 | 父交易 `vout=0`，金额 `1000 sat` |
| 接收输出 | `400 sat` |
| 找零输出 | `318 sat` |
| 手续费 | `282 sat` |
| 总大小 | `223 B` |
| stripped size | `113 B` |
| weight | `562 WU` |
| vsize | `141 vB` |
| 费率 | `2 sat/vB` |

浏览器地址：<https://mempool.space/testnet4/tx/ad00f80a9c85264ebf3ca4299d61cca06efba0487223d4e6caa9d9e58e9ac105>

保存的广播证据表明，本地重算 txid 与节点返回 txid 完全一致。最终采样时该交易仍未确认，所以“发送交易”和“解析完整区块”使用了两个明确区分的对象：交易部分解析该子交易；完整区块部分解析已确认父交易所在的高度 144878 区块。README 和报告均不把未确认交易描述为已确认。

## 4. 技术路线

### 4.1 协议层

核心解析器未使用第三方 Bitcoin SDK，主要实现包括：

- CompactSize 整数的编码、解码与最短编码检查；
- 小端字段、哈希显示顺序和交易 outpoint 处理；
- Legacy 与 SegWit 交易反序列化、重序列化；
- txid、wtxid、stripped size、weight 和 virtual size 计算；
- 80 字节区块头解析、交易计数和整块交易遍历；
- 紧凑难度 `nBits` 到 256 位目标值的转换；
- 区块哈希、Merkle 根和 PoW 条件重算；
- Bech32 v0 SegWit 地址编码与解码；
- P2WPKH 和本实验特定 P2WSH(OP_TRUE) 的锁定条件验证。

### 4.2 密码学层

`bitcoin_codec.py` 使用 Python 整数和标准库哈希函数实现：

- secp256k1 椭圆曲线点加与标量乘；
- 压缩公钥编码与解码；
- RFC 6979 确定性 nonce；
- ECDSA 签名与验签；
- low-S 规范化；
- DER 签名编码与严格解码；
- SHA-256、double-SHA-256 和 HASH160；
- BIP143 `SIGHASH_ALL` 签名原像及中间哈希。

这些实现用于课程审计和教学验证，不是经过侧信道加固、形式验证或生产审计的钱包密码库。

### 4.3 字节覆盖不变量

解析过程中，每个协议字段都会生成一个半开区间 `Span(start, end, name, value)`。输出逐位表之前，程序执行三项强制检查：

1. 每个 Span 必须完全位于原始字节数组范围内；
2. 任意两个 Span 不得覆盖同一个字节；
3. 最终不得存在 `UNCLAIMED` 字节。

因此，单独检查字段长度之和等于原始长度还不够；项目同时排除了“字段重叠刚好抵消字段遗漏”的情况。交易和区块只有在所有字节都恰好属于一个协议字段时，才会生成最终逐位文件。

### 4.4 Script 验证范围

本项目不是通用 Bitcoin Script 虚拟机，而是针对作业真实交易实现并审计两条明确路径：

- **P2WPKH**：验证 witness 公钥 HASH160、BIP143 摘要、DER 编码、ECDSA 签名、low-S 和最终 CleanStack；
- **P2WSH(OP_TRUE)**：验证 `SHA256(witnessScript)` 与 witness program 一致，执行 `OP_TRUE` 并检查最终 CleanStack。

未实现 Taproot/Tapscript、任意 Script 控制流、完整共识 flag 集或 mempool policy 仿真。

## 5. 项目目录

```text
task1/
|-- README.md                         # 本文件：作业总览、复现与验收说明
|-- code/                             # 所有 Python 源代码
|   |-- README.md                     # 代码目录快速入口
|   |-- requirements.txt              # 可视化与截图工具依赖
|   |-- bitcoin_codec.py              # Bitcoin 协议、密码学和 Script 核心
|   |-- wallet_tool.py                # 测试网钱包、UTXO、签名交易与广播
|   |-- claim_op_true_utxos.py        # P2WSH(OP_TRUE) 教学 UTXO 合并工具
|   |-- chain_analyzer.py             # 交易和完整区块下载、解析与审计
|   |-- test_bitcoin_codec.py         # 6 项确定性回归测试
|   |-- visualize_results.py          # 从 JSON/CSV 生成三张报告图
|   `-- capture_evidence.py           # 可选的区块浏览器截图工具
|-- data/                             # 测试网络钱包 JSON，包含已公开测试私钥
|-- output/                           # 广播证据、raw 数据、逐位表和可视化结果
|   |-- testnet4_op_true_funding.json
|   |-- testnet4_signed_broadcast.json
|   |-- testnet4_funding_analysis/
|   |-- testnet4_signed_analysis/
|   |-- sample_confirmed/
|   `-- figures/
|-- report/
|   |-- main.tex                      # 中文 LaTeX 报告源码
|   |-- main.pdf                      # 编译后的最终报告
|   `-- figures/                      # 题目截图裁剪等报告本地图片
`-- 作业要求/                          # 课程原始题目截图
```

`report/` 中的 `.aux`、`.log`、`.out` 和 `.toc` 是 XeLaTeX 编译辅助文件；`report/tmp/` 只用于 PDF 视觉检查，不属于核心提交内容。

## 6. 源代码文件说明

### 6.1 `code/bitcoin_codec.py`

这是项目的核心模块，所有关键协议与密码学计算均在此实现。主要职责包括：

- secp256k1 参数、点运算、公钥编解码；
- RFC 6979、ECDSA、low-S 和 DER；
- Base58Check、Bech32 与 SegWit v0 地址；
- CompactSize 和安全字节读取器；
- `Transaction`、`TxInput`、`TxOutput`、`Block` 数据结构；
- 交易/区块序列化和反序列化；
- txid、wtxid、Merkle 根、目标值和 PoW；
- BIP143 签名摘要；
- P2WPKH 与 P2WSH(OP_TRUE) 验证轨迹。

### 6.2 `code/wallet_tool.py`

提供三个子命令：

| 子命令 | 作用 | 是否访问网络 | 是否可能广播 |
| --- | --- | --- | --- |
| `new` | 创建测试网络钱包 JSON | 否 | 否 |
| `status` | 查询钱包地址的 UTXO | 是 | 否 |
| `send` | 构造并签名 P2WPKH 交易 | 是 | 只有提供 `--broadcast` 才广播 |

工具支持 `mutinynet`、`signet`、`testnet` 和 `testnet4`。网络请求优先调用系统 `curl`，不可用时回退到 Python `urllib`；两条路径均设置超时和重试。

### 6.3 `code/claim_op_true_utxos.py`

仅面向 Testnet4 上锁定条件明确为 `P2WSH(SHA256(OP_TRUE))` 的公开教学输出。程序会：

1. 计算 `witnessScript=0x51` 对应的 P2WSH 地址；
2. 查询并筛选已确认 UTXO；
3. 以 `0x51` 作为每个输入的 witness script；
4. 将选中金额合并到课程钱包 P2WPKH 地址；
5. 本地计算 txid、wtxid、size、weight、vsize 和费率；
6. 只有显式提供 `--broadcast` 时才向节点提交交易。

该工具不会获取或推测任何第三方私钥，但它仍然是会产生链上状态变化的工具，不能无目的重复执行。

### 6.4 `code/chain_analyzer.py`

该程序负责从 Esplora 兼容 API 获取 raw transaction 和 raw block，并输出完整审计证据。若目标交易已确认，可自动采用交易状态中的区块哈希；若交易未确认，必须显式提供 `--block-hash`，用于完成“解析整个区块”的独立任务。

### 6.5 `code/test_bitcoin_codec.py`

自动化测试覆盖标准曲线向量、签名篡改、low-S、DER、Bech32、CompactSize 非最短编码、真实交易往返、P2WPKH、P2WSH(OP_TRUE)、区块 Merkle/PoW 和逐字节行数。

### 6.6 `code/visualize_results.py`

从 `output/testnet4_signed_analysis/` 的 JSON/CSV 读取真实实验数据，生成：

- `transaction_byte_layout.png`：SegWit 交易字节区间布局；
- `script_stack_trace.png`：P2WPKH Script 栈执行轨迹；
- `runtime_validation.png`：txid、BIP143、Script、区块、Merkle 和 PoW 验证汇总。

### 6.7 `code/capture_evidence.py`

可选工具。使用 Playwright 打开 Testnet4 区块浏览器并截取交易页面。它不参与交易构造、签名、解析或正确性判定，因此浏览器页面变化不会影响核心实验结论。

## 7. 运行环境与依赖

本项目已在以下环境完成最终验证：

- Windows 11；
- Python 3.12.9；
- Matplotlib 3.10.7；
- Playwright 1.61.0；
- XeLaTeX；
- Poppler `pdftoppm`（仅用于 PDF 逐页视觉检查）。

核心协议、密码学、钱包、解析器和测试只使用 Python 标准库。第三方包仅用于图片和网页截图：

```powershell
python -m pip install -r code/requirements.txt
```

如需运行浏览器截图工具，还需要安装 Playwright 浏览器；如果本机已有 Microsoft Edge，程序会优先使用固定 Edge 路径：

```powershell
python -m playwright install chromium
```

所有命令均建议在 `task1` 根目录运行，这样 `data/` 和 `output/` 的相对路径与报告保持一致。

## 8. 推荐验收流程

下面的流程不会创建新钱包，也不会广播新交易。

### 8.1 语法检查

```powershell
python -m py_compile `
  code/bitcoin_codec.py `
  code/wallet_tool.py `
  code/claim_op_true_utxos.py `
  code/chain_analyzer.py `
  code/test_bitcoin_codec.py `
  code/visualize_results.py `
  code/capture_evidence.py
```

### 8.2 自动化测试

```powershell
python -m unittest discover -s code -p "test_*.py" -v
```

预期结果：

```text
Ran 6 tests
OK
```

### 8.3 重新生成可视化

```powershell
python code/visualize_results.py
```

该命令只读取现有 JSON/CSV 并覆盖 `output/figures/` 中的三张结果图，不访问网络、不签名、不广播。

### 8.4 重新编译报告

```powershell
cd report
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
cd ..
```

运行两遍用于稳定目录、引用和页码。最终报告入口为 `report/main.pdf`。

## 9. 钱包与交易工具使用方法

本节命令会读写 `data/` 或访问测试网络。任何带 `--broadcast` 的命令都会尝试改变测试网络链上状态，复核既有作业时不需要重复广播。

### 9.1 查看帮助

```powershell
python code/wallet_tool.py --help
python code/wallet_tool.py new --help
python code/wallet_tool.py status --help
python code/wallet_tool.py send --help
python code/claim_op_true_utxos.py --help
python code/chain_analyzer.py --help
```

### 9.2 新建测试钱包

```powershell
python code/wallet_tool.py new `
  --network testnet4 `
  --wallet data/my_testnet4_wallet.json
```

程序使用操作系统随机源生成 32 字节候选私钥，并拒绝覆盖已存在的钱包文件。输出 JSON 包含私钥和测试网 WIF，必须按敏感文件对待。

### 9.3 查询 UTXO

```powershell
python code/wallet_tool.py status `
  --wallet data/testnet4_sender_wallet.json
```

该命令只查询网络，不构造或广播交易。

### 9.4 构造交易但不广播

```powershell
python code/wallet_tool.py send `
  --wallet data/testnet4_sender_wallet.json `
  --destination tb1qkts77kng6xv0rxldrjjfctk5jmf5nx3ltsndlw `
  --amount 400 `
  --fee-rate 2 `
  --output output/local_unsigned_broadcast_evidence.json
```

尽管文件名可自定义，程序生成的交易实际上已经在本地完成签名；“不广播”是指没有向节点 POST raw transaction。只有添加 `--broadcast` 才会提交交易。

### 9.5 广播开关

```text
--broadcast
```

该参数必须显式提供。广播后程序还会验证节点返回 txid 是否与本地 txid 完全一致；不一致时立即报错，不会写成成功证据。

`--allow-unconfirmed` 允许选择未确认 UTXO，只适合明确理解父子交易关系的测试场景。正常情况下应优先花费已确认 UTXO。

## 10. 交易与区块分析方法

### 10.1 分析已确认交易及其所在区块

```powershell
python code/chain_analyzer.py `
  --network testnet4 `
  --txid 4aa330ae4ecf52c82f38d22149b2b7da79f928e1cdad47bb33b553c093a25f7a `
  --output output/recheck_funding
```

交易已确认时，程序会从 API 状态中读取其区块哈希。

### 10.2 分析未确认交易并指定一个完整区块

```powershell
python code/chain_analyzer.py `
  --network testnet4 `
  --txid ad00f80a9c85264ebf3ca4299d61cca06efba0487223d4e6caa9d9e58e9ac105 `
  --block-hash 0000000000b9d2773b283332f6e1c36da7fdd7b11af12fa7f14866e0beb425ca `
  --output output/recheck_signed
```

这里显式指定的是已确认父交易所在区块，用于完成全区块解析；它不表示未确认子交易位于该区块中。

### 10.3 支持的网络名称

| `--network` 值 | API 根地址 | 说明 |
| --- | --- | --- |
| `testnet4` | `https://mempool.space/testnet4/api` | 本作业最终链上实验使用 |
| `signet` | `https://mempool.space/signet/api` | 默认 Bitcoin Core Signet |
| `mutinynet` | `https://mutinynet.com/api` | 出块更快的公开 Signet 环境 |
| `testnet` | `https://mempool.space/testnet/api` | 旧测试网接口 |

不同网络的 UTXO 不能互通，即使地址文本都以 `tb1` 开头也不能混用。

## 11. 分析产物说明

每个 `output/*_analysis/` 目录包含以下 10 类文件：

| 文件 | 内容 |
| --- | --- |
| `transaction.raw.hex` | 交易线协议原始字节的连续十六进制表示 |
| `transaction_summary.json` | txid、wtxid、版本、输入输出数、大小、weight、vsize 和状态 |
| `transaction_bits.txt` | 每个交易字节的十进制偏移、十六进制偏移、字节值、8 位二进制和字段名 |
| `transaction_fields.csv` | 交易字段的起止偏移、长度、wire hex 和解释值 |
| `script_audit.json` | BIP143 中间值、签名信息、Script 栈轨迹和最终判定 |
| `block.raw.hex` | 完整区块线协议原始字节 |
| `block_summary.json` | 区块头、目标值、Merkle 根、PoW、交易数和字节覆盖结论 |
| `block_bits.txt` | 完整区块每个字节的 8 位展开和字段归属 |
| `block_fields.csv` | 完整区块字段边界和解释值 |
| `block_transaction_index.csv` | 区块内每笔交易的 txid、wtxid、size、weight 和 vsize |

关键目录用途：

- `output/testnet4_funding_analysis/`：已确认父交易及其所在完整区块；
- `output/testnet4_signed_analysis/`：课程 P2WPKH 子交易与指定完整区块的审计；
- `output/sample_confirmed/`：默认 Signet 已确认交易和 74123 B 区块回归样本；
- `output/figures/`：由真实 JSON/CSV 生成的报告图片。

## 12. 自动化测试覆盖

`code/test_bitcoin_codec.py` 包含 6 项测试：

1. **secp256k1 与 ECDSA**：标量 1 必须得到标准压缩生成点公钥；签名必须为 low-S；原消息验签成功，篡改消息验签失败；DER 必须可逆；
2. **Bech32 往返**：已知 witness program 必须编码为标准 `tb1q...` 地址并正确解码；
3. **CompactSize 规范性**：非最短编码必须被拒绝；
4. **真实已确认交易**：原始交易必须完整消费并可无损重序列化，txid/wtxid 必须匹配，P2WPKH Script 必须通过；
5. **完整区块与字节覆盖**：区块哈希、Merkle 根和 PoW 必须通过，交易数必须正确，逐位表必须恰有“原始字节数 + 表头”行；
6. **P2WSH(OP_TRUE)**：witness program 必须匹配，最终栈必须满足 CleanStack。

测试刻意包含失败路径，例如消息被篡改后 ECDSA 必须失败、非最短 CompactSize 必须抛出异常，避免只验证正常输入。

## 13. 安全边界与使用限制

### 13.1 私钥边界

- `data/*.json` 中的 `private_key_hex` 和测试网 WIF 均为私钥；
- 这些文件已经作为课程交付公开，不能再用于任何需要保密的场景；
- 禁止向其中任何地址发送主网 BTC；
- 不要把本项目钱包格式直接用于生产系统。

### 13.2 广播边界

- `wallet_tool.py send` 默认只构造和保存，不广播；
- `claim_op_true_utxos.py` 默认只构造和保存，不广播；
- 只有显式添加 `--broadcast` 才会向测试网络提交交易；
- 教师验收已有结果时只需读取 `output/`，不需要重复广播。

### 13.3 实现边界

- 椭圆曲线代码以正确性和可读性为目标，未实现常数时间、防故障或侧信道保护；
- Script 解释器只覆盖本作业实际使用的 P2WPKH 和 P2WSH(OP_TRUE)；
- API 返回仅作为原始数据来源和广播通道，密码学结论由本地代码独立重算；
- 网络服务可能限流、超时或改变页面结构，但既有 `output/` 足以离线复核主要结论；
- 未确认状态是时间相关事实，重新查询时可能变化，README 保留的是报告最终采样时的状态。

## 14. 报告说明

完整报告位于：

- LaTeX 源码：`report/main.tex`；
- 最终 PDF：`report/main.pdf`。

报告包含：

- 原始作业截图与严格化验收目标；
- UTXO、SegWit、Bech32、BIP143、ECDSA、区块头、难度目标和 Merkle 树理论；
- 父交易和子交易的真实广播证据；
- 课程签名交易的字段级与逐字节解析；
- BIP143 中间值和 P2WPKH/P2WSH Script 栈轨迹；
- 完整区块、Merkle 根和 PoW 验证；
- 测试、局限、结果文件索引和核心源代码附录。

重构后，报告源码附录从 `../code/` 读取实际 Python 文件，报告图片从 `../output/figures/` 读取，因此报告与当前目录结构保持一致。

## 15. 常见问题

### 15.1 测试提示找不到 `sample_confirmed`

请从 `task1` 根目录执行测试。测试代码会根据自身位置定位项目根目录下的 `output/sample_confirmed/`。如果该目录确实被删除，与真实链上样本有关的两项测试会跳过；完整提交中已提供该目录，不应出现跳过。

### 15.2 `ModuleNotFoundError: bitcoin_codec`

请使用 README 给出的命令，例如：

```powershell
python code/wallet_tool.py --help
python -m unittest discover -s code -p "test_*.py" -v
```

不要在项目根目录直接执行 `python -m code.wallet_tool`，当前代码按可直接运行脚本组织，并未声明为安装式 Python 包。

### 15.3 网络 API 超时

程序会自动重试 3 次。仍失败时可以稍后重试或检查当前网络。自动化测试、既有 JSON/CSV、逐位表、可视化和报告编译均可离线完成。

### 15.4 交易未确认，无法自动确定区块

对未确认交易运行 `chain_analyzer.py` 时应提供 `--block-hash`。该区块是“完整区块解析”任务的对象，不代表未确认交易属于该区块。

### 15.5 Playwright 找不到浏览器

执行：

```powershell
python -m playwright install chromium
```

或者确认 Microsoft Edge 位于代码中配置的路径。截图工具是可选项，不影响核心结果。

## 16. 提交清单

建议提交以下内容：

- `README.md`：作业总说明；
- `code/`：全部源代码与依赖清单；
- `data/`：复现实验所需的测试网钱包数据；
- `output/`：广播、原始数据、逐位解析、Script、区块验证和图片证据；
- `report/main.tex`：LaTeX 报告源码；
- `report/main.pdf`：最终报告；
- `作业要求/`：课程原始题目截图。

提交前应完成以下检查：

- [ ] 报告封面姓名、学号和班级已填写；
- [ ] `python -m unittest discover -s code -p "test_*.py" -v` 显示 6 项测试全部通过；
- [ ] `report/main.pdf` 能正常打开，目录、图片、表格和源码附录完整；
- [ ] `output/` 中的两个广播 JSON、三个分析目录和三张可视化图片存在；
- [ ] 已明确说明 `data/` 仅含公开的测试网络密钥；
- [ ] 未向任何测试地址发送主网 BTC。

## 17. 主要规范与资料

- BIP 141：Segregated Witness，共识层结构、wtxid 与 weight；
- BIP 143：SegWit v0 的交易签名验证摘要；
- BIP 173：原生 SegWit v0 的 Bech32 地址；
- BIP 94：Bitcoin Testnet4；
- RFC 6979：确定性 DSA/ECDSA nonce；
- SEC 2：secp256k1 曲线参数；
- Bitcoin Developer Reference：交易、区块与 Script 数据结构；
- mempool/Esplora API：测试网络原始交易、区块和广播接口。

更完整的理论推导、引用信息和访问日期见 `report/main.pdf` 的参考文献部分。
