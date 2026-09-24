# 01_data

nanoamp 的测试数据。仓库不包含链接层：每个样本目录下直接存放分析所需的文件，
随仓库提交，clone 后不需要额外的准备步骤。

```text
01_data/
|-- TSM20260826/            # 2026-08-26 批次，6 个样本
|-- ZNF8/                   # ZNF8 靶点，15 个克隆 + 1 个 WT 对照
|-- nano_seq/               # 2026-09-17 批次，G1–G5 + 293T-G1–G5
|-- SD260728184122_1/       # 公司结构化交付（不属于下面这套命名，保持原样）
|-- SD260812174403_1/       # 同上
|-- README.md               # 本文件
`-- README-raw.md           # 公司原始交付的文件命名与目录结构说明
```

## 样本目录的固定文件名

```text
01_data/<dataset>/<sample>/
  reads.fastq          测序数据（必填）
  reference.self.fa    目的序列（必填，公司主导共识序列）
  reference.wt.fa      独立对照参考（可选）
  consensus.N.fa       第 N 个聚类簇的共识序列
  variants.N.xlsx      第 N 簇的公司变异统计表
  sanger.N.ab1         第 N 簇的 Sanger 峰图
  meta.tsv             角色 → 文件名 → 公司原始文件的对应表
```

示例：

```text
01_data/TSM20260826/E4-3/
  reads.fastq           529,626 B
  reference.self.fa     585 B
  reference.wt.fa       589 B
  consensus.1.fa        585 B
  variants.1.xlsx       227,999 B
  sanger.1.ab1          227,192 B
  meta.tsv
```

分析仅需要 `reads.fastq` 和一个参考序列（`reference.self.fa` 或 `reference.wt.fa`）：

```powershell
Rscript -e "library(nanoamp); run_haplotype_analysis( \
  reads='01_data/TSM20260826/E4-3/reads.fastq', \
  reference='01_data/TSM20260826/E4-3/reference.self.fa', \
  outdir='tmp/test_results/r/demo/E4-3', mode='A')"
```

在 GUI 中选择 FASTQ 后，若同目录存在 `reference.self.fa`，参考序列会被自动填入。

## meta.tsv：每个文件的来历

公司交付的文件名包含样本、项目号、日期与孔位（例如
`E4-3_TSM20260826-020-01254_20260827-020-BAN05-5_H08.fastq`），仓库内统一改为
上面的固定名字，原始文件名记录在 `meta.tsv` 中：

| 列 | 含义 |
|---|---|
| `dataset` / `sample` | 数据集与样本，对应目录名 |
| `role` | `reads` / `consensus` / `reference.self` / `reference.wt` / `variants` / `sanger` |
| `cluster` | 聚类簇编号（`consensus.N` / `variants.N` / `sanger.N` 的 N） |
| `file` | 本目录里的文件名 |
| `source_dir` | 公司交付时的批次目录 |
| `source_file` | 公司交付时的原始文件名 |
| `source_note` | 该参考序列的来源说明（例如"公司主导共识序列（cluster 1）"） |

同一份公司文件可能被多个角色使用（`reference.self.fa` 是该样本 cluster 1 的
共识序列，`reference.wt.fa` 是另一个样本的共识序列），因此这些文件在各自目录中
保存为独立副本；分析直接读取文件本身，不依赖链接跳转。

## 新增一个样本

```text
01_data/<dataset>/<sample>/
  reads.fastq  reference.self.fa  meta.tsv     # 最少这三个
```

`meta.tsv` 的写法（Tab 分隔，表头固定）：

```text
dataset	sample	role	cluster	file	source_dir	source_file	source_note
TSM20260826	E4-3	reads		reads.fastq	TSM20260826-020-01254	E4-3_....fastq
TSM20260826	E4-3	reference.self		reference.self.fa	TSM20260826-020-01254	E4-3_....1.seq	公司主导共识序列（cluster 1）
```

功能回归（`run_functional_tests.R`）会遍历 `01_data/*/*/meta.tsv` 自动发现样本，
并按 `role` 确定要运行的文件；没有 `meta.tsv` 的目录（例如两个 SD 批次）会被跳过。

## 两个 SD 批次与 README-raw.md

`SD260728184122_1/`、`SD260812174403_1/` 是公司的结构化交付（`Bam/`、`Var/`、
`QC/`、`Sequence/` + `merged_data.*.xls`），包含扩增子参考序列、变异表、覆盖度图和
Sanger 峰图，但不包含 FASTQ，因此不属于上面的样本命名体系，按公司原始结构保留。

`README-raw.md` 是公司交付文件的完整说明：目录结构、命名规则、每种文件后缀的用途、
变异表字段，以及若干注意事项（例如 `.var.xls` 实际是 TSV、BAM 的参考不是全基因组、
低深度样本的解释需谨慎）。

## 数据来源

数据来自若干批次的纳米孔靶向扩增子测序 + Sanger 验证交付，覆盖 3 个可分析数据集
（`TSM20260826`、`ZNF8`、`nano_seq`，共 32 个样本）与 2 个结构化交付批次。
`TSM20260826` 的名称来自项目号 `TSM20260826-020-01254` 的短名；`nano_seq` 是
2026-09-17 批次的目录名；`ZNF8` 是靶点名。

样本与实验条件（哪个基因、哪种编辑、预期结果）不在数据文件本身中，需要结合实验记录；
`README-raw.md` 第 11 节列出了仅凭数据无法确定的项目。
