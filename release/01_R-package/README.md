# R package 版

面向**需要在 R 里编写代码、或把 nanoamp 嵌入自身分析流程**的用户。

如果只需要分析单个样本，使用图形界面版操作更少 —— 见
[`../03_GUI/README.md`](../03_GUI/README.md)。

## 目录内容

```text
01_R-package/
`-- nanoamp_0.1.0.tar.gz      R 包源码发行版
```

## 安装

### 使用安装器

双击 `../install.exe` 会装好 R、109 个依赖包和本包，并配置好库路径。
安装完成后直接：

```r
library(nanoamp)
```

### 手动安装

前提：已装好 R（≥ 4.2）。

```r
# 1) 依赖（CRAN + Bioconductor）
install.packages(c("BiocManager", "data.table", "jsonlite", "optparse", "readxl"))
BiocManager::install(c("Biostrings", "IRanges", "Rsamtools"))
BiocManager::install(c("DECIPHER", "pwalign"))   # 可选：方案 B 聚类 / R 内比对后端
install.packages(c("shiny", "DT"))               # 可选：图形界面

# 2) 本包
install.packages("nanoamp_0.1.0.tar.gz", repos = NULL, type = "source")
```

> 若不需要本地编译，可使用 `install.exe` 装好的二进制依赖库：
> 库位置是 `%LOCALAPPDATA%\nanoamp\R\lib`。

## 快速上手

```r
library(nanoamp)

res <- run_haplotype_analysis(
  reads     = "sample.fastq",       # 测序文件
  reference = "target.fa",          # 目的序列
  outdir    = "results/sampleA",    # 输出目录
  mode      = "A",                  # A 参考引导（默认，推荐）
  top_n     = 20
)

res$haplotypes    # 单倍型表：rank / haplotype_id / count / proportion / ...
res$variants      # 候选变异位点
res$qc            # 质量指标
```

### 三种模式

| 模式 | 做什么 | 什么时候用 |
|---|---|---|
| `"A"` | 参考引导校正 + 单倍型计数 | **默认**。有可靠目的序列时的常规定量 |
| `"B"` | 从头聚类 + 簇共识 | 没有可靠参考、需要纯数据驱动 |
| `"C"` | 原始 reads 精确匹配 | 仅诊断用，展示测序错误的影响 |

> 不要用 `"C"` 做定量：纳米孔 reads 有约 0.5%–2% 错误率，直接精确匹配会把
> 绝大多数 reads 误判成"不一致"。

### 主要参数

| 参数 | 默认 | 说明 |
|---|---:|---|
| `top_n` | 20 | 输出前 n 条单倍型 |
| `min_reads` | 3 | 候选变异至少需要多少 reads 支持 |
| `min_freq` | 0.02 | 候选变异最低频率 |
| `min_identity` | 0.90 | read 与参考的最低一致度 |
| `aligner` | `"minimap2"` | 换成 `"r"` 使用 R 内成对比对（无需外部程序，速度较慢） |
| `threads` | 4 | 线程数 |
| `keep_intermediates` | `TRUE` | 是否保留 BAM 等中间文件 |

功能注释相关参数（可选，不传 `annotation` 时一切与以前逐字节一致）：

| 参数 | 默认 | 说明 |
|---|---|---|
| `annotation` | `NULL` | **配置 JSON 的路径**；给了才启用功能注释 |
| `list_transcripts` | `FALSE` | 只打印扩增子重叠的转录本后返回，不做分析（需要联网） |
| `annotation_proteins` | `FALSE` | `annotation.tsv` 里多两列参考/突变蛋白序列（可能很长） |
| `annotation_detail` | `FALSE` | 额外写 `variants_annotation.tsv`（每个变异一行） |
| `strict` | `FALSE` | 注释有转录本被跳过时让本次运行失败（默认只记账，退出码仍为 0） |

完整参数见 `?run_haplotype_analysis`，或 `nanoamp_defaults()`。

## 输出

`outdir` 下会生成：

| 文件 | 内容 |
|---|---|
| `haplotypes.tsv` | 单倍型表（核心结果） |
| `haplotypes.fasta` | 前 `top_n` 条单倍型序列 |
| `variants.tsv` | 变异位点，列名与公司 `*.var.xls` 兼容 |
| `qc.tsv` | 质量指标 |
| `run_manifest.json` | 参数、版本、输入文件哈希（可追溯） |
| `alignments.bam(.bai)` | 比对结果（`keep_intermediates = TRUE` 时） |

启用功能注释（`annotation = <config.json>`）后还会多出：

| 文件 | 内容 |
|---|---|
| `annotation.tsv` | 每个「单倍型 × 转录本」一行，含中英双列后果、蛋白变化、转录本冲突标记 |
| `variants_annotation.tsv` | 每个变异一行，含 CDS 坐标、密码子与氨基酸变化（`annotation_detail = TRUE` 且本次确有变异时） |

```r
res <- run_haplotype_analysis(
  reads      = "01_data/TSM20260826/E4-3/reads.fastq",
  reference  = "01_data/TSM20260826/E4-3/reference.self.fa",
  outdir     = "tmp/test_results/r/demo/E4-3_annot",
  annotation = "02_code/r/inst/configs/example_cds.json",  # 离线 CDS 路线，不需要联网
  annotation_detail = TRUE
)
res$annotation   # 单倍型 × 转录本的后果表（未启用注释时为 NULL）
```

两条路线的配置方式不同（离线 `cds` 需要自己给 CDS 坐标，在线 `genome` 需要联网），
字段说明见 `02_code/r/inst/configs/README.md`，完整输出契约见
`02_code/shared/docs/output_schema.md`。

**注释被跳过时不会报错**：`res$qc` 与 `qc.tsv` 会记录 `n_transcripts_skipped` /
`annotation_skip_reason`，`run_manifest.json` 记录 `annotation.skipped_transcripts`。
要让这种情况直接失败，传 `strict = TRUE`。**判断注释覆盖范围请看这些字段，
不要只看 `annotation.tsv` 有几行。**

## 命令行接口（同包提供）

```r
nanoamp_cli(c("doctor"))
nanoamp_cli(c("call", "--reads", "sample.fastq", "--reference", "target.fa",
              "--mode", "A", "--outdir", "results/sampleA"))

# 带功能注释（离线 CDS 路线；--strict 会让"注释被跳过"变成失败）
nanoamp_cli(c("call", "--reads", "sample.fastq", "--reference", "target.fa",
              "--mode", "A", "--outdir", "results/sampleA",
              "--annotate-config", "02_code/r/inst/configs/example_cds.json",
              "--annotation-detail"))
```

## 完整文档

- `02_code/r/README.md` — 英文完整教程
- `02_code/r/README-CN.md` — 中文完整教程
- `02_code/r/inst/docs/INSTALL_DEPENDENCIES-CN.md` — 依赖安装与排错

## 已知限制

- **不会**做 basecalling：输入必须是已经 basecall 过的 FASTQ。
- **功能注释是选做步骤**，两条路线的限制不同：
  - 离线 `cds` 路线：CDS 长度必须是 3 的倍数，坐标必须按自己的扩增子给出；
    长度不对时**跳过该注释并记账**（`qc.tsv` 的 `n_transcripts_skipped` /
    `annotation_skip_reason`），**退出码仍为 0**；
  - 在线 `genome` 路线：需要能访问 Ensembl REST。扩增子不在内置 panel 时会退化为
    逐染色体扫描，**可能非常慢**；与 GRCh38 匹配不足（锚定覆盖率 < 0.9）时**明确报错**，
    不会给出猜出来的坐标；网络不可达时**非零退出**。
  - `protein_change` 是 HGVS **风格**但**未经 HGVS 认证**，不应作为临床报告依据；
    注释结果随 Ensembl release 变化（见 `run_manifest.json` 的
    `annotation.ensembl_release`）。
  - 注释**不新增任何 R 依赖包**；在线路线需要系统里有 `curl.exe`（Windows 10 1803
    起自带，缺失时回退到 R 自带的下载能力）。
- 比例是 **reads 层面的估计**，不是分子比例：没有 UMI，无法区分 PCR 重复，
  纳米孔对不同长度序列也可能有捕获偏好。低深度样本的置信区间会很宽。
