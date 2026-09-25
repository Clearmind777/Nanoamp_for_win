# 命令行版（CLI）

面向**需要批量处理几十上百个样本**的用户。

如果只是偶尔分析一两个样本，使用图形界面版操作更少 —— 见
[`../03_GUI/README.md`](../03_GUI/README.md)。

## 目录内容

```text
02_CLI/
|-- README.md
`-- bin/
    |-- nanoamp.cmd         Windows 启动器（安装后会被复制到 PATH 目录）
    |-- nanoamp             Linux / macOS 启动器（同仓库跨平台保留）
    |-- nanoamp.R           R 驱动脚本（开发时用）
    |-- install_cli.bat     把 nanoamp.cmd 装到指定目录
    `-- install_cli.sh      Linux / macOS 版本的安装脚本
```

## 安装

**推荐方式：直接双击 `../install.exe`。** 它会：

1. 把启动器和驱动脚本装到 `%LOCALAPPDATA%\nanoamp\`；
2. 把 `%LOCALAPPDATA%\nanoamp\bin` 加进**用户 PATH**；
3. 把 `minimap2.exe` 放到同一个目录并写进驱动脚本。

安装完成后**新开一个命令行窗口**（PowerShell 或 cmd 均可）即可使用：

```bat
nanoamp doctor
```

> PATH 的改动只对新开的窗口生效，已经打开的窗口读不到。

## 三条命令

```bat
nanoamp doctor                           :: 检查环境：R 版本、依赖包、minimap2
nanoamp call --reads ... --reference ... --outdir ...   :: 分析一个样本
nanoamp batch --sample-sheet samples.tsv --outdir ...   :: 批量分析
```

### `nanoamp doctor`

```bat
nanoamp doctor
```

输出示例（关注 `minimap2` 是否显示路径，而不是 `NOT FOUND`）：

```text
nanoamp version: 0.1.0
R version: R version 4.6.1 (2026-06-24 ucrt)
platform: windows-x86_64
  Biostrings   TRUE
  ...
  minimap2     C:\Users\xxx\AppData\Local\nanoamp\bin\minimap2.exe (2.31-r1302)
  samtools     NOT FOUND
  curl         C:\Windows\system32\curl.exe
  cache-dir    C:\Users\xxx\AppData\Local\nanoamp\cache\ref
  cache-size   0
  configs      C:/Users/xxx/AppData/Local/nanoamp/R/lib/nanoamp/configs
  annotation   available
```

末尾五行与**功能注释（可选）**有关：`curl` 是在线路线用的 HTTP 客户端
（`NOT FOUND` 时只有在线路线不可用，会回退到 R 自带的下载能力）；`cache-dir` /
`cache-size` 是参考序列切片的缓存位置与占用；`configs` 是**随包的示例配置目录**
—— 里面的 `example_cds.json` / `example_online.json` 可以直接给
`--annotate-config` 用（安装器另外在 `<安装目录>\configs\` 放一份可编辑副本）；
`annotation` 为 `available` 表示注释所需的 R 包齐全。

### `nanoamp call` — 单个样本

```bat
nanoamp call ^
  --reads   "D:\data\sampleA.fastq" ^
  --reference "D:\data\target.fa" ^
  --mode A ^
  --top-n 20 ^
  --outdir  "D:\results\sampleA"
```

`^` 是 cmd 的换行符；在 PowerShell 里用反引号 `` ` ``，或写成一整行。

| 参数 | 默认 | 说明 |
|---|---|---|
| `--reads` | **必填** | 输入 FASTQ（可 `.gz`） |
| `--reference` | **必填** | 目的序列 FASTA |
| `--outdir` | **必填** | 输出目录（自动创建） |
| `--mode` | `A` | `A` 参考引导 / `B` 从头聚类 / `C` 精确匹配 |
| `--top-n` | 20 | 输出前 n 条单倍型 |
| `--min-reads` | 3 | 变异最少 reads 支持数 |
| `--min-freq` | 0.02 | 变异最低频率 |
| `--min-identity` | 0.90 | read 最低一致度 |
| `--identity-cutoff` | 0.99 | 方案 B 聚类阈值 |
| `--min-cluster-reads` | 2 | 方案 B 最小簇大小 |
| `--consensus-method` | `decipher` | `decipher` 或 `medoid` |
| `--aligner` | `minimap2` | 换成 `r` 使用 R 内比对（无需外部程序） |
| `--threads` | 4 | 线程数 |
| `--ref-label` | 参考文件名 | 输出里的参考名称 |
| `--no-intermediates` | 关 | 不保留 BAM 等中间文件 |

参数取值不确定时，可先用默认值分析 E4-3 这个样本，再与
`00_materials/tutorial.md` 里的预期输出对比。

#### 功能注释参数（可选，共 9 个）

不加其中任何一个时，输出与以前逐字节一致；`batch` 会把它们逐样本转交下去。

| 参数 | 默认 | 说明 |
|---|---|---|
| `--annotate-config <config.json>` | 关 | **启用注释的唯一开关**；配置里写 `"route": "genome"` 或 `"cds"` |
| `--transcript <ENST…\|all>` | 配置里的值 | 只注释指定转录本；`all` = 全部重叠转录本（不改配置文件，只覆盖本次运行） |
| `--list-transcripts` | 关 | 只列出扩增子重叠的转录本后退出（需要联网，不做分析）；同一份清单会写成 `<outdir>\transcripts.tsv`（GUI 的转录本下拉框读的就是它） |
| `--annotation-proteins` | 关 | `annotation.tsv` 多两列参考/突变蛋白序列（可能很长） |
| `--annotation-detail` | 关 | 额外写 `variants_annotation.tsv`（每个变异一行的后果） |
| `--cache-dir <dir>` | 用户缓存目录 | 参考序列切片的缓存位置（等价于设 `NANOAMP_CACHE_DIR`） |
| `--no-cache` | 关 | 本次不读也不写缓存（**不会删除缓存目录**，目录由并发运行共享） |
| `--clear-cache` | — | 清空缓存目录后退出（不做分析，**不需要** `--reads`/`--reference`） |
| `--strict` | 关 | 注释有转录本被跳过时**以非零状态退出**（默认只是记账，退出码仍为 0） |
| `--min-ref-coverage` | 0.90 | read 至少要覆盖参考序列的多大比例（`aligner = "r"` 下按实际比对片段计算） |

两个与缓存/网络有关的子命令：

```bat
nanoamp cache                  :: 打印 cache-dir / cache-size / cache-files
nanoamp cache --clear          :: 清空缓存
nanoamp doctor --check-online  :: 问一次 Ensembl 是否可用，不可用时退出码非 0
```

> `--annotate`（少了 `-config`）会被直接拒绝并提示正确写法；`--annotation-route`
> 不存在（路线写在配置文件里）；`--ensembl-release` 未实现。

### `nanoamp batch` — 批量

样本表是一个 **TSV**（制表符分隔），必须包含这三列（列名不能改）：

```text
sample	reads	reference
sampleA	D:/data/sampleA.fastq	D:/data/targetA.fa
sampleB	D:/data/sampleB.fastq	D:/data/targetB.fa
```

- `sample` 会成为输出子目录名，**不要含 `/` `\` 或空格**；
- `reads` / `reference` 建议使用绝对路径；相对路径相对于**执行命令时所在的目录**，
  而不是相对于样本表的位置。

还可以**加一列可选的 `ref_label`**，给每个样本单独指定参考名称
（对应 `call` 的 `--ref-label`）。不加这一列就用参考文件名。
这个名字会出现在 `qc.tsv` 的 `reference_label` 行和 `run_manifest.json`
的 `qc.reference_label` 里 —— **不会**改 `run_manifest.json` 顶层的
`reference.name`，那一项始终是 FASTA 里的原始序列名。

然后：

```bat
nanoamp batch --sample-sheet samples.tsv --mode A --threads 8 --outdir "D:\results"
```

`batch` 接受和 `call` **完全一样的分析参数**（含功能注释的那 9 个），只是把
`--reads` / `--reference` 换成了样本表，并额外多了 `--sample-sheet`。
注释配置整批共用一份，注释结果与覆盖情况按样本各自写进该样本的目录
（`batch_summary.tsv` 只汇总成功 / 失败，不含注释细节）。
参考名称不走命令行，
而是上面说的 `ref_label` 列 —— 因为批量时每个样本可能不同。

上面 `call` 的参数表整张都适用，例如：

```bat
nanoamp batch ^
  --sample-sheet samples.tsv ^
  --outdir "D:\results" ^
  --mode A ^
  --threads 8 ^
  --min-reads 5 ^
  --no-intermediates
```

输出结构：

```text
D:\results\
|-- batch_summary.tsv        每个样本一行汇总（含 status、error 列）
|-- sampleA\                 和单独跑 call 时完全一样的输出
|   |-- haplotypes.tsv
|   |-- qc.tsv
|   `-- ...
`-- sampleB\
    `-- ...
```

任何一个样本失败**不会中断整批**：该样本的 `status` 记为 `error`、`error` 列
写下报错原因，其余样本照常跑完。因此分析结束后应首先检查
`batch_summary.tsv` 的 `status` 列，而不是看屏幕最后一行。

失败的样本如果没有任何产出，它那个空目录会被自动删掉（避免一排空目录
看起来像"跑了一半"）；如果失败前已经写进去了一些文件，目录会保留下来，
便于排查现场。成功和失败的样本加起来，目录数和 `batch_summary.tsv` 的
`status=ok` 行数应当一致。

> 用 Excel 存 TSV 时注意：选「文本（制表符分隔）」，不要选 CSV。
> 路径建议使用正斜杠 `/`；反斜杠偶尔会被转义。

## 输出文件

每次 `call` 会在 `--outdir` 生成：

```text
haplotypes.tsv          单倍型表（核心结果，可用 Excel 打开）
haplotypes.fasta        前 top-n 条单倍型序列
variants.tsv            变异位点，列名与公司 *.var.xls 兼容
qc.tsv                  质量指标
run_manifest.json       参数、版本、输入哈希（可追溯）
annotation.tsv          仅启用功能注释时：每个「单倍型 × 转录本」一行后果
variants_annotation.tsv 仅启用注释 + --annotation-detail 且本次确有变异时：每个变异一行
alignments.bam(.bai)    比对结果（除非 --no-intermediates）
```

`qc.tsv` 还会多出注释指标（`n_transcripts_annotated` / `n_transcripts_skipped` /
`annotation_available` / `annotation_skip_reason` 等），`run_manifest.json` 会多出
`annotation` 段（含 `skipped_transcripts`，逐条说明哪个转录本被跳过、为什么）。

**判断"这次到底注释了哪些转录本"，请看这些字段，不要只看 `annotation.tsv` 有几行。**

## 功能注释（可选）

不传 `--annotate-config` 时这一节可以整节跳过。用仓库自带的 E4-3 数据跑离线路线
（配置里的坐标就是该扩增子上最长的开读框，118..237）：

```bat
nanoamp call ^
  --reads   "01_data\TSM20260826\E4-3\reads.fastq" ^
  --reference "01_data\TSM20260826\E4-3\reference.self.fa" ^
  --mode A ^
  --annotate-config "02_code\r\inst\configs\example_cds.json" ^
  --annotation-detail ^
  --outdir  "tmp\test_results\demo\E4-3_annot"
```

跑完会多出 `annotation.tsv`（12 行 = 12 个单倍型 × 1 个转录本）与
`variants_annotation.tsv`（22 行 = 每个变异一行）。行数本身不是重点，
要点是**覆盖情况被记录下来**：`qc.tsv` 的 `n_transcripts_annotated` /
`n_transcripts_skipped` 与 `run_manifest.json` 的 `annotation.skipped_transcripts`。

在线路线先探查、再注释：

```bat
:: 1) 看扩增子落在哪些转录本（需要联网）
nanoamp call --reads "01_data\TSM20260826\E4-3\reads.fastq" --reference "01_data\TSM20260826\E4-3\reference.self.fa" --outdir "tmp\test_results\demo\E4-3_list" --list-transcripts

:: 2) 指定转录本做注释
nanoamp call --reads "..." --reference "..." --mode A --annotate-config "02_code\r\inst\configs\example_online.json" --transcript ENST00000621650 --outdir "tmp\test_results\demo\E4-3_online"
```

两条路线的差别：

| 路线 | 需要联网 | 限制 |
|---|---|---|
| `cds`（离线） | 否 | CDS 长度必须是 3 的倍数，坐标必须按自己的扩增子给出；长度不对时**跳过该注释并记账**，退出码仍为 0 |
| `genome`（在线） | 是 | 扩增子不在内置 panel（当前只有 ZNF8）时会退化为逐染色体扫描，**可能非常慢**；与 GRCh38 匹配不足（锚定覆盖率 < 0.9）时**明确报错**；网络不可达时**非零退出** |

> 注释**不新增任何 R 依赖包**，只多一个外部前提：系统里有 `curl.exe`
> （Windows 10 1803 起自带）。配置字段、取坐标的方法与缓存细节见
> `02_code/r/inst/configs/README.md`、`02_code/shared/docs/output_schema.md`
> 与教程 §2.10。

## 用命令行查看结果

```bat
:: 前 10 行单倍型表
more +0 haplotypes.tsv | findstr /n "^" | findstr /b "^[1-9]: ^10:"

:: 只看 QC 里的 reads 数
type qc.tsv | findstr n_reads_total
```

也可以直接用 Excel 打开 `haplotypes.tsv`。

## 退出码

| 码 | 含义 |
|---:|---|
| 0 | 成功 |
| 1 | 失败（参数错误、文件不存在、依赖缺失、分析出错、网络不可达） |

批量脚本可据此判断执行结果。

**功能注释被跳过时退出码仍是 0**：注释是附加步骤，它被跳过或不可用时序列分析本身
仍然成功，进程返回 0，但会把"跳过了什么、为什么"写进 `qc.tsv`
（`n_transcripts_skipped` / `annotation_skip_reason`）与 `run_manifest.json`
（`annotation.skipped_transcripts`）。要在流水线里把它当失败，加 `--strict`
（退出码 1，`run_manifest.json` 的 `status` 记为 `"failed"`）。

唯一的例外是**在线路线取不到数据**（网络不可达、Ensembl 返回错误）：这属于分析无法
完成，会直接以非零状态退出，不会给出"没有注释的成功结果"。

## 构建 / 开发说明

- 驱动脚本 `nanoamp_cli.R` 由 `install.exe` 生成到
  `%LOCALAPPDATA%\nanoamp\config\`，里面写死了库路径和 `NANOAMP_MINIMAP2`。
- `nanoamp.cmd` **必须是纯 ASCII**：cmd.exe 用控制台 OEM 代码页读取 `.cmd`，
  UTF-8 中文会被解析成乱码命令。中文说明一律放 README。
- 仓库内也可以直接运行（不安装）：

  ```bat
  set R_LIBS_USER=D:\tools\R\lib
  Rscript 02_code\cli\nanoamp.R doctor
  ```
