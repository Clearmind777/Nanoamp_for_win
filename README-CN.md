# nanoamp — Windows

`nanoamp` 用于分析纳米孔 PCR 产物的测序数据。给定 FASTQ 和目的序列，它会校正
测序错误、重建单倍型，并输出数量最多、比例最高的序列。

本仓库是项目的 **Windows 变体**，独占所有 Windows 相关内容：原生
`minimap2.exe`、MSYS2/MINGW-w64 编译方案、Windows 下的 R 环境脚本，
以及离网安装包。

Linux 变体在姊妹仓库 `a_09_18_26_mapping_programs_dev_for_linux`。

两个变体**都不使用 conda，也不使用 WSL**。

## 仓库结构

```text
00_materials/     委托文档、开发方案、工作报告和完整教程（tutorial.md）
01_data/          原始测试数据和规范化链接层
02_code/          源代码
  r/              nanoamp R 包（R/annotate*.R、ref_online.R、io.R 等；inst/configs/ 为示例注释配置）
  cli/            独立 R CLI 入口和启动器（make cli 用）
  gui/            独立 R Shiny GUI 入口和启动器（make gui 用）
  PythonGUI/      Python/Tkinter 图形界面（发行版 GUI 就是它的产物）
  shared/         跨语言参数与输出契约（docs/output_schema.md 含注释与状态字段）
03_dependence/    内置 minimap2.exe、编译方案、离网安装包、R 环境脚本
  stress/         环境压力矩阵运行器（A–D 组）
  baselines/functional/  提交入库的功能回归基线（168 次运行）
release/          发布产物：三个交付形态 + 安装/卸载器
tmp/test_results/ 运行结果（除 README 外 Git 忽略）
tmp/builds/       R CMD build / check 产物（Git 忽略）
```

## 快速开始

仓库已内置 `minimap2.exe`（静态链接，运行时不需要 MSYS2 / Cygwin / conda / WSL），
因此在正常情况下仅需要 R。

```powershell
# 1. 安装 R 包（R 本身怎么装见 03_dependence/r-environment/README.md）
R CMD INSTALL 02_code/r

# 2. 环境检查
sh 02_code/cli/nanoamp doctor

# 3. 跑单样本（测试数据就在 01_data/ 里，无需额外准备）
sh 02_code/cli/nanoamp call `
  --reads 01_data/TSM20260826/E4-3/reads.fastq `
  --reference 01_data/TSM20260826/E4-3/reference.self.fa `
  --mode A --top-n 20 `
  --outdir tmp/test_results/cli/demo

# 4. 启动 GUI
Rscript 02_code/gui/run_gui.R
```

R 控制台：

```r
library(nanoamp)
res <- run_haplotype_analysis(
  reads     = "01_data/TSM20260826/E4-3/reads.fastq",
  reference = "01_data/TSM20260826/E4-3/reference.self.fa",
  outdir    = "tmp/test_results/r/demo/E4-3",
  mode      = "A"
)
res$haplotypes
```

### 命令行有哪些子命令

```text
nanoamp call   --reads <fastq> --reference <fasta> --outdir <dir> [--mode A|B|C]
nanoamp batch  --sample-sheet <tsv> --outdir <dir> [--mode A|B|C]
nanoamp doctor [--check-online]      # 环境自检；--check-online 顺带测 Ensembl 连通性
nanoamp cache  [--cache-dir <dir>] [--clear]   # 查看/清空注释缓存
nanoamp help
```

`--min-ref-coverage <p>`（默认 0.90）控制 read 至少要覆盖参考序列的多大比例；
`--aligner r` 选择 R 内比对后端（不需要 minimap2）。完整的注释相关参数见
`02_code/r/README-CN.md` 与 `release/02_CLI/README.md`。

## 输入文件契约（摘要）

完整表格（格式细节、路径限制、每个功能对应要准备什么、注释配置字段校验）见
`README.md` 的 §2「输入文件契约」。要点：

| 项目 | 内容 |
|---|---|
| 最少必需 | **FASTQ（一个样本一个文件）+ 目的序列 FASTA + 一个可写的输出目录**；参考基因组、GTF/GFF、公司 `.xlsx` 变异表、Sanger 峰图都不需要 |
| FASTQ | 每条 read 四行（`@名称`/序列/`+`/质量），序列必须一行；行数须为 4 的倍数、`@` 与 `+` 位置必须正确，否则明确报错；`.gz` 按后缀**或 gzip 魔数**识别；名称去掉 `@` 作为 `read_id`；序列大写化；**质量行不参与任何计算**；空文件报错 |
| FASTA | 必须有 `>` 头；**只用第一条序列**（多序列文件不报错，其余被忽略）；按 DNA 读取并大写化；文件缺失或为空时报错；路径与 MD5 记入 `run_manifest.json` |
| 长度关系 | reads 默认需覆盖参考的 ≥ 90%（`--min-ref-coverage` 0.90）、一致度 ≥ 90%（`--min-identity` 0.90） |
| 命名 | 程序**不要求**任何文件名；唯一约定是 GUI 会在 FASTQ 同目录找 `reference.self.fa` / `reference.fa` / `reference.wt.fa` 自动填入，以及 `nanoamp batch` 样本表的列名 `sample/reads/reference`（可选 `ref_label`），`sample` 值会用作输出子目录名 |
| 路径 | 支持空格与中文；超过 260 字符且未启用长路径时明确报错；结果表覆盖写，`nanoamp.log` 追加写（同一输出目录重复运行会累积，建议每次用新目录） |
| 按功能准备 | 模式 A/B 还需比对程序（内置 minimap2 或 `--aligner r`），模式 C 不需要；离线 CDS 注释需 `"route": "cds"` 配置且 CDS 长度是 3 的倍数；在线 genome 注释需联网且目的序列与 GRCh38 锚定覆盖率 ≥ 90%；批量需样本表 |

## 功能注释（可选，默认关闭）

不传 `--annotate-config`（命令行）或不勾选「功能注释…」（图形界面）时，输出与该功能
出现之前**逐字节一致**。启用后会把每条单倍型的变异翻译成生物学后果，并多写
`annotation.tsv`（每个「单倍型 × 转录本」一行）、`variants_annotation.tsv`
（加 `--annotation-detail`）与 `transcripts.tsv`（用 `--list-transcripts`）。

两条路线：

| 路线 | 需要联网 | 需要提供 |
|---|---|---|
| `cds`（离线） | 否 | 扩增子参考上的 CDS 区间、链与读码框（长度必须是 3 的倍数） |
| `genome`（在线） | 是 | 无需提供：程序自行在 GRCh38 定位扩增子并从 Ensembl REST 取转录本结构 |

图形界面在选好**目的序列**后会把「CDS 止」按该序列长度**预填**（提示行标明这是预填值，
可改；改过之后窗口不再覆盖它），命令行没有这个预填，`cds.start/end` 必须自己给。

被跳过的转录本会记账（`qc.tsv` 的 `annotation_skip_reason`、
`run_manifest.json` 的 `annotation.skipped_transcripts`），此时退出码仍是 0；
`--strict` 才会把它变成失败。命令行还可以用 `--transcript <ENST…|all>` 指定注释哪一个
（或全部）转录本，用 `--annotation-proteins` 在 `annotation.tsv` 里附带参考/突变蛋白序列。
注释不新增 R 依赖；在线路线需要 `curl.exe`
（缺失时回退到 R 的下载能力）。示例配置随包提供（`nanoamp doctor` 打印 `configs` 路径，
`install.exe` 另复制一份到 `<安装目录>\configs\`）。

缓存相关命令：`nanoamp cache`（打印缓存目录/体积/文件数）、`nanoamp cache --clear`
（清空）、`nanoamp doctor --check-online`（测 Ensembl 连通性，不可达时非零退出）。

## 运行状态

每次运行都会写 `run_manifest.json`（含 `status` = `done`/`failed`/`cancelled`、
`error_class` = `input`/`environment`/`network`/`internal`、`error_message`、
`log_path`）与 `nanoamp.log`。**失败的运行也会创建输出目录并写下这两个文件**；
退出码仍然是 0（成功）/ 1（失败）。图形界面会按 `error_class` 给出对应的提示。

结果表是**覆盖写**的：同一次运行的注释两页只显示本次产生的内容，输出目录里若还留着
上一次的 `annotation.tsv`，界面会提示"未显示"而不是画成新结果。点「开始分析」会清空六个
标签页（「运行日志」除外，它是会话历史），上一次的结果保留在内存里，可点「查看上次结果」
回看，直到关闭程序。窗口启动时会往日志里写「仓库根目录 / Rscript / minimap2」三行实际路径。

## 测试数据：`01_data/<dataset>/<sample>/`

样本目录中直接存放分析所需的文件，**文件名固定**：

```text
01_data/TSM20260826/E4-3/
  reads.fastq            ← 测序数据
  reference.self.fa      ← 目的序列
  reference.wt.fa        ← 对照参考（可选）
  consensus.N.fa         ← 公司共识序列
  variants.N.xlsx        ← 公司变异统计表
  sanger.N.ab1           ← Sanger 峰图
  meta.tsv               ← 上面每个文件原本是公司的哪个交付文件
```

这些都是**普通文件、随仓库提交**，clone 之后不需要任何生成或修复步骤，
直接使用 `reads.fastq` + `reference.self.fa` 即可分析（GUI 选择 FASTQ 后会自动
在同一目录中查找 `reference.self.fa`）。

要新增样本：建立 `01_data/<dataset>/<sample>/`，按上述名称放入文件，
并编写一份 `meta.tsv`（列：`dataset / sample / role / cluster / file /
source_dir / source_file / source_note`）。功能回归会自动发现所有带
`meta.tsv` 的样本目录。`01_data/README-raw.md` 保留了公司原始交付的
文件命名与目录结构说明，`SD260728184122_1/`、`SD260812174403_1/` 两个批次
仍是公司的原始结构。

## 文档索引

| 文档 | 内容 |
|---|---|
| `00_materials/tutorial.md` | **完整教程**：GUI 版、CLI 版、R 包版 + 外部依赖工具配置 |
| `README.md` | 面向使用者的说明（安装、图形界面、结果解读、排错） |
| `02_code/README.md` | 源码目录与组件状态 |
| `02_code/r/README.md` | R 包教程（英文） |
| `02_code/r/README-CN.md` | R 包教程（中文） |
| `02_code/shared/docs/output_schema.md` | 输出契约（含注释与运行状态字段） |
| `02_code/cli/README.md` | CLI 契约与启动器 |
| `02_code/gui/README.md` | R Shiny GUI 功能 |
| `02_code/PythonGUI/README.md` | Python/Tkinter 界面实现与打包细节 |
| `01_data/README.md` | 链接层的提交策略与重建方法 |
| `release/README.md` | 发布产物与安装器 |
| `03_dependence/README-CN.md` | 内置工具与 Windows 平台支持矩阵 |
| `03_dependence/stress/README.md` | 环境压力矩阵用例清单（含手工用例） |
| `03_dependence/baselines/functional/README.md` | 功能回归基线与刷新方法 |
| `03_dependence/windows-x86_64/README.md` | Windows 源码编译 minimap2 |
| `03_dependence/r-environment/README.md` | R 环境搭建与测试运行 |
| `03_dependence/offline-bundle/README.md` | 离网安装 |
| `00_materials/README.md` | 规划文档与工作报告索引 |

## 外部工具

解析顺序：

1. `NANOAMP_MINIMAP2` / `NANOAMP_SAMTOOLS`；
2. `03_dependence/<os>-<arch>/bin/`（Windows 下为 `.exe`）；
3. `PATH`。

安装版里第 1 条由图形界面自己设置：它会找到安装目录（默认 `%LOCALAPPDATA%\nanoamp`，
换过安装位置时由 `%LOCALAPPDATA%\nanoamp.path` 指向）并把 `<安装目录>\bin\minimap2.exe`
固定给 R，**因此"安装时不勾选加入 PATH"也照样能用**；该文件由 `install.exe` 无条件复制，
窗口启动时会把它的实际路径写进运行日志第一屏。

仓库已内置 **Windows x86_64 的 minimap2 2.31**，由本仓库从上游源码编译并静态链接，
运行时不需要 MSYS2 / Cygwin / conda / WSL（只依赖 `KERNEL32.dll` 和 `msvcrt.dll`）。
上游没有官方 Windows 构建，要复现这个产物：

```powershell
pwsh -File 03_dependence/windows-x86_64/install_msys2_toolchain.ps1  # 编译链（约 1.5 GB）
bash 03_dependence/windows-x86_64/build_minimap2.sh                  # 编译
```

Windows on ARM 请改用 R 内后端：

```r
run_haplotype_analysis(..., aligner = "r")
```

该后端报告的覆盖度与 identity 来自 read **实际比对到的参考片段**（早期版本把每条
read 都当作覆盖整条参考序列，导致部分覆盖的 read 也能通过 `--min-ref-coverage 0.99`；
默认的 `minimap2` 后端一直是正确的）。

samtools 是可选依赖且未内置：默认用 `Rsamtools::asBam()` 完成 SAM→BAM，
不需要任何 samtools 二进制。

R 包自己读取 FASTQ（`R/io.R`），**不再需要 `ShortRead`**；安装器的固定版本清单是
有意的超集，可能与包实际需要的集合不完全一致。

## 运行测试

```powershell
# 单元测试（会用到内置的 minimap2）：48 个用例 / 192 个断言
Rscript 03_dependence/r-environment/run_tests.R

# 基于 01_data/ 真实数据的功能回归（168 次运行）
Rscript 03_dependence/r-environment/run_functional_regression.R `
  --outdir tmp/test_results/r/test_run_win --modes A,B,C --threads 4
```

用 `make` 跑同一套验证（失败时以非零状态退出）：

```bash
make functional-test   # 跑回归并与提交入库的基线逐行比较
make stress-test       # 环境压力矩阵 A–D 组（A 组需要联网）
make gui-test          # Python 界面自测（7 个脚本）
make release-test      # 安装器与发布布局自测（9 个脚本）
```

最近的实测结果：`R CMD check` 为 `Status: OK`；功能回归 168 次运行与基线逐行一致；
环境压力矩阵 **47 PASS / 0 FAIL / 2 SKIP**（两个 SKIP 是需真机的磁盘满与 ARM64）。

方案 B 的聚类引擎 `DECIPHER::Clusterize` 在上游是随机算法（同一输入换一个随机数状态，
实测同一阈值下得到 29 与 30 个簇），所以本包固定种子并把 `clustering_seed`
（默认 42）写进 `qc.tsv`，方案 B 因此可复现；方案 A / C 本身就是逐字节可复现的。

从零搭建 Windows R 环境（R 安装、镜像、依赖安装）见
`03_dependence/r-environment/README.md`。

## 离网安装

可将全部上游安装程序预置成一个固定版本、带完整性校验的安装包，
供无网机器一次性部署（R 安装器、完整 R 包依赖闭包、MSYS2 工具链、minimap2 源码）：

```powershell
# 有网机器
Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R

# 无网机器
pwsh -File 03_dependence/offline-bundle/install_offline.ps1
```

安装包写入 git 忽略的 `dist/`：仓库保留可复现的配方与哈希，不保留二进制。
为什么不入库、精确体积构成，以及 USB / release assets 两种替代方案，
见 `03_dependence/offline-bundle/README.md`。

## 常用命令

```bash
make install          # 安装 R 包
make test             # 运行 testthat 测试
make check            # 构建并 R CMD check
make functional-test  # 168 次真实运行的功能回归 + 基线比对
make functional-baseline  # 重跑并刷新基线
make stress-test      # 环境压力矩阵 A–D 组
make cli              # 运行 nanoamp doctor
make gui              # 启动 Shiny GUI
make gui-python       # 启动 Python/Tkinter GUI
make gui-exe          # 重新打包图形界面 exe
make gui-test         # Python 界面自测（7 个脚本）
make install-exe      # 重新打包 release/install.exe
make release-assets   # 重打发布资产
make release-test     # 安装器/发布布局自测
make deps             # 查看内置 minimap2.exe 的来源与重建方式
make toolchain        # 安装 MSYS2/MINGW-w64 编译链
make offline-bundle   # 生成离网安装包到 dist/
make offline-install  # 从安装包离线安装
make clean-scratch    # 清理打包临时目录
```

## 许可证

MIT。
