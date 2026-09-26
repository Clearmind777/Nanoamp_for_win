# 03_dependence

nanoamp **Windows 版本**随项目分发的外部工具目录。

本仓库是 Windows 变体；Linux 变体在姊妹仓库
`a_09_18_26_mapping_programs_dev_for_linux`。

## 目录结构

```text
03_dependence/
|-- README.md
|-- README-CN.md
|-- manifest.tsv
|-- licenses/
|   `-- minimap2-LICENSE.txt
|-- windows-x86_64/
|   |-- README.md
|   |-- install_msys2_toolchain.ps1   # 可复现的编译链安装脚本
|   |-- build_minimap2.sh             # 从源码编译 minimap2.exe
|   `-- bin/minimap2.exe              # 仓库内编译，静态链接
|-- windows-arm64/README.md
|-- offline-bundle/                   # 离网安装（R + R 包）
|   |-- README.md
|   |-- fetch_offline_bundle.R
|   `-- install_offline.ps1
|-- stress/                           # 环境压力矩阵
|   |-- README.md
|   |-- run_stress_tests.py           # A–D 组，跑真实 CLI
|   `-- data/znf8_exon_amplicon.fa    # 在线用例使用的真实 GRCh38 片段
|-- baselines/
|   `-- functional/                   # 提交入库的功能回归基线
|       |-- README.md
|       |-- comparison.tsv
|       |-- summary_by_mode.tsv
|       `-- run_index.tsv
`-- r-environment/                    # Windows 下的 R 环境与测试脚本
    |-- README.md
    |-- setup_r_environment.R
    |-- run_tests.R
    |-- run_functional_regression.R
    `-- check_functional_baseline.R   # 与 baselines/functional/ 逐行比对
```

## nanoamp 如何查找外部工具

解析顺序：

1. 环境变量 `NANOAMP_MINIMAP2` / `NANOAMP_SAMTOOLS`；
2. `03_dependence/<os>-<arch>/bin/<tool>.exe`；
3. `PATH`。

`NANOAMP_DEPENDENCE_DIR` 可以指定其他 `03_dependence` 位置，适合 R 包安装后使用。

`nanoamp doctor` 会显示平台、依赖目录，以及每个工具解析到的路径和版本。

## Windows 平台支持矩阵

| 平台 | minimap2 | samtools | 说明 |
|---|---|---|---|
| windows-x86_64 | 已内置 2.31（仓库内编译） | 未内置 | 静态链接，无需 MSYS2 / Cygwin / conda / WSL；samtools 不需要，Rsamtools 已覆盖 |
| windows-arm64 | 无二进制 | 未内置 | 用 R 内后端（`aligner = "r"`），或跑 x86_64 版本（模拟） |

上游事实：

- minimap2 只发布 Linux x86_64 预编译包，没有**官方** Windows 二进制；
  源码可以用 MSYS2 MINGW-w64 工具链在 Windows 上原生编译，本仓库的
  `windows-x86_64/bin/minimap2.exe` 即由此生成。
- samtools 只发布源码，本项目不需要它：默认由 `Rsamtools::asBam()` 把
  minimap2 的 SAM 转成 BAM。仅在显式设置 `use_samtools = TRUE` 时才会走
  samtools 路径，此时需要自行编译（htslib 官方 INSTALL 文档推荐 Windows
  使用 MSYS2/MINGW64）。
- 本项目不使用 conda，也不使用 WSL。

## R 内比对后端

`run_haplotype_analysis(..., aligner = "r")` 使用 Biostrings/pwalign 的成对比对，
不依赖任何外部二进制。其速度低于 minimap2，适用于中小扩增子，以及
Windows on ARM 这类没有 minimap2 构建的平台。

该后端报告的覆盖度与 identity **来自 read 实际比对到的参考片段**。（早期版本把每条
read 都当作覆盖整条参考序列，于是只覆盖一半的 read 也能通过 `--min-ref-coverage 0.99`
并被计为参考单倍型；默认的 `minimap2` 后端一直是正确的。）

方案 C（`mode = "C"`）同样不需要外部工具。

## R 包依赖

R 包自己读取 FASTQ（`R/io.R`：按扩展名或 gzip 魔数识别压缩、拒绝畸形记录），
因此**不再需要 `ShortRead`** —— 包的 `DESCRIPTION`、CLI 与 GUI 都没有它。
其余依赖为 `Biostrings`、`IRanges`、`Matrix`、`Rsamtools`、`data.table`、
`jsonlite`、`methods`、`optparse`、`readxl`、`stats`、`utils`；`DECIPHER`
（方案 B 聚类）与 `pwalign`（Bioconductor ≥ 3.19 下的 `aligner = "r"` 后端）是可选依赖，
`shiny`/`DT` 只在 Shiny 图形界面里用到。

Windows 的 R 环境脚本（`r-environment/setup_r_environment.R`）安装的就是上面这套，
并且**刻意不装 `ShortRead`**：`ShortRead` 会无条件导入 `pwalign`，从而把一个可选
provider 变成每次安装的硬依赖。安装器的固定版本清单
（`release/deps/pinned-R4.6.tsv`）则是**有意的超集**：它与已冻结的离线资产一同校验，
因此可能仍包含 `ShortRead`，这不影响包真正需要什么。

两个注释示例配置（`example_cds.json`、`example_online.json`）随 R 包分发
（`nanoamp/inst/configs/`，`nanoamp doctor` 的 `configs` 一行会打印该路径），
用 `--annotate-config` 指定；`install.exe` 另会复制一份到 `<安装目录>\configs\`。

## 环境压力矩阵

`stress/run_stress_tests.py` 用**真实 CLI**（与 GUI 相同的调用方式）跑方案环境矩阵中
可自动化的用例，其余记为 `SKIP` 并写明手工步骤：

```powershell
# 全部（A 组需要联网）
python 03_dependence/stress/run_stress_tests.py --group A,B,C,D

# 只跑离线组
python 03_dependence/stress/run_stress_tests.py --group B,C,D
```

分组：**A** 网络/代理/缓存，**B** 输入退化与注释矩阵规模，**C** 环境（含空格与中文的
路径、超长路径、缓存目录解析顺序、缺 curl、PATH 无帮助），**D** 取消与并发。
结果写入 `tmp/test_results/stress/stress_results.tsv`；最近一次全量运行是
**47 PASS / 0 FAIL / 2 SKIP**（两个 SKIP 是需真机的磁盘满与 ARM64）。`make stress-test`
一次跑完四组，用例与方案编号的对应关系见 `stress/README.md`。

## 功能回归基线

`r-environment/run_functional_regression.R` 会对 `01_data/` 中每个样本跑方案 A/B/C
（共 168 次）。`r-environment/check_functional_baseline.R` 把一次运行与
`baselines/functional/` 中提交入库的快照**逐行**比较（`status`、变异数、
`top1_variants`、reads 数、`mapping_rate`、`mean_identity`、`top1_proportion`；
原本 `ok` 的运行一旦不再成功会直接判失败）。

```bash
make functional-test       # 跑回归并与基线比较
make functional-baseline   # 重跑并刷新基线（务必先看 diff）
```

方案 B 调用的 `DECIPHER::Clusterize` 在上游是随机算法（同一输入换一个随机数状态，
实测同一阈值下得到 29 与 30 个簇），所以本包在调用前固定种子并把
`clustering_seed`（默认 42）写进 `qc.tsv`，同时不改动调用方 R 会话的随机数流。
没有这一步，方案 B 的每一行都会在两次运行之间变化，基线也只能当参考。

## Windows 源码编译

编译分两步，不使用 conda 或 WSL：

```powershell
# 1. 便携式 MSYS2 + MINGW-w64 工具链（约 1.5 GB，位于仓库之外）
pwsh -File 03_dependence/windows-x86_64/install_msys2_toolchain.ps1

# 2. 编译并安装 minimap2.exe
bash 03_dependence/windows-x86_64/build_minimap2.sh
```

工具链体积过大，不纳入仓库；仓库保留上述两个脚本、编译产物及其来源信息。
固定版本、编译参数和哈希见 `windows-x86_64/README.md`。

## 离网安装

上游安装程序可以预置为固定版本、带完整性校验的离线包，用于无网络机器的部署：

```powershell
# 有网机器
Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R
# 无网机器
pwsh -File 03_dependence/offline-bundle/install_offline.ps1
```

写入 git 忽略的 `dist/` 的离线包包含 R 安装器、R 包依赖闭包、MSYS2 工具链与
minimap2 源码。已发布的离线依赖资产
`release/_build/nanoamp-0.1.0-windows-offline-deps.zip`（约 248 MB）包含
R 4.6.1 安装器、109 个 R 包二进制与 `minimap2.exe`。不入库的原因，以及
USB / release assets 两种替代方案，见 `offline-bundle/README.md`。

## 许可证

- minimap2：MIT；
- samtools：MIT/Expat（本仓库未内置）。

内置 minimap2 的许可证文本位于 `licenses/`。
