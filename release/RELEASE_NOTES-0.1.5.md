# nanoamp 0.1.5 — Windows 版

纳米孔 PCR 产物分析工具。给它一个 FASTQ 和一个目的序列，它告诉你这个样本里有
多少条序列是**完全正确**的、其余的长什么样、各占多少比例，并且（可选）把这些
变异翻译成**蛋白层面的后果**。

**不需要懂生信、不需要懂编程、不需要联网、不需要管理员权限，全程不使用
conda 也不使用 WSL。**

> **这一版相对 0.1.3 的主要变化**
>
> 1. **可选的功能注释**：把变异翻译成 `frameshift` / `stop_gained` / `missense` /
>    `synonymous` 等后果与 `p.Ala35fs` 这类蛋白变化。两条路线：**离线 CDS**
>    （不联网，自己给 CDS 坐标）与**在线 genome**（程序在 GRCh38 上定位扩增子并
>    从 Ensembl 取转录本结构）。不启用时输出与以前**逐字节一致**。
> 2. **运行状态结构化**：`run_manifest.json` 现在带 `status` / `error_class` /
>    `error_message` / `log_path`，每次运行都写 `nanoamp.log`（失败也写），
>    GUI 会按错误类别给出"怎么办"的提示。
> 3. **GUI 完善**：转录本选择（列出转录本→下拉框指定 ENST）、缓存/网络面板
>    （目录/占用/刷新/清空/测试 Ensembl 连接）、高级参数面板
>    （比对方式/线程/各阈值，**只发送改动过的值**）、可复制的蛋白序列窗口、
>    「注释结果 ↔ 单倍型结果」双向联动筛选、「复制诊断信息」。
>    窗口标题统一为 `nanoamp`，界面里所有路径统一用 `\`（不再出现 `/` 与 `\` 混用）。
> 4. **不再需要 `ShortRead`**：nanoamp 自带 FASTQ 解析器（按 gzip 魔数识别压缩、
>    畸形文件明确拒绝）。
> 5. **修掉若干会让结果不可靠或让人误解的缺陷**：`--no-cache` 不再删除缓存目录；
>    与目的序列完全一致的样本记为 `no_variant`（而不是"同义"）；离线 CDS +
>    负链时等位基因正确反向互补；**Mode B 结果可复现**（聚类引擎随机种子已固定并
>    记入 `qc.tsv` 的 `clustering_seed`）；HTTP 大响应不再被截断；`--aligner r`
>    的覆盖度/一致度按真实比对片段计算（此前会把只覆盖一半的 read 当成全覆盖）。

---

## 下载哪个文件

| 附件 | 大小 | 说明 |
|---|---:|---|
| `nanoamp-0.1.5-windows-setup.zip` | 32.9 MB | **主程序包**：安装器、卸载器、GUI、CLI、R 包、示例注释配置、minimap2 |
| `nanoamp-0.1.0-windows-offline-deps.zip` | 236.5 MB | **离线依赖包**（可选）：R 4.6.1 安装器 + 109 个 R 依赖包 + minimap2 |

两个包**都要**，且**解压到同一个目录**（例如 `D:\nanoamp\`）。只解压主程序包时，
安装器会提示"安装包不完整"（除非选择联网安装）。

```text
D:\nanoamp\
|-- install.exe
|-- uninstall.exe
|-- README.md
|-- 01_R-package\         R 包（tarball + 说明）
|-- 02_CLI\               命令行版说明
|-- 03_GUI\               图形界面版说明
|-- deps\                 固定版本依赖清单
`-- _offline\             离线依赖（只有第二个包里有）
    |-- r\R-4.6.1-win.exe
    |-- r-packages\bin\windows\contrib\4.6\
    `-- minimap2.exe
```

## 安装：三步

1. 把两个压缩包解压到**同一个**、**路径不含中文和空格**的目录，例如 `D:\nanoamp\`。
2. 双击 `install.exe` → 点「开始安装」，等 3–10 分钟。安装位置可改，默认装在
   当前用户目录下（`%LOCALAPPDATA%\nanoamp`），不需要管理员权限；桌面快捷方式与
   PATH 条目默认创建，可取消。
3. 安装完成后双击桌面的「nanoamp 分析工具」。建议先点一次 **「环境自检」**，
   确认 `R version` 是 4.6.x、`minimap2` 显示安装目录下的路径。

安装器做的事：选 R（系统里已有 R 4.6 就直接用，否则用随包的 R 4.6，**不动你原有的 R**）
→ 从 `_offline` 装 109 个依赖包（离线）→ 装 nanoamp R 包 → 复制示例注释配置到
`<安装目录>\configs\` → 放好 `minimap2.exe` → 建快捷方式与命令行入口 → 自检
（含 `curl` / 缓存目录 / 示例配置 / 注释可用性）。

## 用法

| 形态 | 适合谁 | 怎么用 |
|---|---|---|
| **GUI** | 不写代码的人（绝大多数情况） | 双击桌面图标；选 FASTQ、目的序列、输出目录 → 开始分析 |
| **CLI** | 批量处理几十上百个样本 | `nanoamp call` / `nanoamp batch`（详见 `02_CLI/README.md`） |
| **R 包** | 嵌进自己的 R 流程 | `run_haplotype_analysis()`（详见 `01_R-package/README.md`） |

三个形态共用同一套分析核心，结果不会互相矛盾。

### 功能注释（可选）

GUI 勾选「功能注释…」，命令行加 `--annotate-config <config.json>`：

- **离线 CDS 路线**：给出 CDS 在**目的序列**上的起止坐标（1-based，两端都算），
  长度必须是 3 的倍数。不需要网络。
- **在线 genome 路线**：什么都不用给；程序自行在 GRCh38 定位扩增子并从 Ensembl
  取转录本结构。建议先点「列出转录本」确认能定位，并可指定具体 ENST。

产物：`annotation.tsv`（每个「单倍型 × 转录本」一行）、`variants_annotation.tsv`
（每个变异一行，`--annotation-detail`）、`transcripts.tsv`（`--list-transcripts`），
以及 `qc.tsv` 与 `run_manifest.json` 里的注释统计。**被跳过的转录本会记账**
（`annotation_skip_reason` / `annotation.skipped_transcripts`），此时退出码仍是 0；
要让流水线把它当失败，加 `--strict`。

### 三种分析模式

| 模式 | 做什么 | 什么时候用 |
|---|---|---|
| **A**（默认） | 参考引导：比对到目的序列，校正测序错误，保留真实变异 | 有明确目的序列时 |
| **B** | 从头聚类（DECIPHER）：不需要参考序列 | 不知道目的序列长什么样 |
| **C** | 原始精确匹配：不做错误校正 | **只作诊断**，比例会明显偏低 |

用仓库里的 E4-3 样本跑模式 A，预期得到：438 条 reads、426 条参与分析、
`mapping_rate 0.9977`、12 种单倍型、目的序列占 31.5%（H2 = 134 条）。

## 这一版的验证情况

| 验证 | 结果 |
|---|---|
| `R CMD check` | Status: OK |
| 单元测试（testthat） | 48 个用例 / 192 个断言全通过 |
| GUI 自测 / 安装器逻辑自测 | 7 个脚本 / 9 个脚本全部通过 |
| 功能回归（`01_data/` 里 168 个真实运行） | 与提交在仓库里的基线**逐行一致**（`make functional-test`） |
| 环境压力矩阵（离线、代理、缓存损坏、路径含空格与中文、超长路径、取消、并发…） | 47 通过 / 0 失败 / 2 需真机（磁盘满、ARM64） |
| Linux 与 Windows 结果一致性 | Mode A 单倍型表、Mode C、注释结果一致；差异只有本版有意修复的几处（标签、`protein_verified`、Mode B 种子、`--aligner r` 覆盖度） |

## 附件校验值

```text
nanoamp-0.1.5-windows-setup.zip
  sha256  494886c61c8814543bd204d6fb8b6ce81fe1ef12e571bf3131b885053a3b5384

nanoamp-0.1.0-windows-offline-deps.zip
  sha256  2db72289a8ecef7e16ef388f8c6a8a59c1369b6c2212fcfa29d92297d9162d40
```

在 PowerShell 里核对：

```powershell
Get-FileHash .\nanoamp-0.1.5-windows-setup.zip -Algorithm SHA256
```

## 已知限制

1. **依赖 R**：GUI 的 exe 只打包界面（约 11 MB），不含 R 运行时。
2. **exe 冷启动约 1–3 秒**：单文件打包每次运行要解压到临时目录。
3. **GUI 没有批量功能**：批量用命令行的 `nanoamp batch`。
4. **离线 CDS 路线**的坐标要由使用者按自己的扩增子给出；长度不是 3 的倍数时跳过该
   注释并记账（退出码仍为 0）。
5. **在线 genome 路线**需要访问 Ensembl。扩增子不在内置 gene panel（当前只有 ZNF8）时
   会退化为逐染色体扫描，**可能非常慢**；目的序列与 GRCh38 匹配不足时明确报错，
   不会给出猜出来的坐标；网络不可达时非零退出，不会静默降级。
6. `protein_change` 是 **HGVS 风格**但**未经 HGVS 认证**，不应作为临床报告依据。
   注释结果随 Ensembl release 变化（记录在 `run_manifest.json` 的
   `annotation.ensembl_release`）。
7. **`--aligner r`（纯 R 比对）**的覆盖度/一致度已按真实比对片段计算；该后端比
   minimap2 慢，只有在没有可用 minimap2 时才建议使用。
8. **未在完全无 R 的真机上走查安装器自带 R 的路径**（开发机上始终存在 R）；
   "系统 R 版本不匹配就用自带 R"的决策由 `release/_installer/test_r_version_choice.py` 锁定。
9. **磁盘满、Windows ARM64、高 DPI（125%/150%）**三种环境的实测仍是手工项。
10. **上游（Linux 仓库）回灌未做**：本版在 Windows 侧修掉的若干上游缺陷
    （`--no-cache` 语义、无变异标签、Mode B 种子、大响应体截断、R 比对覆盖度等）
    尚未同步回 Linux 仓库。
11. **R 包本体仍是 0.1.0**：R 包的版本号与安装包版本号分开，安装包 0.1.5 里带的是
    当前源码构建的 `nanoamp_0.1.0.tar.gz`。

## 许可证

MIT。
