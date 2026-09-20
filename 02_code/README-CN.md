# 02_code：源代码目录

本目录包含 `nanoamp` R 包、基于 R 的命令行版本，以及 R Shiny GUI。

```text
02_code/
|-- README.md / README-CN.md
|-- shared/                 # 跨语言参数与输出 schema
|   |-- params/default_params.json
|   `-- docs/output_schema.md
|-- r/                      # nanoamp R 包
|   |-- DESCRIPTION / NAMESPACE / LICENSE
|   |-- R/
|   |-- inst/
|   |   |-- docs/           # 依赖安装教程
|   |   |-- scripts/        # run_analysis.R、CLI、测试脚本
|   |   |-- shiny/          # 独立 Shiny 入口
|   |   `-- windows/        # RInno 打包骨架
|   |-- tests/testthat/
|   |-- exec/nanoamp        # 包内 CLI 包装
|   |-- man/                # 生成的帮助文档
|   `-- README.md / README-CN.md
|-- cli/                    # 仓库级 CLI 入口与启动器
`-- gui/                    # 仓库级 Shiny GUI 入口与启动器
```

Python 版本已经取消，后续开发统一以 R 技术栈为主。
外部工具统一放在仓库根目录的 `03_dependence/`。

## 设计原则

1. **一套算法，多种外壳**：CLI 和 GUI 都调用 `nanoamp` R 包，不重复实现分析逻辑；
2. **共享契约**：参数名、默认值和输出列在 `shared/` 统一定义；
3. **数据与代码分离**：测试数据在 `01_data/`，运行结果在 `tmp/test_results/<前端>/`；
4. **GUI 以 Windows 为主要目标**：使用 Shiny，可跨 Windows、Linux、macOS 运行，
   后续可用 RInno 打包为 Windows 安装包。
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
  --reads 01_data/ln_test_data/TSM20260826/E4-3/reads.fastq \
  --reference 01_data/ln_test_data/TSM20260826/E4-3/reference.self.fa \
  --mode A --top-n 20 \
  --outdir tmp/test_results/r/demo/E4-3
```

R 控制台：

```r
library(nanoamp)
res <- run_haplotype_analysis(
  reads     = "01_data/ln_test_data/TSM20260826/E4-3/reads.fastq",
  reference = "01_data/ln_test_data/TSM20260826/E4-3/reference.self.fa",
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

Windows 上安装 R 包后，可直接运行：

```bat
Rscript -e "library(nanoamp); nanoamp_gui()"
```

GUI 规划、启动脚本和 Windows 打包说明见 `gui/README.md`。

## 当前状态

| 组件 | 状态 |
|---|---|
| R 包 | 已实现，并通过 `R CMD check`（`Status: OK`） |
| 基于 R 的 CLI | 已实现（`nanoamp_cli()` 和 `02_code/cli`） |
| R Shiny GUI | 初版已实现（`nanoamp_gui()` 和 `02_code/gui`） |
| Windows 安装包 | 计划使用 RInno |

外部工具统一放在 `03_dependence/`；平台支持矩阵和 R 内后备方案见
`03_dependence/README-CN.md`。

## 共享契约

- `shared/params/default_params.json`：参数名与默认值；
- `shared/docs/output_schema.md`：输出文件与字段定义；
- `cli/README.md`：CLI 命令契约；
- `gui/README.md`：GUI 行为与部署规划。
