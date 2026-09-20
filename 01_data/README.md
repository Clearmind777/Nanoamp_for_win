# 01_data

nanoamp 的测试数据。

```text
01_data/
|-- test_data/       # 公司原始交付（不要改动）
|   `-- readme.md    # 逐类文件的说明
`-- ln_test_data/    # 规范化链接层 + manifest.tsv
    `-- .gitignore   # 大文件的副本不提交，见下
```

## test_data

来自若干批次的纳米孔 PCR 产物原始交付：

```text
SD260728184122_1/
SD260812174403_1/
TSM20260826-020-01254/
ZNF8/
nano_seq/
```

每类文件的含义见 `test_data/readme.md`。**这个目录是唯一的事实来源，
任何时候都不要修改它** —— 链接层全部由它生成。

## ln_test_data

规范化后的目录层，让每个样本的输入文件都叫同一个名字：

```text
ln_test_data/<dataset>/<sample>/
  reads.fastq
  reference.self.fa
  reference.wt.fa
  consensus.N.fa
  variants.N.xlsx
  sanger.N.ab1
  meta.tsv
```

`ln_test_data/manifest.tsv` 记录了每个文件对应 `test_data/` 里的哪个原始文件。

### 克隆之后必须先跑一次

`.fastq` / `.xlsx` / `.ab1` 是 `test_data/` 的**逐字节副本**，占了 40 MB，
因此不提交到 Git。克隆下来以后跑一条命令把它们补齐：

```bash
Rscript 03_dependence/r-environment/materialize_test_data.R
```

脚本会按 `manifest.tsv` 逐个复制，并对每个文件做 md5 校验：只要有一个缺失或
内容不对，它会打印出来并以非零状态退出。输出结尾必须是：

```text
ALL ln_test_data LINKS RESOLVE TO THE CORRECT CONTENT
```

`.fa` 文件保留在 Git 里：它们不是逐字节副本，而是把公司的 `.seq` / `.ab1`
解析后重新写出的 FASTA，复制不出来，只能由 `prepare_test_data.R` 生成。

### 需要重建整个链接层时

改了 `test_data/`，或者要新增数据集时，运行：

```bash
Rscript 02_code/r/inst/scripts/prepare_test_data.R   # 重建链接 + manifest.tsv
Rscript 03_dependence/r-environment/materialize_test_data.R   # 补齐大文件副本
```

`prepare_test_data.R` 生成的是相对符号链接；Windows 上创建符号链接需要开发者模式，
所以上一步在 Windows 往往只写出一个几百字节的"指向路径的文本文件"，
`materialize_test_data.R` 正是用来把这种状态修成真实副本的。

`test_data/` 下的原始文件永远不会被修改。
