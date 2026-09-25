# nanoamp 依赖安装与配置（Windows）

本文说明如何在 Windows 上安装并配置 `minimap2`、`samtools`
以及 `nanoamp` 需要的 R 包。

本仓库是项目的 Windows 变体，**不使用 conda，也不使用 WSL**；
Linux 变体在姊妹仓库 `a_09_18_26_mapping_programs_dev_for_linux`。

## 1. 需要哪些依赖

| 依赖 | 类型 | 用途 |
|---|---|---|
| `minimap2` | 外部命令 | 方案 A/B 的 reads 比对 |
| `samtools` | 可选外部命令 | 兼容后备；默认使用 Rsamtools |
| R 包 | R 包 | 核心分析 |
| `DECIPHER` | 可选 R 包 | 方案 B 从头聚类 |
| `shiny`、`bslib`、`DT` | 可选 R 包 | GUI |

方案 C（原始精确匹配）不需要 `minimap2`。`samtools` 从来不是必需依赖，
因为 `Rsamtools::asBam()` 已经负责 SAM→BAM。

## 2. minimap2 已经内置

通常无需另行安装：仓库已内置原生 Windows 版 minimap2 2.31，

```text
03_dependence\windows-x86_64\bin\minimap2.exe
```

`nanoamp` 查找工具的顺序：

1. 环境变量 `NANOAMP_MINIMAP2` / `NANOAMP_SAMTOOLS`；
2. `03_dependence\<os>-<arch>\bin\`（Windows 下为 `.exe`）；
3. `PATH`。

内置二进制在第 2 级被解析，因此会被自动找到，无需修改 PATH。它是静态链接
libwinpthread 和 zlib 的，只依赖 `KERNEL32.dll` 和 `msvcrt.dll`，
在没装 MSYS2 / Cygwin / conda / WSL 的机器上也能直接运行。

验证：

```r
library(nanoamp)
nanoamp:::nanoamp_tool_path("minimap2")
# ".../03_dependence/windows-x86_64/bin/minimap2.exe"
nanoamp:::nanoamp_tool_version("minimap2")
# "2.31-r1302"
```

### 从源码重建

上游没有官方 Windows 二进制，但 minimap2 可以用 MSYS2 MINGW-w64 工具链在
Windows 上原生编译。以下两步无需人工干预，也不需要管理员权限：

```powershell
# 1. 便携式 MSYS2 + MINGW-w64 工具链（约 1.5 GB，位于仓库之外）
pwsh -File 03_dependence/windows-x86_64/install_msys2_toolchain.ps1

# 2. 编译并安装 minimap2.exe
bash 03_dependence/windows-x86_64/build_minimap2.sh
```

固定版本、关键编译参数和产物哈希见
`03_dependence/windows-x86_64/README.md`。

### 无法使用内置二进制时

在 Windows on ARM 或需要完全不依赖外部工具时，可使用 R 内后端：

```r
run_haplotype_analysis(..., aligner = "r")
```

它比 minimap2 慢，适合中小扩增子。方案 C 同样不需要任何外部工具。

也可以使用自行构建的二进制：将 `minimap2.exe` 放入
`03_dependence\windows-x86_64\bin\` 即可被解析，或用
`NANOAMP_MINIMAP2` 指向它。加入 `PATH` 也可以，但没有必要。

## 3. samtools

不需要，也未内置。默认由 `Rsamtools::asBam()` 把 minimap2 的 SAM 输出转成
BAM。只有显式设置 `use_samtools = TRUE` 时才需要 samtools，那就得自行编译
——htslib 官方 INSTALL 文档推荐 Windows 用 MSYS2/MINGW64。

## 4. R 包

必需：

```r
install.packages(c(
  "Biostrings", "Rsamtools", "IRanges", "Matrix",
  "data.table", "optparse", "jsonlite", "readxl"
))
```

如果 CRAN 上没有这些 Bioconductor 包：

```r
if (!requireNamespace("BiocManager", quietly = TRUE)) install.packages("BiocManager")
BiocManager::install(c("Biostrings", "Rsamtools", "IRanges"))
```

可选：

```r
BiocManager::install("DECIPHER")     # 方案 B 聚类
BiocManager::install("pwalign")      # Bioconductor >= 3.19 下 aligner = "r" 需要
install.packages(c("shiny", "DT"))   # GUI
```

如需完全脚本化安装（包含仓库之外的专用库和本网络可用的镜像），执行：

```powershell
Rscript 03_dependence/r-environment/setup_r_environment.R
```

## 5. 验证清单

```r
library(nanoamp)
nanoamp_cli("doctor")
```

预期输出：

```text
nanoamp version: 0.1.0
R version: ...
Rscript: ...
  Biostrings   TRUE
  ...
  DECIPHER     TRUE
  minimap2     .../03_dependence/windows-x86_64/bin/minimap2.exe
  samtools     NOT FOUND
```

检查要点：

- `minimap2` 应显示路径而不是 `NOT FOUND`；
- `samtools` 显示 `NOT FOUND` 是正常的，无影响；
- R 包应为 `TRUE`；
- `DECIPHER` 可能是 `FALSE`：方案 B 会退化为贪心聚类，仍可运行；建议安装 DECIPHER。

## 6. Windows 常见问题

- **`conda install minimap2 samtools` 不可用**：这些包没有 win-64 构建，
  而且本项目本来就不用 conda。
- **本项目不使用 WSL**，无需安装。
- **PATH 未刷新**：改完 `PATH` 要重启 RStudio。
- **路径含空格或中文**：优先用 `C:\tools\...` 这类路径。
- **Windows SmartScreen**：如被拦截，放行下载的二进制。
- **存在多个 R 安装**：用 `Rscript -e 'cat(R.home())'` 确认包安装到了实际使用的 R 中。

## 7. 依赖削减现状

已实现：

1. 默认由 `Rsamtools::asBam()` 完成 SAM→BAM，`samtools` 命令成为可选项；
2. 仓库内置原生 Windows `minimap2.exe`，无需任何外部安装步骤；
3. `aligner = "r"` 提供 R 内成对比对后端，适合中小数据量以及 Windows on ARM；
4. 大数据量仍推荐 minimap2。

只有确实需要 samtools 路径时才设置 `use_samtools = TRUE`。
