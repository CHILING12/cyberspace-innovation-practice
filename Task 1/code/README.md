# 作业一代码目录

本目录保存 Task 1 的 Python 程序。任务说明和实验结果见上一级 [`README.md`](../README.md)，详细分析见 `../report/`。

建议从 `task1` 根目录运行程序，使 `data/` 和 `output/` 的相对路径保持一致：

```powershell
python -m pip install -r code/requirements.txt
python -m unittest discover -s code -p "test_*.py" -v
python code/visualize_results.py
```

核心协议、密码学、钱包和分析代码只依赖 Python 标准库；`requirements.txt` 中的 Matplotlib 用于生成图片，Playwright 仅用于可选的区块浏览器截图。

任何带 `--broadcast` 的命令都会尝试向 Bitcoin 测试网络提交交易。查看已有结果不需要重新广播，直接检查上一级 `output/` 即可。
