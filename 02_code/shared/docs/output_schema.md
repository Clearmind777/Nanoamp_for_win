# 输出文件 schema（跨语言契约）

所有实现（R 核心库、CLI、GUI）都应在 `--outdir` 下生成以下文件，字段名保持一致。

## haplotypes.tsv

方案 A / B：

| 列名 | 类型 | 说明 |
|---|---|---|
| `rank` | int | 按支持 reads 数排名 |
| `haplotype_id` / `cluster_id` | string / int | 单倍型或簇编号 |
| `count` | int | 支持 reads 数 |
| `proportion` | float | 占比，0–1 |
| `ci_low` / `ci_high` | float | 比例的 95% Wilson 置信区间 |
| `is_reference` | bool / NA | 是否与参考序列一致 |
| `n_snv` / `n_ins` / `n_del` | int / NA | 变异数量 |
| `length` | int | 单倍型长度 |
| `variants` | string | 变异描述，多条用 `;` 分隔；`.` 表示无变异 |

方案 C：

| 列名 | 类型 | 说明 |
|---|---|---|
| `rank` | int | 按原始序列出现次数排名 |
| `haplotype_id` | string | H1、H2… |
| `count` | int | 出现次数 |
| `proportion` | float | 占比 |
| `is_reference` | bool | 是否等于参考正链或反链 |
| `length` | int | 序列长度 |
| `sequence` | string | 原始序列 |

## haplotypes.fasta

- 方案 A/B：前 `top_n` 条单倍型/簇共识序列；
- 方案 C：前 `top_n` 条原始序列；
- header 建议：`H<rank>_<variant_summary>` 或 `C<cluster_id>_<variant_summary>`。

## variants.tsv

方案 A 列名与公司 `*.var.xls` 兼容：

```text
Chr  Pos  Ref  Alt  DP  Ref_dp  Alt_dp  Freq  DP4  Seq  Filter_Status  Filter_Reason
```

- `Ref` / `Alt` 中的 `-` 表示插入/缺失；
- `Freq` 为 0–1 的小数，公司表为百分比时需除以 100；
- `Filter_Status` 取值 `PASS` / `FILTERED`。

方案 B 的 `variants.tsv` 至少包含：

```text
cluster_id  count  type  pos  ref  alt  Seq
```

## qc.tsv

两列 `metric` / `value`，至少包含：

```text
mode
reference_label
reference_length
n_reads_total
n_reads_primary
n_reads_used
mapping_rate
mean_identity
mean_coverage
n_haplotypes / n_clusters
top1_proportion
top1_is_reference
```

方案 A 额外包含 `aligner`、`n_raw_variants`、`n_pass_variants`、
`exact_reference_proportion`。方案 B 额外包含 `aligner`、`identity_cutoff`、
`clustering_method`、`consensus_method`、`decipher_version`。

## run_manifest.json

记录：

```text
nanoamp_version
mode
timestamp
r_version / python_version
reference: {name, length, md5, path}
params
qc
reads_md5
```
