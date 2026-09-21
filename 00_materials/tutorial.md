# nanoamp 使用教程（Windows 版）

本文是**照着做就能出结果**的教程。三道菜：

| 部分 | 给谁看 | 你会学到 |
|---|---|---|
| [第 1 部分 GUI 版](#第-1-部分-gui-版使用教程) | 不写代码的人（绝大多数情况用这个） | 双击图标 → 选两个文件 → 点按钮 → 看结果 |
| [第 2 部分 CLI 版](#第-2-部分-cli-版使用教程) | 要一次跑几十个样本的人 | 命令行 `nanoamp call` / `nanoamp batch` |
| [第 3 部分 R 包与依赖配置](#第-3-部分-r-包安装与外部依赖工具配置教程) | 要把分析写进自己流程的人 | 装 R 包、装 minimap2、排错 |

---

## 0. 开始之前

### 0.1 这个软件干什么

你从测序公司拿到一个样本一个的 `fastq` 文件。你想知道三件事：

1. 这个样本里，有多少条序列是**我设计的那个序列**？
2. 剩下的序列**哪里不一样**（哪个碱基变了、哪里多了、哪里少了）？
3. 各占**多少比例**？

nanoamp 就是回答这三个问题的。

### 0.2 术语速查（看一次就懂）

| 词 | 大白话 |
|---|---|
| **FASTQ** | 测序公司给你的原始数据文件，扩展名 `.fastq`（可能压缩成 `.fastq.gz`） |
| **FASTA / 目的序列 / 参考序列** | 你**期望**得到的正确序列，一个 `.fa` 或 `.fasta` 文件 |
| **read / 条** | 测序仪读出的一条序列。"426 条 reads" = 426 条序列 |
| **单倍型 / haplotype** | 一组**完全相同**的（校正后）序列。H1、H2 就是两种不同的序列 |
| **占比 / proportion** | 这个单倍型占全部 reads 的百分比。← **你最关心的数字** |
| **校正 / correction** | 先把测序错误改掉，再统计。见 0.4 节 |
| **模式 A / B / C** | 三种算法。**日常只用 A**，理由见 0.3 节 |

### 0.3 三种模式：默认用 A

| 模式 | 做什么 | 什么时候用 |
|---|---|---|
| **A（默认，推荐）** | 参考引导校正 + 单倍型计数 | **有靠谱的目的序列时的常规定量。用这个。** |
| **B** | 从头聚类（不需要参考） | 没有可靠参考、想纯数据驱动地看看有哪几簇 |
| **C** | 原始 reads 精确匹配 | **只用于诊断**，展示测序错误的影响。**不要用它做定量** |

> 图形界面里还有一个"模式"下拉框，请保持 `A - 参考引导（推荐）`。

### 0.4 为什么不能直接数？—— 全文最重要的一段

纳米孔测序**每一条 read 都有约 0.5%–2% 的测序错误**。

所以如果你把原始 read 直接去和目的序列一位一位地比：

- 一条 500 bp 的 read，即使它来自正确的目的序列，也常常有 1–3 个碱基是测错的；
- 结果就是"一字不差"的 read 只占一部分。本教程用的 E4-3 样本只有 **9.4%**
  （模式 C 的 `exact_any_proportion`），别的样本也大多在 2%–20% 之间 ——
  差别取决于测序质量、序列长度和真实混样比例。

**这不是实验失败，是测序错误把真实结果掩盖了。**

nanoamp 的做法是：先比对 → 找出候选变异 → 把不满足可信度门槛的差异**当成测序错误改掉** → 再按"校正后的序列"分类计数。

所以 nanoamp 给出的 33.3% / 31.5% / 26.8% 才是可信的比例。注意
`exact_reference_proportion`（见 §1.4.2）**不是**校正前的原始匹配率，而是
**校正后**仍然等于目的序列的那一类所占的比例 —— 它和结果表里
`is_reference = 是` 的占比本来就是同一个数。要"完全不校正"的原始匹配率，
请看模式 C 的 `exact_any_proportion`。

> 记住一句话：**看到"完全一致只有 3%"不要慌，那是测序错误，不是你的实验。**

### 0.5 准备工作（一次性）

1. 把收到的 `release` 文件夹**完整解压**到一个**路径里没有中文、没有空格**的地方，例如 `D:\nanoamp\`。
2. 双击解压后的 **`install.exe`** → 点「开始安装」→ 等 3–10 分钟。
3. 安装完成后，桌面会出现 **「nanoamp 分析工具」** 快捷方式。

安装程序做的事（**全程不需要联网，不需要管理员权限**）：

| 步骤 | 内容 |
|---|---|
| 1 | 找到或安装 R（要求 ≥ 4.2） |
| 2 | 安装 R 依赖包（共 109 个，全部来自安装包自带，不联网） |
| 3 | 安装 nanoamp 主程序 |
| 4 | 注册 `nanoamp` 命令（可取消） |
| 5 | 创建桌面快捷方式「nanoamp 分析工具」（可取消） |
| 6 | 安装比对程序 `minimap2.exe` 到安装目录的 `bin\` |
| 7 | 自检 |

装到哪了（默认）：

```text
%LOCALAPPDATA%\nanoamp\            安装目录，即 C:\Users\<你的用户名>\AppData\Local\nanoamp
  R\lib\                           109 个 R 依赖包 + nanoamp 包
  app\nanoamp.exe                  图形界面
  bin\nanoamp.cmd                  命令行启动器
  bin\minimap2.exe                 比对程序
  config\                          生成的 R 驱动脚本与日志
  config.ini                       安装记录

%USERPROFILE%\Documents\.Renviron  一行 R_LIBS_USER，指向上面的 R\lib
%USERPROFILE%\Desktop\nanoamp 分析工具.lnk
用户 PATH                          追加 %LOCALAPPDATA%\nanoamp\bin
```

想验证装好了没有：

```bat
nanoamp doctor
```

或者（不安装、只检查）：

```bat
release\install.exe --check
```

卸载：双击 `release\uninstall.exe`。**你自己装的 R、你的数据和结果文件都不会被删除。**

### 0.6 本教程用的测试样本

全教程都用仓库里这一份真实测试数据，方便你对照：

```text
01_data\TSM20260826\E4-3\reads.fastq            ← 测序数据
01_data\TSM20260826\E4-3\reference.self.fa      ← 目的序列
```

**这份数据的正确结果是**（下文的每一步都以此为准）：

```text
排名  编号  reads 数  占比     是否一致   变异
 1    H1     142    33.3%     否       218delG
 2    H2     134    31.5%     是       .
 3    H3     114    26.8%     否       218delG;135C>T
```

`qc.tsv` 里应看到：

```text
n_reads_total      438
n_reads_primary    437
n_reads_used       426
mapping_rate       0.9977
reference_length   529
```

如果你的运行结果和上面**不完全一样**，先别慌，对照第 1.6 节逐项检查。

---

# 第 1 部分：GUI 版使用教程

> 图形界面版（GUI）是给不写代码的人用的。**只跑一两个样本，就用它。**

## 1.1 打开窗口

两种方式，选一个：

| 方式 | 操作 | 什么时候用 |
|---|---|---|
| **桌面快捷方式** | 双击桌面上的 **「nanoamp 分析工具」** | 正常安装过的机器，推荐 |
| **直接运行 exe** | 双击 `release\03_GUI\nanoamp.exe` | 想跳过安装；但前提是**已经跑过一次 `install.exe`**（R 和依赖都就位了） |

> ⚠️ `nanoamp.exe` 里**只有界面**（约 10 MB），**不含 R 运行时**。R 和 109 个依赖包由 `install.exe` 安装。
> 所以在一台全新的机器上直接双击 `nanoamp.exe` 是打不开分析的。

打开后窗口长这样（从上到下四块）：

```text
┌─────────────────────────────────────────────────────────┐
│  nanoamp - 纳米孔 PCR 产物分析                            │
│  分析逻辑由 nanoamp R 包执行，本窗口只是调用它的外壳。      │
├─────────────────────────────────────────────────────────┤
│  输入                                                    │
│   测序文件 (FASTQ)  [__________________] [浏览…]         │  ← ① 选 fastq
│   目的序列 (FASTA)  [__________________] [浏览…]         │  ← ② 选参考序列
│   输出目录          [__________________] [浏览…]         │  ← ③ 结果放哪
│   模式 [A - 参考引导 ▾]   显示前 n 条 [20]                │  ← ④ 一般不用改
├─────────────────────────────────────────────────────────┤
│  [单倍型结果] [QC 指标] [输出文件] [运行日志]              │  ← ⑤ 结果在这里
│  排名 │ 编号 │ reads 数 │ 占比 │ 是否与目的序列一致 │ ...  │
│  ...                                                     │
│  ┌ 选中某一行可查看该单倍型的完整序列 ────────────────┐    │
├─────────────────────────────────────────────────────────┤
│  [开始分析] [环境自检]              [打开输出目录]  ▓▓▓  │  ← ⑥ 点这里开始
│  就绪。选择 FASTQ 和参考序列后点击"开始分析"。             │
└─────────────────────────────────────────────────────────┘
```

先认一下部件：

| 部件 | 作用 |
|---|---|
| **测序文件 (FASTQ)** | 公司给的 `.fastq` 文件 |
| **目的序列 (FASTA)** | 你的预期序列 `.fa` / `.fasta` |
| **输出目录** | 结果放哪。默认 `我的文档\nanoamp 结果`，一般不用改 |
| **模式** | 保持 `A - 参考引导（推荐）` |
| **显示前 n 条** | 结果表里最多列出多少种单倍型，保持 `20` |
| **单倍型结果** 标签页 | 核心结果表 |
| **QC 指标** 标签页 | 数据质量 |
| **输出文件** 标签页 | 本次生成的文件的清单，双击可用系统默认程序打开 |
| **运行日志** 标签页 | R 的实时输出，**出错时看这里** |
| **开始分析** 按钮 | 启动分析（后台线程，窗口不会卡死） |
| **环境自检** 按钮 | 跑一次 `nanoamp doctor`，把 R / 依赖 / minimap2 的状态写进日志 |
| **打开输出目录** 按钮 | 在资源管理器里打开结果文件夹 |

## 1.2 填四个输入（逐步操作）

**第 1 步：选测序文件**

1. 点 **测序文件 (FASTQ)** 右边的「浏览…」。
2. 文件类型选 `FASTQ`，找到并双击：

   ```text
   01_data\TSM20260826\E4-3\reads.fastq
   ```

3. 选好后，如果你的 `reads.fastq` 同目录下正好有 `reference.self.fa`，
   程序会**自动**把参考序列填上。本样本就会自动填上
   `01_data\TSM20260826\E4-3\reference.self.fa`。

**第 2 步：确认目的序列**

如果第 1 步没有自动填，就自己点 **目的序列 (FASTA)** 的「浏览…」，选中：

```text
01_data\TSM20260826\E4-3\reference.self.fa
```

> 本题的关键：**参考序列必须是"这个样本的预期序列"**，不能拿别的样本的。
> 拿错了，结果里"是否一致"几乎全是"否"。

**第 3 步：输出目录**

默认是 `我的文档\nanoamp 结果`，**不用改**。

> 想改就点「浏览…」。建议用纯英文路径，例如 `D:\nanoamp_results\E4-3`。
> 注意：**界面里没有"批量"功能**，一次只能跑一个样本。

**第 4 步：模式与前 n 条**

| 字段 | 本教程填什么 | 说明 |
|---|---|---|
| **模式** | `A - 参考引导（推荐）` | 默认值就是它 |
| **显示前 n 条** | `20` | 默认值。调大能让 `haplotypes.fasta` 保存更多序列 |

## 1.3 点「开始分析」

1. 点 **「开始分析」**。
2. 状态栏会变成 **"正在分析…（首次运行需加载 R 包，可能稍慢）"**，右侧进度条来回滚动。
3. 本样本数据量很小（438 条 reads），**几秒到几十秒**就完成。
4. 完成后状态栏变成：

   ```text
   分析完成，输出目录：<你的输出目录>（12 条单倍型）
   ```

   「打开输出目录」按钮同时变亮。

> 不确定环境是否正常时，**先点一次「环境自检」**，它会把 R、依赖包、minimap2
> 的状态逐行写进「运行日志」。看到 `minimap2` 那一行是路径而不是 `NOT FOUND` 就对了。

## 1.4 看四个标签页

### 1.4.1 「单倍型结果」—— 最常看的一张表

列的含义：

| 列 | 含义 |
|---|---|
| **排名** | 按 reads 数从多到少排 |
| **编号** | H1、H2… 每种不同序列的编号 |
| **reads 数** | 支持这条序列的 reads 条数 |
| **占比** | 占全部 reads 的百分比 ← **你最关心的数值** |
| **是否与目的序列一致** | `是` = 和你要的序列完全一样；`否` = 有差异 |
| **SNV / 插入 / 缺失** | 相对目的序列有几处变异 |
| **变异** | 具体描述，例如 `218delG` = 第 218 位少了一个 G；`.` = 没有变异 |
| **长度** | 这条序列的碱基数 |

**本样本 E4-3 的实际结果，你应该看到完全一样的前三行：**

```text
排名  编号  reads 数  占比     是否一致   变异
 1    H1     142    33.3%     否       218delG
 2    H2     134    31.5%     是       .
 3    H3     114    26.8%     否       218delG;135C>T
```

往下还有 9 行（H4 到 H12，每行只有 1–16 条 reads，占比 0.2%–3.8%）。
**12 条单倍型**就是"12 种不同的序列"。

**怎么读这三行 —— 大白话版：**

- **H2，31.5%，"是"** → 这个样本里有 **31.5% 的序列正是你设计的那个目的序列**。这是最重要的一行。
- **H1，33.3%，"218delG"** → **最多的一种**序列，比目的序列**在第 218 位少了一个 G**（del = deletion = 缺失）。它占了三分之一。
- **H3，26.8%，"218delG;135C>T"** → 这一种**同时**有两个变异：第 218 位少一个 G，**并且**第 135 位的 C 变成了 T（`135C>T` 读作"第 135 位 C→T"）。分号表示两个变异同时存在于同一条序列上。
- 三者相加 ≈ 91.6%，剩下 8.4% 是零零散散的少数序列（H4 的 `135C>T` 单独出现占 3.8% 是其中最大的一种）。

**一个重要的科学结论**：这个样本里"目的序列"只占 31.5%，而**带 218delG 的两种加起来占了 60.1%**。
说明这份样品**不是纯的目的序列**，主体是一个缺了一个 G 的变体。这不是软件出错，而是实验结果——**样品不纯**。

**变异的读法：**

| 写法 | 读作 | 含义 |
|---|---|---|
| `218delG` | 第 218 位缺失 G | 目的序列第 218 位的 G 在这条序列里没有了 |
| `135C>T` | 第 135 位 C 变成 T | 点突变（SNV） |
| `134insT` | 在第 134 位后插入 T | 多了一个碱基 |
| `.` | 无变异 | 与目的序列完全一致 |

**选中任意一行**，表格下方的灰框里会显示这条单倍型的**完整碱基序列**。

> 如果显示"未导出序列，如需其序列，把「显示前 n 条」调大后重新运行"，是因为
> `haplotypes.fasta` 只保存前 n 条（默认 20）。调大后重跑即可。

### 1.4.2 「QC 指标」—— 判断数据质量，看这 5 行

本样本 E4-3 的实际值：

| 指标 | 本样本实际值 | 怎么看 |
|---|---:|---|
| `n_reads_total` | **438** | 总 reads 数。**低于 100 条时比例不可靠**，低于 50 条基本没意义 |
| `n_reads_primary` | **437** | 比对到主比对位置的 reads 数 |
| `n_reads_used` | **426** | 通过质量过滤、真正参与统计的 reads 数 |
| `mapping_rate` | **0.9977** | 比对成功率 = 437 ÷ 438。**正常应 > 0.95**，本样本 99.8%，非常好 |
| `reference_length` | **529** | 目的序列的长度（bp）。要和你预期的扩增子长度一致 |

QC 表里还会给出更多行，本样本的其它关键值：

| 指标 | 本样本实际值 | 含义 |
|---|---:|---|
| `mean_identity` | 0.9939 | 平均一致度。**正常 0.98 以上**，0.994 说明 reads 质量很好 |
| `n_raw_variants` | 573 | 校正前发现的可疑变异位点（大部分是测序错误） |
| `n_pass_variants` | 4 | 通过门槛、**被认定为真实**的候选变异数 |
| `n_haplotypes` | 12 | 一共分出 12 种不同的序列 |
| `top1_proportion` | 0.3333 | 最多的那一种占 33.3% |
| `top1_is_reference` | FALSE | **最多的那种不是目的序列**（就是 H1 的 218delG） |
| `exact_reference_proportion` | 0.3146 | **校正后**等于目的序列的 reads 占比（与上表 `is_reference = 是` 那一行同值） |

> **注意最后一行**：`exact_reference_proportion` 是**校正后**的占比，
> 所以它和 H2 的 31.5% 本来就是同一个数 —— 不是巧合。
> 它**不是**"测序错误有多严重"的体检指标。
>
> 想知道校正前有多差，用**模式 C** 跑同一个样本，看 `exact_any_proportion`：
> 本样本只有 **0.0936（9.4%）**，其它样本大多在 2%–20%。那个数字才回答
> "原始 read 里一位不差的占多少"。
>
> 一句话：模式 C 的 `exact_any_proportion` 低 ≠ 实验失败；模式 A 里
> `is_reference = 是` 的占比才是答案，而 `exact_reference_proportion` 就是它。

**573 个候选变异只有 4 个通过**，这个对比本身就是 nanoamp 的价值所在：
它把 569 个测序错误挡在了外面。

### 1.4.3 「输出文件」—— 本次生成的文件

显示文件名和字节数。**双击任意一行用系统默认程序打开**（`.tsv` 会用 Excel 打开）。

本样本 E4-3 会生成：

| 文件 | 大小（本样本） | 内容 |
|---|---:|---|
| `haplotypes.tsv` | 1.5 KB | **单倍型表**（就是 1.4.1 那张表），可用 Excel 打开 |
| `haplotypes.fasta` | 2.7 KB | 前 n 条单倍型的**完整序列** |
| `variants.tsv` | 86 KB | 所有候选变异位点，列名与公司 `*.var.xls` 兼容 |
| `qc.tsv` | 0.4 KB | 质量指标（就是 1.4.2 那些） |
| `run_manifest.json` | 1.3 KB | 本次运行的参数、版本、输入文件 MD5（可追溯） |
| `alignments.bam` | 133 KB | 比对结果（中间文件） |
| `alignments.bam.bai` | 96 B | 上面那个 BAM 的索引 |
| `alignments.bam.minimap2.log` | 1.1 KB | minimap2 自己的日志 |

### 1.4.4 「运行日志」—— 出错时第一个看的地方

这里按时间顺序显示 R 的每一行输出，包括：

- 你的操作命令（例如 `$ nanoamp call --reads ... --reference ... --outdir ... --mode A --top-n 20`）
- 分析过程的逐步日志
- **「环境自检」的输出**（`nanoamp doctor` 的全部内容）
- **报错的完整堆栈**

**排错顺序：先看「运行日志」的最后 10 行。**

## 1.5 用 Excel 打开结果

1. 打开「输出文件」标签页，双击 `haplotypes.tsv`；**或者**
2. 点「打开输出目录」，在资源管理器里双击 `haplotypes.tsv`。

如果双击没反应、或者 Excel 没有自动关联 `.tsv`：

1. 在文件上点**右键 → 打开方式 → 选择其他应用 → Excel**；
2. 或者先打开 Excel，**文件 → 打开 → 浏览**，把文件类型改成"所有文件"，再选 `.tsv`；
3. 或者把 `haplotypes.tsv` **另存/改名为** `haplotypes.txt`，Excel 就能直接打开。

> ⚠️ **中文乱码怎么办**：nanoamp 输出的 TSV 是 **UTF-8** 编码。
> 如果 Excel 里中文显示成乱码，用 **数据 → 从文本/CSV** 导入，把"文件原始格式"
> 选成 **65001: Unicode (UTF-8)**，再点"加载"。
>
> 💡 用 Excel 看结果**没问题**，但不要用 Excel 把结果"另存为 CSV"再拿去给程序读
> （会破坏制表符分隔）。要看原始文件就用记事本。

## 1.6 结果和预期不一致？逐项对照

| 症状 | 最可能的原因 | 怎么办 |
|---|---|---|
| 双击图标没反应 / 一闪而过 | R 或依赖没装好 | 先双击 `release\install.exe` 跑一次完整安装 |
| 状态栏显示"未找到 R" | `config.ini` 里的 `rscript=` 路径失效 | 重新运行 `install.exe` |
| 点「开始分析」弹"文件不存在" | 选了移动过的文件 | 重新用「浏览…」选一次 |
| 「运行日志」里 `minimap2 NOT FOUND` | minimap2 没装上 | 先点「环境自检」确认；再重跑 `install.exe` 修复 |
| `n_reads_total` 明显不是 438 | 选错了 FASTQ 文件 | 确认选的是 `E4-3\reads.fastq` |
| `reference_length` 不是 529 | 选错了参考序列 | 确认选的是 `E4-3\reference.self.fa` |
| 「是否一致」几乎没有"是" | ①reads 太少 ②参考选错 ③样品真的不纯 | 先看 `n_reads_total`；再确认参考是**本样本**的预期序列；都不是的话，结果就是对的 |
| 分析失败 | ①文件被别的程序占用 ②输出目录没写权限 ③FASTQ 格式不对 | 看「运行日志」最后几行 |
| 中文/含空格路径出错 | 路径编码问题 | 输入和输出都改用 `D:\nanoamp_data\` 这类纯英文无空格路径 |

---

# 第 2 部分：CLI 版使用教程

> 命令行版（CLI）是给**要一次处理几十上百个样本**的人用的。
> 只用同一个分析核心，结果和 GUI **不可能不一致**（GUI 就是调用它）。

## 2.1 打开一个命令行窗口

| 方式 | 操作 |
|---|---|
| **PowerShell（推荐）** | 按 `Win + X` → 选「终端」或「Windows PowerShell」 |
| **cmd** | 按 `Win + R`，输入 `cmd`，回车 |
| **在当前目录直接开** | 在文件资源管理器的**地址栏**里输入 `powershell` 再回车 |

装完 `install.exe` 后**必须新开一个窗口**，PATH 的改动只对新窗口生效。

先确认能用：

```bat
nanoamp doctor
```

如果提示"不是内部或外部命令"，见 2.8 节。

> 想把工作目录切到本仓库：

```bat
cd /d D:\Documents\master_degree\projects\xialab\a_09_18_26_mapping_programs_dev\a_09_18_26_mapping_programs_dev_for_win
```

## 2.2 `nanoamp doctor` —— 先跑这个

```bat
nanoamp doctor
```

本机实际输出（长这样）：

```text
nanoamp version: 0.1.0
R version: R version 4.6.1 (2026-06-24 ucrt)
Rscript: C:/PROGRA~1/R/R-4.6.1/bin/Rscript
platform: windows-x86_64
dependence directory: NOT FOUND
  Biostrings   TRUE
  IRanges      TRUE
  Matrix       TRUE
  Rsamtools    TRUE
  ShortRead    TRUE
  data.table   TRUE
  optparse     TRUE
  jsonlite     TRUE
  readxl       TRUE
  DECIPHER     TRUE
  minimap2     C:\Users\<你的用户名>\AppData\Local\nanoamp\bin\minimap2.exe (2.31-r1302)
  samtools     NOT FOUND
```

**怎么读这份输出 —— 只看 5 件事：**

| 行 | 期望 | 不对怎么办 |
|---|---|---|
| `nanoamp version` | `0.1.0` | 如果是别的版本号，说明装的是旧包，重跑 `install.exe` |
| `R version` | 有版本号，**≥ 4.2** | 报错说找不到 Rscript 就重跑 `install.exe` |
| 各 R 包 | 全部 `TRUE` | 有一个 `FALSE` 就重跑 `install.exe` |
| **`minimap2`** | **一个 `.exe` 的路径 + `(2.31-r1302)`** | 若是 `NOT FOUND`，见第 3.5 节 |
| `samtools` | `NOT FOUND` | **这是正常的，无影响**（见 3.5 节） |

关于 `dependence directory: NOT FOUND`：

- 这是**正常的**。它指的是仓库里的 `03_dependence\` 目录。
  安装版把 minimap2 放进了安装目录的 `bin\`，所以这一行显示 NOT FOUND 完全不影响使用。
- 只有在仓库目录里直接跑源码时，它才会显示 `...\03_dependence`。

`DECIPHER` 是 `FALSE` 也能跑（只影响模式 B，会退化成贪心聚类）。

## 2.3 `nanoamp call` —— 分析一个样本（本教程主角）

用本仓库的 E4-3 测试数据，**复制下面整段到 PowerShell 直接回车**：

```powershell
nanoamp call --reads "01_data\TSM20260826\E4-3\reads.fastq" --reference "01_data\TSM20260826\E4-3\reference.self.fa" --mode A --top-n 20 --outdir "tmp\test_results\demo\E4-3"
```

> 上面是一整行。在 PowerShell 里想换行写，行尾用反引号 `` ` ``；
> 在 cmd 里换行，行尾用 `^`。

**预期输出**（末尾会打印结果表）：

```text
rank  haplotype_id  count  proportion  is_reference  variants
1     H1            142    0.333       FALSE         218delG
2     H2            134    0.315       TRUE          .
3     H3            114    0.268       FALSE         218delG;135C>T
...
```

（`proportion` 是小数，`0.315` 就是 31.5%。GUI 里显示成百分比是为了好读。）

跑完后 `tmp\test_results\demo\E4-3\` 里就是 1.4.3 节列的那 8 个文件。

## 2.4 nanoamp call 的全部参数

| 参数 | 默认值 | 说明 | 什么时候改 |
|---|---|---|---|
| `--reads` | **必填** | 输入 FASTQ（可 `.gz`） | 每次都要给 |
| `--reference` | **必填** | 目的序列 FASTA | 每次都要给 |
| `--outdir` | **必填** | 输出目录（不存在会自动创建） | 每次都要给 |
| `--mode` | `A` | `A` 参考引导 / `B` 从头聚类 / `C` 精确匹配 | 日常保持 A；C 只做诊断 |
| `--top-n` | `20` | 输出前 n 条单倍型 | 想看更多稀有序列时调大（如 100） |
| `--min-reads` | `3` | 一个候选变异至少要多少条 reads 支持才算真的 | 深度很低的数据可降到 2 |
| `--min-freq` | `0.02` | 候选变异最低频率（2%） | 想找 1% 以下的稀有变异可降到 0.01 |
| `--min-identity` | `0.90` | read 与参考的最低一致度 | 数据质量差时可降到 0.85 |
| `--identity-cutoff` | `0.99` | **仅模式 B** 的聚类阈值 | 只有用 B 时才管 |
| `--min-cluster-reads` | `2` | **仅模式 B** 的最小簇大小 | 只有用 B 时才管 |
| `--consensus-method` | `decipher` | **仅模式 B**：`decipher` 或 `medoid` | 只有用 B 时才管 |
| `--aligner` | `minimap2` | 换成 `r` 用 R 内比对（**无需外部程序**，较慢） | 没有 minimap2 时用（见 3.6） |
| `--threads` | `4` | 线程数 | 机器核多就调大，如 `--threads 8` |
| `--ref-label` | 参考文件名 | 输出里显示的参考名称 | 想让 `variants.tsv` 的 `Chr` 列短一点/好看一点 |
| `--no-intermediates` | 关（即保留） | 不保留 `alignments.bam` 等中间文件 | 只想留 TSV、省空间时加上 |

**只改一个参数的例子**（想看前 100 条单倍型，并用 8 线程）：

```powershell
nanoamp call --reads "01_data\TSM20260826\E4-3\reads.fastq" --reference "01_data\TSM20260826\E4-3\reference.self.fa" --mode A --top-n 100 --threads 8 --outdir "tmp\test_results\demo\E4-3_top100"
```

**不带 BAM 中间文件的例子**：

```powershell
nanoamp call --reads "01_data\TSM20260826\E4-3\reads.fastq" --reference "01_data\TSM20260826\E4-3\reference.self.fa" --mode A --no-intermediates --outdir "tmp\test_results\demo\E4-3_lean"
```

## 2.5 `nanoamp batch` —— 批量分析

### 2.5.1 准备样本表（sample sheet）

样本表是一个 **TSV**（制表符分隔的纯文本），**至少要有三列**：

```text
sample	reads	reference
```

- 第一行是**列名**，必须正好是 `sample`、`reads`、`reference`（小写）。
- 可选第四列 `ref_label`。
- 每行一个样本。
- 分隔符是**制表符（Tab）**，不是逗号！这是最容易错的地方。

在本仓库根目录新建一个文件 `samples.tsv`，内容如下
（**列之间必须是真正的 Tab 键，不是空格**）：

```text
sample	reads	reference
E4-3	01_data/TSM20260826/E4-3/reads.fastq	01_data/TSM20260826/E4-3/reference.self.fa
E4-9	01_data/TSM20260826/E4-9/reads.fastq	01_data/TSM20260826/E4-9/reference.self.fa
E4-19	01_data/TSM20260826/E4-19/reads.fastq	01_data/TSM20260826/E4-19/reference.self.fa
```

> **用 Excel 存 TSV 的正确姿势：**
> 1. 在 Excel 里把三列填好（A 列 `sample`，B 列 `reads`，C 列 `reference`）；
> 2. **文件 → 另存为 → 保存类型选「文本（制表符分隔）(*.txt)」**；
> 3. **不要选 CSV**（CSV 是逗号分隔，nanoamp 读不了）；
> 4. 存完把扩展名改成 `.tsv`。
>
> **路径里用正斜杠 `/` 最稳**，反斜杠 `\` 在 TSV 里偶尔会被当成转义符。

### 2.5.2 跑批量

```powershell
nanoamp batch --sample-sheet "samples.tsv" --mode A --threads 8 --outdir "tmp\test_results\batch"
```

### 2.5.3 批量结果长什么样

```text
tmp\test_results\batch\
  batch_summary.tsv          ← 汇总表：每个样本一行，含状态
  E4-3\                      ← 每个样本一个子目录，内容与 call 完全一样
    haplotypes.tsv
    haplotypes.fasta
    variants.tsv
    qc.tsv
    run_manifest.json
    alignments.bam ...
  E4-9\
  E4-19\
```

`batch_summary.tsv` 的列：

| 列 | 含义 |
|---|---|
| `sample` | 样本名（来自样本表） |
| `mode` | 用的模式 |
| `outdir` | 这个样本的输出目录 |
| `status` | `ok` = 成功；`error` = 失败 |
| `error` | 失败时的错误信息（成功时为空） |

> 一个样本失败**不会**中断整批。跑完看 `status` 列，`error` 的样本原因写在
> `error` 列里，直接读那一列就够了。
>
> 失败的样本如果什么都没产出，它那个空目录会被自动删掉，所以
> **不要用「有没有目录」判断成功失败** —— 以 `status` 列为准。
> 万一它在失败前已经写了一部分文件，目录会保留下来，方便查现场。

## 2.6 输出目录里到底有什么

每次 `call`（`batch` 的每个子目录也一样）会生成：

```text
<outdir>\
|-- haplotypes.tsv              ← 核心结果：单倍型表
|-- haplotypes.fasta            ← 前 top-n 条单倍型的完整序列
|-- variants.tsv                ← 所有候选变异位点（含 PASS 和 FILTERED）
|-- qc.tsv                      ← 质量指标（两列：metric / value）
|-- run_manifest.json           ← 参数、版本、输入文件 MD5（可追溯）
|-- alignments.bam              ← 比对结果（加了 --no-intermediates 则没有）
|-- alignments.bam.bai          ← BAM 索引
`-- alignments.bam.minimap2.log ← minimap2 的日志
```

### `haplotypes.tsv` 的列（完整版）

| 列 | 含义 |
|---|---|
| `rank` | 排名，按支持 reads 数从多到少 |
| `haplotype_id` | 单倍型编号：H1、H2… |
| `count` | 支持这条序列的 reads 条数 |
| `proportion` | 占比（**小数**，0.333 = 33.3%） |
| `ci_low` / `ci_high` | 占比的 95% 置信区间（Wilson 区间） |
| `is_reference` | 是否与目的序列完全一致（`TRUE` / `FALSE`） |
| `n_snv` / `n_ins` / `n_del` | SNV / 插入 / 缺失的个数 |
| `length` | 这条单倍型的长度（bp） |
| `variants` | 变异描述；`.` 表示无变异 |
| `signature` | 变异的内部机器可读标识（下游程序用，人不用看） |

> **`ci_low` / `ci_high` 是干什么的**：它是"这个百分比有多准"的范围。
> 比如 H2 的 `ci_low=0.272`、`ci_high=0.360`，意思是"真实比例大概在 27.2%–36.0% 之间"。
> 438 条 reads 的样本，区间有接近 9 个百分点宽 —— 这就是低深度数据的客观限制。
> **写文章报比例时建议连区间一起报。**

### `variants.tsv` 的列

列名与公司 `*.var.xls` 兼容：

```text
Chr  Pos  Ref  Alt  DP  Ref_dp  Alt_dp  Freq  DP4  Seq  Filter_Status  Filter_Reason
```

| 列 | 含义 |
|---|---|
| `Chr` | 参考序列名 |
| `Pos` | 位置（1 起算） |
| `Ref` / `Alt` | 参考碱基 / 变异碱基；`-` 表示插入或缺失 |
| `DP` | 该位点总深度 |
| `Ref_dp` / `Alt_dp` | 支持参考 / 支持变异的 reads 数 |
| `Freq` | 变异频率（**0–1 的小数**，不是百分数） |
| `DP4` | 正链参考、负链参考、正链变异、负链变异 的 reads 数 |
| `Seq` | 变异位点周围的序列上下文 |
| `Filter_Status` | `PASS` = 通过，认定为真实变异；`FILTERED` = 被过滤掉（视为测序错误） |
| `Filter_Reason` | 被过滤的原因，如 `supporting reads < 3`、`frequency < 2.0%`、`homopolymer length >= 4 bp with low frequency` |

本样本 E4-3 的 `variants.tsv` 共 **573 行数据，其中只有 4 行是 `PASS`**：

| Pos | Ref | Alt | Alt_dp | Freq | Filter_Status |
|---:|---|---|---:|---:|---|
| 218 | G | - | 270 | 0.63380 | **PASS**（218delG） |
| 135 | C | T | 133 | 0.31221 | **PASS**（135C>T） |
| 134 | - | T | 15 | 0.03521 | **PASS**（134insT） |
| 136 | C | T | 14 | 0.03286 | **PASS**（136C>T） |

这 4 个 PASS 正好对应单倍型表里出现过的 4 种"真实"变异：
`218delG`、`135C>T`、`134insT`、`136C>T`。
其余 **569 行都是 `FILTERED`**（测序错误或支持数不足）。

**这就是"为什么不能直接数"的量化证据**：原始比对给出 573 个"差异"，
nanoamp 判断其中 569 个是测序错误。

### `qc.tsv`

两列：`metric` 和 `value`。本样本 E4-3 的完整内容：

```text
metric	value
mode	A
aligner	minimap2
reference_label	E4-3_TSM20260826-020-01254_20260827-020-BAN05-5_H08.1
reference_length	529
n_reads_total	438
n_reads_primary	437
n_reads_used	426
mapping_rate	0.997717
mean_identity	0.993877
mean_coverage	425.6427
n_raw_variants	573
n_pass_variants	4
n_haplotypes	12
top1_proportion	0.333333
top1_is_reference	FALSE
exact_reference_proportion	0.314554
```

（你运行时 `mean_coverage`、`n_raw_variants` 等可能有极小的差异，
那是比对软件的正常随机性；`n_reads_*`、`mapping_rate`、`reference_length`
和单倍型组成应当完全一致。）

### `run_manifest.json`

记录本次运行的一切，用于**追溯**：nanoamp 版本、模式、时间戳、R 版本、
参考序列的名字/长度/MD5、全部参数、完整 QC 值、reads 文件的 MD5。

**想证明"这张表是哪次运行、用什么参数、拿什么输入跑出来的"，给人看这个文件就行。**

## 2.7 用命令行快速看一眼结果

```bat
:: 只看 QC 里的关键几行
type "tmp\test_results\demo\E4-3\qc.tsv" | findstr "n_reads_total mapping_rate reference_length"

:: 看单倍型表的前 5 行
powershell -Command "Get-Content 'tmp\test_results\demo\E4-3\haplotypes.tsv' -TotalCount 5"

:: 只看 variants.tsv 里通过过滤的真实变异（/R "	PASS" 里的字符是 Tab）
findstr /R "	PASS" "tmp\test_results\demo\E4-3\variants.tsv"
```

PowerShell 里更顺手：

```powershell
Import-Csv "tmp\test_results\demo\E4-3\haplotypes.tsv" -Delimiter "`t" | Select-Object -First 5
```

## 2.8 退出码（写批处理脚本时用）

| 码 | 含义 |
|---:|---|
| **0** | 成功 |
| **1** | 失败（参数错误、文件不存在、依赖缺失、分析出错） |

当前实现所有失败都返回 `1`，更细的退出码是后续改进方向。

在 PowerShell 里判断：

```powershell
nanoamp call --reads "01_data\TSM20260826\E4-3\reads.fastq" --reference "01_data\TSM20260826\E4-3\reference.self.fa" --outdir "tmp\test_results\demo\E4-3"
if ($LASTEXITCODE -ne 0) { Write-Host "分析失败！" } else { Write-Host "分析成功" }
```

在 cmd 里判断：

```bat
nanoamp doctor
if errorlevel 1 echo 环境自检失败
```

## 2.9 `nanoamp` 命令用不了？

| 症状 | 原因 | 解决 |
|---|---|---|
| "不是内部或外部命令" | ①装了但没勾选加 PATH ②窗口是装之前开的 | **新开一个窗口**；仍不行就重跑 `install.exe` 并勾选「把 nanoamp 命令加入用户 PATH」 |
| 新窗口仍不行 | 手工加 PATH | 把 `%LOCALAPPDATA%\nanoamp\bin` 加进**用户** PATH，再新开窗口 |
| 找得到命令、报 R 相关错误 | 驱动脚本里的库路径失效 | 重跑 `install.exe` |

> 另一种不依赖 PATH 的用法：直接用完整路径
> `"%LOCALAPPDATA%\nanoamp\bin\nanoamp.cmd" doctor`。

---

# 第 3 部分：R 包安装与外部依赖工具配置教程

> 这一部分是给**要在 R 里写代码**、或把 nanoamp 嵌进自己分析流程的人。
> 只用 GUI 的人可以跳过，但 **3.5 节（minimap2）值得所有人看一眼**。

## 3.1 安装 R 包：两种方式

### 方式一（推荐）：一键安装器

双击 `release\install.exe`，点「开始安装」。它会自动：

1. 找到或安装 R（≥ 4.2）；
2. 安装 109 个 R 依赖包（来自安装包自带，**全程不联网**）；
3. 安装 `nanoamp` 主程序；
4. 把 R 库指向 `%LOCALAPPDATA%\nanoamp\R\lib`，**通过 `%USERPROFILE%\Documents\.Renviron` 里的 `R_LIBS_USER` 生效**；
5. 安装 `minimap2.exe` 到 `%LOCALAPPDATA%\nanoamp\bin\`。

装完打开 R / RStudio，直接：

```r
library(nanoamp)
```

> 为什么不会污染你原来的 R 库：安装器**不往你已有的库里塞东西**，
> 而是新建一个专门的库（`%LOCALAPPDATA%\nanoamp\R\lib`），
> 再用 `Documents\.Renviron` 里的 `R_LIBS_USER` 把 R 指过去。

### 方式二：手动安装（已有 R ≥ 4.2）

```r
# 第 1 步：装依赖，见 3.2 节的完整清单
# 第 2 步：从本地 tarball 装 nanoamp 本体
install.packages("release/01_R-package/nanoamp_0.1.0.tar.gz", repos = NULL, type = "source")
```

或者先切到仓库根目录再执行上面那句（相对路径就对得上）。
用绝对路径也行：

```r
install.packages("D:/Documents/master_degree/projects/xialab/a_09_18_26_mapping_programs_dev/a_09_18_26_mapping_programs_dev_for_win/release/01_R-package/nanoamp_0.1.0.tar.gz",
                 repos = NULL, type = "source")
```

> 如果提示找不到依赖包：先做完 3.2 节。如果不想自己编译依赖，
> 直接走方式一更省事 —— 一键安装器装好的库是**二进制版**，不用编译。

### 验证装好了

```r
library(nanoamp)
packageVersion("nanoamp")     # 应为 '0.1.0'
nanoamp_cli("doctor")         # 等价于命令行的 nanoamp doctor
```

## 3.2 完整依赖清单

nanoamp 的依赖分两组：**CRAN** 和 **Bioconductor**。

| 组 | 包 | 必需性 | 用途 |
|---|---|---|---|
| **CRAN** | `BiocManager` | 必需 | 用来装 Bioconductor 包的"安装器" |
| **CRAN** | `data.table` | 必需 | 快速处理大表格 |
| **CRAN** | `jsonlite` | 必需 | 写 `run_manifest.json` |
| **CRAN** | `optparse` | 必需 | 解析命令行参数 |
| **CRAN** | `readxl` | 必需 | 读公司的 `*.xlsx` 变异表（用于对照） |
| **CRAN** | `shiny` | 可选 | R Shiny 图形界面 |
| **CRAN** | `DT` | 可选 | R Shiny 里的交互表格 |
| **Bioconductor** | `Biostrings` | **必需** | 序列读写与操作 |
| **Bioconductor** | `IRanges` | **必需** | 区间运算 |
| **Bioconductor** | `Rsamtools` | **必需** | **SAM → BAM 转换（这就是不需要 samtools 的原因）** |
| **Bioconductor** | `ShortRead` | **必需** | 读 FASTQ |
| **Bioconductor** | `Matrix` | 必需（CRAN/Bioc 均有） | 稀疏矩阵，聚类用 |
| **Bioconductor** | `DECIPHER` | 可选（推荐） | **模式 B** 的从头聚类。不装会退化成贪心聚类 |
| **Bioconductor** | `pwalign` | 可选 | **`aligner = "r"` 时需要**（Bioconductor ≥ 3.19） |

### 分组的安装命令（直接复制）

```r
# ---- CRAN 组 ----
install.packages(c("BiocManager", "data.table", "jsonlite", "optparse", "readxl"))

# 可选：R Shiny 图形界面
install.packages(c("shiny", "DT"))
```

```r
# ---- Bioconductor 组 ----
if (!requireNamespace("BiocManager", quietly = TRUE)) install.packages("BiocManager")

# 必需的核心包
BiocManager::install(c("Biostrings", "IRanges", "Rsamtools", "ShortRead", "Matrix"))

# 可选但推荐：模式 B 的聚类引擎
BiocManager::install("DECIPHER")

# 可选：只有在用 aligner = "r" 时才需要（Bioconductor >= 3.19）
BiocManager::install("pwalign")
```

### 一条命令装全套（省事版）

```r
install.packages(c("BiocManager", "data.table", "jsonlite", "optparse", "readxl", "shiny", "DT"))
BiocManager::install(c("Biostrings", "IRanges", "Rsamtools", "ShortRead", "Matrix", "DECIPHER", "pwalign"))
```

装完再装本体：

```r
install.packages("release/01_R-package/nanoamp_0.1.0.tar.gz", repos = NULL, type = "source")
```

> **关于 `Matrix`**：Bioconductor 上也能装到，CRAN 上也有。两边都列一份没有坏处。

## 3.3 检查依赖装全了没有

```r
library(nanoamp)
nanoamp_cli("doctor")
```

看哪些行是 `FALSE`。逐项对照 3.2 节的表格补装即可。

也可以只查一个包：

```r
requireNamespace("Biostrings", quietly = TRUE)   # 应为 TRUE
```

## 3.4 安装 R 包时的常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| `there is no package called 'Biostrings'` | 只装了 CRAN 组，没装 Bioconductor 组 | 执行 3.2 节的 Bioconductor 命令 |
| 装 `pwalign` 报"没有这个包" | 你的 Bioconductor 版本 < 3.19 | 这台机器用 minimap2 就行，不需要 `pwalign`；或升级 R 与 Bioconductor |
| 装源码包要编译、报错缺工具链 | 手动装依赖走的是源码路线 | **改用一键安装器**，它装的是二进制包，不需要编译 |
| `library(nanoamp)` 报"不存在叫 'nanoamp' 这个名字的包" | 本体没装，或装到了另一个 R 库 | 见 3.8 节 |

## 3.5 外部工具：`minimap2`（重要）

### 它是干什么的

`minimap2` 是一个**比对程序**：把每一条 read 放到目的序列上，找出它对应的位置。
nanoamp 自己不做比对，这一步外包给 minimap2。**模式 A 和模式 B 都需要它。
模式 C 不需要。**

### 好消息：已经内置，你不用装

仓库里带了一个**原生 Windows、静态链接**的 minimap2：

```text
03_dependence\windows-x86_64\bin\minimap2.exe
```

"静态链接"的意思是：它只依赖 `KERNEL32.dll` 和 `msvcrt.dll`
—— 这两个是 Windows 自带的。所以它**不需要 MSYS2、Cygwin、conda、WSL**，
也不需要你配任何环境变量。

**`install.exe` 会把这个 `minimap2.exe` 复制到安装目录**：

```text
%LOCALAPPDATA%\nanoamp\bin\minimap2.exe
```

所以你装完之后通常**什么都不用做**。

> 顺带说明：`conda install minimap2 samtools` 这条路是走不通的
> —— 这些包没有 Windows 构建，而且**本项目全程不使用 conda，也不使用 WSL**。

### nanoamp 怎么找到 minimap2（解析顺序）

nanoamp 按下面这个顺序逐级查找，**找到第一个就用**：

| 顺序 | 位置 | 说明 |
|---:|---|---|
| 1 | 环境变量 **`NANOAMP_MINIMAP2`** | 指向一个具体的 `minimap2.exe`。**优先级最高** |
| 2 | **`03_dependence\<os>-<arch>\bin\`** | 即仓库内 `03_dependence\windows-x86_64\bin\minimap2.exe` |
| 3 | **`PATH`** | 系统 PATH 里的任何 `minimap2` |

补充说明：

- 环境变量 `NANOAMP_DEPENDENCE_DIR` 可以把"第 2 级"整个换成别的目录。
- 安装版的做法是：生成的 CLI 驱动脚本里**直接写死** `NANOAMP_MINIMAP2`
  （指向 `%LOCALAPPDATA%\nanoamp\bin\minimap2.exe`），所以**不会误用到系统里别的副本**。
- 有 `NANOAMP_SAMTOOLS` 这个变量，但本项目用不到 samtools（见下）。

### 怎么验证它被找到了

在 R 里：

```r
library(nanoamp)
nanoamp:::nanoamp_tool_path("minimap2")
# 安装版："C:/Users/<你的用户名>/AppData/Local/nanoamp/bin/minimap2.exe"
# 仓库里： ".../03_dependence/windows-x86_64/bin/minimap2.exe"

nanoamp:::nanoamp_tool_version("minimap2")
# "2.31-r1302"
```

在命令行里：

```bat
nanoamp doctor
```

看到这样一行就对了：

```text
  minimap2     C:\Users\<你的用户名>\AppData\Local\nanoamp\bin\minimap2.exe (2.31-r1302)
```

### `samtools` 不需要 —— 别去找它

| 问题 | 答案 |
|---|---|
| 需要装 samtools 吗？ | **不需要。** |
| 为什么？ | minimap2 输出的是 **SAM**，nanoamp 需要的是 **BAM**。这个转换由 R 包 **`Rsamtools::asBam()`** 完成，**不需要外部程序**。 |
| 我 `nanoamp doctor` 里看到 `samtools NOT FOUND` | **正常，无影响。** 不要为此做任何事。 |
| 什么时候才需要 samtools？ | 只有你**显式**设置 `use_samtools = TRUE` 时才需要 —— 那就得自己编译，不推荐。 |

### `minimap2` 显示 `NOT FOUND` 怎么办

按顺序试：

1. 重新运行 `release\install.exe`（勾选正常选项），它会重新复制 `bin\minimap2.exe`；
2. 手工把 `03_dependence\windows-x86_64\bin\minimap2.exe` 复制到
   `%LOCALAPPDATA%\nanoamp\bin\`；
3. 或者设一个环境变量指向仓库里的副本（**只对当前窗口有效**）：

   ```powershell
   $env:NANOAMP_MINIMAP2 = "D:\Documents\master_degree\projects\xialab\a_09_18_26_mapping_programs_dev\a_09_18_26_mapping_programs_dev_for_win\03_dependence\windows-x86_64\bin\minimap2.exe"
   nanoamp doctor
   ```

4. 确认杀毒软件没有把 `minimap2.exe` 删掉。

## 3.6 完全不想用 minimap2？用 R 内比对后端

`aligner = "r"` 让 nanoamp 改用 **R 自己的成对比对**来替代 minimap2，
**一个外部程序都不需要**。

```r
run_haplotype_analysis(
  reads     = "01_data/TSM20260826/E4-3/reads.fastq",
  reference = "01_data/TSM20260826/E4-3/reference.self.fa",
  outdir    = "tmp/test_results/r/demo/E4-3_r",
  mode      = "A",
  aligner   = "r"
)
```

命令行等价写法：

```powershell
nanoamp call --reads "01_data\TSM20260826\E4-3\reads.fastq" --reference "01_data\TSM20260826\E4-3\reference.self.fa" --mode A --aligner r --outdir "tmp\test_results\demo\E4-3_r"
```

**什么时候用它：**

- `minimap2` 在你机器上跑不起来（例如 **Windows on ARM**，没有对应的构建）；
- 你想做到"零外部依赖"；
- 数据量很小（几百条 reads 的扩增子），慢一点无所谓。

**代价：**

- **慢**。适合中小扩增子，不适合大数据量。
- 需要 **`pwalign`** 包（**Bioconductor ≥ 3.19** 把 `pairwiseAlignment()`
  从 `Biostrings` 挪到了 `pwalign`）：

  ```r
  BiocManager::install("pwalign")
  ```

  不装会报类似这样的错：

  ```text
  pairwiseAlignment is not an exported object from 'namespace:Biostrings'
  ```

- 单纯想看"原始精确匹配"用**模式 C**，它也不需要任何外部工具：

  ```r
  run_haplotype_analysis(reads = "...", reference = "...", outdir = "...", mode = "C")
  ```

## 3.7 在 R 里跑完 E4-3（完整例子 + 预期结果）

**打开 R 或 RStudio，把下面整段复制进去执行：**

```r
library(nanoamp)

res <- run_haplotype_analysis(
  reads     = "01_data/TSM20260826/E4-3/reads.fastq",
  reference = "01_data/TSM20260826/E4-3/reference.self.fa",
  outdir    = "tmp/test_results/r/demo/E4-3",
  mode      = "A",     # 参考引导（默认，推荐）
  top_n     = 20
)

# 单倍型表（核心结果）
res$haplotypes

# 候选变异位点
res$variants

# 质量指标
res$qc
```

> 用相对路径时，请先把工作目录设到仓库根目录：
> `setwd("D:/Documents/master_degree/projects/xialab/a_09_18_26_mapping_programs_dev/a_09_18_26_mapping_programs_dev_for_win")`。

**预期结果**（`res$haplotypes` 的前三行）：

```text
  rank haplotype_id count proportion    is_reference          variants
1    1           H1   142  0.3333333         FALSE           218delG
2    2           H2   134  0.3145540          TRUE                 .
3    3           H3   114  0.2676056         FALSE   218delG;135C>T
```

**预期 QC**（`res$qc` 的关键项）：

```text
reference_length   529
n_reads_total      438
n_reads_primary    437
n_reads_used       426
mapping_rate       0.997717
n_haplotypes       12
```

**同时** `tmp/test_results/r/demo/E4-3/` 下会写出和命令行完全一样的那些文件
（`haplotypes.tsv`、`haplotypes.fasta`、`variants.tsv`、`qc.tsv`、
`run_manifest.json`、`alignments.bam`）。

### 其它常用调用

```r
# 看一眼所有参数的默认值
nanoamp_defaults()

# 查看某个函数的完整帮助
?run_haplotype_analysis

# 从 R 里直接调命令行接口（等价于命令行的 nanoamp call）
nanoamp_cli(c("call",
              "--reads",     "01_data/TSM20260826/E4-3/reads.fastq",
              "--reference", "01_data/TSM20260826/E4-3/reference.self.fa",
              "--mode",      "A",
              "--top-n",     "20",
              "--outdir",    "tmp/test_results/r/demo/E4-3"))

# 只保留 TSV，不写 BAM 等中间文件
res <- run_haplotype_analysis(
  reads = "01_data/TSM20260826/E4-3/reads.fastq",
  reference = "01_data/TSM20260826/E4-3/reference.self.fa",
  outdir = "tmp/test_results/r/demo/E4-3_lean",
  keep_intermediates = FALSE
)
```

## 3.8 R 包相关排错

### 找不到 R（R not found）

| 现象 | 解决 |
|---|---|
| 装 `nanoamp` 时报"R 不存在" | 从 <https://cran.r-project.org/bin/windows/base/> 下载安装（一路点"下一步"），或用 `install.exe` 自动装 |
| 命令行 `Rscript` 找不到 | 安装 R 时勾选加入 PATH，或手工把 `R的安装目录\bin` 加进 PATH，然后**新开窗口** |
| 装完 `library(nanoamp)` 仍然失败 | 用 `Rscript -e "cat(R.home())"` 确认你装的 R 和你在用的 R 是同一个 |
| 装了多个 R | 卸载不需要的，或始终用完整路径调用 `Rscript.exe` |

### 包装不上 / `library(nanoamp)` 报错

**症状：**

```text
Error in library(nanoamp) : there is no package called 'nanoamp'
```

**按顺序检查：**

1. **确认装到了哪个库**：

   ```r
   .libPaths()                              # 这台 R 会去哪些目录找包
   "nanoamp" %in% rownames(installed.packages())
   ```

2. **确认 `R_LIBS_USER` 生效了**（一键安装器装好的库在这里）：

   ```r
   Sys.getenv("R_LIBS_USER")
   # 期望：C:/Users/<你的用户名>/AppData/Local/nanoamp/R/lib
   ```

   若为空或不对，检查 `%USERPROFILE%\Documents\.Renviron` 里有没有这一行：

   ```text
   R_LIBS_USER="C:/Users/<你的用户名>/AppData/Local/nanoamp/R/lib"
   ```

   **改完 `.Renviron` 必须重启 R / RStudio 才生效。**

3. **确认包装上了**：

   ```r
   installed.packages()["nanoamp", "LibPath"]
   ```

4. 还不行就重跑 `release\install.exe`。

> 想让某个包在指定库里装，用：
> `install.packages("...", lib = "C:/Users/<你的用户名>/AppData/Local/nanoamp/R/lib")`

### 中文路径 / 非 ASCII 路径

**症状**：安装失败、分析报错、输出文件名乱码。

**原因**：Windows 用户名常含中文（如 `C:\Users\张三\`），
R 和外部程序在一些环节对非 ASCII 路径处理不好。

**解决：**

| 做什么 | 怎么做 |
|---|---|
| 安装包解压位置 | 用 `D:\nanoamp\` 这类**纯英文、无空格**的路径 |
| 输出目录 | 输出到 `D:\nanoamp_results\`，不要输出到桌面 |
| 输入数据 | 把数据拷到 `D:\nanoamp_data\` 再分析 |
| 已经装在中文路径下 | 重新运行 `install.exe`，点「修改…」换到 `D:\nanoamp` |
| 只是想验证是不是路径问题 | 把数据拷到 `C:\temp\test\` 再跑一遍 |

> **注意**：图形界面默认输出到 `我的文档\nanoamp 结果`，
> 而"我的文档"的**真实路径**可能就是含中文的 `C:\Users\张三\Documents`。
> 如果遇到乱码/失败，第一件事就是把输出目录改成 `D:\nanoamp_results\`。

### 其它常见报错对照表

| 报错 | 原因 | 解决 |
|---|---|---|
| `minimap2` not found | 见 3.5 节 | 重跑 `install.exe`，或设 `NANOAMP_MINIMAP2` |
| `pairwiseAlignment` is not an exported object from `Biostrings` | Bioconductor ≥ 3.19 把它挪到了 `pwalign` | `BiocManager::install("pwalign")` |
| `DECIPHER` not installed | 模式 B 需要 | 模式 B 会自动退化成贪心聚类仍能跑；想更好就装上 |
| 模式 B 很慢 | 从头聚类本身开销大 | 减小 `max_msa_seqs`、增大 `threads`，或改用模式 A |
| 模式 C 里所有比例都很低 | **这是预期的** —— 纳米孔 reads 有错误 | 改用模式 A |
| 输入 FASTQ 读不进来 | 文件不是标准 FASTQ / 不是 basecall 过的结果 | nanoamp **不做 basecalling**，输入必须已经是 basecall 过的 FASTQ |

## 3.9 依赖削减现状（为什么依赖这么少）

已经做到的：

1. **默认由 `Rsamtools::asBam()` 完成 SAM→BAM**，`samtools` 命令成为**可选项**；
2. **仓库内自带原生 Windows `minimap2.exe`**，无需任何外部安装步骤；
3. **`aligner = "r"` 提供 R 内成对比对后端**，适合中小数据量以及 Windows on ARM；
4. 大数据量仍推荐 minimap2。

只有确实需要 samtools 路径时才设置 `use_samtools = TRUE`。

---

# 附录 A：一张图记住全流程

```text
测序公司给的 reads.fastq
        │
        │  ① 比对（minimap2；或 aligner="r"）
        ▼
   每条 read 落在目的序列的哪个位置
        │
        │  ② 发现候选变异（本样本 573 个）
        ▼
   用门槛筛：min_reads / min_freq / homopolymer / strand_bias
        │
        │  ③ 没通过的差异 = 测序错误，改掉（本样本筛掉 569 个）
        ▼
   "校正后"的序列
        │
        │  ④ 按序列分组计数
        ▼
   12 种单倍型 ──> haplotypes.tsv（H1 33.3% / H2 31.5% / H3 26.8% …）
                     └─ 其中 H2 = 目的序列 = 31.5%  ← 你要的答案
```

# 附录 B：报错自查清单（三分钟版）

遇到问题，按这个顺序做，90% 的情况能定位：

1. **GUI 用户**：看「运行日志」标签页的**最后 10 行**。
2. **先点/跑 `nanoamp doctor`**（GUI 里是「环境自检」按钮）：
   - R 版本有没有？
   - 每个 R 包是不是 `TRUE`？
   - `minimap2` 那行是路径还是 `NOT FOUND`？（`samtools` 是 `NOT FOUND` **不用管**）
3. **`release\install.exe --check`**：确认安装状态，应当报告"状态：可用"。
4. **检查输入**：文件名对不对？参考序列是不是**本样本**的预期序列？路径里有没有中文和空格？
5. **看 QC**：`n_reads_total` 有多少？低于 100 时比例不可靠。
6. **看 `run_manifest.json`**：确认这次到底用了什么参数、什么输入。

# 附录 C：文档索引

| 文档 | 内容 |
|---|---|
| `README.md` | 仓库根目录总说明 |
| `00_materials/tutorial.md` | **本文 —— 使用教程** |
| `release/README.md` | 发布产物总览与安装器说明 |
| `release/01_R-package/README.md` | R 包版安装与使用 |
| `release/02_CLI/README.md` | CLI 版安装与使用 |
| `release/03_GUI/README.md` | GUI 版安装与使用 |
| `02_code/r/README.md` | R 包完整教程（英文） |
| `02_code/r/README-CN.md` | R 包完整教程（中文） |
| `02_code/r/inst/docs/INSTALL_DEPENDENCIES-CN.md` | 依赖安装与排错 |
| `03_dependence/README.md` | 内置工具与平台支持矩阵 |

# 附录 D：已知限制（避免误会）

1. **依赖 R**：图形界面 exe 只打包界面，不含 R 运行时。
2. **GUI 冷启动约 1–3 秒**：单文件打包每次运行要解压到临时目录。
3. **图形界面没有批量功能**：批量要用命令行的 `nanoamp batch`。
4. **没有 GTF / CDS 功能注释**：不会判断移码 / 提前终止 / missense。
5. **不做 basecalling**：输入必须是已经 basecall 过的 FASTQ。
6. **比例是 reads 层面的估计，不是分子比例**：没有 UMI，无法区分 PCR 重复，
   纳米孔对不同长度序列也可能有捕获偏好。**低深度样本的置信区间会很宽**
   —— 本样本 438 条 reads，H2 的 95% 区间就有 27.2%–36.0% 那么宽，
   所以别把 31.5% 和 33.3% 的差别当成"真的不一样"。
7. **本项目全程不使用 conda，也不使用 WSL。**
