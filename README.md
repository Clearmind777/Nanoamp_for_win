# nanoamp — 纳米孔 PCR 产物分析（Windows 版）

**一句话说明：** 把纳米孔测序公司交付的 FASTQ 文件，和你想要的正确序列比对一下，
告诉你有多少条是**完全正确**的、其他不一样的序列长什么样、各占多少比例。

不需要懂生信，不需要懂编程。装好之后双击一个图标就能用。

---

## 目录

1. [这个软件能帮你做什么](#1-这个软件能帮你做什么)
2. [第一次使用：三步搞定](#2-第一次使用三步搞定)
3. [怎么用（图解步骤）](#3-怎么用图解步骤)
4. [怎么看结果](#4-怎么看结果)
5. [三种版本，该用哪个](#5-三种版本该用哪个)
6. [遇到问题怎么办](#6-遇到问题怎么办)
7. [给开发者：源码与二次开发](#7-给开发者源码与二次开发)

---

## 1. 这个软件能帮你做什么

你从测序公司拿到一个 `fastq` 文件（一个样本一个文件）。你想知道：

- 这个样本里，有多少条序列是**我设计的那个序列**？
- 剩下的序列**哪里不一样**（哪个碱基变了、哪里插入了、哪里缺了）？
- 两种各占**多少比例**？

nanoamp 就是回答这三个问题的。

> **为什么不能直接数？**
> 纳米孔测序的每一条 read 都有约 0.5%–2% 的测序错误。如果直接拿原始 read 去和
> 目标序列比对，会发现"完全一致"的比例明显偏低 —— 这不是实验失败，而是被测序错误
> 掩盖了。nanoamp 会先把测序错误校正掉、把真实变异保留下来，
> 再按"校正后的序列"分类计数。所以它给出的比例才是可信的。
>
> 偏低多少既看样本，也看你说的是哪个数：本仓库的验收数据（`01_data` 里的 E4-3）
> **原始 read 一位不差**的只有 **9.4%**（模式 C 的 `exact_any_proportion`）；
> **校正后**仍等于目的序列的是 **31.5%**（模式 A 的 `exact_reference_proportion`，
> 也就是结果表里 `是否与目的序列一致 = 是` 那一行的占比）。后者正是 nanoamp
> 要回答的问题。

---

## 2. 第一次使用：三步搞定

### 第 1 步：解压

把收到的压缩包**完整解压**到一个**路径里没有中文和空格**的地方，例如：

```text
D:\nanoamp\
```

> ⚠️ 不要直接在压缩包里双击运行，也不要放在桌面（桌面路径通常含中文用户名）。
> 解压后应该能看到 `install.exe` 和 `_offline`、`01_R-package` 等文件夹。

### 第 2 步：双击 `install.exe`

会弹出安装窗口，点**「开始安装」**，然后等 3–10 分钟。

窗口上方有两处可以按需调整，不确定就保持默认：

| 项目 | 默认 | 说明 |
|---|---|---|
| **安装位置** | 当前用户目录下 | 点「修改…」可以改到 `D:\nanoamp` 这类位置。窗口会显示该磁盘剩余空间 |
| **在桌面创建快捷方式** | ☑ 勾选 | 不想动桌面就取消勾选 |
| **把 nanoamp 命令加入 PATH** | ☑ 勾选 | 取消勾选则命令行需要用完整路径调用 |

安装程序会自动做完这些事（**全程不需要联网，不需要管理员权限**）：

| 它会做的事 | 说明 |
|---|---|
| 找到或安装 R | R 是统计分析环境，nanoamp 依赖它。找不到就自动从安装包里装 |
| 安装 R 依赖包 | 共 109 个，全部来自安装包，不联网下载 |
| 安装 nanoamp 主程序 | 核心分析引擎 |
| 注册 `nanoamp` 命令 | 供命令行使用（可取消） |
| 在桌面创建快捷方式 | 「nanoamp 分析工具」（可取消） |
| 安装比对程序 minimap2 | 已随包提供，静态链接，无需额外配置 |
| 最后自检 | 确认一切就绪 |

安装完成后会弹提示框告诉你成功了。

> 默认安装位置：`C:\Users\<你的用户名>\AppData\Local\nanoamp`
> 如果你改过位置，提示框和 `install.exe --check` 都会显示实际路径。

### 第 3 步：开始分析

双击桌面上的 **「nanoamp 分析工具」** 图标，就打开了分析窗口。

---

## 3. 怎么用（图解步骤）

窗口长这样，从上到下四块：

```text
┌─────────────────────────────────────────────────────────┐
│  nanoamp - 纳米孔 PCR 产物分析                            │
├─────────────────────────────────────────────────────────┤
│  输入                                                    │
│   测序文件 (FASTQ)  [__________________] [浏览…]         │  ← ① 选 fastq
│   目的序列 (FASTA)  [__________________] [浏览…]         │  ← ② 选参考序列
│   输出目录          [__________________] [浏览…]         │  ← ③ 选结果放哪
│   模式 [A - 参考引导 ▾]   显示前 n 条 [20]                │  ← ④ 一般不用改
├─────────────────────────────────────────────────────────┤
│  [单倍型结果] [QC 指标] [输出文件] [运行日志]              │  ← ⑤ 结果在这里
│  排名 │ 编号 │ reads 数 │ 占比 │ 是否一致 │ 变异 │ ...    │
│  ...                                                     │
│  ┌ 选中某一行会显示这条序列的完整碱基 ─────────────┐       │
├─────────────────────────────────────────────────────────┤
│  [开始分析] [环境自检]              [打开输出目录]  ▓▓▓  │  ← ⑥ 点这里开始
│  就绪。选择 FASTQ 和参考序列后点击"开始分析"。             │
└─────────────────────────────────────────────────────────┘
```

**操作顺序：**

1. 点 **测序文件** 后面的「浏览…」，选中公司给你的 `.fastq` 文件。
2. 点 **目的序列** 后面的「浏览…」，选中你的目的序列 `.fa`/`.fasta` 文件。
   - 如果 fastq 所在文件夹里正好有 `reference.self.fa`，选完 fastq 后会自动填上。
3. **输出目录** 默认是 `我的文档\nanoamp 结果`，一般不用改。
4. **模式** 保持 `A - 参考引导（推荐）`。**显示前 n 条** 保持 20。
5. 点 **「开始分析」**。等几秒到几十秒（看数据量）。
6. 状态栏出现「分析完成」就结束了，结果在「单倍型结果」标签页里。

> 不确定环境是否正常时，先点一次 **「环境自检」**，它会把 R、依赖包、minimap2
> 的状态列在「运行日志」里。

---

## 4. 怎么看结果

### 「单倍型结果」标签页 —— 最常看的一张表

| 列 | 含义 |
|---|---|
| **排名** | 按 reads 数从多到少排 |
| **编号** | H1、H2… 每种不同序列的编号 |
| **reads 数** | 支持这条序列的 reads 条数 |
| **占比** | 占全部 reads 的百分比 ← **你最关心的数值** |
| **是否与目的序列一致** | `是` = 和你要的序列完全一样；`否` = 有差异 |
| **SNV / 插入 / 缺失** | 这条序列相对目的序列有几种变异 |
| **变异** | 具体描述，例如 `218delG` 表示第 218 位少了一个 G |
| **长度** | 这条序列的碱基数 |

**举例**（某样本真实结果）：

```text
排名  编号  reads 数  占比     是否一致   变异
 1    H1     142    33.3%     否       218delG
 2    H2     134    31.5%     是       .
 3    H3     114    26.8%     否       218delG;135C>T
```

读法：这个样本里 **31.5% 是你要的目的序列**；最多的一种（33.3%）比目的序列
少了一个 G；第三多的（26.8%）同时少了 G 又有一个 C→T 的点突变。

选中任意一行，下方会显示这条序列的完整碱基。

> 注意：`是否一致` 是根据**校正后**的序列判断的。想知道"完全不校正时原始 read 有
> 多少条一位不差"，请用**模式 C**，看它的 `exact_any_proportion`（E4-3 只有 9.4%，
> 多数样本在 2%–20% 之间）—— 那才是测序错误的体现，不是实验结果。
> 「QC 指标」里的 `exact_reference_proportion` 是**校正后**参考序列的占比，
> 两者不是一回事，别混。

### 「QC 指标」标签页 —— 判断数据质量

| 指标 | 怎么看 |
|---|---|
| `n_reads_total` | 总 reads 数。**低于 100 条时比例不可靠** |
| `n_reads_used` | 实际参与分析的 reads 数 |
| `mapping_rate` | 比对成功率，正常应 > 0.95 |
| `mean_identity` | 平均一致度，正常 0.98 以上 |

### 「输出文件」标签页

每次分析会在输出目录生成这些文件，**双击可以在系统默认程序里打开**：

| 文件 | 内容 |
|---|---|
| `haplotypes.tsv` | 单倍型表（就是上面那张表），可用 Excel 打开 |
| `haplotypes.fasta` | 前 n 条单倍型的完整序列 |
| `variants.tsv` | 所有候选变异位点，格式与公司 `*.var.xls` 兼容 |
| `qc.tsv` | 质量指标 |
| `run_manifest.json` | 本次运行的参数、版本、输入文件校验值（可追溯） |

---

## 5. 三种版本，该用哪个

| 版本 | 适合谁 | 怎么用 | 位置 |
|---|---|---|---|
| **GUI 版**（图形界面） | **不写代码的人** — 绝大多数情况用这个 | 双击桌面「nanoamp 分析工具」 | `release/03_GUI/` |
| **CLI 版**（命令行） | 需要批量处理几十上百个样本的同学 | 命令行输入 `nanoamp call ...` | `release/02_CLI/` |
| **R package 版** | 要把分析嵌进自己 R 流程的生信同学 | `library(nanoamp)` 后调用函数 | `release/01_R-package/` |

三个版本**共用同一套分析核心**，结果不会互相矛盾 —— 它们都是调用同一个
`nanoamp` R 包。装上 `install.exe` 后三个版本都能用。

- GUI 版详情见 [`release/03_GUI/README.md`](release/03_GUI/README.md)
- CLI 版详情见 [`release/02_CLI/README.md`](release/02_CLI/README.md)
- R 包版详情见 [`release/01_R-package/README.md`](release/01_R-package/README.md)

---

## 6. 遇到问题怎么办

### 双击 `install.exe` 没反应 / 一闪而过

安装包可能没解压完整。重新解压，确认解压后目录里有 `_offline`、`01_R-package`、
`03_GUI` 这几个文件夹。

### 提示「没有找到 R」

安装包里应该带 `_offline\r\R-4.6.1-win.exe`。如果没有，到
<https://cran.r-project.org/bin/windows/base/> 下载安装（全部点"下一步"），
然后回到安装窗口点「重试」。

### 提示「安装包不完整」

压缩包解压不完整，或者被杀毒软件删掉了部分文件。关掉杀毒软件重新解压，或换一个
解压位置（**路径不要含中文和空格**）。

### 分析时提示找不到 minimap2

先点「环境自检」看 `minimap2` 那一行。应显示安装目录下的路径。若显示
`NOT FOUND`，重新运行 `install.exe` 修复。

### 结果里「是否一致」几乎没有「是」

1. 先看「QC 指标」里的 `n_reads_total`。太少（< 50）时比例不可靠。
2. 确认你选的**目的序列**确实是本样本的预期序列（有时候会拿错参考文件）。
3. 如果实验本身就是混样或编辑效率低，那结果是对的 —— 这正说明样本不纯。

### 中文路径 / 用户名导致失败

把安装包解压到 `D:\nanoamp\` 这类**纯英文无空格**路径再装。
输出目录也建议用英文路径。

### 想卸载

双击安装包里的 **`uninstall.exe`**，它会显示检测到的安装位置和占用空间，
列出将要删除的内容，确认后自动清理：

- 安装目录
- 桌面快捷方式
- 用户 PATH 里的 nanoamp 条目
- `.Renviron` 里的 `R_LIBS_USER` 行

**你自己安装的 R、你的 R 库、你的测序数据和结果文件都不会被删除。**

> 如果 nanoamp 窗口还开着，部分文件可能删不掉。关掉窗口再运行一次即可。

### 命令行里输入 `nanoamp` 提示不是内部或外部命令

PATH 需要新开一个命令行窗口才生效。若仍无效，手工把
`%LOCALAPPDATA%\nanoamp\bin` 加进用户 PATH。

---

## 7. 给开发者：源码与二次开发

以上是给使用者的部分。以下是本仓库作为**开发仓库**的结构。

### 仓库结构

```text
release/             ← 发布产物：三个交付形态 + 一键安装器
  01_R-package/      R 包发行版（tarball + 安装说明）
  02_CLI/            命令行发行版（启动器 + 说明）
  03_GUI/            图形界面发行版（nanoamp.exe + 说明）
  install.exe        一键安装器（构建产物）
  uninstall.exe      一键卸载器（构建产物）
  _installer/        安装器与卸载器源码
  _offline/          离线依赖（R 安装器、R 包、minimap2）
02_code/             源码
  r/                 nanoamp R 包源码
  cli/               CLI 入口脚本（make cli 用）
  gui/               R Shiny 图形界面（make gui 用）
  PythonGUI/         Python/Tkinter 图形界面源码（发行版 GUI 就是这个的产物）
  shared/            参数与输出契约
01_data/             测试数据（`<dataset>/<sample>/` 规范化命名，文件即数据）
03_dependence/       内置的 minimap2.exe、R 环境脚本与编译方案
00_materials/        委托文档、开发方案、历次工作报告、完整教程
  tutorial.md        傻瓜式教程：GUI 版 / CLI 版 / R 包版 + 依赖工具配置
04_builds/           R 包构建产物（Git 忽略）
tmp/test_results/    运行输出（Git 忽略）
```

### 开发环境搭建

```powershell
# 1. 安装 R 依赖（本仓库用 D:\tools\R\lib 作为独立库，避免污染系统库）
Rscript 03_dependence/r-environment/setup_r_environment.R

# 2. 安装 R 包
R CMD INSTALL --library=D:/tools/R/lib 02_code/r

# 3. 跑测试（测试数据就在 01_data/ 里，无需额外准备）
Rscript 03_dependence/r-environment/run_tests.R
Rscript 03_dependence/r-environment/run_functional_regression.R `
  --outdir tmp/test_results/r/test_run_win --modes A,B,C --threads 4
```

### 常用 make 目标

```bash
make install          # 安装 R 包
make test             # testthat 测试
make check            # R CMD check
make cli              # 运行 nanoamp doctor
make gui              # 启动 Shiny 界面
make gui-python       # 启动 Python/Tkinter 界面
make gui-exe          # 重新打包 02_code/PythonGUI/dist/nanoamp.exe
make gui-test         # Python 界面自测
make install-exe      # 重新打包 release/install.exe
make deps             # 说明内置 minimap2.exe 的来源
make toolchain        # 安装 MSYS2/MINGW-w64 编译链（重建 minimap2 用）
make offline-bundle   # 获取离线依赖包
```

### 重新构建发布产物

```powershell
# R 包 tarball
R CMD build 02_code/r --no-build-vignettes

# 图形界面 exe（需要 pip install pyinstaller）
python 02_code/PythonGUI/build_exe.py

# 一键安装器 + 一键卸载器 exe（需要 pip install pyinstaller）
python release/_installer/build_exe.py

# 自测
python release/_installer/test_installer_logic.py    # 安装器逻辑，不实际安装
python release/_installer/test_release_layout.py     # 三个交付形态的布局自检
python release/_installer/test_window_fit.py         # 两个窗口不会被内容挤出边界
python release/_installer/test_locked_file_retry.py  # 文件被占用时的重试与报错
```

查看两个窗口的实际长相（需要 `pip install pywinauto pillow`，仅开发用）：

```powershell
# 安装器：默认路径、换到 D 盘、盘符不存在三种状态
python release/_installer/inspect_installer_live.py tmp/test_results/shots

# 卸载器：在沙箱里造一份假安装，截图后再删掉，不碰真实系统
python release/_installer/capture_uninstaller_populated.py tmp/test_results/shots
```

### 外部工具与平台说明

- `minimap2.exe` 由本仓库从上游源码编译并**静态链接**，只依赖
  `KERNEL32.dll` 和 `msvcrt.dll`，因此目标机器无需 MSYS2 / Cygwin / conda / WSL。
- `samtools` **不需要**：SAM→BAM 默认由 `Rsamtools::asBam()` 完成。
- 本项目**全程不使用 conda，也不使用 WSL**。
- 本仓库是 **Windows 变体**；Linux 变体在姊妹仓库
  `a_09_18_26_mapping_programs_dev_for_linux`。

### 文档索引

| 文档 | 内容 |
|---|---|
| `00_materials/tutorial.md` | **完整傻瓜式教程**：GUI 版、CLI 版、R 包版安装使用 + 外部依赖工具配置 |
| `release/README.md` | 发布产物总览与安装器说明 |
| `release/01_R-package/README.md` | R 包版安装与使用 |
| `release/02_CLI/README.md` | CLI 版安装与使用 |
| `release/03_GUI/README.md` | GUI 版安装与使用 |
| `02_code/r/README.md` | R 包完整教程（英文） |
| `02_code/r/README-CN.md` | R 包完整教程（中文） |
| `02_code/PythonGUI/README.md` | Python 界面实现与打包细节 |
| `03_dependence/README.md` | 内置工具与平台支持矩阵 |
| `03_dependence/offline-bundle/README.md` | 离线安装包的设计与理由 |
| `00_materials/README.md` | 委托文档与历次工作报告 |

### 已知限制

1. **依赖 R**：图形界面 exe 只打包界面（10 MB），不含 R 运行时。
2. **exe 冷启动约 1–3 秒**：单文件打包每次运行需解压到临时目录。
3. **无批量界面**：CLI 的 `nanoamp batch` 尚未接进图形界面。
4. **无 GTF / CDS 功能注释**：委托中点名的"移码/提前终止/missense"尚未实现。
5. **测试数据是普通文件**：`01_data/<dataset>/<sample>/` 里直接就是
   `reads.fastq` / `reference.self.fa` / `consensus.N.fa` / `variants.N.xlsx` /
   `sanger.N.ab1`，随仓库一起提交，**克隆后不需要任何准备步骤**。
   每个样本目录里的 `meta.tsv` 记录这些文件原本是公司的哪个交付文件。
   详见 `01_data/README.md`。
6. **仓库体积**：`.git` 里含 `release/_offline` 的离线负载（R 安装器 87 MB 等），
   完整克隆约 320 MB。发布包是直接解压使用的，使用者不需要克隆仓库。

---

## 许可证

MIT。
