# 上游源码工作树

实验脚本预期本目录下存在以下六个工作树：

```text
pr1257_before/
pr1257_after/
pr1446_before/
pr1446_after/
pr1058_before/
pr1058_after/
```

可从 `bitcoin-core/secp256k1` 仓库按下列提交创建：

| 案例 | 修改前提交 | 修改后提交 |
|---|---|---|
| PR #1257 | `464a9115b4ed` | `4a496a36fb07` |
| PR #1446 | `07687e811d1c` | `10e6d29b60c3` |
| PR #1058 | `d8311688bd38` | `da515074e3eb` |

示例（在项目根目录执行）：

```powershell
git clone https://github.com/bitcoin-core/secp256k1.git .\data\repo\source
git -C .\data\repo\source worktree add ..\pr1257_before 464a9115b4ed
git -C .\data\repo\source worktree add ..\pr1257_after 4a496a36fb07
git -C .\data\repo\source worktree add ..\pr1446_before 07687e811d1c
git -C .\data\repo\source worktree add ..\pr1446_after 10e6d29b60c3
git -C .\data\repo\source worktree add ..\pr1058_before d8311688bd38
git -C .\data\repo\source worktree add ..\pr1058_after da515074e3eb
```

`source/` 与六个工作树属于本地复现资源，已由根目录 `.gitignore`
排除，不需要提交。
