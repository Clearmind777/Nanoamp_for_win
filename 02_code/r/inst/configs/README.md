# 功能注释配置（configs/）

这里的 JSON 是 `--annotate-config` 的输入。不传这个参数时，程序的行为与以前完全一致
（不写任何注释产物）；传了才启用功能注释。

```bash
sh 02_code/cli/nanoamp call \
  --reads <reads.fastq> --reference <amplicon.fa> --outdir <out> \
  --annotate-config 02_code/configs/example_online.json
```

## 两个示例

| 文件 | `route` | 需要网络 | 用途 |
|---|---|---|---|
| `example_online.json` | `genome` | 是 | 默认路线。程序自己在 GRCh38 上定位扩增子，并从 Ensembl REST 取转录本结构 |
| `example_cds.json` | `cds` | 否 | 离线兜底。自己给出 CDS 在扩增子参考上的起止坐标，只做翻译 |

两个示例都是**能直接跑通**的配置，但它们绑定的是仓库自带的测试数据；换自己的扩增子
时必须替换坐标（见下面）。

## 字段说明

| 字段 | 适用路线 | 含义 |
|---|---|---|
| `name` | 两者 | 配置名，会写进 `qc.tsv` 的 `annotation_name` 和 `run_manifest.json` |
| `route` | 两者 | `genome`（默认）或 `cds` |
| `cds.start` | `cds` | CDS 起始位置，1-based，落在**扩增子参考**上；必填 |
| `cds.end` | `cds` | CDS 结束位置；省略则到参考序列末尾 |
| `cds.strand` | `cds` | `+` 或 `-`（负链会先取反向互补再翻译） |
| `cds.frame` | `cds` | `0` / `1` / `2`，翻译前跳过的碱基数 |
| `cds.boundaries` | `cds` | `inclusive`（默认，两端都算）或 `half_open` |
| `genetic_code` | 两者 | Biostrings 的遗传密码表名，默认 `Standard` |
| `transcript_id` | `genome` | 只注释指定转录本（如 `ENST00000621650`） |
| `transcript_all` | `genome` | `true` 时注释所有重叠转录本，而不只是 MANE Select |
| `notes` | 两者 | 自由文本，仅供人看 |

未列出的键会被忽略；上面 `example_cds.json` 里的 `amplicon_reference` 就属于这种
纯说明字段，程序不会去读它。

## 怎么拿到 `cds` 路线的坐标

按可靠性从高到低：

1. **扩增子设计文件**：引物与载体/基因的坐标表，通常直接给出 CDS 在设计序列上的起止；
2. **公司交付的注释**：`01_data/test_data/**/variants.*.xlsx` 这类表格里的坐标体系；
3. **自己找开读框**：在扩增子参考上找 `ATG ... 终止密码子`。仓库自带的
   `example_cds.json` 就是这么定的（E4-3 扩增子上最长的 ORF，118..237，120 bp）。
   注意这只保证"能翻译"，**不保证它就是真实 CDS**——真实坐标要来自实验设计。
4. **先用 `genome` 路线反推**：联网跑一次 `--list-transcripts`，看程序把扩增子定位到
   哪个转录本、CDS 在第几段，再换算到扩增子坐标系。

## 两条硬性约束

**1. CDS 长度必须是 3 的倍数。** 否则程序不会猜、不会截断，而是跳过该注释。例如：

```
WARN  annotation: amplicon_cds_55_320 skipped: CDS length 266 is not a multiple of 3 (drop 2 bp or fix the frame)
```

这种情况下运行仍然以退出码 0 结束（序列分析本身是成功的），但 `qc.tsv` 会写入
`annotation_available = FALSE` 和 `annotation_skip_reason`，`run_manifest.json` 的
`annotation` 段会写入 `available: false`、`skipped_transcripts`。

如果只是**部分**转录本被跳过（`--transcript all` 时常见：某个转录本没有权威 CDS），
`available` 仍是 `true`，但 `annotation_skip_reason`、`skipped_transcripts` 以及
`qc.tsv` 的 `n_transcripts_annotated` / `n_transcripts_skipped` 同样会记录被跳过的是
哪一个、为什么。**只看 `annotation.tsv` 里出现了几条是不够的，请以这些字段为准。**

**2. `cds` 坐标只对得上你给的那条参考序列。** 传给 `--reference` 的 FASTQ/FASTA
必须是坐标所基于的那条扩增子；换参考就要重新给坐标。

## `genome` 路线的注意事项

- 需要联网（Ensembl REST）。取不到时会**非零退出**并给出提示，不会静默降级；
- 结果随 Ensembl release 变化，发表或复核请记录 `run_manifest.json` 里的
  `annotation.ensembl_release`（本版还没有 `--ensembl-release` 来钉死版本）；
- 如果扩增子不在内置 gene panel 里，程序会退化成逐染色体扫描，可能非常慢
  （结果会缓存到 `~/.cache/nanoamp/ref/`，重跑可续）；这种情况建议改用 `cds` 路线。
