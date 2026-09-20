# 06_GUI — Windows 桌面界面（Python / Tkinter）

一个可以直接双击打开的简易图形窗口，用来跑 nanoamp 分析并查看结果。

```
06_GUI/
|-- run_gui.py                 # 源码入口：python 06_GUI\run_gui.py
|-- build_exe.py               # 打包成 nanoamp.exe
|-- nanoamp.spec               # PyInstaller 配置
|-- nanoamp_gui/
|   |-- __init__.py
|   |-- app.py                 # 窗口本体（Tkinter）
|   `-- r_runner.py            # 定位 R 并调用 nanoamp CLI
|-- tests/                     # 无界面自测脚本
`-- dist/nanoamp.exe           # 双击即用（打包产物，已入库）
```

## 定位：和已有的 Shiny GUI 什么关系

`02_code/gui/` 里已经有一个 **R Shiny** 界面（`nanoamp_gui()`）。两者不冲突，
取舍不同：

| | Shiny GUI (`02_code/gui`) | 本目录（Python/Tkinter） |
|---|---|---|
| 运行时 | 需要 R + shiny + DT | 只需 R（界面本身已打包成 exe） |
| 呈现方式 | 起本地 HTTP 服务，用浏览器打开 | 原生 Windows 窗口，无浏览器、无端口 |
| 双击即用 | 需要 `.bat` 或 Rscript 命令 | 直接双击 `nanoamp.exe` |
| 打包路径 | RInno（重，需在 Windows 上构建） | PyInstaller（已验证，10 MB 单文件） |
| 功能完整度 | 更全（参数更多、DT 交互表、下载按钮） | 精简：核心参数 + 结果查看 |

两者**共用同一套分析核心** —— 都调用 `nanoamp` R 包，界面里没有任何重写的算法。
所以结果不会出现"两个界面算出不同答案"的情况。

## 快速开始

### 方式一：双击 exe

```
06_GUI\dist\nanoamp.exe
```

窗口打开后：选测序文件 → 选目的序列 → 选输出目录 → 点"开始分析"。

### 方式二：从源码运行

```powershell
python 06_GUI\run_gui.py
```

只用标准库（tkinter 随 CPython 提供），不需要 pip 安装任何东西。

## 界面功能

- **测序文件 (FASTQ)**、**目的序列 (FASTA)**：文件选择器；如果 FASTQ 所在目录里有
  `reference.self.fa` / `reference.fa` / `reference.wt.fa`，选完 reads 会自动填上参考。
- **输出目录**：默认 `04_results/gui`。
- **模式**：A 参考引导（默认）／B 从头聚类／C 精确匹配。
- **显示前 n 条 (top-n)**：默认 20。
- **单倍型结果**：排名、编号、reads 数、占比、是否与目的序列一致、SNV/插入/缺失数、
  长度、变异描述；选中某一行会在下方显示该单倍型的完整序列。
- **QC 指标**：`qc.tsv` 的键值。
- **输出文件**：本次运行产生的文件，双击可用系统默认程序打开。
- **运行日志**：R 的实时输出（含 `[INFO]` 进度）。
- **环境自检**：跑 `nanoamp doctor`，确认 R 包、依赖和 minimap2 是否就绪。
- **打开输出目录**：在资源管理器中打开结果目录。

分析在后台线程执行，窗口不会卡死；进度条为不确定模式（R 未输出百分比）。

## 环境要求

分析本身由 R 完成，所以目标机器**必须装 R**，`nanoamp` 包也必须装好：

```r
R CMD INSTALL 02_code/r
```

`minimap2.exe` 已随仓库提供（`03_dependence/windows-x86_64/bin/minimap2.exe`），
无需额外安装。**不需要 conda，不需要 WSL，也不需要浏览器。**

exe 只打包了界面，不含 R。所以它比"完整绿色版"小得多（10 MB），代价是目标机器要有 R。

### R 与库的定位顺序

`r_runner.py` 找 Rscript 的顺序：

1. 环境变量 `NANOAMP_RSCRIPT`（指向 `Rscript.exe`）
2. `D:\tools\R`、`C:\tools\R`、`C:\Program Files\R`、`%LOCALAPPDATA%\Programs\R`
   下的 `R-*\bin\Rscript.exe`（优先版本号最大的）
3. `PATH` 里的 `Rscript`

找 R 库的顺序：`NANOAMP_R_LIB` → `D:\tools\R\lib` → `C:\tools\R\lib` →
`%LOCALAPPDATA%\R\win-library\4.6` → `4.5`。

都找不到时，窗口会弹出提示而不是静默失败。

## 重新打包 exe

```powershell
pip install pyinstaller
python 06_GUI\build_exe.py
```

产物：`06_GUI\dist\nanoamp.exe`（one-file、windowed、无控制台窗口）。

> 注意：打包时 `console=False`，R 的输出不会打印到控制台，只会在界面的
> "运行日志"里显示。如果启动就崩，会弹出一个显示 traceback 的错误框
> （由 `run_gui.py` 的 `_show_fatal` 负责）。

## 自测

```powershell
python 06_GUI\tests\test_headless.py     # 路径解析、R 定位、doctor、解析器
python 06_GUI\tests\test_e2e.py          # 真实跑一次分析并校验结果解析
python 06_GUI\tests\test_frozen.py       # 打包产物的路径解析与启动
python 06_GUI\tests\screenshot.py out.png  # 截图（人工查看用）
```

## 实现要点

1. **不重写算法。** `r_runner.py` 生成一个极小的 R 包装脚本，调用
   `nanoamp_cli()`，参数与命令行完全一致。
2. **不用 `Rscript -e`。** 传参给 `-e` 不可靠（`commandArgs(trailingOnly=TRUE)`
   会带上 `--args`），而且路径里的空格和中文很容易被转义搞坏；用真实脚本文件更稳。
   包装脚本写在 `tmp/`（已 gitignore），这样相对路径仍然成立。
3. **UTF-8 显式处理。** R 会输出中文日志；读取子进程输出时按字节读、显式
   UTF-8 解码（`errors="replace"`），避免控制台代码页导致异常或乱码。
4. **给 R 的路径用正斜杠。** 路径要嵌进生成的 R 字符串字面量里，Windows 反斜杠
   会被当成转义序列（`\R`、`\t`）而报错——这个坑已经踩过一次。
5. **不闪控制台。** `subprocess` 用 `CREATE_NO_WINDOW`。
6. **`haplotypes.fasta` 只含 top-n 序列。** 选中排名更靠后的行时，界面会说明
   "该单倍型未导出序列，把 top-n 调大后重跑"，而不是显示空白。

## 已知限制

1. **依赖 R。** 不是独立绿色版；exe 只包含界面。
2. **单文件启动稍慢。** one-file 打包每次运行都要解压到临时目录，冷启动约 1–3 秒。
3. **没有中英文切换**，界面文案目前是中文。
4. **没有批量模式**（CLI 的 `nanoamp batch` 尚未接进界面）。
5. **不含 GTF / CDS 功能注释** —— 该功能在 R 核心里也还没实现。
6. **窗口未在小于 880×600 的屏幕上验证。**
7. **代理环境下的 pip。** 本机曾因系统代理（`127.0.0.1:7890`）未运行导致
   `pip install pyinstaller` 报 `ProxyError`；用 `NO_PROXY=*` 绕过即可。这只影响
   打包，不影响程序运行。
