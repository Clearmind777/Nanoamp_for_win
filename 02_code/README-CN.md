# 02_code：源代码目录

本目录包含 `nanoamp` R 包、基于 R 的命令行版本，以及图形界面。

本仓库是项目的 **Windows 变体**；Linux 变体位于姊妹仓库
`a_09_18_26_mapping_programs_dev_for_linux`。

```text
02_code/
|-- README.md / README-CN.md
|-- shared/                 # 跨语言参数与输出 schema
|   |-- params/default_params.json
|   `-- docs/output_schema.md
|-- r/                      # nanoamp R 包
|   |-- DESCRIPTION / NAMESPACE / LICENSE
|   |-- R/                  # align.R、io.R（自带 FASTQ 解析）、annotate.R、
|   |                       #   annotate_config.R、ref_online.R、cli.R 等
|   |-- inst/
|   |   |-- configs/        # 随包分发的注释示例配置（进 tarball）
|   |   |-- docs/           # 依赖安装教程
|   |   |-- scripts/        # run_analysis.R、CLI、测试脚本
|   |   |-- shiny/          # 独立 Shiny 入口
|   |   `-- windows/        # RInno 打包骨架
|   |-- tests/testthat/     # 48 个用例 / 192 个断言
|   |-- exec/nanoamp        # 包内 CLI 包装
|   |-- man/                # 生成的帮助文档
|   `-- README.md / README-CN.md
|-- cli/                    # 仓库级 CLI 入口与启动器
`-- gui/                    # 仓库级 Shiny GUI 入口与启动器
```

R 是分析核心；CLI 与图形界面均为外壳，调用 `nanoamp` R 包，不重复实现分析逻辑。
Python/Tkinter 界面属于同一类外壳。外部工具统一放在仓库根目录的
`03_dependence/`。

早期版本计划过的 Python CLI 并未实现：命令行开发统一基于 R 包
（`nanoamp_cli()`）。`PythonGUI/` 中的 Python 代码是桌面图形界面，不是 CLI，
`release/03_GUI/` 打包的 `nanoamp.exe` 即由它构建。

## 设计原则

1. **一套算法，多种外壳**：CLI 和 GUI 都调用 `nanoamp` R 包，不重复实现分析逻辑；
2. **共享契约**：参数名、默认值和输出列在 `shared/` 统一定义；
3. **数据与代码分离**：测试数据在 `01_data/`，运行结果在 `tmp/test_results/<前端>/`；
4. **GUI 以 Windows 为主要目标**：使用 Shiny，可跨 Windows、Linux、macOS 运行，
   后续可用 RInno 打包为 Windows 安装包；`PythonGUI/` 中的 Python/Tkinter 界面
   面向同一 Windows 桌面，改用 PyInstaller 打包。
5. **优先使用内置工具**：外部工具先从
   `03_dependence/<os>-<arch>/bin/` 解析，其次才是 `PATH`。

## R 包快速开始

```bash
# 安装 R 包
R CMD INSTALL 02_code/r

# 环境检查（仓库内启动器）
sh 02_code/cli/nanoamp doctor

# 单样本分析
nanoamp call \
  --reads 01_data/TSM20260826/E4-3/reads.fastq \
  --reference 01_data/TSM20260826/E4-3/reference.self.fa \
  --mode A --top-n 20 \
  --outdir tmp/test_results/r/demo/E4-3
```

R 控制台：

```r
library(nanoamp)
res <- run_haplotype_analysis(
  reads     = "01_data/TSM20260826/E4-3/reads.fastq",
  reference = "01_data/TSM20260826/E4-3/reference.self.fa",
  outdir    = "tmp/test_results/r/demo/E4-3",
  mode      = "A"
)
res$haplotypes
```

## GUI

```r
library(nanoamp)
nanoamp_gui()
```

Windows 上安装 R 包后，可运行：

```bat
Rscript -e "library(nanoamp); nanoamp_gui()"
```

GUI 规划、启动脚本和 Windows 打包说明见 `gui/README.md`。

## 功能注释（可选）

默认关闭：不传 `--annotate-config`（命令行）或不勾选「功能注释…」（图形界面）时，
输出与该功能出现之前**逐字节一致**。启用后，程序把每条单倍型的变异翻译成生物学后果，
并多写这些文件：

| 文件 | 内容 |
|---|---|
| `annotation.tsv` | 每个「单倍型 × 转录本」一行，含中英双列后果、蛋白变化与转录本冲突标记 |
| `variants_annotation.tsv` | 加 `--annotation-detail` 时生成：每个变异一行，含 CDS 坐标、密码子与氨基酸变化 |
| `transcripts.tsv` | 用 `--list-transcripts`（或图形界面的「列出转录本」）时生成：扩增子重叠的转录本清单 |

两条路线写在配置文件里（`"route": "genome"` 或 `"cds"`）：

- **`cds`（离线）**：使用者在扩增子参考上给出 CDS 区间（1-based、两端都算、长度必须是
  3 的倍数），全程不联网；
- **`genome`（在线）**：程序自行在 GRCh38 定位扩增子，并从 Ensembl REST 取转录本结构。

被跳过的转录本会**记账而不是被隐藏**（`qc.tsv` 的 `annotation_skip_reason`、
`run_manifest.json` 的 `annotation.skipped_transcripts`），此时退出码仍是 0（序列分析
本身成功了）；流水线需要把它当失败时加 `--strict`。注释**不新增任何 R 依赖**
（复用 Biostrings/jsonlite），唯一外部前提是在线路线需要 `curl.exe`，缺失时回退到
R 自带的下载能力。示例配置随包分发（`inst/configs/`，路径见 `nanoamp doctor` 的
`configs` 一行），`install.exe` 另会复制一份到 `<安装目录>\configs\`。

这些功能对应的命令行接口：

```text
nanoamp call   --reads <fastq> --reference <fasta> --outdir <dir> [--mode A|B|C]
nanoamp batch  --sample-sheet <tsv> --outdir <dir> [--mode A|B|C]
nanoamp doctor [--check-online]      # 环境自检；顺带探测 Ensembl 连通性
nanoamp cache  [--cache-dir <dir>] [--clear]
nanoamp help
```

最近新增的参数：`--annotate-config`、`--transcript <ENST...|all>`、
`--list-transcripts`、`--annotation-proteins`、`--annotation-detail`、
`--min-ref-coverage <p>`、`--cache-dir`、`--no-cache`、`--clear-cache` 与 `--strict`；
`qc.tsv` 里的 `clustering_seed` 记录让方案 B 可复现的随机种子。

## 运行状态

每次运行都会写 `run_manifest.json`（参数、版本、输入校验值，以及 `status` =
`done`/`failed`/`cancelled`、`error_class` = `input`/`environment`/`network`/`internal`、
`error_message`、`log_path`）和 `nanoamp.log`。**失败的运行也会创建输出目录并写下这两个
文件**，因此"失败"与"什么都没产出"不会无法区分。退出码仍然是 0（成功）/ 1（失败）。

## 当前状态

| 组件 | 状态 |
|---|---|
| R 包 | 已实现；`R CMD check` 为 `Status: OK`；48 个 testthat 用例 / 192 个断言；自带 FASTQ 解析，不依赖 `ShortRead` |
| 基于 R 的 CLI | 已实现（`nanoamp_cli()` 和 `02_code/cli`），含 `doctor [--check-online]` 与 `cache [--clear]` |
| 功能注释 | 已实现并有测试（离线 `cds` 与在线 `genome` 两条路线） |
| 功能回归 | `01_data/` 上 168 次运行与 `03_dependence/baselines/functional/` 中提交入库的基线逐行比对（`make functional-test`）；方案 B 通过记录的 `clustering_seed` 可复现 |
| 环境压力矩阵 | `03_dependence/stress/run_stress_tests.py`（A–D 组）：最近一次全量 47 PASS / 0 FAIL / 2 SKIP（需真机的磁盘满与 ARM64） |
| R Shiny GUI | 初版已实现（`nanoamp_gui()` 和 `02_code/gui`） |
| Python/Tkinter GUI | 已实现，打包为 `02_code/PythonGUI/dist/nanoamp.exe`；7 个自测脚本全部通过 |
| Windows 安装包 | 已实现，使用 PyInstaller 构建（`release/_installer/`；产出 `install.exe` 与 `uninstall.exe`）；9 个逻辑测试脚本全部通过 |

外部工具统一放在 `03_dependence/`；平台支持矩阵和 R 内后备方案见
`03_dependence/README-CN.md`。

## 共享契约

- `shared/params/default_params.json`：参数名与默认值；
- `shared/docs/output_schema.md`：输出文件与字段定义，含注释章节
  （`transcripts.tsv`、`annotation.tsv`、`variants_annotation.tsv`、后果词表、
  注释 QC 指标）以及 `run_manifest.json` 的状态字段；
- `cli/README.md`：CLI 命令契约；
- `gui/README.md`：GUI 行为与部署规划。
