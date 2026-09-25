# 输出文件 schema（跨语言契约）

所有实现（R 核心库、CLI、GUI）都应在 `--outdir` 下生成以下文件，字段名保持一致。

`--outdir` 里除了结果表，总有这两个"运行档案"（**失败时也会写**）：

```text
run_manifest.json   本次运行的参数/版本/状态/失败原因
nanoamp.log         本次运行的日志（与终端输出同一份内容）
```

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
`clustering_method`、`consensus_method`、`decipher_version`、
**`clustering_seed`**、`clustering_note`。

> **Mode B 的可复现性**：`DECIPHER::Clusterize` 是随机算法——同一份输入连续调用会
> 给出不同的簇（实测同一批 437 条 reads：38/38/35 簇，即使 `processors = 1`）。
> nanoamp 在调用前固定随机种子（`clustering_seed`，默认 42），因此 Mode B 现在
> 可复现；该字段写入 `qc.tsv` 供追溯。种子只在调用期间生效，不会改动调用方 R 会话的
> 随机数流（有单测锁定）。

## run_manifest.json

记录：

```text
nanoamp_version
mode
status                            # done | failed | cancelled
timestamp
r_version / python_version
log_path                          # 本次运行的日志文件（nanoamp.log）
reference: {name, length, md5, path}
params
qc
reads_md5
annotation                        # 仅启用功能注释时
error_class / error_message       # 仅失败时
```

### status —— 这次运行到底怎么了

| 值 | 谁写 | 含义 |
|---|---|---|
| `done` | R | 分析正常跑完（注释被跳过也仍是 `done`，见下） |
| `failed` | R | 分析中途失败；同时给出 `error_class` 与 `error_message` |
| `cancelled` | GUI | 用户在图形界面点了「取消操作」，R 进程被终止；由 GUI 补写 |

`failed` 的 `error_class` 只有四种取值，GUI 用它挑选"怎么办"的提示（不再对
所有失败都弹同一句话）：

| error_class | 含义 | 提示方向 |
|---|---|---|
| `input` | 输入或配置问题（文件不存在、FASTQ/FASTA 格式、配置非法、CDS 长度不是 3 的倍数…） | 检查选的文件与注释配置 |
| `environment` | 运行环境问题（缺 R 包、缺外部工具、输出目录不可写、磁盘满） | 先跑「环境自检」，必要时重跑安装器 |
| `network` | 网络问题（在线注释访问 Ensembl 失败、代理/防火墙） | 改用离线 CDS 配置，或修好网络重试 |
| `internal` | nanoamp 自身错误（含自检不通过） | 把运行日志 + 本文件一起反馈 |

**失败也一定会留下 `run_manifest.json` 和 `nanoamp.log`**（目录会被创建），
所以"运行失败后什么都没有"这种情况不会发生；退出码仍然是 0（成功）/ 1（失败）。

> `--strict`（可选）：默认情况下"注释有转录本被跳过"只是**降级**（记为
> `annotation_available=false` / `annotation_skip_reason`，退出码 0）。加上
> `--strict` 后它变成失败：`status = "failed"` 且退出码 1，供流水线使用。
> 不加这个参数，行为与以前完全一致。

---

# 功能注释（可选）

启用方式：GUI 勾选「功能注释…」，或命令行加 `--annotate-config <config.json>`。
**不传该参数时，输出与未启用注释时逐字节一致**（有测试锁定这一点）。

## transcripts.tsv（`--list-transcripts` / GUI「列出转录本」）

只做"列出候选转录本"这一次运行时写出：该扩增子在 GRCh38 上重叠到的每个转录本一行。
控制台同时打印同样内容的人工表格，但 GUI 的转录本下拉框是从**这个文件**读的，
所以列名属于契约的一部分：

| 列名 | 说明 |
|---|---|
| `transcript_id` / `name` | 转录本 ID 与名称（无名称写 `-`） |
| `biotype` | `protein_coding` / `lncRNA` … |
| `mane` / `canonical` | 是否为 MANE Select / Ensembl canonical（否为空格） |
| `chrom` / `start` / `end` / `strand` | 定位到的扩增子区间（1-based，闭区间） |
| `cds_overlap_bp` | 该转录本与扩增子的 CDS 重叠碱基数；`--list-transcripts` 默认不计算，故为空 |

没有任何转录本重叠时也会写出这个文件，只是 0 行——GUI 因此不需要特判。

## annotation.tsv

每个**单倍型 × 所选转录本**一行；`--transcript all` 时包含全部重叠转录本。

| 列名 | 类型 | 说明 |
|---|---|---|
| `haplotype_id` | string | 关联 `haplotypes.tsv` |
| `count` / `proportion` | int / float | 从 `haplotypes.tsv` 带过来，便于直接阅读 |
| `transcript_id` / `transcript_name` | string | 所用转录本 |
| `is_mane` / `is_canonical` | bool | 该转录本是否 MANE Select / Ensembl canonical |
| `cds_ok` | bool | FALSE 表示边界或序列异常，后续列为空 |
| `ref_protein_length` / `alt_protein_length` | int | 参考/突变蛋白长度（aa） |
| `n_aa_changed` | int | 氨基酸改变数 |
| `protein_change` | string | HGVS 风格描述（**非合规 HGVS**），如 `p.Lys2Glu`、`p.Phe3fs`、`p.Lys2del` |
| `consequence_en` / `consequence_zh` | string | 后果英文枚举与中文标签（中英双列） |
| `consequence_any_transcript` / `_zh` | string | 该单倍型在所选转录本中**最严重**的后果 |
| `transcript_conflict` | bool | 同一单倍型在不同转录本下后果不同 |
| `variants` / `signature` | string | 与 `haplotypes.tsv` 一致 |
| `notes` | string | 异常说明，例如 `length change +14 bp (not a multiple of 3)` |
| `ref_protein` / `alt_protein` | string | 仅 `--annotation-proteins` 时输出（可能很长） |
| `rank` | int | 单倍型 × 转录本的排序序号，**附在最后一列** |

### 后果枚举（`consequence_en`）

顺序即严重度从高到低（用于 `consequence_any_transcript` 的取最严重）：

```text
frameshift  stop_gained  stop_lost  start_lost
inframe_insertion  inframe_deletion  missense  synonymous
splice_donor  splice_acceptor  splice_region
5_prime_UTR  3_prime_UTR  intron  outside_cds  intergenic
cds_boundary_disrupted  cds_ambiguous_base  no_variant
```

约定：**与目的序列完全一致的单倍型记 `no_variant`**（蛋白变化 `p.(=)`），
而不是 `synonymous`——后者表示"有编码改变但沉默"，含义不同。

### qc.tsv 注释相关指标

```text
annotation_enabled  annotation_name  annotation_route  annotation_source
ensembl_release  genetic_code  n_transcripts  annotation_available
n_transcripts_annotated  n_transcripts_skipped
n_haplotypes_annotated  n_haplotypes_skipped
n_frameshift  n_stop_gained  n_stop_lost  n_start_lost
n_missense  n_synonymous  n_inframe  n_transcript_conflicts
annotation_skip_reason                     # 仅当 n_transcripts_skipped > 0
```

`annotation_source` 是结构/序列的真正来源：`ensembl-rest`（`genome` 路线）或
`cds-config`（`cds` 路线，全程离线，不访问 Ensembl）。

`n_transcripts` 是选中的转录本数，`n_transcripts_annotated` /
`n_transcripts_skipped` 是其中成功与失败的条数（两者之和等于 `n_transcripts`）。

**只要有转录本被跳过——无论是"部分成功"还是"全部失败"——都会被记录**，因为控制台的
WARN 在运行结束后无法追溯：

- `qc.tsv`：`n_transcripts_skipped > 0` 时写 `annotation_skip_reason`；
- `run_manifest.json`：`annotation.skipped_transcripts` 始终存在，逐条给出
  `transcript_id` / `transcript_name` / `problem`。

全部失败时（例如配置里的 CDS 长度不是 3 的倍数）还额外写
`annotation_available = FALSE` 与 `annotation.available = false`；**进程仍以退出码 0 结束**，
因为序列分析本身是成功的。GUI 会把这两种情况显示在「注释结果」页的状态行。

**判断"这次到底注释了哪些转录本"请看 `n_transcripts_skipped` 与
`skipped_transcripts`，不要只看 `annotation.tsv` 里出现了几个转录本。**

### run_manifest.json 的 annotation 段

```json
"annotation": {
  "enabled": true,
  "available": true,
  "source": "ensembl-rest",
  "ensembl_release": "116",
  "config_path": "...", "config": { },
  "genomic": { "chrom": "19", "start": 0, "end": 0, "strand": "+",
                "identity": 1.0, "n_mismatch": 0, "method": "exact_match" },
  "transcripts": [ { "transcript_id": "ENST...", "transcript_name": "...",
                     "is_mane": true, "is_canonical": true,
                     "cds_length": 0, "protein_length": 0,
                     "protein_verified": true, "cds_blocks": 0 } ],
  "skipped_transcripts": [ { "transcript_id": "ENST...", "transcript_name": "...",
                             "problem": "could not fetch the authoritative CDS sequence" } ]
}
```

`protein_verified` 的含义是**真正的校验结果**：`true` 仅当本次把该转录本的参考 CDS 翻译后
与 Ensembl 提供的蛋白逐残基比对通过；离线 `cds` 路线没有权威蛋白可比对，因此为 `false`
（这条是 Windows 版相对 Linux 版的修正——Linux 版此处恒为 `true`，见差异说明 L10）。

没有任何转录本可用时（`available: false`）：

```json
"annotation": {
  "enabled": true,
  "available": false,
  "source": "cds-config",
  "ensembl_release": null,
  "config_path": "...", "config": { },
  "genomic": null,
  "transcripts": [],
  "skipped_transcripts": [
    { "transcript_id": "amplicon_cds_55_320",
      "transcript_name": "example",
      "problem": "CDS length 266 is not a multiple of 3 (drop 2 bp or fix the frame)" }
  ]
}
```

## variants_annotation.tsv（变异级明细，可选）

仅当 `--annotation-detail`（GUI：勾选「输出变异级明细」）时生成：每个变异一行。

| 列名 | 说明 |
|---|---|
| `haplotype_id` | 所属单倍型；`transcript_id` 为所用转录本 |
| `type` | `snv` / `ins` / `del` / `delregion` |
| `genome_pos` | `genome` 路线为基因组坐标（1-based）；`cds` 路线为**目的序列上的坐标** |
| `cds_pos` | 该变异在拼接后 CDS 中的位置；空表示不在 CDS 内 |
| `ref` / `alt` | 所在坐标系正链上的等位基因（负链已翻转） |
| `codon_ref` / `codon_alt` | 受影响密码子（仅替换类变异） |
| `aa_ref` / `aa_alt` | 对应氨基酸（仅替换类变异） |
| `consequence_en` / `consequence_zh` | 单变异后果（中英双列） |

注意：这是**单变异**视角。多变异组合的最终后果以 `annotation.tsv` 为准——两者可能不同。

### 负链支持

定位到负链（`genome` 路线的定位结果，或 `cds` 路线的 `cds.strand`）时，
`genome_pos` 按 `end - pos + 1` 换算（插入为 `end - pos + 2`，因为插入锚定在插入点之后），
**等位基因与 CDS 一起反向互补**，使所有操作都能作用在正链序列上。正链与负链表述的同一变异
必须得到相同后果（由 `tests/testthat/test-annotate-offline.R` 的镜像测试保证）。

### 缓存与网络（Windows）

| 项 | 说明 |
|---|---|
| 缓存位置 | `NANOAMP_CACHE_DIR` → `%LOCALAPPDATA%\nanoamp\cache\ref` → `%TEMP%\nanoamp\ref`（Linux 用 XDG 目录） |
| `--cache-dir` | 覆盖缓存目录（等价于设置 `NANOAMP_CACHE_DIR`） |
| `--no-cache` | **本次运行不读写缓存**（不会删除缓存目录——目录由并发运行共享） |
| `--clear-cache` | 清空缓存目录并退出 |
| HTTP 客户端 | 优先系统 `curl`；缺失时回退到 R 自带的下载能力 |
| 失败策略 | 服务不可达时**报错并以非零状态退出**，绝不返回"没有注释的成功结果" |

