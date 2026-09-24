# 工作报告 19：安装器复制文件时重试（修掉 WinError 32）

- 日期：2026-09-25
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.18.md`（移除空的 `04_builds\`、重建 R 包 tarball）
- 本轮委托：上一轮报告 §5 提出的问题（安装器复制文件不重试），用户选择「加上重试」

---

## 1. 问题回顾

上一轮重跑验证时，安装**整体失败**：

```text
PermissionError: [WinError 32] 另一个程序正在使用此文件，进程无法访问。
  File install_nanoamp.py, line 1268, in _configure_gui  ->  shutil.copy2
```

两个现实诱因都会造成它：

- PyInstaller 的 onefile 程序会起"引导父进程 + 真正子进程"，**上一个 GUI 还在跑**
  就占着 `<安装目录>\app\nanoamp.exe`；
- 安全软件会**扫描刚写出的 exe**，扫描期间文件同样被占用。

卸载器删文件时本来就有重试（`REMOVE_RETRY_DELAYS`，5 次、递增到 8 秒），
而安装器复制文件是"一次失败就整体失败"——**这是不对称的**。

## 2. 改动

`release/_installer/install_nanoamp.py`：

```python
COPY_RETRY_DELAYS = (0.0, 0.5, 1.0, 2.0, 4.0)      # 与卸载器的删除重试同思路

def copy_with_retry(src, dst, say=None) -> Path:
    """复制文件；被占用时按递增间隔重试，全部失败则给出可操作的报错。"""
```

- 首次立即尝试，之后 0.5s / 1s / 2s / 4s 递增，共 5 次；
- 每次失败都写进安装日志（`第 n/5 次复制未完成（文件被占用）：<文件名>`），
  中途成功也写一行（`第 n 次尝试复制成功 -> <路径>`），用户能看出"卡了一下但装上了"；
- 最终失败时抛出可操作的说明：**请关闭正在运行的 nanoamp 窗口（或暂停安全软件的
  实时扫描）后重新安装**，并带上原始错误。

三处复制全部改用它（此前都是裸 `shutil.copy2`）：

| 位置 | 复制的文件 |
|---|---|
| `_install_cli` | `02_CLI/bin/nanoamp.cmd` → `<安装目录>\bin\nanoamp.cmd` |
| `_install_cli` | minimap2.exe → `<安装目录>\bin\minimap2.exe` |
| `_configure_gui` | 图形界面 nanoamp.exe → `<安装目录>\app\nanoamp.exe`（就是本次报错点） |

## 3. 单元测试：`release/_installer/test_copy_retry.py`（新增）

| 用例 | 检查 |
|---|---|
| 生产用的重试阶梯 | 次数 ≥ 3、间隔递增、首次立即尝试、最后一次等待 ≥ 2 秒（够杀软扫完） |
| 占用几次后释放 | 第 4 次成功；文件**逐字节**落地；日志里有"复制未完成"和"复制成功" |
| 一直占用 | 抛错而不是假装成功；尝试次数 == 5；报错里含处理建议与文件路径 |
| **真实 Windows 共享冲突** | 用 `msvcrt.locking` 锁住目标文件，确认复制**确实被挡住**，解锁后成功 |
| 目标目录不存在 | 自动逐级创建 |

已登记进 `Makefile` 的 `release-test` 与 `release/README.md` 的测试清单。

## 4. 端到端验证：拿锁住的 GUI 文件去装

单测之外，用**重新打包的 install.exe**做了一次真实复现
（`tmp/verify_copy_retry_e2e.ps1` + `tmp/hold_lock.py`）：

1. 在沙箱里预置 `<安装目录>\app\nanoamp.exe`，由另一个进程用 `msvcrt.locking` 锁住；
2. 锁在 `<安装目录>\bin\minimap2.exe` 出现（即 GUI 复制的前一步）后再保持 3 秒才释放；
3. 全程运行 `install.exe --silent`。

结果：

```text
第 1/5 次复制未完成（文件被占用）：nanoamp.exe
第 2/5 次复制未完成（文件被占用）：nanoamp.exe
第 3/5 次复制未完成（文件被占用）：nanoamp.exe
第 4 次尝试复制成功 -> …\target\app\nanoamp.exe
已安装图形界面 -> …\target\app\nanoamp.exe
安装成功。
```

```text
retried while locked : True
recovered afterwards : True
install succeeded    : True
GUI exe replaced     : True  (11278657 vs 11278657 bytes)
E2E OK - the locked file was retried and the install completed
```

**同样的场景在改动前就是上一轮那次整体失败**，所以这条链路现在真的闭合了。

## 5. 顺带修好的验证脚本问题

`tmp/verify_installed_015.ps1` 原来只 `Kill()` 父进程，PyInstaller 的子进程会活着并
锁住 exe（正是上一次失败的根因）。现在改用 `taskkill /PID … /T /F` 杀整棵进程树，
并打印残留进程数——本轮跑完显示 `leftover nanoamp processes: 0`。

（这些是 `tmp/` 下的临时脚本，不进仓库。）

## 6. 回归

- **13 个测试脚本全绿**（安装器 9 + GUI 4，含新增的 `test_copy_retry.py`）；
- 常规联网安装（无 `_offline`）在新资产上重跑：`install exit=0`、`config.ini` 正常、
  109/109 固定版本、`bin\minimap2.exe` 同哈希、`doctor` 通过；
- 安装后的 CLI `nanoamp call` 退出码 0；GUI 跑完 E4-3：12 条单倍型、
  `mapping_rate 0.997717`、`n_reads_total 438`；`app\nanoamp.exe` 启动正常；
- 资产重新打包：setup `b3cec804…` → **`34a89a52…`**（含新的 `install.exe`），
  离线依赖包未变 `2db72289…`。

## 7. 改动的文件

| 文件 | 改动 |
|---|---|
| `release/_installer/install_nanoamp.py` | 新增 `COPY_RETRY_DELAYS`、`copy_with_retry()`；三处复制改用它 |
| `release/_installer/test_copy_retry.py` | 新增测试（5 类用例、15 项断言） |
| `release/install.exe` | 重新构建（同一份源码，行为新增重试） |
| `Makefile` | `release-test` 加入 `test_copy_retry.py` |
| `release/README.md` | 测试清单更新（并区分"卸载重试"与"安装重试"） |
| `release/_build/SHA256SUMS.txt` | 重新生成 |

## 8. 复现

```powershell
# 单元测试
python release\_installer\test_copy_retry.py

# 端到端：锁住目标 GUI 文件再安装
python release\_installer\build_exe.py install
python release\_build\build_assets.py
& tmp\verify_copy_retry_e2e.ps1
```
