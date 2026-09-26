# 02_code/PythonGUI — Windows 桌面界面（Python / Tkinter）

用于执行 nanoamp 分析并查看结果的图形窗口，以单个 `nanoamp.exe` 交付。

```
02_code/PythonGUI/
|-- run_gui.py                 # 源码入口：python 02_code\PythonGUI\run_gui.py
|-- build_exe.py               # 打包成 nanoamp.exe
|-- nanoamp.spec               # PyInstaller 配置
|-- nanoamp_gui/
|   |-- __init__.py
|   |-- app.py                 # 窗口本体（Tkinter）
|   `-- r_runner.py            # 定位 R 并调用 nanoamp CLI
|-- tests/                     # 无界面自测脚本
`-- dist/nanoamp.exe           # 打包产物（已入库）
```

## 定位：与 Shiny GUI 的关系

`02_code/gui/` 中已有一个 **R Shiny** 界面（`nanoamp_gui()`）。两者并存，取舍不同：

| | Shiny GUI (`02_code/gui`) | 本目录（Python/Tkinter） |
|---|---|---|
| 运行时 | 需要 R + shiny + DT | 只需 R（界面本身已打包成 exe） |
| 呈现方式 | 起本地 HTTP 服务，用浏览器打开 | 原生 Windows 窗口，无浏览器、无端口 |
| 启动方式 | 需要 `.bat` 或 Rscript 命令 | 直接运行 `nanoamp.exe` |
| 打包路径 | RInno（需在 Windows 上构建） | PyInstaller（已验证，10 MB 单文件） |
| 功能完整度 | 更全（参数更多、DT 交互表、下载按钮） | 精简：核心参数 + 结果查看 |

两者**共用同一套分析核心** —— 都调用 `nanoamp` R 包，界面中不含重写的算法。
因此两个界面不会得出不同的结果。

## 运行方式

### 方式一：运行 exe

```
02_code\PythonGUI\dist\nanoamp.exe
```

窗口打开后，依次选择测序文件、目的序列和输出目录，再点击 `开始分析`。

### 方式二：从源码运行

```powershell
python 02_code\PythonGUI\run_gui.py
```

仅使用标准库（tkinter 随 CPython 提供），无需 pip 安装任何依赖。

## 界面功能

- **测序文件 (FASTQ)**、**目的序列 (FASTA)**：文件选择器；若 FASTQ 所在目录中存在
  `reference.self.fa` / `reference.fa` / `reference.wt.fa`，选定 reads 后会自动填入参考序列。
  窗口中**所有路径统一用 `\`**（Tk 的文件对话框返回 `/`，载入时会被规范化），
  复制出去即可直接用。
- **输出目录**：默认 `我的文档\nanoamp 结果`（可从「浏览…」更改）。
- **模式**：A 参考引导（默认）／B 从头聚类／C 精确匹配。
- **显示前 n 条 (top-n)**：默认 20。
- **功能注释…**（可选开关）：勾选后出现注释参数 —— 配置来源
  （`离线 CDS（不联网）` / `在线 genome（需联网，用 Ensembl）` / `自定义 JSON…`）、
  CDS 起/止/链/读码框、输出变异级明细、输出蛋白序列、转录本下拉框与「列出转录本」按钮，
  以及缓存一行（目录/文件数/占用 + 刷新 + 清空缓存 + 测试 Ensembl 连接）。
- **高级参数…**（可选开关）：比对方式（minimap2 / r）、线程、最小支持 reads、
  最小频率、最小一致度、最小覆盖、聚类一致度、最小簇 reads、簇共识、是否保留 BAM。
  **只有改动过的值才会传给命令行**，与不勾选完全等价；「恢复默认值」一键复位。
- **六个标签页**：单倍型结果（选中一行显示完整序列）、注释结果、变异注释、
  QC 指标、输出文件（双击用系统默认程序打开）、运行日志。
- **联动与筛选**：在「单倍型结果」选中一行，注释/变异两页自动只显示该单倍型，
  点「显示全部」恢复；选中注释行会选中对应的单倍型，并可「查看蛋白序列…」
  （或双击）打开可滚动、可复制的蛋白窗口。
- **环境自检**：执行 `nanoamp doctor`（含 curl / 缓存目录 / 配置目录 / 注释可用性）。
- **复制诊断信息**：把运行日志整段复制到剪贴板。
- **打开输出目录**：在资源管理器中打开结果目录。

窗口标题与窗口内的主标题都是 `nanoamp`。

分析在后台线程执行，窗口不会无响应；进度条为不确定模式（R 未输出百分比）。

## 环境要求

分析由 R 完成，因此目标机器必须安装 R，且 `nanoamp` 包必须安装完成：

```r
R CMD INSTALL 02_code/r
```

`minimap2.exe` 已随仓库提供（`03_dependence/windows-x86_64/bin/minimap2.exe`），
无需额外安装。不需要 conda，不需要 WSL，也不需要浏览器。

exe 仅打包界面，不含 R，因此体积明显小于完整绿色版（10 MB），代价是目标机器需要
预装 R。

### R 与库的定位顺序

`r_runner.py` 定位 Rscript 的顺序：

1. 环境变量 `NANOAMP_RSCRIPT`（指向 `Rscript.exe`）
2. `install.exe` 在 `config.ini` 里记录的 `rscript=`（安装器自带 R 时就是它，
   路径由 `NANOAMP_HOME` 或 `%LOCALAPPDATA%\nanoamp.path` 指向的安装目录决定）
3. `%LOCALAPPDATA%\nanoamp\R\R-runtime\bin\Rscript.exe`（安装器自带 R 的默认位置）
4. `D:\tools\R`、`C:\tools\R`、`C:\Program Files\R`、`%LOCALAPPDATA%\Programs\R`
    下的 `R-*\bin\Rscript.exe`（优先版本号最大的）
5. `PATH` 里的 `Rscript`

定位 R 库的顺序：`NANOAMP_R_LIB` → `config.ini` 里的 `rlib=` → `<安装目录>\R\lib` →
`<安装目录>\R\R-runtime\library` → `D:\tools\R\lib` → `C:\tools\R\lib` →
`%LOCALAPPDATA%\R\win-library\4.6` → `4.5`。

上述位置均未命中时，窗口弹出提示，不会静默失败。

## 重新打包 exe

```powershell
pip install pyinstaller
python 02_code\PythonGUI\build_exe.py
```

产物：`02_code\PythonGUI\dist\nanoamp.exe`（one-file、windowed、无控制台窗口）。

> 说明：打包时 `console=False`，R 的输出不会打印到控制台，仅在界面的
> `运行日志` 中显示。若启动即失败，会弹出显示 traceback 的错误框
> （由 `run_gui.py` 的 `_show_fatal` 负责）。

## 自测

```powershell
python 02_code\PythonGUI\tests\test_headless.py            # 路径解析、R 定位、doctor、解析器
python 02_code\PythonGUI\tests\test_bundled_r_lookup.py    # 只用安装目录里的自带 R 也能启动
python 02_code\PythonGUI\tests\test_e2e.py                 # 真实跑一次分析并校验结果解析
python 02_code\PythonGUI\tests\test_frozen.py              # 打包产物的路径解析与启动
python 02_code\PythonGUI\tests\test_annotation_gui.py      # 注释面板、高级参数、缓存行、联动、窗口尺寸
python 02_code\PythonGUI\tests\test_cancel_analysis.py     # 取消分析
python 02_code\PythonGUI\tests\test_failure_reporting.py   # 失败分类与 GUI 提示
python 02_code\PythonGUI\tests\screenshot.py out.png       # 截图（人工查看用）
```

`make gui-test` 一次跑完前七个。

## 实现要点

1. **不重写算法。** `r_runner.py` 生成一个极小的 R 包装脚本，调用
   `nanoamp_cli()`，参数与命令行完全一致。
2. **不使用 `Rscript -e`。** 传参给 `-e` 不可靠（`commandArgs(trailingOnly=TRUE)`
   会带上 `--args`），且路径中的空格和中文容易被转义破坏；使用真实脚本文件更稳定。
   包装脚本写在 `tmp/`（已 gitignore），使相对路径仍然成立。
3. **UTF-8 显式处理。** R 会输出中文日志；读取子进程输出时按字节读、显式
   UTF-8 解码（`errors="replace"`），避免控制台代码页导致异常或乱码。
4. **传给 R 的路径使用正斜杠。** 路径需嵌入生成的 R 字符串字面量，Windows 反斜杠
   会被当作转义序列（`\R`、`\t`）而报错。
5. **不闪控制台。** `subprocess` 使用 `CREATE_NO_WINDOW`。
6. **`haplotypes.fasta` 只含 top-n 序列。** 选中排名更靠后的行时，界面会提示
   "该单倍型未导出序列，把 top-n 调大后重跑"，而不是显示空白。

## 已知限制

1. **依赖 R。** 不是独立绿色版；exe 只包含界面。
2. **单文件启动较慢。** one-file 打包每次运行都要解压到临时目录，冷启动约 1–3 秒。
3. **没有中英文切换**，界面文案目前为中文。
4. **没有批量模式**（CLI 的 `nanoamp batch` 尚未接入界面）。
5. **功能注释是可选步骤，且有前提**：离线 CDS 路线要自己给 CDS 坐标（长度须为 3 的倍数）；
   在线 genome 路线需要联网，扩增子不在内置 panel 时定位会很慢。`protein_change` 是
   HGVS 风格但未经认证，不作临床依据。
6. **窗口未在小于 880×600 的屏幕上验证**；同时打开「功能注释…」与「高级参数…」时，
   结果表在 864 px 高的屏幕上只剩约 71 px（窗口已增长到屏幕允许的最大值）。
7. **代理环境下的 pip。** 本机曾因系统代理（`127.0.0.1:7890`）未运行导致
   `pip install pyinstaller` 报 `ProxyError`；设置 `NO_PROXY=*` 可绕过。该问题只影响
   打包，不影响程序运行。
