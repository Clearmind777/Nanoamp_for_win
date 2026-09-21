# 公司原始交付的文件说明（按原始命名整理）

> 本文档描述**公司交付时的原始文件名与目录结构**，原文件在 `01_data/test_data/`。
> 现在仓库里 `TSM20260826/`、`ZNF8/`、`nano_seq/` 三个数据集已经改成
> `<dataset>/<sample>/<规范化文件名>`（`reads.fastq`、`reference.self.fa`、
> `consensus.N.fa`、`variants.N.xlsx`、`sanger.N.ab1`），
> **每个样本目录里的 `meta.tsv` 记录了规范化文件名与原文件名的对应关系**。
> `SD260728184122_1/`、`SD260812174403_1/` 两个批次不属于链接层，保持下面的原始结构。
> 下文出现的 `test_data/` 路径即指当初的原始交付目录。

---

# test_data 数据说明

> 目录：`01_data/test_data`
> 规模：5 个子目录，约 408 个文件，约 81 MB
> 说明：本文根据目录结构、文件内容和 BAM 头信息整理。具体基因、编辑方式和样本分组建议再与实验人员核对。

---

## 0. 一句话总结

这是一批**基因编辑 / 碱基编辑后，对目标区域做靶向扩增子测序（主要是 Oxford Nanopore 纳米孔测序）的验证数据**，同时包含 Sanger 测序峰图、比对结果和变异统计表。

数据要回答的核心问题是：

1. 目标位点发生了哪种突变（SNP、插入、缺失等）；
2. 突变在样本中占多大比例（Freq / 变异比例）；
3. 不同克隆、不同处理条件之间突变情况有什么差异；
4. 纳米孔结果能否被 Sanger 测序验证。

---

## 1. 判断依据

这些结论不是只看文件名猜的，主要依据如下：

- BAM 的 `@PG` 行显示使用 `minimap2 -ax map-ont`，`map-ont` 是 Oxford Nanopore 长读长比对模式。
- BAM 上游路径中出现 `02.NanoFilt/xxx_clean.fastq.gz`，说明 reads 经过 NanoFilt 质控。
- FASTQ read ID 形如 `@20260827_250301Y0002_Run0001/379571/32-596`，是典型的 Nanopore 测序 read 命名。
- TSM / nano_seq / ZNF8 的 BAM 上游路径出现 `Consensus_.../tmp_reads/Clust_0.reads.cutBarcodes.fasta`，说明 reads 按 barcode 拆分后又做了聚类，取主簇（Clust_0）做共识序列。
- `.ab1` 是 ABI Sanger 测序峰图格式。
- `.变异统计表.xlsx` 的字段明确包含变异类型、变异比值、变异比例和变异位点峰图。

---

## 2. 数据处理流程

从文件名和 BAM 头信息推断，整体流程大致是：

```text
样本 DNA
  ↓ PCR 扩增目标区域 / 提取质粒
  ↓ Nanopore 测序
  ↓ basecalling
  ↓ NanoFilt 质控，得到 *.fastq
  ↓ 按 barcode 拆分到各个样本
  ↓ reads 聚类（Clust_0、Clust_1 ...）
  ↓ 每个簇生成共识序列 *.seq / *.consensus.fasta
  ↓ minimap2 将该簇 reads 比对回共识序列或扩增子参考序列
  ↓ 得到 *.sort.bam / *.sorted.bam 及索引 *.bai
  ↓ 变异检测
  ↓ *.var.xls、*.filt.var.xls、*.变异统计表.xlsx
  ↓ Sanger 测序进行正交验证，得到 *.ab1
```

不同目录处在流程的不同阶段：

- `SD260728184122_1/`、`SD260812174403_1/`：整理好的结构化交付结果，包含 Bam / Var / QC / Sequence 四个子目录。
- `TSM20260826-020-01254/`、`nano_seq/`、`ZNF8/`：更接近原始导出或中间结果的平铺目录，一个样本的多种文件混在一起。

---

## 3. 目录总览

```text
test_data/
├── SD260728184122_1/        # 3 个有效样本 + 1 个只有 QC 的样本
├── SD260812174403_1/        # 15 个样本，分 A4、E4 两组
├── TSM20260826-020-01254/   # 6 个样本，平铺目录
├── ZNF8/                    # ZNF8 靶点：15 个克隆样本 + 1 个 WT 对照
└── nano_seq/                # 10 个样本：G1–G5 + 293T-G1–G5 对照
```

| 目录 | 样本数 | 实验类型 | 参考序列长度 | 比对 reads 量级 | 目录组织 |
|---|---:|---|---|---|---|
| `SD260728184122_1` | 3 个有效样本 | Nanopore 扩增子测序 | ZAK 493 bp；GCN2 593 bp | 7,381–9,146 | 结构化：Bam/Var/QC/Sequence |
| `SD260812174403_1` | 15 个样本 | Nanopore 扩增子测序 | E4 组 529 bp；A4 组 794 bp | 225–14,005 | 结构化：Bam/Var/QC/Sequence |
| `TSM20260826-020-01254` | 6 个样本 | Nanopore + Sanger | 约 319–568 bp（少数簇更长） | 37–360 | 平铺，按孔位命名 |
| `ZNF8/ZNF8` | 15 个克隆 | Nanopore + Sanger | 约 208–320 bp | 14–188 | 平铺，按克隆编号命名 |
| `ZNF8/2026.8.29-wt` | 1 个 WT 对照 | Nanopore + Sanger | 320 bp | 42 | 平铺 |
| `nano_seq` | 10 个样本 | Nanopore + Sanger | 约 637–740 bp | 52–310 | 平铺，G1–G5 与 293T-G1–G5 |

---

## 4. 文件后缀与用途速查

| 文件后缀 / 文件名 | 文件类型 | 主要用途 | 常用打开方式 |
|---|---|---|---|
| `*.fastq` | FASTQ 文本 | Nanopore 质控后的原始 reads，是聚类和共识序列的输入 | `zcat`、`seqkit`、`NanoPlot`、Python |
| `*.seq` | FASTA 文本 | 某个聚类簇的共识序列，代表该样本的主导序列 | 文本编辑器、SnapGene、BioEdit、`samtools faidx` |
| `*.consensus.fasta` | FASTA 文本 | SD 目录中的共识序列，与 Sanger 结果对应 | 同上 |
| `*.for.ref.fa` | FASTA 文本 | SD 目录中该样本使用的扩增子参考序列 | 文本编辑器、BLAST |
| `*.fasta` / `*.fa` | FASTA 文本 | 比对用参考序列，通常是样本自己的共识序列 | 文本编辑器、`samtools faidx` |
| `*.sort.bam` / `*.sorted.bam` | BAM 二进制 | reads 比对结果，用于看覆盖度、支持 reads 和变异位点 | `samtools`、IGV、Geneious |
| `*.bai` | BAM 索引 | 让 BAM 可以按坐标快速访问 | 随 BAM 一起使用，不需要手动打开 |
| `*.var.xls` | 其实是 TSV 文本 | 全部变异位点的完整表，包含 PASS 和 FILTERED | 文本编辑器、`column`、Python、Excel |
| `*.filt.var.xls` | 其实是 TSV 文本 | 过滤后的变异表，一般只保留通过过滤的位点 | 同上 |
| `merged_data.var.xls` | 真正的 Excel 二进制 | 多样本合并的全部变异表 | Excel、LibreOffice、`pandas.read_excel` |
| `merged_data.filt.var.xls` | 真正的 Excel 二进制 | 多样本合并的过滤后变异表 | 同上 |
| `*.变异统计表.xlsx` | Excel | 单样本变异汇总表，含变异比例和峰图 | Excel、LibreOffice、openpyxl |
| `*.ab1` | Sanger 峰图二进制 | 关键位点的 Sanger 验证结果 | SnapGene、BioEdit、Chromas、Sequencher |
| `*.fai` | FASTA 索引 | 记录参考序列长度和偏移，供 samtools 快速访问 | 自动生成，一般不用手动看 |
| `*.dna` | SnapGene 二进制 | 质粒 / 载体图谱，含全序列和注释 | SnapGene 或兼容软件 |
| `*.clean.read.length.png` | PNG 图片 | reads 长度分布质控图 | 图片查看器 |
| `*.coverage.png` | PNG 图片 | 目标区域覆盖度图 | 图片查看器 |

---

## 5. 逐目录详细说明

### 5.1 `SD260728184122_1/`

这是 2026-07-28 批次的结构化交付结果，涉及两个靶点：ZAK 和 GCN2。

有效样本：

| 样本 | 类型 | 参考长度 |
|---|---|---:|
| `G22607283800_1-293T-ZAK` | 293T 背景 + ZAK | 493 bp |
| `G22607283801_1-ZAK` | ZAK | 493 bp |
| `G22607283802_1-293T-GCN2` | 293T 背景 + GCN2 | 593 bp |

`G22607283803_1-GCN2` 只在 `QC/` 中有 QC 图，没有 BAM、变异表、consensus 或 Sanger 结果，可能是测序失败或数据未交付的样本。

每个有效样本的完整文件组合：

```text
Bam/
  <样本>.for.ref.fa          # 扩增子参考序列
  <样本>.sorted.bam          # reads 比对到 for.ref
  <样本>.sorted.bam.bai      # BAM 索引
Var/
  <样本>.var.xls             # 全部变异，含 FILTERED
  <样本>.filt.var.xls        # 过滤后变异
QC/
  <样本>.clean.read.length.png
  <样本>.coverage.png
Sequence/
  <样本>.consensus.fasta     # Sanger / 组装共识序列
  <样本>_1.ab1               # Sanger 峰图
```

目录根下还有：

- `merged_data.var.xls`：3 个样本合并的全部变异表；
- `merged_data.filt.var.xls`：3 个样本合并的过滤后变异表。

**这个目录的比对模式**：reads 比对到公共扩增子参考 `for.ref`，变异是相对参考序列计算的，因此 `*.var.xls` 里的 `PASS` 位点可以直接理解为候选编辑位点。

### 5.2 `SD260812174403_1/`

这是 2026-08-12 批次的结构化交付结果，共 15 个样本，分两组：

| 分组 | 样本 | 数量 | 参考长度 |
|---|---|---:|---:|
| E4 组 | `G22608076105`、`106`、`108`、`109`、`110`、`111` | 6 | 529 bp |
| A4 组 | `G22608076112`–`G22608076120` | 9 | 794 bp |

样本命名形如 `G22608076105_1-E4-293T-1`：

- `G22608076105_1`：样本编号；
- `E4` / `A4`：实验分组或靶点代号；
- `293T`：细胞背景；
- `-1`、`-2`：同组内的重复或克隆编号。

注意：E4 组和 A4 组的 `for.ref.fa` 序列不同，长度分别是 529 bp 和 794 bp，说明它们不是同一个扩增子，很可能是两个不同的靶点或两套引物。

文件结构与 `SD260728184122_1/` 相同：

```text
Bam/        *.sorted.bam、*.bam.bai、*.for.ref.fa
Var/        *.var.xls、*.filt.var.xls
QC/         *.clean.read.length.png、*.coverage.png
Sequence/   *.consensus.fasta、*_1.ab1
根目录       merged_data.var.xls、merged_data.filt.var.xls
```

这个目录的测序深度差异很大：`G22608076118` 只有 225 条比对 reads，而 `G22608076105` 有 14,005 条。低深度样本的变异频率可靠性会明显低于高深度样本。

### 5.3 `TSM20260826-020-01254/`

这是 2026-08-26 批次的平铺目录，共 6 个样本：

```text
E4-3
E4-9
E4-19
G2-1-9
293T-E4
293T-G2
```

其中 `293T-E4` 和 `293T-G2` 很可能是对应的 293T 对照。

样本文件名可以拆成：

```text
<样本名>_<TSM项目号>_<测序日期>-<批次>-<BAN编号>-<板位>.<结果编号>.<文件类型>
```

例如：

```text
E4-19_TSM20260826-020-01254_20260827-020-BAN05-5_B09.1.sort.bam
```

表示：

- `E4-19`：样本名；
- `TSM20260826-020-01254`：项目编号；
- `20260827-020-BAN05-5_B09`：测序日期、批次、BAN 编号和孔位；
- `.1`：第 1 个聚类簇 / 第 1 套分析结果；
- `.sort.bam`：排序后的比对文件。

同一个样本可能出现 `.1`、`.2` 等多个结果，表示该样本的 reads 被分成了多个簇，分别生成共识序列并单独做变异检测。例如 `E4-19` 有 `.1` 和 `.2` 两个结果。

每个样本通常有：

```text
<前缀>.fastq                              # 该样本的质控后 reads
<前缀>.<簇号>.seq                         # 该簇的共识序列
<前缀>.<簇号>.sort.bam                    # 该簇 reads 比对回共识序列
<前缀>.<簇号>.sort.bam.bai
<前缀>.<簇号>_1.ab1                       # Sanger 峰图
<前缀>.<簇号>.变异统计表.xlsx             # 该簇的变异统计
```

注意：不是每个簇都完整拥有全部文件。有的簇只有 BAM 和索引，没有 `.seq`、`.ab1` 或 `.xlsx`，通常代表该簇支持 reads 较少、没有作为主要结果输出。

这个目录的 BAM 参考序列是**样本自己的共识序列**，不是公共参考基因组。因此：

- `*.seq` 看的是该样本的主导序列；
- `*.sort.bam` 和 `*.变异统计表.xlsx` 看的是在该共识序列背景下，还有哪些少数 reads 支持其他等位基因；
- 如果要判断编辑是否符合预期，需要把 `.seq` 再与 WT / 参考序列单独比对。

### 5.4 `ZNF8/`

这是 ZNF8 靶点的编辑验证数据，分为两个子目录：

#### `ZNF8/ZNF8/`

15 个编号克隆样本：

```text
3、4、5、6、7、9、10、11、12、13、14、16、17、18、20
```

编号不连续，可能表示部分克隆未送测或未成功。文件名形如：

```text
4_TSM20260827-020-01363_20260828-020-BAN09-2_G12.1.seq
```

- 开头的 `4` 是克隆编号；
- `TSM20260827-020-01363` 是项目编号；
- 后面的日期、BAN 编号、孔位与 TSM 目录含义相同；
- `.1`、`.2`、`.3`、`.4` 是不同聚类簇或不同分析结果。

部分样本有多个簇结果，例如：

- 样本 `4`：`.1`–`.4`；
- 样本 `13`、`14`、`16`、`17`、`3`、`5`、`9`：有 `.1`、`.2`。

多簇通常说明该样本的测序 reads 不是单一序列，可能存在混合克隆、杂合编辑、PCR 重组或测序噪声，需要结合变异比例判断。

#### `ZNF8/2026.8.29-wt/`

WT（野生型）对照，样本名为：

```text
WT_TSM20260828-020-01380_20260829-020-BAN05-4_B11
```

包含：

```text
WT_....fastq
WT_....fastq.fai
WT_....1.seq
WT_....1.sort.bam
WT_....1.sort.bam.bai
WT_....1_1.ab1
```

这里的 `fastq.fai` 是按 FASTA 索引方式给 FASTQ 建的索引，属于流程中间产物，不是标准 FASTQ 文件。

#### `ZNF8/ZNF8.dna`

这是 SnapGene 格式的质粒 / 载体图谱文件，包含 ZNF8 相关的完整序列和注释信息。它通常作为参考质粒序列使用，可用 SnapGene 打开，或导出为 FASTA / GenBank 后再做比对。

### 5.5 `nano_seq/`

这是 2026-09-17 批次的平铺目录，共 10 个样本：

```text
G1、G2、G3、G4、G5
293T-G1、293T-G2、293T-G3、293T-G4、293T-G5
```

`293T-G1`–`293T-G5` 很可能是对应的 293T 细胞对照，用来区分编辑引入的变异和细胞背景 / 测序误差。

每个样本的结构与 TSM 目录一致：

```text
<前缀>.fastq
<前缀>.1.seq
<前缀>.1.sort.bam
<前缀>.1.sort.bam.bai
<前缀>.1_1.ab1
<前缀>.1.变异统计表.xlsx
```

共识序列长度约 637–740 bp，reads 数约 52–310 条，属于低深度扩增子数据，适合看主导序列和主要变异类型，不适合检测很低频率的亚克隆。

---

## 6. 一个样本应该怎么看

拿到任意一个样本，建议按下面的顺序看：

1. **先看 FASTQ**
   - 文件：`*.fastq`
   - 目的：确认 reads 数量、长度分布和质控情况。
   - 这一步决定后面的变异结果是否可信。

2. **再看共识序列**
   - 文件：`*.seq` 或 `*.consensus.fasta`
   - 目的：了解该样本的主导序列是什么。
   - 如果多个簇都有 `.seq`，需要比较它们之间的差异。

3. **看比对文件**
   - 文件：`*.sort.bam` / `*.sorted.bam` + `*.bai`
   - 目的：查看目标区域的覆盖度、每个位点的支持 reads。
   - SD 目录比对到 `for.ref`；TSM / nano_seq / ZNF8 比对到样本自己的共识序列。

4. **看变异表**
   - 文件：`*.变异统计表.xlsx`
   - 目的：快速查看主要变异位点、变异类型、变异比例和峰图。
   - 适合做结果汇报和克隆筛选。

5. **看完整变异表**
   - 文件：`*.var.xls`、`*.filt.var.xls`
   - 目的：查看所有候选位点，以及被过滤位点的原因。
   - 适合排查假阳性、poly 结构附近的可疑变异。

6. **看 Sanger 验证**
   - 文件：`*.ab1`
   - 目的：用 Sanger 峰图确认关键位点。
   - 如果 Nanopore 显示某位点突变比例较高，但 Sanger 峰图没有对应杂合峰，需要谨慎判断。

7. **做多样本比较**
   - 文件：`merged_data.var.xls`、`merged_data.filt.var.xls`
   - 目的：横向比较不同样本的变异位点和频率。

---

## 7. 变异结果表字段说明

### 7.1 `*.var.xls` / `*.filt.var.xls`

虽然扩展名是 `.xls`，但这两个文件通常其实是制表符分隔的文本（TSV），可以用文本编辑器或 `column -t -s$'\t'` 查看。

列的含义：

| 列名 | 含义 |
|---|---|
| `Chr` | 参考序列名。SD 目录中通常是样本名；`for.ref` 表示扩增子参考 |
| `Pos` | 突变位点在参考序列上的位置，从 1 开始计数 |
| `Ref` | 参考碱基。`-` 表示插入 |
| `Alt` | 突变碱基。`-` 表示缺失 |
| `DP` | 该位点总覆盖深度 |
| `Ref_dp` | 支持参考碱基的 reads 数 |
| `Alt_dp` | 支持突变碱基的 reads 数 |
| `Freq` | 突变频率，约等于 `Alt_dp / DP` |
| `DP4` | 高质量碱基计数，格式为 `ref-forward, ref-reverse, alt-forward, alt-reverse` |
| `Seq` | 突变位点附近的序列上下文，用 `[Ref/Alt]` 标出变异 |
| `Filter_Status` | `PASS` 或 `FILTERED` |
| `Filter_Reason` | 被过滤的原因，例如频率过低或位于 poly 结构附近 |

`Seq` 列的读法：

```text
TTCATTTAAA[C/T]CTTTTTTTTT   # 第 135 位 C → T
TTCATTTAAA[-/T]CCTTTTTTTT   # 第 135 位插入 T
CATTTAAACC[T/-]TTTTTTTTTG   # 第 137 位 T 缺失
```

`*.filt.var.xls` 通常只保留通过过滤的位点，列比 `*.var.xls` 少 `Filter_Status` 和 `Filter_Reason`。

### 7.2 `merged_data.var.xls` / `merged_data.filt.var.xls`

这两个是真正的 Excel 二进制文件（CDFV2 格式），不是 TSV。内部包含一个 `Merged Data` 工作表，列与单样本 `*.var.xls` 一致，只是把多个样本的结果合并到一张表中，适合做横向比较。

用 Python 读取时需要 `xlrd`：

```python
import pandas as pd
df = pd.read_excel("merged_data.var.xls")
```

### 7.3 `*.变异统计表.xlsx`

这是面向结果解读的汇总表，工作表名为 `常规变异表`，列包括：

| 列名 | 含义 |
|---|---|
| `组装序列名称` | 该结果对应的共识序列 / 样本名称 |
| `突变碱基位置` | 突变位置 |
| `变异类型` | `SNP`、`Homo`、插入、缺失等类型标签 |
| `输出碱基` | 共识序列上的碱基 |
| `变异碱基` | 检测到的另一种碱基；`-` 表示缺失 |
| `变异比值` | 各碱基的支持 reads 数，例如 `T:101 C:243` |
| `变异比例(%)` | 变异碱基 reads 占该位点总 reads 的百分比 |
| `变异位点结果` | 突变位点附近的序列上下文 |
| `变异位点峰图` | 内嵌的 Sanger 峰图 JPEG 图片 |

这个表最适合快速回答“哪个位点突变了、比例是多少、峰图长什么样”。

---

## 8. 命名规则速查

### 8.1 SD 目录

```text
SD260728184122_1
└── G22607283800_1-293T-ZAK
```

- `SD`：项目 / 交付批次前缀；
- `260728`：日期 2026-07-28；
- `184122`：时间或批次编号；
- `_1`：该批次下的第 1 组数据；
- `G22607283800`：样本编号；
- `293T`：细胞背景；
- `ZAK`、`GCN2`、`A4`、`E4`：靶点、分组或实验条件代号。

### 8.2 TSM / nano_seq / ZNF8 目录

```text
<样本名>_TSM<日期>-<批次>-<编号>_<测序日期>-<批次>-<BAN编号>-<板位>_<孔位>.<簇号>.<文件类型>
```

例如：

```text
4_TSM20260827-020-01363_20260828-020-BAN09-2_G12.1.seq
```

- `4`：克隆 / 样本编号；
- `TSM20260827-020-01363`：项目编号；
- `20260828`：测序日期 2026-08-28；
- `BAN09`、`BAN10`：barcode / 建库批次代号；
- `G12`、`A01`、`B02`：96 孔板孔位；
- `.1`、`.2`：聚类簇编号或分析结果编号。

---

## 9. 常见坑与注意事项

1. **`.var.xls` 不是真正的 Excel 文件**
   - 单样本 `*.var.xls` 和 `*.filt.var.xls` 实际上是制表符分隔的文本，直接用 Excel 打开可能会跳格式警告。
   - 部分文件是 GBK 编码，在 Linux 或 Python 中按 UTF-8 读取会显示乱码。
   - 建议：
     ```bash
     iconv -f gbk -t utf-8 G22607283800_1-293T-ZAK.var.xls > fixed.tsv
     ```
     或在 Python 中：
     ```python
     pd.read_csv("xxx.var.xls", sep="\t", encoding="gbk")
     ```

2. **`merged_data.var.xls` 才是真正的 Excel 二进制文件**
   - 它需要 Excel / LibreOffice，或 `pandas + xlrd` 读取。
   - 不要再按 TSV 解析。

3. **BAM 的参考序列不是全基因组**
   - SD 目录：`@SQ SN:for.ref`，是扩增子参考。
   - TSM / nano_seq / ZNF8：`@SQ SN:<样本名>`，是该样本自己的共识序列。
   - 不要把 `Pos` 当成 hg38 坐标，也不要把 BAM 当作全基因组比对结果。

4. **BAM 里的 reads 不等于 FASTQ 里的全部 reads**
   - 例如 `E4-3` 的 FASTQ 有 438 条 reads，但 BAM 只有 360 条。
   - 这是因为 BAM 只包含主簇（通常是 `Clust_0`）的 reads，其他簇或未聚类的 reads 没有进入这个 BAM。

5. **一个样本可能有多个簇结果**
   - `.1`、`.2`、`.3` 不是重复测序，而是不同聚类簇 / 单倍型 / 分析结果。
   - 做结论前要确认哪个簇是主导簇，以及各簇的 reads 支持量。

6. **不是所有文件都齐全**
   - 低支持簇可能只有 BAM，没有 `.seq`、`.ab1` 或 `.xlsx`。
   - `SD260728184122_1` 中的 `G22607283803_1-GCN2` 只有 QC 图，没有测序结果。

7. **注意参考序列长度和分组**
   - `SD260812174403_1` 中 E4 组的参考是 529 bp，A4 组的参考是 794 bp，两组不能直接按同一坐标比较。
   - `SD260728184122_1` 中 ZAK 参考 493 bp，GCN2 参考 593 bp，同样不能混用坐标。

8. **`.fastq.fai` 属于流程产物**
   - 例如 `WT_..._B11.fastq.fai`，是按 FASTA 索引方式给 FASTQ 建立的索引。
   - 它不是标准 FASTQ 文件的一部分，也不影响 reads 内容。

9. **低深度样本的解释要谨慎**
   - reads 只有几十条的样本，低频变异（例如 5%）可能只对应 1–3 条 reads，容易受测序误差影响。
   - 建议结合 `DP`、`Alt_dp`、`DP4` 和 Sanger 峰图一起判断。

10. **poly 结构附近的变异要特别小心**
    - 过滤原因中经常出现“poly 结构长度 ≥ 4bp 且突变频率较低”。
    - 这类位点容易出现插入 / 缺失假阳性，通常不应直接作为编辑效率的依据。

---

## 10. 常用查看命令

查看 BAM 头信息和参考序列：

```bash
samtools view -H sample.sorted.bam
```

查看比对统计：

```bash
samtools flagstat sample.sorted.bam
```

查看某区域覆盖度：

```bash
samtools depth -a sample.sorted.bam | head
```

统计 FASTQ reads 数：

```bash
echo $(( $(wc -l < sample.fastq) / 4 ))
```

查看共识序列：

```bash
head sample.seq
```

查看变异表：

```bash
column -t -s$'\t' sample.var.xls | head
```

将 GBK 编码的变异表转换为 UTF-8：

```bash
iconv -f gbk -t utf-8 sample.var.xls > sample.utf8.tsv
```

---

## 11. 目前仍不能仅凭数据确定的信息

以下内容需要结合实验记录或项目文档确认：

1. `A4`、`E4`、`G1`–`G5` 分别对应哪个基因、哪个位点或哪种编辑条件；
2. `293T` 样本是空白细胞对照，还是转染了对照质粒；
3. `ZNF8` 各克隆编号对应的具体处理或筛选结果；
4. 每个样本的目标编辑类型（碱基替换、插入、缺失、同义 / 错义等）；
5. `.1`、`.2` 等多簇结果中，哪个簇被实验人员认定为最终结果；
6. 上游分析工具的版本和参数（例如聚类阈值、变异频率阈值、过滤规则）。

如果需要进一步整理，建议补充一份实验设计表，把这些样本与基因、靶点、处理条件、预期编辑结果对应起来。
