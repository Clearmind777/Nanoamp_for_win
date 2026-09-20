# 工作报告 11：仓库瘦身、目录重排、安装/卸载窗口缺陷修复

> 日期：2026-09-21
> 关联：`work_report.10.md`
> 本轮范围：仓库体积优化；目录重排；用 `01_data` 写 GUI/CLI/R 包三版教程；
> 截图核对安装器与卸载器界面；修掉发现的所有缺陷

---

## 1. 本轮 11 项需求与结果

| # | 需求 | 结果 |
|---|---|---|
| 1 | win 仓库 > 1 GB，优化 | 完成：1.15 GB → 约 0.7 GB |
| 2 | 用 `01_data` 写 GUI/CLI/R 包教程 + 依赖配置 | 完成：新增 `00_materials/tutorial.md`（1297 行） |
| 3 | `02_code/cli`、`02_code/gui` 还有用吗 | 结论：**都有用，保留**（见 §3） |
| 4 | `04_results` → `tmp/test_results` | 完成，脚本与文档全部改完 |
| 5 | `05_builds` → `04_builds` | 完成 |
| 6 | `06_GUI` → `02_code/PythonGUI` | 完成（重命名时踩到一个 Windows 大小写坑，见 §3） |
| 7 | 优化 `03_dependence/` 和 `dist/` | 完成：`dist/` 早已删除；`03_dependence` 只有 1.3 MB，无需处理 |
| 8 | `01_data` 测试数据占位更小 | 完成：受版本控制内容 85 MB → 22 MB |
| 9 | 截图核对安装/卸载界面；测试「文件被占用→重试」 | 完成：**发现 3 个真实缺陷并修掉**（见 §4） |
| 10 | 发现 bug 及时修 | 完成：共修 6 个 |
| 11 | 更新 `README.md` / `README-CN.md` | 完成 |

**回归：** 功能测试 A/B/C 各 56/56 通过，mode A `mean_overlap_rate` 0.9807，
与改动前完全一致；R 单元测试 34 项全过；Python 界面三个测试全过；
安装器四个测试脚本全过。

---

## 2. 仓库瘦身

从 1.15 GB 降到约 0.7 GB（`.git` 0.32 GB + 工作区 0.39 GB）。

### 2.1 删掉构建中间产物（26.5 MB）

`release/_installer/build/` 是 PyInstaller 的中间目录，本来就在 `.gitignore` 里，
但一直留在磁盘上。同样的还有各处 `__pycache__`。

### 2.2 删掉 BAM/BAI（34 MB）

`01_data/test_data` 下的 63 个 `.bam` + `.bai`。理由：

- BAM 只是 `Rsamtools::asBam()` 产生的**中间产物**，不是公司交付内容；
- 链接层 `manifest.tsv` / 各样本 `meta.tsv` 里没有任何一条引用它们；
- 功能回归（A/B/C 各 56 次运行）删掉后仍然全过。

### 2.3 链接层里的副本不再提交（40 MB）

`01_data/ln_test_data` 里 103 个 `.fastq` / `.xlsx` / `.ab1` 与 `test_data/` 下的
原件**逐字节相同**（已用 MD5 全部核对）。它们被排除出版本库：

```bash
Rscript 03_dependence/r-environment/materialize_test_data.R   # clone 后跑一次
```

脚本按 `manifest.tsv` 逐个复制，对每个文件做 MD5 校验，缺文件或内容不符就
报错退出，因此不会出现「少文件但没人发现」。

`.fa` **保留提交**：它们不是逐字节副本，而是把公司的 `.seq` / `.ab1` 解析后
重新写出的 FASTA（共 98 个，不到 100 KB），复制不出来。

**实测过的三种状态：**

| 场景 | 结果 |
|---|---|
| 103 个文件全部缺失 | 复制 103 个，201/201 通过校验 |
| 1 个文件被换成 109 字节的文本桩（未开开发者模式的 Windows clone 就是这个状态） | 识别为桩并替换为真副本 |
| 1 个文件内容被改坏 | MD5 校验失败，非零退出 |

### 2.4 还没做的：`.git` 历史

`.git` 仍是 0.32 GB，其中一个 pack 装着 `release/_offline` 的离线负载
（R 安装器 87.5 MB 等）。这部分负载是**故意提交**的 —— 发布包要能从一个普通
clone 或 U 盘直接使用，不需要联网重新下载。要真正减小它只能改写历史或重建
Git 仓库，风险与收益都需要单独确认，本轮未动。

---

## 3. 目录重排

| 旧 | 新 | 说明 |
|---|---|---|
| `06_GUI/` | `02_code/PythonGUI/` | 与 R Shiny 版区分 |
| `05_builds/` | `04_builds/` | |
| `04_results/` | `tmp/test_results/` | |
| `02_code/cli/` | 不变 | **保留** |
| `02_code/gui/` | 不变 | **保留** |

### 3.1 关于 `02_code/cli` 和 `02_code/gui`

两个都还在用，删了会坏事：

- `02_code/cli/nanoamp` 是 `make cli` 执行的脚本本身；
  `release/02_CLI/bin/` 里那份是它的发布副本。
- `02_code/gui/run_gui.R` 是 `make gui` 启动的 R Shiny 界面，
  与 Python 版是两个独立实现。

### 3.2 重命名时踩到的坑（已修）

`git mv 06_GUI 02_code/GUI` 一头撞上 **Windows 文件系统大小写不敏感**：
`02_code/gui`（R Shiny）和 `02_code/GUI` 是同一个目录，于是变成了
`02_code/GUI/06_GUI/`。后面几次只改大小写的 `git mv` 让两个版本的文件混进
同一个目录，只剩一个 `README.md`。

**教训：在 Windows 上永远不要用只差大小写的目录名做 `git mv`。**
最后改用无歧义的名字 `02_code/PythonGUI` 解决，Python 版 README 从
`git show HEAD:06_GUI/README.md` 恢复。

---

## 4. 安装器 / 卸载器：截图核对发现的问题

这一项是本轮最重要的部分。用 `pywinauto` 驱动真实窗口并截图（而不是只读代码），
一共发现 **3 个真实缺陷**，全部修复。

### 4.1 「开始安装」/「开始卸载」按钮被挤出窗口（严重）

**症状：** 内容变高时，底部按钮跑到了窗口下沿之外 —— 控件存在、能点，但看不见。

**证据：** 卸载器 `winfo_reqheight()` 需要 739 px，窗口只有 600 px，
按钮条 `y=0 h=1`（根本没被布局）。两个窗口都有这个问题。

**原因：** 按钮条**最后**才 `pack`，前面的日志区一旦占满，按钮就没有空间了。

**修复：** 按钮改为先 `pack(side="bottom")`，日志区再 `pack(expand=True)`
去吸收剩余高度；并新增 `fit_to_content()`，按内容实际需要的高度定窗口大小，
屏幕不够高时收窄日志区（最多 3 行）。新增 `test_window_fit.py` 锁住这个不变量：
在 1920x1080 / 1366x768 / 1280x720 三种屏幕下，所有控件都必须在窗口内、
按钮必须可达、不能有文字超宽。

### 4.2 长路径被截断

**症状：** 安装目录、以及「随程序安装的 R 运行时（完整路径）」
在窗口里被硬生生切掉一截。

**修复：** 安装目录标签加 `wraplength` 折行；R 运行时的路径从勾选框文字里
拆出来，单独一行缩进显示。`test_window_fit.py` 里加了通用断言：
任何不能折行、又比窗口宽的控件都算失败，防止这类问题再次出现。

### 4.3 「该磁盘剩余空间」是空的，且看不到原因（严重）

**症状：** 启动时那一行**空着**，要等用户碰一下路径框才出现。
另外盘符不可读时只把标签变红，不说为什么。

**原因：** `StringVar` 的 `trace` 只在**后续**编辑时触发，构建完没主动刷新一次。

**修复：** `_build()` 结尾补一次 `_update_space()`；新增 `_drive_free_for()`
沿父目录找存在的盘符，盘符不可读时明确写出
「无法读取该磁盘的剩余空间，请检查路径是否存在」。

**截图验证过三种状态：** 默认路径、改到 `D:\nanoamp`（正确显示 200.1 GB
并随输入实时更新）、`Q:\nope`（盘符不存在，给出解释）。

### 4.4 「文件被占用 → 重试」路径

原实现有一个**藏在细节里的问题**：`shutil.rmtree(onerror=...)` 里的回调
会吞掉异常 —— 即便重试也失败，`rmtree` 也照常返回，调用方的重试循环会以为
成功了，于是删不干净却报「已删除」。新增 `_remove_tree()` 包装：
记下第一个失败，最后若目录仍然存在就抛出来。

同时把删除失败的诊断补成「列出占用它的文件」，并把固定 1.5 s 等待改成
递增等待（0/1/2/4/8 s，代码里是 `REMOVE_RETRY_DELAYS`，测试可压缩）。

另外新增 `_stop_running_background_processes()`：卸载前先结束仍在运行的
`nanoamp.exe`。**按可执行文件完整路径匹配安装目录**，不会误伤同名程序。

**实测四种场景**（`release/_installer/test_locked_file_retry.py`）：

| 场景 | 期望 | 实测 |
|---|---|---|
| `nanoamp.exe` 正在安装目录里运行（最常见：用户没关窗口就卸载） | 停掉它再删 | 认出 PID 并结束，第 1 次尝试删除成功 |
| 文件被死锁不放 | 重试后明确失败，目录保持完整 | 4 次重试全记录，报 `删除失败` 并给出处理建议，目录**没有被半删** |
| 无锁 | 一次成功、不啰嗦 | 第 1 次成功，无重试日志 |
| 只读文件 | 清掉只读位后删除 | 成功 |

### 4.5 其他修复

- 「占用约 0 MB」对小于 1 MB 的目录改为显示 KB（原来四舍五入成 0 很像个 bug）。
- 卸载器 `.fasta` 之类的假安装里 `size=8 KB` 原先显示成 `0 MB`，同上。
- 安装位置区在窗口顶部，`修改…` 选到非 `nanoamp` 目录时自动加一层子目录
  （work_report.10 已有，本轮截图复核确认仍然正确）。

### 4.6 顺带发现：`batch` 的文档与行为不一致

复核文档时把 `release/02_CLI/README.md` 的批量章节拿真数据实测了一遍
（3 行样本表：一个正常样本 + 一个故意写错路径的样本 + 又一个正常样本），
发现两个问题：

1. **文档写错了。** 原文说 `batch` 接受 `call` 的全部参数，但 `--ref-label`
   在 `batch` 里根本不是一个命令行参数 —— 它是样本表里的可选列 `ref_label`。
   参数表还漏了 `--min-cluster-reads`。
2. **失败样本会留下一个空目录。** 分析函数在打开输入文件**之前**就创建
   `outdir`，所以路径写错的样本虽然 `status=error`，却留下一个空目录。
   一排空目录看起来像"整批跑了一半"，很难一眼看出到底成了几个。

实测输出（`batch_summary.tsv`）：

```text
sample	mode	outdir	                                status	error
E4-3	A	tmp/test_results/cli/batch_out/E4-3	ok	""
broken	A	tmp/test_results/cli/batch_out/broken	error	FASTQ file not found: ...
E4-3-wt	A	tmp/test_results/cli/batch_out/E4-3-wt	ok	""
```

**修复：** 样本失败且目录为空时删除它；只要里面有文件就保留，绝不破坏
半成品。验证：`broken` 目录消失，两个成功样本各 8 个文件完好，
`status` 列不变。

同时确认 `ref_label` 列确实生效：它出现在 `qc.tsv` 的 `reference_label` 行和
`run_manifest.json` 的 `qc.reference_label`，但**不会**改
`run_manifest.json` 顶层的 `reference.name`（那一项始终是 FASTA 原始序列名）。
这个区别容易误解，已写进两份文档。

`release/02_CLI/README.md` 和 `00_materials/tutorial.md` 现在都完整写明了
样本表列含义、`batch` 与 `call` 的参数关系、输出结构，
以及"失败不中断整批、以 `status` 列为准"。

---

## 5. 教程

新增 `00_materials/tutorial.md`（1297 行），全部用 `01_data/ln_test_data` 里的
真实样本（E4-3 等）举例：

- **第 1 部分 GUI 版**：解压 → 安装 → 选文件 → 读结果，每一步都有预期输出；
- **第 2 部分 CLI 版**：单样本、批量、参数表；
- **第 3 部分 R 包版**：`R CMD INSTALL`、`library(nanoamp)`、函数调用；
- **外部依赖工具配置**：R 怎么装、`minimap2.exe` 从哪来、
  `R_LIBS_USER` 与 `.Renviron` 的关系、离线包怎么用；
- 附 4 个附录（输出文件字典、QC 指标、模式 A/B/C 对比、故障排查）。

顺带修掉一处**自相矛盾**：原文说「完全一致的只有 2%–4%」，
但同一份文档记录的 `exact_reference_proportion` 是 **0.3146**（31.5%），
实测数据直接推翻了这个说法。改为引用实测值，并说明这个数字随样本变化。

---

## 6. 验证清单

| 项目 | 结果 |
|---|---|
| 功能回归 mode A | 56/56 通过，`mean_overlap_rate` 0.9807 |
| 功能回归 mode B | 56/56 通过，`mean_overlap_rate` 0.5409 |
| 功能回归 mode C | 56/56 通过 |
| R 单元测试 | 34 项全过 |
| Python 界面 `test_headless` / `test_e2e` / `test_frozen` | 全过 |
| 安装器 `test_installer_logic` / `test_release_layout` | 全过 |
| 安装器 `test_window_fit` | 6/6 |
| 安装器 `test_locked_file_retry` | 4/4 |
| 链接层重建 | 103 个文件，201/201 校验通过 |
| `install.exe --check` / `uninstall.exe --dry-run` | 输出正常 |
| CLI `batch` 实测（含一个失败样本） | `status` = ok / error / ok，失败样本空目录已清理 |

> mode B 的 `mean_top1_proportion` 在两次运行间会有 ±0.005 左右的浮动
> （0.7275 / 0.7329），这是 DECIPHER 聚类的固有随机性，不是回归。
> mode A 的 `mean_overlap_rate` 稳定在 0.9807。

---

## 7. 遗留

1. `.git` 0.32 GB —— 需要改写历史或重建仓库才能降下来，待确认。
2. CLI 的 `nanoamp batch` 尚未接进图形界面。
3. GTF / CDS 功能注释（移码 / 提前终止 / missense）尚未实现。
4. 安装器只在有 R 的机器上验证过；无 R 干净机器上的报错路径仍未完整走查。
5. `release/02_CLI/README.md` 对批量参数的说明仍偏简略。

---

## 8. 发布后发现的严重缺陷（0.1.1 修复）

发布 v0.1.0 到 GitHub Release 后，用户实测反馈：**点「开始安装」，无论选哪个
安装位置，都弹「安装路径含有非法字符」** —— 安装器完全无法使用。

### 8.1 原因

本轮为「路径含非法字符时给出提示」而加的校验写成了：

```python
target = Path(root_text)
if any(ch in str(target) for ch in '<>:"|?*'):
```

字符集本身没错，**用错了对象**：Windows 的盘符锚点 `C:\` 天生含一个冒号，
所以 `':'` 对**每一个绝对路径**都命中，包括默认的
`%LOCALAPPDATA%\nanoamp`。这是本轮自己引进的回归。

### 8.2 修复

新增 `_illegal_path_chars()`，先剥掉盘符锚点（或 UNC 前缀）再查：

```python
body = str(target)[len(target.anchor):]
return sorted({ch for ch in '<>:"|?*' if ch in body})
```

于是 `C:` 里的冒号不再被误判，而路径段里真正的冒号（`D:\a\b:c`）照样拦下。
顺带修掉：安装位置指向一个**已存在的同名文件**时，原先的报错文不对题，
现在明确说明。

### 8.3 防止再犯

新增 `release/_installer/test_install_path_validation.py`：

- 13 个**合法**路径必须通过：盘符冒号、空格、括号、连字符、中文用户名、
  UNC 共享、盘根；
- 8 个**真正非法**的必须拦下；
- 另外直接驱动真实的「开始安装」处理函数（拦截 messagebox），
  断言合法路径下**不弹任何对话框**。

### 8.4 验证

没有只靠单元测试。重建 `install.exe` 后：

1. 在真实窗口里点「开始安装」→ 界面正常进入「安装 R 依赖包…」，
   进度条推进、详情有日志，**不再报错**；
2. 重新打包并发布后，**从 GitHub 下载发布好的附件**、解包、比对
   `install.exe` 哈希与仓库一致，再点一次「开始安装」→ 同样正常。

### 8.5 发布处理

v0.1.0 的安装器无法使用，因此：

- 发布 **v0.1.1**（修复版），附件为 `nanoamp-0.1.1-windows-setup.zip`
  + `nanoamp-0.1.0-windows-offline-deps.zip`（离线依赖无变化，保留原名）；
- **删除 v0.1.0 的 Release**，避免用户下到坏包；tag `v0.1.0` 保留以便追溯
  源码版本。

### 8.6 一个仍未在真机验证的路径

「机器上没有 R → 安装器自己静默安装 R 运行时」这条分支**仍未实测**
（本机已有 R 4.6.1，走的是「检测到已安装的 R」）。已写进 0.1.1 的
Release 说明「已知限制」。

---

## 9. 另一台 Win10 机器上发现的两个缺陷（0.1.2 修复）

用户在**没有系统 R** 的 Win10 机器上实测 0.1.1，报告两个问题。

### 9.1 点「环境自检」报 `Could not find Rscript.exe`

**原因：** 这台机器上没有 R，所以 `install.exe` 把自带的 R 装进了
`<安装目录>\R\R-runtime\`，并把位置写进了 `config.ini` 的 `rscript=`。
**但图形界面从来不读 `config.ini`。** 它的候选列表只有
`C:\Program Files\R`、`D:\tools\R`、`%LOCALAPPDATA%\Programs\R`、`PATH`
这些「常见位置」，自带的 R 一个都不在其中。

于是出现了很讽刺的一幕：唯一知道 R 在哪儿的程序把答案写下来了，
而需要这个答案的程序没有去看。

**修复：** `r_runner._candidate_rscipts()` 现在按顺序查：

1. `NANOAMP_RSCRIPT` 环境变量；
2. **`config.ini` 里的 `rscript=`**（经 `NANOAMP_HOME`、
   `%LOCALAPPDATA%\nanoamp.path` 指针文件、或默认安装目录找到）；
3. 自带 R 运行时 `<安装目录>\R\R-runtime\bin\Rscript.exe`；
4. 常见位置；
5. `PATH`。

顺带修掉反方向同样的问题：`install.exe` 自己的 `_r_candidates()` 也看不见
它上一轮装好的自带 R，所以「再跑一次安装器来修复」会**又装一遍 R**。
现在它先查指针文件和默认安装目录。

### 9.2 桌面上多出一个「R 4.6.1」图标

**原因：** R 的安装器是 Inno Setup，静默安装时默认会创建桌面和开始菜单
快捷方式。用户只要 nanoamp 的图标，不该多出 R 的。

**修复：** 调用 R 安装器时加上
`/MERGETASKS="!desktopicon,!quicklaunchicon"`（以及
`/SUPPRESSMSGBOXES /SP-`）。考虑到 R 以后的版本可能不认这个参数，
另加一层兜底 `_hide_bundled_r_shortcuts()`：安装 R 前后各拍一次桌面与
开始菜单的快照，**只删「安装期间新出现」且「名字像 R 的」**快捷方式 ——
用户自己本来就有的 R 图标、以及任何无关图标都不会被碰。

### 9.3 新增测试

| 测试 | 覆盖 |
|---|---|
| `02_code/PythonGUI/tests/test_bundled_r_lookup.py` | 自带的 R 只存在于 `R-runtime`：默认安装位置、改过安装位置（靠 `nanoamp.path`）、`NANOAMP_HOME` 三种路径都能找到 |
| `release/_installer/test_r_shortcut_cleanup.py` | 沙箱 `USERPROFILE`/`APPDATA`：用户原有的 R 图标保留、R 新图标从桌面和开始菜单都删掉、第二次运行是空操作 |

第二个测试全程在沙箱里跑，**不读也不写真实桌面**（已单独确认真实桌面未被
触碰）。

### 9.4 验证

- 两个 exe 都重建了：`nanoamp.exe`（改的是图形界面的查找逻辑）、
  `install.exe`（改的是快捷方式抑制）；
- 在沙箱 `LOCALAPPDATA`/`APPDATA`/`USERPROFILE` 下静默安装 → 退出码 0，
  `config.ini` 写入了 `rscript=`；
- 用**真实的** `r_runner.find_rscript()` 和 `app.find_repo_root()`
  读那份 config → 两者都正确解析出安装目录和 Rscript；
- 发布后从 GitHub 下载 `nanoamp-0.1.2-windows-setup.zip`，
  sha256 与本地一致，包内 `install.exe` / `nanoamp.exe` 字节数正确。

### 9.5 发布处理

- 发布 **v0.1.2**；**删除 v0.1.1 的 Release**（tag 保留）；
- 离线依赖包仍为 `nanoamp-0.1.0-windows-offline-deps.zip`（内容未变）。
