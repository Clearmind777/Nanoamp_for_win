# 工作报告 28：安装器把 `uninstall.exe` 放进安装目录（自删除）

- 日期：2026-09-27
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.27.md`（GUI 七项优化 + 注释页卡死修复，提交 `5ccd6a8`）
- 本轮委托：**"`uninstall.exe` 是 `install.exe` 生成的，还是本身就有的？"** →
  说明它本来就随包发布 → 使用者确认："**希望安装完把 `uninstall.exe` 一起放进安装目录**"，
  并明确 **不建开始菜单项**。
- 本轮提交：见 §6（已推送）

---

## 1. 起点：它本来就是随包发布的独立程序

清点结论（上一轮汇报 + 本轮再次核对）：

- `release/install.exe`、`release/uninstall.exe` 是两个**互相独立**的 PyInstaller 产物
  （`build_exe.py` 里 `install.spec` → install.exe、`uninstall.spec` → uninstall.exe），
  两个都进 setup 资产（`build_assets.py` 的 `SETUP_ITEMS`）；
- `install.exe` **不生成、也不复制** uninstall.exe（`install_nanoamp.py` 里 "uninstall"
  只出现在注释里）；实测安装树里原来没有 `uninstall.exe`；
- 于是以前卸载必须留着解压出来的安装包 —— 这正是本轮要消除的约束。

## 2. 改法

### 2.1 安装器（`install_nanoamp.py`）

- 新增 `Context.uninstaller_exe`（安装包里的 `uninstall.exe`）；
- 新增安装步骤 **"放入卸载程序…"**（第 6/7 步，插在桌面快捷方式与自检之间），
  把 `uninstall.exe` 复制到 `<安装目录>\uninstall.exe`（沿用 `copy_with_retry`，
  文件被占用会重试）；安装包里没有该文件时只记警告、不中断安装；
- 安装日志里有一行 `已放置卸载程序 -> …`，另有提示"卸载时双击它即可；它删完安装目录
  最后会把自己也删掉"。

### 2.2 卸载器（`uninstall_nanoamp.py`）

难点：卸载器现在**住在要被删除的目录里**，而 Windows 不允许删除正在运行的程序。
处理方式：

1. `_running_exe()` / `_inside()`：判断"正在运行的这个 exe 是否在安装目录内"
   （比较时统一 `resolve()` + 大小写归一 + 去掉结尾分隔符，避免 Windows 的 8.3 短名/
   大小写差异导致误判 —— 这里判错就等于删自己）；
2. `_remove_tree_skipping(root, skip)`：**跳过**正在运行的 exe（不是"删失败再跳过"，
   而是根本不碰它），其余文件与目录立刻删掉；真被别的进程占用时依旧抛错、不静默放过；
3. `_schedule_final_cleanup(exe, root)`：写一个纯 ASCII 的 `%TEMP%\nanoamp_finish_uninstall_<pid>.cmd`，
   用**分离进程**启动（`DETACHED_PROCESS`），脚本**循环重试 `del`**，成功后
   `rmdir` 空目录并删除脚本自身；路径作为参数传入，所以路径里有空格、`&`、中文都不需要
   拼进批处理文本；
4. 日志会写清楚：`本程序就在该目录里（uninstall.exe），最后一个文件会在本窗口关闭后自动
   删除。` / `已安排在本窗口关闭后删除最后的 uninstall.exe 与空目录。`
   （`freed` 统计里扣掉了这个稍后才消失的文件大小）

> 第一版脚本写的是"等文件消失再删"，那等于永远等不到（文件正是被自己占着）——
> 端到端验证时发现安装目录留下一个 `uninstall.exe` 与一个残留脚本，改成"循环重试删除"
> 后一次通过。这个坑已由单元测试锁住（见 §4 第 4 项：先占住文件 2 秒再放开，helper
> 必须在 25 秒内完成）。

### 2.3 让装进安装目录的那一份真正可用（`nanoamp_common.py`）

`config_candidates()` 现在**优先读"正在运行的程序旁边的 `config.ini`"**，然后才是指针文件
与默认位置。这样即使 `%LOCALAPPDATA%\nanoamp.path` 记录丢失，双击安装目录里的
`uninstall.exe` 依然知道自己该删哪个目录（安装目录里就有 `config.ini`）。
安装包里的那一份旁边没有 `config.ini`，行为与以前完全一致。

## 3. 文档

- `release/README.md`（会进 setup 资产）：目录结构里注明"安装时会被复制进安装目录"；
  安装步骤表新增第 7 步；安装后的目录清单里加入 `uninstall.exe`；「卸载」一节说明
  两个副本都能用、自删除的 1–2 秒过程、以及 config.ini 优先规则；
- 根 `README.md` §7「卸载」、`README-CN.md`、`00_materials/tutorial.md` 同步改写为
  "双击安装目录里的 `uninstall.exe`"。

## 4. 验证

| 验证 | 结果 |
|---|---|
| 新增 `release/_installer/test_uninstaller_selfdelete.py` | 全通过：① 程序旁的 `config.ini` 排在候选首位、且 `find_existing_install()` 因此解析到自己那份安装；② `_inside()` 对根目录/子目录/无关路径/未冻结进程的判断；③ `_remove_tree_skipping()` 保留正在运行的 exe、删掉其余内容、目录暂时留下；被别的进程占用时**抛错**而不是放过；④ 分离 helper：文件被占住 2 秒后放开，helper 在 25 秒内删掉目录并自删 |
| 安装器自测 9 + 1 个脚本 | 全部通过（含新脚本；`test_release_layout.py` 仍确认资产结构） |
| 端到端（`tmp/verify_round28_uninstall.ps1`，用重建后的资产） | 解压 setup + 离线依赖 → 静默安装（`--no-path --no-shortcut`、非默认位置）：安装 exit 0，`<安装目录>\uninstall.exe` 存在，目录清单为 `app, bin, config, configs, R, config.ini, uninstall.exe`；安装包里那份 `uninstall.exe --dry-run` 仍能正确识别安装（`安装目录 … (366 MB)`）；随后**双击安装目录里那份** `--silent`：exit 0，日志显示"安装目录内容已删除（第 1 次尝试）"+"已安排…自删除"，**整个安装目录（含 uninstall.exe）在数秒内消失**，`config.ini` 与位置指针一并清理，`%TEMP%` 里没有残留脚本 |
| 发布产物 | 重建 `install.exe`（11.4 MB）、`uninstall.exe`（10.8 MB）、两个 zip；setup 包 sha256 `e2826ff9…`，离线包 `2db72289…`（逐字节一致）；`build_assets.py` 逐条校验 18 / 113 个条目 |
| 文档/编码 | 改动文档 UTF-8 无 BOM、无替换字符；全树 209 个文本文件无乱码；窗口示意图未变（审计 0 处错位） |

## 5. 本轮顺带确认的行为

- 卸载器**不会**把自己当普通进程杀掉：`_stop_running_background_processes()` 只按
  `nanoamp*` 前缀且镜像路径在安装目录内匹配，`uninstall.exe` 不在其中；
- `--dry-run` 仍然只报告不删除（验证里用过）；
- `uninstall.exe` 依旧可以单独拷走使用（不依赖 `_offline/`、不依赖安装包）。

## 5b. 补修：自删除 helper 会弹出可见控制台窗口（使用者报告）

使用者反馈："刚刚你在工作时，不停弹出 `ping 127.0.0.1` 的终端弹窗"。原因就在本轮的
helper 上：

- 我用 `ping -n 2 127.0.0.1 >nul` 做延时（在批处理里这是最省事、最通用的等待），
  每次循环都会**启动一个 ping 进程**；
- 启动 helper 时我同时给了 `CREATE_NO_WINDOW | DETACHED_PROCESS`。这两个标志是冲突的：
  `DETACHED_PROCESS` 使子进程**不继承父进程的控制台**，于是 Windows 给它**新建**一个
  控制台并显示出来 —— cmd 与它派生的 ping 因此每次都在屏幕上闪一个窗口。
  （`CREATE_NO_WINDOW` 的本意是"创建但不显示控制台"，被 DETACHED_PROCESS 覆盖了。）

修法：

1. **去掉 `DETACHED_PROCESS`**（helper 本来就不需要它：它是独立进程，父进程退出后照样
   继续跑），保留 `CREATE_NO_WINDOW`，并额外传 `STARTUPINFO`（`STARTF_USESHOWWINDOW` +
   `SW_HIDE`）双保险；延时仍用 `ping`（现在跑在隐藏控制台里），重试次数由 120 降为 60；
2. 新增自测 **第 5 节**（`test_uninstaller_selfdelete.py`）：
   - 用假的 `Popen` 断言启动参数里**有** `CREATE_NO_WINDOW`、**没有** `DETACHED_PROCESS`，
     且有隐藏窗口的 startupinfo；
   - 再用 `EnumWindows` + `tasklist` **实测**：helper 运行期间，`cmd.exe` / `ping.exe`
     拥有的可见顶层窗口数为 **0**；
3. 端到端脚本 `tmp/verify_round28_uninstall.ps1` 也加了同样的实测：卸载过程中轮询
   `Get-Process cmd,ping | Where MainWindowHandle -ne 0`，本次结果 `(none)`。

> 结论：`ping` 弹窗是我这边引入的临时问题（只出现在卸载的最后一步），不是 Windows 或
> 使用者环境的问题；修好后既不再有窗口，也不改变删除行为（安装目录、`uninstall.exe`、
> `config.ini`、位置指针照旧全部清理干净）。

## 6. 提交与推送

- 代码：`release/_installer/install_nanoamp.py`、`release/_installer/uninstall_nanoamp.py`、
  `release/_installer/nanoamp_common.py`、新增 `release/_installer/test_uninstaller_selfdelete.py`；
- 文档：`release/README.md`、`release/RELEASE_NOTES-0.1.5.md`、`README.md`、`README-CN.md`、
  `00_materials/tutorial.md`、本报告与索引；
- 产物：`release/install.exe`、`release/uninstall.exe`、`release/_build/SHA256SUMS.txt`
  （setup 包最终 sha256 `5b273c03…`：去 `DETACHED_PROCESS` 后又重建了一次 uninstall.exe）；
- **Release 仍未上传**：仓库里的 setup 包与已发布的 v0.1.5 同名但内容不同，要发布请新建
  tag（例如 v0.1.6）。

## 7. 仍未做

1. `D:\tools\R\lib`（nanoamp + 109 个包）未恢复 → `test_e2e`、`test_failure_reporting` 仍无法复跑；
2. 上游回灌（Linux 仓库的 L1–L13）；
3. 真机压力用例：C4 磁盘满、C9 ARM64、E2 高 DPI 截图；
4. GUI 大表虚拟化/分页（P2-2，可选）。
