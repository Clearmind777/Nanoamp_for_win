# nanoamp — 纳米孔 PCR 产物分析（Windows 版）

**功能摘要：** 将纳米孔测序公司交付的 FASTQ 文件与目的序列进行比对，统计其中**完全正确**
的 reads 数量、其余序列的差异形式及其各自占比。

使用图形界面无需生物信息学或编程背景，安装完成后通过桌面快捷方式启动。

---

## 目录

1. [功能概述](#1-功能概述)
2. [首次安装：三个步骤](#2-首次安装三个步骤)
3. [图形界面操作步骤](#3-图形界面操作步骤)
4. [结果解读](#4-结果解读)
5. [三种交付版本的选择](#5-三种交付版本的选择)
6. [故障排查](#6-故障排查)
7. [面向开发者：源码与二次开发](#7-面向开发者源码与二次开发)

---

## 1. 功能概述

输入为测序公司交付的一个 `fastq` 文件（一个样本一个文件），nanoamp 回答以下三个问题：

- 该样本中有多少条序列与**设计的目的序列**完全一致？
- 其余序列**差异在哪里**（哪个碱基发生替换、何处插入、何处缺失）？
- 两类序列各占**多少比例**？

> **不能直接计数的原因**
> 纳米孔测序的每一条 read 都带有约 0.5%–2% 的测序错误。直接以原始 read 与目标序列
> 比对时，"完全一致"的比例会明显偏低 —— 这不是实验失败，而是测序错误掩盖了真实结果。
> nanoamp 先校正测序错误、保留真实变异，再按"校正后的序列"分类计数，因此其给出的
> 比例具有参考意义。
>
> 偏低幅度既取决于样本，也取决于统计的是哪个数值：本仓库的验收数据（`01_data` 里的
> E4-3）中，**原始 read 一位不差**的比例为 **9.4%**（模式 C 的 `exact_any_proportion`）；
> **校正后**仍等于目的序列的比例为 **31.5%**（模式 A 的 `exact_reference_proportion`，
> 即结果表中 `是否与目的序列一致 = 是` 那一行的占比）。后者正是 nanoamp
> 要回答的问题。

---

## 2. 首次安装：三个步骤

### 第 1 步：解压

将压缩包**完整解压**到**路径中不含中文和空格**的目录，例如：

```text
D:\nanoamp\
```

> 请勿直接在压缩包内双击运行，也不要解压到桌面（桌面路径通常包含中文用户名）。
> 解压后应能看到 `install.exe`、`01_R-package`、`deps` 等文件夹。
>
> 发布资产有两个，均在 `release/_build/` 下构建：`nanoamp-0.1.5-windows-setup.zip`
> （约 34 MB，**可独立安装**）与 `nanoamp-0.1.0-windows-offline-deps.zip`
> （约 248 MB，可选，用于离线安装）。仅安装 setup 包时需要联网：安装器会先测速选源，
> 再按 `deps/pinned-R4.6.tsv` 中**固定的版本**下载 R 依赖包。需要在无网络环境下安装时，
> 可再将 offline-deps 包解压到同一个 `nanoamp-windows\` 目录，解压后会多出一个
> `_offline` 文件夹，安装器即改用该文件夹中的依赖包。

### 第 2 步：双击 `install.exe`

弹出安装窗口后点击**「开始安装」**，安装耗时约 3–10 分钟（需要联网下载依赖时约
5–15 分钟，取决于网络速度）。

窗口上方有以下三项可按需调整，不确定时保持默认：

| 项目 | 默认 | 说明 |
|---|---|---|
| **安装位置** | 当前用户目录下 | 点「修改…」可以改到 `D:\nanoamp` 这类位置。窗口会显示该磁盘剩余空间 |
| **在桌面创建快捷方式** | 默认勾选 | 不需要桌面快捷方式时可取消勾选 |
| **把 nanoamp 命令加入 PATH** | 默认勾选 | 取消勾选则命令行需要用完整路径调用 |

安装程序会自动完成以下操作（**不需要管理员权限**）：

| 操作 | 说明 |
|---|---|
| 找到或安装 R | R 是统计分析环境，nanoamp 依赖它。系统中已有的 R 版本与依赖包一致（当前 4.6）时直接使用；否则安装随包提供的 R 4.6（安装在安装目录内，不改动用户已有的 R） |
| 安装 R 依赖包 | 共 109 个：**有 `_offline` 就离线安装**；没有时自动测速选源（清华/中科大/北外/南大/阿里云/官方），按 `deps/pinned-R4.6.tsv` 里**固定的版本**下载并校验 |
| 安装 nanoamp 主程序 | 核心分析引擎 |
| 注册 `nanoamp` 命令 | 供命令行使用（可取消） |
| 在桌面创建快捷方式 | 「nanoamp 分析工具」（可取消） |
| 安装比对程序 minimap2 | 已随包提供，静态链接，无需额外配置 |
| 最后自检 | 确认各项环境就绪 |

安装完成后弹出提示框，报告安装结果。

> 默认安装位置：`C:\Users\<用户名>\AppData\Local\nanoamp`（即 `%LOCALAPPDATA%\nanoamp`）。
> 若安装时修改过位置，提示框和 `install.exe --check` 都会显示实际路径。

### 第 3 步：开始分析

双击桌面快捷方式 **「nanoamp 分析工具」**，打开分析窗口。

---

## 3. 图形界面操作步骤

窗口自上而下分为四个区域：

```text
┌─────────────────────────────────────────────────────────┐
│  nanoamp - 纳米孔 PCR 产物分析                            │
├─────────────────────────────────────────────────────────┤
│  输入                                                    │
│   测序文件 (FASTQ)  [__________________] [浏览…]         │  ← ① 选择 FASTQ 文件
│   目的序列 (FASTA)  [__________________] [浏览…]         │  ← ② 选择参考序列
│   输出目录          [__________________] [浏览…]         │  ← ③ 选择输出目录
│   模式 [A - 参考引导 ▾]   显示前 n 条 [20]                │  ← ④ 通常无需修改
├─────────────────────────────────────────────────────────┤
│  [单倍型结果] [QC 指标] [输出文件] [运行日志]              │  ← ⑤ 结果区
│  排名 │ 编号 │ reads 数 │ 占比 │ 是否一致 │ 变异 │ ...    │
│  ...                                                     │
│  ┌ 选中某一行会显示这条序列的完整碱基 ─────────────┐       │
├─────────────────────────────────────────────────────────┤
│  [开始分析] [环境自检]              [打开输出目录]  ▓▓▓  │  ← ⑥ 开始分析
│  就绪。选择 FASTQ 和参考序列后点击"开始分析"。             │
└─────────────────────────────────────────────────────────┘
```

**操作顺序：**

1. 点 **测序文件** 后面的「浏览…」，选中测序公司交付的 `.fastq` 文件。
2. 点 **目的序列** 后面的「浏览…」，选中目的序列 `.fa`/`.fasta` 文件。
   - 若 fastq 所在文件夹中存在 `reference.self.fa`，选择 fastq 后会自动填入该文件。
3. **输出目录** 默认是 `我的文档\nanoamp 结果`，通常无需修改。
4. **模式** 保持 `A - 参考引导（推荐）`，**显示前 n 条** 保持 20。
5. 点 **「开始分析」**，等待数秒至数十秒，取决于数据量。
6. 状态栏显示「分析完成」后，结果位于「单倍型结果」标签页中。

> 需要确认环境状态时，可先执行一次 **「环境自检」**，该操作会将 R、依赖包、minimap2
> 的状态输出到「运行日志」中。

---

## 4. 结果解读

### 「单倍型结果」标签页 —— 主要结果表

| 列 | 含义 |
|---|---|
| **排名** | 按 reads 数从多到少排 |
| **编号** | H1、H2… 每种不同序列的编号 |
| **reads 数** | 支持这条序列的 reads 条数 |
| **占比** | 占全部 reads 的百分比 ← **主要参考数值** |
| **是否与目的序列一致** | `是` 表示与目的序列完全一致；`否` 表示存在差异 |
| **SNV / 插入 / 缺失** | 这条序列相对目的序列有几种变异 |
| **变异** | 具体描述，例如 `218delG` 表示第 218 位少了一个 G |
| **长度** | 这条序列的碱基数 |

**示例**（某样本实际结果）：

```text
排名  编号  reads 数  占比     是否一致   变异
 1    H1     142    33.3%     否       218delG
 2    H2     134    31.5%     是       .
 3    H3     114    26.8%     否       218delG;135C>T
```

解读：该样本中 **31.5% 的 reads 与目的序列一致**；占比最高的一种（33.3%）比目的序列
少一个 G；第三多的一种（26.8%）既缺失一个 G，又有一个 C→T 的点突变。

选中任意一行，下方会显示这条序列的完整碱基。

> 注意：`是否一致` 是根据**校正后**的序列判断的。完全不校正时原始 read 一位不差的
> 比例需查看**模式 C** 的 `exact_any_proportion`（E4-3 为 9.4%，
> 多数样本在 2%–20% 之间）—— 该数值反映的是测序错误，而非实验结果。
> 「QC 指标」里的 `exact_reference_proportion` 是**校正后**参考序列的占比，
> 两者含义不同，不可混用。

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

### 功能注释（可选）

勾选输入区的**「功能注释…」**即启用：程序会把每条单倍型的变异翻译成生物学后果
（移码 / 提前终止 / 终止丢失 / 整码插入缺失 / 错义 / 同义，以及 UTR、内含子、剪接区），
并在输出目录多写两个文件：

| 文件 | 内容 |
|---|---|
| `annotation.tsv` | 每个「单倍型 × 转录本」一行，含中英双列后果、蛋白变化、转录本冲突标记 |
| `variants_annotation.tsv` | 勾选「输出变异级明细」时生成：每个变异一行，含 CDS 坐标、密码子与氨基酸变化 |

两条路线，界面里直接选：

| 路线 | 是否需要联网 | 你要提供什么 |
|---|---|---|
| **离线 CDS（不联网）** | 不需要 | 在界面里填 CDS 的起止坐标、链与读码框（坐标以目的序列为准，1-based；长度必须是 3 的倍数） |
| **在线 genome（需联网）** | 需要 | 什么都不用填：程序自行在 GRCh38 定位扩增子并从 Ensembl 取转录本结构 |

判断注释覆盖了哪些转录本，请以 **`qc.tsv` 的 `n_transcripts_annotated` /
`n_transcripts_skipped` / `annotation_skip_reason`** 为准（「注释结果」页会把它们显示在状态行），
**不要只看 `annotation.tsv` 有几行**。注释被跳过时退出码仍是 0，因为序列分析本身成功了。

---

## 5. 三种交付版本的选择

| 版本 | 适用场景 | 使用方式 | 位置 |
|---|---|---|---|
| **GUI 版**（图形界面） | **不使用命令行的用户** —— 适用于多数场景 | 双击桌面「nanoamp 分析工具」 | `release/03_GUI/` |
| **CLI 版**（命令行） | 需要批量处理大量样本（几十至上百个） | 命令行输入 `nanoamp call ...` | `release/02_CLI/` |
| **R package 版** | 需要将分析集成到自有 R 流程中 | `library(nanoamp)` 后调用函数 | `release/01_R-package/` |

三个版本**共用同一套分析核心**，均调用同一个 `nanoamp` R 包，因此结果一致。
安装 `install.exe` 后三个版本均可使用。

- GUI 版详情见 [`release/03_GUI/README.md`](release/03_GUI/README.md)
- CLI 版详情见 [`release/02_CLI/README.md`](release/02_CLI/README.md)
- R 包版详情见 [`release/01_R-package/README.md`](release/01_R-package/README.md)

---

## 6. 故障排查

### 双击 `install.exe` 无反应 / 窗口一闪而过

安装包可能未解压完整。请重新解压，并确认解压后目录中包含 `deps`、`01_R-package`、
`03_GUI`、`bin` 这几个文件夹（`_offline` 是可选的）。

### 提示「没有找到 R」

安装器按以下顺序查找：系统中已有的 R 4.6、随包提供的 `_offline\r\R-4.6.1-win.exe`，
最后从测速选出的镜像下载 R 4.6.1。以上途径均不可用时才会弹出该提示，此时可以到
<https://cran.r-project.org/bin/windows/base/> 下载并安装 R 4.6.x（安装过程保持默认选项），
然后回到安装窗口点「重试」。

### 已安装 R，但提示 R 版本不匹配 / 装不上

nanoamp 的 109 个依赖包是按**某一个** R 小版本编译的（当前是 **4.6**），
R 的小版本之间二进制不兼容，所以：

- 已有 **R 4.6.x** → 安装器直接使用，不会再安装一份 R；
- 仅有 **R 4.5 或别的版本** → 安装器会安装**随包提供的 R 4.6**，安装在
  `<安装目录>\R\R-runtime`，**不会改动、也不会卸载用户已有的 R**。
  安装完成后 `nanoamp doctor` 里的 `R version` 应当是 4.6.x。

> 0.1.2 及更早的安装器在装有 R 4.5 的机器上会失败：它只要找到 R ≥ 4.2 就用，
> 于是选中 R 4.5，随后因为包里只有 4.6 的依赖包而报
> 「安装包内没有适配 R 4.5 的依赖包」。**0.1.3 起已修复**（见
> `00_materials/work_reports/work_report.14.md`）。
>
> 若仍在使用 0.1.2 的安装包，有两种临时处理方式：
> 1. 先从包里运行 `_offline\r\R-4.6.1-win.exe`（或在 R 官网安装 R 4.6.x），
>    再重新运行 `install.exe` —— 它会检测到 4.6 并直接使用；
> 2. 或者改用 0.1.3 的安装包。

### 提示「安装包不完整」

压缩包解压不完整，或者部分文件被被杀毒软件删除。请关闭杀毒软件后重新解压，或更换一个
解压位置（**路径不要含中文和空格**）。

> 从 0.1.4 起，没有 `_offline` 文件夹**不算**不完整：安装器会改成联网下载依赖
> （需要 `deps\pinned-R4.6.tsv`，该文件位于 setup 包中）。

### 未使用离线依赖包 / 依赖下载很慢或失败

109 个 R 依赖包有两种来源：

| 情况 | 安装器怎么做 |
|---|---|
| 有 `_offline\` 文件夹 | 直接离线安装，**安装过程不需要联网**（推荐：把 offline-deps 包也解压到同一个 `nanoamp-windows\`） |
| 没有 `_offline\` | 先并发测试 6 个镜像（清华 / 中科大 / 北外 / 南大 / 阿里云 / 官方）的下载速度，选最快的，再按 `deps\pinned-R4.6.tsv` 里**固定的版本**下载（约 159 MB），逐个校验版本 |

安装窗口的日志里会显示测速结果、选中的镜像和下载进度。如果出现
「下载失败：<包名> —— 已试过所有镜像」，说明网络不通或该版本已从镜像撤下，
这时下载 `nanoamp-0.1.0-windows-offline-deps.zip` 解压到同一个 `nanoamp-windows\`
再装一次即可（离线包里有完全相同的一套版本）。

### 分析时提示找不到 minimap2

先点「环境自检」，查看 `minimap2` 那一行，应显示安装目录下的路径。若显示
`NOT FOUND`，重新运行 `install.exe` 修复。

### 结果里「是否一致」几乎没有「是」

1. 先看「QC 指标」里的 `n_reads_total`。数值太少（< 50）时比例不可靠。
2. 确认所选的**目的序列**确实是本样本的预期序列（有时会误用其他参考文件）。
3. 如果实验本身就是混样或编辑效率低，该结果即为真实情况 —— 说明样本不纯。

### 中文路径 / 用户名导致失败

把安装包解压到 `D:\nanoamp\` 这类**纯英文无空格**路径再安装。
输出目录也建议使用英文路径。

### 卸载

双击安装包里的 **`uninstall.exe`**，它会显示检测到的安装位置和占用空间，
列出将要删除的内容，确认后自动清理：

- 安装目录
- 桌面快捷方式
- 用户 PATH 里的 nanoamp 条目
- `.Renviron` 里的 `R_LIBS_USER` 行

**用户自行安装的 R、已有的 R 库、测序数据和结果文件都不会被删除。**

> 如果 nanoamp 窗口还开着，部分文件可能删不掉。关闭窗口后再运行一次即可。

### 命令行里输入 `nanoamp` 提示不是内部或外部命令

PATH 的修改需要新开一个命令行窗口才生效。若仍无效，可手动把
`%LOCALAPPDATA%\nanoamp\bin` 加进用户 PATH。

---

## 7. 面向开发者：源码与二次开发

以上为面向使用者的部分。以下是本仓库作为**开发仓库**的结构。

### 仓库结构

```text
release/             ← 发布产物：三个交付形态 + 安装器
  01_R-package/      R 包发行版（tarball + 安装说明）
  02_CLI/            命令行发行版（启动器 + 说明）
  03_GUI/            图形界面发行版（nanoamp.exe + 说明）
  install.exe        安装器（构建产物）
  uninstall.exe      卸载器（构建产物）
  _installer/        安装器与卸载器源码
  deps/              固定版本依赖清单（联网安装用；进 setup 资产）
  _offline/          离线依赖源材料（R 安装器、R 包、minimap2；进 offline-deps 资产）
  _build/            打包工作区（两个 zip 与 SHA256SUMS.txt；zip 不进 Git）
02_code/             源码
  r/                 nanoamp R 包源码
  cli/               CLI 入口脚本（make cli 用）
  gui/               R Shiny 图形界面（make gui 用）
  PythonGUI/         Python/Tkinter 图形界面源码（发行版 GUI 即其产物）
  shared/            参数与输出契约
01_data/             测试数据（`<dataset>/<sample>/` 规范化命名，文件即数据）
03_dependence/       内置的 minimap2.exe、R 环境脚本与编译方案
00_materials/        委托文档、开发方案、历次工作报告、完整教程
  tutorial.md        教程：GUI 版 / CLI 版 / R 包版 + 依赖工具配置
tmp/test_results/    运行输出（Git 忽略）
tmp/builds/          R CMD build / check 产物（Git 忽略）
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

# 安装器 + 卸载器 exe（需要 pip install pyinstaller）
python release/_installer/build_exe.py

# 自测
python release/_installer/test_installer_logic.py    # 安装器逻辑，不实际安装
python release/_installer/test_release_layout.py     # 三个交付形态的布局自检
python release/_installer/test_window_fit.py         # 两个窗口不会被内容挤出边界
python release/_installer/test_locked_file_retry.py  # 文件被占用时的重试与报错
python release/_installer/test_r_version_choice.py   # 系统 R / 随包 R 的选择规则
python release/_installer/test_pinned_deps.py        # 固定版本清单、选源与 minimap2 来源
```

查看两个窗口的实际渲染效果（需要 `pip install pywinauto pillow`，仅开发用）：

```powershell
# 安装器：默认路径、换到 D 盘、盘符不存在三种状态
python release/_installer/inspect_installer_live.py tmp/test_results/shots

# 卸载器：在沙箱里造一份假安装，截图后再删掉，不修改真实系统
python release/_installer/capture_uninstaller_populated.py tmp/test_results/shots
```

### 外部工具与平台说明

- `minimap2.exe` 由本仓库从上游源码编译并**静态链接**，只依赖
  `KERNEL32.dll` 和 `msvcrt.dll`，因此目标机器无需 MSYS2 / Cygwin / conda / WSL。
- `samtools` **不需要**：SAM→BAM 默认由 `Rsamtools::asBam()` 完成。
- 本项目**不使用 conda，也不使用 WSL**。
- 本仓库是 **Windows 变体**；Linux 变体在姊妹仓库
  `a_09_18_26_mapping_programs_dev_for_linux`。

### 文档索引

| 文档 | 内容 |
|---|---|
| `00_materials/tutorial.md` | **完整教程**：GUI 版、CLI 版、R 包版安装使用 + 外部依赖工具配置 |
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
4. **功能注释的两条路线限制不同**：
   - **离线 CDS 路线**（GUI 里的「离线 CDS（不联网）」）：不需要联网，但 CDS 长度必须是
     3 的倍数、坐标必须由使用者按自己的扩增子给出；长度不对时**跳过该注释并记账**
     （`qc.tsv` 的 `n_transcripts_skipped` / `annotation_skip_reason`），退出码仍为 0。
   - **在线 genome 路线**（「在线 genome（需联网）」）：需要能访问 Ensembl REST；
     扩增子不在内置 panel（当前仅 ZNF8）时会退化为逐染色体扫描，**可能非常慢**；
     参考序列与 GRCh38 匹配不足（锚定覆盖率 < 0.9）时会**明确报错**而不是凭猜测给坐标。
   - 注释结果依赖 Ensembl release（会记录在 `run_manifest.json` 的
     `annotation.ensembl_release`）；`protein_change` 是 HGVS 风格但**未经 HGVS 认证**，
     不应当作临床报告依据。
5. **测试数据是普通文件**：`01_data/<dataset>/<sample>/` 里直接就是
   `reads.fastq` / `reference.self.fa` / `consensus.N.fa` / `variants.N.xlsx` /
   `sanger.N.ab1`，随仓库一起提交，**克隆后不需要任何准备步骤**。
   每个样本目录里的 `meta.tsv` 记录这些文件原本是公司的哪个交付文件。
   详见 `01_data/README.md`。
6. **仓库体积**：`.git` 里含 `release/_offline` 的离线负载（R 安装器 87 MB 等），
   完整克隆约 320 MB。发布包可直接解压使用，使用者不需要克隆仓库。

---

## 许可证

MIT。
