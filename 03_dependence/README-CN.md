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
`-- r-environment/                    # Windows 下的 R 环境与测试脚本
    |-- README.md
    |-- setup_r_environment.R
    |-- run_tests.R
    |-- run_functional_regression.R
    `-- materialize_test_data.R
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
  但源码可以用 MSYS2 MINGW-w64 工具链在 Windows 上原生编译 —— 本仓库的
  `windows-x86_64/bin/minimap2.exe` 就是这么来的。
- samtools 只发布源码，本项目也**根本不需要**它：默认由
  `Rsamtools::asBam()` 把 minimap2 的 SAM 转成 BAM。只有显式设置
  `use_samtools = TRUE` 才会走 samtools，那需要自行编译（htslib 官方
  INSTALL 文档明确推荐 Windows 用 MSYS2/MINGW64）。
- 本项目**全程不使用 conda，也不使用 WSL**。

## R 内比对后端

`run_haplotype_analysis(..., aligner = "r")` 使用 Biostrings/pwalign 的成对比对，
不依赖任何外部二进制。它比 minimap2 慢，适合中小扩增子，以及 Windows on ARM
这类没有 minimap2 构建的平台。

方案 C（`mode = "C"`）同样不需要任何外部工具。

## Windows 源码编译

Windows 上不需要 conda，也不需要 WSL，两步即可：

```powershell
# 1. 便携式 MSYS2 + MINGW-w64 工具链（约 1.5 GB，位于仓库之外）
pwsh -File 03_dependence/windows-x86_64/install_msys2_toolchain.ps1

# 2. 编译并安装 minimap2.exe
bash 03_dependence/windows-x86_64/build_minimap2.sh
```

工具链体积过大，不纳入仓库；仓库保留上述两个脚本、编译产物及其来源信息。
固定版本、编译参数和哈希见 `windows-x86_64/README.md`。

## 离网安装

可以把全部上游安装程序预置成一个固定版本、带完整性校验的安装包，
供无网机器一次性部署：

```powershell
# 有网机器
Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R
# 无网机器
pwsh -File 03_dependence/offline-bundle/install_offline.ps1
```

安装包（R 安装器、R 包依赖闭包、MSYS2 工具链、minimap2 源码）写入
git 忽略的 `dist/`。为什么不入库、以及 USB / release assets 两种替代方案，
见 `offline-bundle/README.md`。

## 许可证

- minimap2：MIT；
- samtools：MIT/Expat（本仓库未内置）。

内置 minimap2 的许可证文本位于 `licenses/`。
