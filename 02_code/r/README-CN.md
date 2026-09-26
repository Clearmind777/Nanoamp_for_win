# nanoamp

`nanoamp` 是一个用 R 编写的纳米孔 PCR 产物分析包。它可以把 reads 比对到目的序列，
校正测序错误，重建单倍型，并输出数量最多、比例最高的序列。

它主要回答这些问题：

- PCR 产物中有多少序列与目标产物完全一致？
- 其他序列是什么，各占多少比例？
- 哪些差异是真实变异，哪些是纳米孔测序错误？
- 多个变异是如何组合在同一条单倍型上的？

## 安装

### 1. 安装依赖

```r
install.packages(c(
  "Biostrings", "Rsamtools", "IRanges", "Matrix",
  "data.table", "optparse", "jsonlite", "readxl"
))

# 方案 B 推荐安装
if (!requireNamespace("BiocManager", quietly = TRUE)) install.packages("BiocManager")
BiocManager::install("DECIPHER")

# Bioconductor >= 3.19 把 pairwiseAlignment() 移出了 Biostrings：
# 只有用 aligner = "r" 时才需要
BiocManager::install("pwalign")

# GUI（可选）
install.packages(c("shiny", "DT"))
```

本包**刻意不依赖 `ShortRead`**：FASTQ 由包自己读取（`R/io.R` 处理普通与 gzip 输入，
并拒绝畸形记录），这也让 `pwalign` 保持"可选 provider"而不是硬依赖。

### 2. 安装 `nanoamp`

从构建好的 tar.gz 安装（例如 `make check` 生成的包；版本号按实际情况调整）：

```r
install.packages("tmp/builds/r/nanoamp_0.1.0.tar.gz", repos = NULL, type = "source")
```

从源码目录安装：

```bash
R CMD INSTALL 02_code/r
```

开发模式安装：

```r
devtools::install("02_code/r")
```

### 3. 安装外部工具

`minimap2` 会优先从 `03_dependence/<os>-<arch>/bin/` 解析，其次才是 `PATH`。
`samtools` 不是必需依赖：默认用 `Rsamtools::asBam()` 完成 SAM→BAM。

Windows 下的详细安装与 PATH 配置说明见
[inst/docs/INSTALL_DEPENDENCIES-CN.md](inst/docs/INSTALL_DEPENDENCIES-CN.md)。

`nanoamp` 会优先使用 `03_dependence/<os>-<arch>/bin/` 中的工具，其次才是
`PATH`。仓库已内置 Windows x86_64 的 minimap2 2.31（仓库内编译，静态链接）；
Windows 平台支持矩阵、重建步骤和 R 内后备方案见 `03_dependence/README-CN.md`。

```bash
minimap2 --version
# 可选：
# samtools --version
```

检查环境：

```r
library(nanoamp)
nanoamp::nanoamp_cli("doctor")
```

## 快速开始

```r
library(nanoamp)

res <- run_haplotype_analysis(
  reads     = "sample.fastq",
  reference = "target.fa",
  outdir    = "results/sampleA",
  mode      = "A",
  top_n     = 20
)

res$haplotypes   # 单倍型结果（按支持 reads 数排名）
res$variants     # 候选变异
res$qc           # 质控指标
```

输入要求：

- `reads`：FASTQ 或 FASTQ.GZ，纳米孔单端 reads；
- `reference`：包含目的序列的 FASTA；
- `outdir`：输出目录，不存在会自动创建。

## 三种分析模式

### 方案 A：参考引导校正（推荐）

先把 reads 比对到目的序列，发现候选变异，把没有通过过滤的差异当作测序错误
校正掉，再按校正后的序列分组计数。

适用于：

- 有可靠的目的序列；
- 需要定量的单倍型比例；
- 需要区分真实变异和纳米孔测序错误。

### 方案 B：从头聚类（探索性）

用 `DECIPHER::Clusterize` 对 reads 聚类，再对每个簇用 `DECIPHER::AlignSeqs`
做多序列比对，并用多数投票生成共识序列。

适用于：

- 没有可靠参考；
- 需要了解主要序列分组的概况；
- 可以接受“差异小于测序错误率的单倍型无法分开”这一限制。

如果 `DECIPHER` 不可用，方案 B 会自动降级为变异模式贪心聚类，并在
`qc.tsv` 中记录。

`DECIPHER::Clusterize` 在上游是随机算法（同一输入换一个随机数状态，实测同一阈值下
得到 29 与 30 个簇），所以本包在调用前固定种子，并把种子写进 `qc.tsv` 的
`clustering_seed`（默认 42）。调用方 R 会话的随机数流会被保存并恢复，因此包调用
不会干扰调用者的随机状态；没有这个种子，方案 B 每次运行的结果都会变化，功能回归
基线也就无法比对。

### 方案 C：原始精确匹配（诊断）

统计原始 reads 与参考正链或反向互补链完全一致的条数。它主要用于展示
纳米孔测序错误的影响，不推荐用于定量。

## 参数

查看默认参数：

```r
nanoamp_defaults()
```

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `top_n` | 20 | 输出前 n 条单倍型 |
| `min_reads` | 3 | 候选变异最低支持 reads 数 |
| `min_freq` | 0.02 | 候选变异最低频率 |
| `min_identity` | 0.90 | read 与参考的最低 identity |
| `min_ref_coverage` | 0.90 | read 覆盖参考的最低比例 |
| `homopolymer` | 4 | homopolymer 过滤阈值 |
| `strand_bias` | 0.90 | 链偏好过滤阈值 |
| `identity_cutoff` | 0.99 | 方案 B 聚类 identity 阈值 |
| `min_cluster_reads` | 2 | 方案 B 最小簇大小 |
| `max_msa_seqs` | 100 | 共识比对最多使用多少条序列 |
| `consensus_method` | `"decipher"` | `"decipher"` 或 `"medoid"` |
| `aligner` | `"minimap2"` | `"minimap2"` 或 `"r"`（R 内后备） |
| `use_samtools` | `FALSE` | 是否用 samtools 替代 Rsamtools 完成 SAM→BAM |
| `threads` | 4 | 线程数 |
| `keep_intermediates` | `TRUE` | 是否保留 BAM 等中间文件 |

## 功能注释（可选）

功能注释是**选做**且默认关闭：不传 `annotation = "<config.json>"`（命令行
`--annotate-config`）时，输出与该功能出现之前**逐字节一致**。启用后，每条单倍型的
变异会被翻译成生物学后果：

- **`cds` 路线（离线）**：配置里给出扩增子参考上的 CDS 区间（`start`、`end`、
  `strand`、`frame`、`boundaries`），长度必须是 3 的倍数；不需要联网，也不需要参考文件。
- **`genome` 路线（在线）**：程序自行在 GRCh38 定位扩增子，并从 Ensembl REST 取
  转录本结构。参考序列与基因组匹配不足时会**明确报错**，而不是硬凑一个坐标。

额外输出（每一列的完整定义见 `shared/docs/output_schema.md`）：

| 文件 | 内容 |
|---|---|
| `annotation.tsv` | 每个「单倍型 × 转录本」一行：中英双列后果、蛋白变化、`consequence_any_transcript`、`transcript_conflict` |
| `variants_annotation.tsv` | `annotation_detail = TRUE` 时：每个变异一行，含基因组/CDS 坐标、密码子与氨基酸变化 |
| `transcripts.tsv` | `list_transcripts = TRUE` 时：扩增子重叠的转录本清单 |

被跳过的转录本是**记账而不是隐藏**：`qc.tsv` 里写 `n_transcripts_annotated`、
`n_transcripts_skipped`，有丢弃时还写 `annotation_skip_reason`；
`run_manifest.json` 的 `annotation.skipped_transcripts` 逐条给出转录本与原因。
注释被跳过时退出码仍是 0（序列分析本身成功了）；流水线需要把它当失败时用
`strict = TRUE`（命令行 `--strict`）。注释**不新增任何 R 依赖**（Biostrings/jsonlite
本来就必需）；在线路线额外需要一个 HTTP 客户端（优先 `curl.exe`，缺失时回退到 R 的
下载能力）。

示例配置随包分发（`inst/configs/example_cds.json`、`example_online.json`）；
`nanoamp doctor` 会打印该目录，`install.exe` 另会复制一份到 `<安装目录>\configs\`。

## 运行状态

每次运行都会把 `run_manifest.json` 与 `nanoamp.log` 写进输出目录。manifest 记录参数、
版本、输入校验值，以及 `status`（`done`/`failed`/`cancelled`）、`error_class`
（`input`/`environment`/`network`/`internal`）、`error_message`、`log_path`。
**失败的运行也会创建目录并写下这两个文件**，因此"失败"与"什么都没产出"不会无法区分。
退出码为 0（成功）/ 1（失败）。

## 输出文件

```text
outdir/
├── haplotypes.tsv
├── haplotypes.fasta
├── variants.tsv
├── qc.tsv
├── run_manifest.json
├── nanoamp.log                # 与终端相同的日志（失败时也会写）
├── annotation.tsv             # annotation = TRUE
├── variants_annotation.tsv    # annotation_detail = TRUE
├── transcripts.tsv            # list_transcripts = TRUE
└── alignments.bam(.bai)       # 方案 A/B，keep_intermediates = TRUE 时保留
```

### haplotypes.tsv

| 列名 | 说明 |
|---|---|
| `rank` | 按支持 reads 数排名 |
| `haplotype_id` / `cluster_id` | 单倍型或簇编号 |
| `count` | 支持 reads 数 |
| `proportion` | 占有效 reads 的比例 |
| `ci_low`、`ci_high` | 95% Wilson 置信区间 |
| `is_reference` | 是否与参考序列一致 |
| `n_snv`、`n_ins`、`n_del` | 变异数量 |
| `length` | 单倍型长度 |
| `variants` | 变异描述；`.` 表示无变异 |

### variants.tsv

方案 A 的列与公司 `*.var.xls` 兼容：

```text
Chr  Pos  Ref  Alt  DP  Ref_dp  Alt_dp  Freq  DP4  Seq  Filter_Status  Filter_Reason
```

- `Freq` 是 0–1 的小数；
- `Ref` 或 `Alt` 中的 `-` 表示插入或缺失；
- `Filter_Status` 为 `PASS` 或 `FILTERED`。

### qc.tsv

两列 `metric` 和 `value`，包括 reads 数、比对率、平均 identity、覆盖度、
聚类方法、共识方法和 DECIPHER 版本。方案 B 另有 `clustering_seed` 与
`clustering_note`；`aligner = "r"` 另有 `pairwise_provider`。注释会加入
`annotation_enabled`、`annotation_name`、`annotation_route`、`annotation_source`、
`ensembl_release`、`genetic_code`、`n_transcripts`、`n_transcripts_annotated`、
`n_transcripts_skipped`、`annotation_available`、`n_haplotypes_annotated`、
`n_haplotypes_skipped`、`n_frameshift`、`n_stop_gained`、`n_stop_lost`、
`n_start_lost`、`n_missense`、`n_synonymous`、`n_inframe`、`n_transcript_conflicts`，
以及有转录本被丢弃时的 `annotation_skip_reason`。

### run_manifest.json

参数、版本、参考序列信息、输入校验值、QC 数值，启用注释时还有 `annotation` 段
（`enabled`、`available`、`source`、`ensembl_release`、`config`、`genomic`、
`transcripts`、`skipped_transcripts`）。此外还包含上文「运行状态」里的 status 字段。

## 命令行版本

R 包自带基于同一套 R 代码的命令行工具：

```bash
nanoamp doctor

nanoamp call \
  --reads sample.fastq \
  --reference target.fa \
  --mode A \
  --top-n 20 \
  --outdir results/sampleA

nanoamp batch \
  --sample-sheet samples.tsv \
  --mode A \
  --outdir results/batch
```

批量分析表是 TSV，至少包含：

```text
sample	reads	reference
```

可选列：`ref_label`。

在没有 minimap2 的平台上，可以用 `--aligner r` 选择 R 内比对后端。
仓库级启动器是 `02_code/cli/nanoamp`（Windows 下为
`02_code/cli/nanoamp.bat`）。

### 子命令与最近新增的参数

```text
nanoamp call   --reads <fastq> --reference <fasta> --outdir <dir> [--mode A|B|C]
nanoamp batch  --sample-sheet <tsv> --outdir <dir> [--mode A|B|C]
nanoamp doctor [--check-online]
nanoamp cache  [--cache-dir <dir>] [--clear]
nanoamp help
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--min-ref-coverage <p>` | 0.90 | read 至少要覆盖参考序列的多大比例 |
| `--annotate-config <config.json>` | 关 | 启用注释；路线取自配置文件里的 `"route"` |
| `--transcript <ENST...\|all>` | 配置里的值 | 只注释指定转录本，或注释全部重叠转录本 |
| `--list-transcripts` | 关 | 打印重叠转录本后退出（同时写 `transcripts.tsv`） |
| `--annotation-proteins` / `--annotation-detail` | 关 | `annotation.tsv` 里加蛋白序列 / 另写 `variants_annotation.tsv` |
| `--cache-dir <dir>` / `--no-cache` / `--clear-cache` | — | 缓存位置、本次绕过（不删除）、清空并退出（可单独使用，不需要输入文件） |
| `--strict` | 关 | 注释有转录本被跳过时改为非零退出 |

`doctor --check-online` 会报告 Ensembl 现在是否可达，不可达时以非零状态退出；
`nanoamp cache` 打印缓存目录、体积与文件数。缓存目录按
`NANOAMP_CACHE_DIR` → `%LOCALAPPDATA%\nanoamp\cache\ref` → `%TEMP%\nanoamp\ref`
的顺序解析；读不出来的缓存条目会被丢弃并重新获取，而不是继续使用。

### 安装 `nanoamp` 命令

```bash
sh "$(Rscript --vanilla -e 'cat(system.file("scripts", "install_cli.sh", package = "nanoamp"))')" ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"
nanoamp doctor
```

也可以直接在 R 中调用：

```r
library(nanoamp)
nanoamp_cli(c("call", "--reads", "sample.fastq", "--reference", "target.fa",
              "--outdir", "results/sampleA"))
```

## 图形界面（GUI）

启动 Shiny GUI：

```r
library(nanoamp)
nanoamp_gui()
```

GUI 提供文件选择、模式选择、高级参数、运行按钮、日志窗口、单倍型/变异交互表格、
QC 结果和下载按钮。

Windows 上：

```bat
Rscript -e "library(nanoamp); nanoamp_gui()"

:: 或使用随包附带的启动脚本
02_code\r\inst\scripts\nanoamp-gui.bat
```

如果只需要 Shiny app 对象而不启动服务器：

```r
app <- nanoamp_gui_app()
```

使用 RInno 制作 Windows 安装包的说明见 `inst/windows/README.md`。

### 外部工具与 R 内后端

`aligner = "minimap2"` 会优先使用内置的 minimap2 二进制。
Windows、ARM 或没有 minimap2 的机器上可以改用：

```r
run_haplotype_analysis(..., aligner = "r")
```

R 内后端使用 Biostrings 成对比对，不需要外部工具；速度较慢，适合中小扩增子。

它报告的覆盖度、identity 与比对终点，都来自 read **实际比对到的参考片段**。
（早期版本把每条 read 都当作覆盖整条参考序列，于是只覆盖一半的 read 也能通过
`--min-ref-coverage 0.99` 并被计为参考单倍型；默认的 `minimap2` 后端一直是正确的。）

`samtools` 不是必需依赖：默认用 `Rsamtools::asBam()` 完成 SAM→BAM。
只有显式设置 `use_samtools = TRUE` 才会调用 samtools。

## RStudio 使用流程

1. 打开 `02_code/r/nanoamp.Rproj`；
2. 修改 `inst/scripts/run_analysis.R` 顶部的 `CONFIG`；
3. 运行整个脚本。

脚本会自动寻找项目根目录，并把结果写到 `tmp/test_results/r/`。

## 使用测试数据

样本文件位于 `01_data/<dataset>/<sample>/`（普通文件，已随仓库提交，
clone 后无需额外准备），每个样本目录包含：

```text
reads.fastq
reference.self.fa
reference.wt.fa
consensus.N.fa
variants.N.xlsx
sanger.N.ab1
meta.tsv
```

示例：

```r
library(nanoamp)
res <- run_haplotype_analysis(
  reads     = "01_data/TSM20260826/E4-3/reads.fastq",
  reference = "01_data/TSM20260826/E4-3/reference.self.fa",
  outdir    = "tmp/test_results/r/demo/E4-3",
  mode      = "A"
)
```

## 测试与验证

```r
# 已安装包的单元测试
testthat::test_check("nanoamp")

# 开发模式
devtools::test("02_code/r")
```

完整功能测试：

```bash
Rscript 02_code/r/inst/scripts/run_functional_tests.R \
  --outdir tmp/test_results/r/test_run_2 --modes A,B,C --threads 4
```

本包已通过 `R CMD check`（当前为 `Status: OK`），并有 48 个 testthat 用例 /
192 个断言。仓库还会对 `01_data/` 中每个样本跑功能回归（168 次运行），并与提交入库的
基线 `03_dependence/baselines/functional/` **逐行**比对：

```bash
make functional-test       # 跑回归并与基线比较
make functional-baseline   # 重跑并刷新基线（务必先看 diff）
```

`make stress-test` 跑环境压力矩阵中可自动化的部分（网络/代理/缓存、退化输入、
含空格与中文的路径、超长路径、取消、并发）；最近一次全量结果是
**47 PASS / 0 FAIL / 2 SKIP**，两个 SKIP 是需要真机的用例（磁盘满、ARM64）。

## 常见问题

| 现象 | 解决办法 |
|---|---|
| 找不到 `minimap2` | 安装 minimap2 并加入 `PATH` |
| 找不到 `samtools` | 通常不需要：默认使用 `Rsamtools`；只有 `use_samtools = TRUE` 才需要 samtools |
| 方案 B 运行较慢 | 降低 `max_msa_seqs`、增加 `threads`，或改用方案 A |
| 方案 B 无法区分相近单倍型 | 这是低于测序错误率时的固有限制，请用方案 A |
| 未安装 `DECIPHER` | 方案 B 会自动降级为贪心聚类；安装 DECIPHER 可改善聚类结果 |
| 报 `pairwiseAlignment` 不是 Biostrings 的导出对象 | Bioconductor ≥ 3.19 把它移到了 `pwalign`：`BiocManager::install("pwalign")` |
| 注释被跳过但退出码是 0 | 这是文档化的降级行为：看 `qc.tsv` 的 `annotation_skip_reason` 与 manifest 的 `annotation.skipped_transcripts`；想让流水线失败就加 `--strict` |
| Ensembl 不可达 / 在线路线失败 | 检查网络与代理、用 `--no-cache` 重试，或把配置改成 `"route": "cds"`（离线，需要 CDS 区间） |
| 方案 C 比例很低 | 纳米孔 reads 有错误，请用方案 A |

## 许可证

MIT。
