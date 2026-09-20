# nanoamp — Windows

`nanoamp` 用于分析纳米孔 PCR 产物的测序数据。给定 FASTQ 和目的序列，它会校正
测序错误、重建单倍型，并输出数量最多、比例最高的序列。

本仓库是项目的 **Windows 变体**，独占所有 Windows 相关内容：原生
`minimap2.exe`、MSYS2/MINGW-w64 编译方案、Windows 下的 R 环境脚本，
以及离网安装包。

Linux 变体在姊妹仓库 `a_09_18_26_mapping_programs_dev_for_linux`。

两个变体**都不使用 conda，也不使用 WSL**。

## 仓库结构

```text
00_materials/     委托文档、开发方案、工作报告和完整教程（tutorial.md）
01_data/          原始测试数据和规范化链接层
02_code/          源代码
  r/              nanoamp R 包
  cli/            独立 R CLI 入口和启动器（make cli 用）
  gui/            独立 R Shiny GUI 入口和启动器（make gui 用）
  PythonGUI/      Python/Tkinter 图形界面（发行版 GUI 就是它的产物）
  shared/         跨语言参数与输出契约
03_dependence/    内置 minimap2.exe、编译方案、离网安装包、R 环境脚本
release/          发布产物：三个交付形态 + 一键安装/卸载器
04_builds/        R 构建包和 R CMD check 产物（Git 忽略）
tmp/test_results/ 运行结果（除 README 外 Git 忽略）
```

## 快速开始

仓库已内置 `minimap2.exe`（静态链接，运行时不需要 MSYS2 / Cygwin / conda / WSL），
所以正常情况下只需要 R。

```powershell
# 1. 安装 R 包（R 本身怎么装见 03_dependence/r-environment/README.md）
R CMD INSTALL 02_code/r

# 2. 环境检查
sh 02_code/cli/nanoamp doctor

# 3. 先修好测试数据链接层（见下方说明），再跑单样本
Rscript 03_dependence/r-environment/materialize_test_data.R
sh 02_code/cli/nanoamp call `
  --reads 01_data/ln_test_data/TSM20260826/E4-3/reads.fastq `
  --reference 01_data/ln_test_data/TSM20260826/E4-3/reference.self.fa `
  --mode A --top-n 20 `
  --outdir tmp/test_results/cli/demo

# 4. 启动 GUI
Rscript 02_code/gui/run_gui.R
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

### Windows 上的 `ln_test_data` 链接层

`01_data/ln_test_data/` 里的 `.fastq` / `.xlsx` / `.ab1` 是 `test_data/` 的逐字节
副本，合计约 40 MB，**不再提交到 Git**（`.fa` 保留，因为它们是重新解析写出的，
复制不出来）。clone 后执行一次把它补齐：

```powershell
Rscript 03_dependence/r-environment/materialize_test_data.R
```

脚本按 `manifest.tsv` 逐项复制并做 MD5 校验，缺文件或内容不符会报错退出，
结尾必须出现 `ALL ln_test_data LINKS RESOLVE TO THE CORRECT CONTENT`。

它同时修复普通 clone（未开开发者模式）留下的状态：那时 git 把每个链接写成约
100 字节、内容是路径的文本桩，脚本会把这些桩替换成真实副本。详见
`01_data/ln_test_data/README.md`。

## 文档索引

| 文档 | 内容 |
|---|---|
| `00_materials/tutorial.md` | **完整教程**：GUI 版、CLI 版、R 包版 + 外部依赖工具配置 |
| `02_code/README.md` | 源码目录与组件状态 |
| `02_code/r/README.md` | R 包教程（英文） |
| `02_code/r/README-CN.md` | R 包教程（中文） |
| `02_code/cli/README.md` | CLI 契约与启动器 |
| `02_code/gui/README.md` | R Shiny GUI 功能 |
| `02_code/PythonGUI/README.md` | Python/Tkinter 界面实现与打包细节 |
| `01_data/ln_test_data/README.md` | 链接层为何不提交、怎么重建 |
| `release/README.md` | 发布产物与一键安装器 |
| `03_dependence/README-CN.md` | 内置工具与 Windows 平台支持矩阵 |
| `03_dependence/windows-x86_64/README.md` | Windows 源码编译 minimap2 |
| `03_dependence/r-environment/README.md` | R 环境搭建与测试运行 |
| `03_dependence/offline-bundle/README.md` | 离网安装 |
| `00_materials/README.md` | 规划文档与工作报告索引 |

## 外部工具

解析顺序：

1. `NANOAMP_MINIMAP2` / `NANOAMP_SAMTOOLS`；
2. `03_dependence/<os>-<arch>/bin/`（Windows 下为 `.exe`）；
3. `PATH`。

仓库已内置 **Windows x86_64 的 minimap2 2.31**，由本仓库从上游源码编译并静态链接，
运行时不需要 MSYS2 / Cygwin / conda / WSL（只依赖 `KERNEL32.dll` 和 `msvcrt.dll`）。
上游没有官方 Windows 构建，要复现这个产物：

```powershell
pwsh -File 03_dependence/windows-x86_64/install_msys2_toolchain.ps1  # 编译链（约 1.5 GB）
bash 03_dependence/windows-x86_64/build_minimap2.sh                  # 编译
```

Windows on ARM 请改用 R 内后端：

```r
run_haplotype_analysis(..., aligner = "r")
```

samtools 是可选依赖且未内置：默认用 `Rsamtools::asBam()` 完成 SAM→BAM，
不需要任何 samtools 二进制。

## 运行测试

```powershell
# 每个 clone 先执行一次，补齐链接层里未提交的大文件副本
Rscript 03_dependence/r-environment/materialize_test_data.R

# 单元测试（会用到内置的 minimap2）
Rscript 03_dependence/r-environment/run_tests.R

# 基于 01_data/ 真实数据的功能回归
Rscript 03_dependence/r-environment/run_functional_regression.R `
  --outdir tmp/test_results/r/test_run_win --modes A,B,C --threads 4
```

从零搭建 Windows R 环境（R 安装、镜像、依赖安装）见
`03_dependence/r-environment/README.md`。

## 离网安装

可以把全部上游安装程序预置成一个固定版本、带完整性校验的安装包，
供无网机器一次性部署（R 安装器、完整 R 包依赖闭包、MSYS2 工具链、minimap2 源码）：

```powershell
# 有网机器
Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R

# 无网机器
pwsh -File 03_dependence/offline-bundle/install_offline.ps1
```

安装包写入 git 忽略的 `dist/`：仓库保留可复现的配方与哈希，不保留二进制。
为什么不入库、精确体积构成，以及 USB / release assets 两种替代方案，
见 `03_dependence/offline-bundle/README.md`。

## 常用命令

```bash
make install          # 安装 R 包
make test             # 运行 testthat 测试
make check            # 构建并 R CMD check
make cli              # 运行 nanoamp doctor
make gui              # 启动 Shiny GUI
make deps             # 查看内置 minimap2.exe 的来源与重建方式
make toolchain        # 安装 MSYS2/MINGW-w64 编译链
make offline-bundle   # 生成离网安装包到 dist/
make offline-install  # 从安装包离线安装
```

## 许可证

MIT。
