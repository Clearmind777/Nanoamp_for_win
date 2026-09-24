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
BiocManager::install(c("Biostrings", "IRanges", "Rsamtools", "ShortRead"))
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

## 命令行接口（同包提供）

```r
nanoamp_cli(c("doctor"))
nanoamp_cli(c("call", "--reads", "sample.fastq", "--reference", "target.fa",
              "--mode", "A", "--outdir", "results/sampleA"))
```

## 完整文档

- `02_code/r/README.md` — 英文完整教程
- `02_code/r/README-CN.md` — 中文完整教程
- `02_code/r/inst/docs/INSTALL_DEPENDENCIES-CN.md` — 依赖安装与排错

## 已知限制

- **不会**做 basecalling：输入必须是已经 basecall 过的 FASTQ。
- **不会**做 GTF / CDS 功能注释（移码 / 提前终止 / missense）—— 尚未实现。
- 比例是 **reads 层面的估计**，不是分子比例：没有 UMI，无法区分 PCR 重复，
  纳米孔对不同长度序列也可能有捕获偏好。低深度样本的置信区间会很宽。
