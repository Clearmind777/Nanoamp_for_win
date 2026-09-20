# 工作报告 8：Windows 桌面界面（Python / Tkinter）与 exe 打包

> 日期：2026-09-20
> 关联：`work_report.7.md`
> 本轮范围：为 win 仓库新增 `06_GUI`——一个双击即开的简易图形窗口，并打包成 `nanoamp.exe`

---

## 1. 摘要

在 win 仓库新增 `06_GUI/`，提供一个 **Python + Tkinter** 的桌面窗口，
并打包为可双击的 `06_GUI/dist/nanoamp.exe`（10.1 MB，单文件、无控制台）。

| 项目 | 结果 |
|---|---|
| 界面工具 | Python 3.13 + Tkinter（标准库，无需 pip 安装） |
| 分析核心 | 仍然调用 `nanoamp` R 包，**未重写任何算法** |
| 打包 | PyInstaller 6.22.3，one-file / windowed |
| 产物 | `06_GUI/dist/nanoamp.exe` (10.1 MB) |
| 自测 | 3 个脚本全部通过（headless / e2e / frozen） |
| 人工验证 | 截图确认窗口渲染与结果填充均正常 |

---

## 2. 为什么是"外壳"而不是重写

`02_code/gui/` 里已经有一个 **R Shiny** 界面。本轮没有替换它，而是**并列新增**
一个更轻的入口：

| | Shiny GUI (`02_code/gui`) | `06_GUI`（Python/Tkinter） |
|---|---|---|
| 运行时 | R + shiny + DT | 只需 R（界面已打包） |
| 呈现 | 起本地 HTTP 服务，浏览器打开 | 原生窗口，无浏览器、无端口 |
| 双击即用 | 需 `.bat` 或 Rscript | 直接双击 `nanoamp.exe` |
| 打包 | RInno（重，须在 Windows 构建） | PyInstaller（已验证，10 MB） |
| 参数完整度 | 更全 | 精简：核心参数 + 结果查看 |

**关键设计：两个界面共用同一个分析核心。**
`06_GUI` 不调用 Shiny、也不重写算法，而是与命令行完全一样地调用
`nanoamp_cli()`。这样不存在"两个界面算出不同答案"的风险。

选 Tkinter 而不是 PySide6：Tkinter 随 CPython 提供，**零运行时依赖**，
PyInstaller 冻结后只有 10 MB；PySide6 会让体积涨到 100 MB 以上。

---

## 3. 结构

```text
06_GUI/
|-- run_gui.py                 # 源码入口
|-- build_exe.py               # 打包脚本
|-- nanoamp.spec               # PyInstaller 配置
|-- nanoamp_gui/
|   |-- app.py                 # 窗口本体（约 600 行）
|   `-- r_runner.py            # 定位 R、生成包装脚本、流式读取输出
|-- tests/                     # 4 个自测/截图脚本
`-- dist/nanoamp.exe           # 打包产物（已入库，10.1 MB）
```

界面布局：上方输入区（FASTQ / FASTA / 输出目录 / 模式 / top-n），
中间四个标签页（单倍型结果、QC 指标、输出文件、运行日志），
下方操作区（开始分析、环境自检、打开输出目录、进度条、状态行）。

结果表列出排名、编号、reads 数、占比、是否与目的序列一致、
SNV/插入/缺失数、长度、变异描述；选中一行在下方显示该单倍型完整序列。
分析在后台线程跑，窗口不卡死。

---

## 4. 实现要点（踩过的坑）

1. **不用 `Rscript -e` 传参。** `commandArgs(trailingOnly = TRUE)` 会把
   `--args` 标记本身也读进来（实测拿到 `"--args" "doctor"`）。改为生成一个
   极小的 R 包装脚本写到 `tmp/`（已 gitignore），参数与命令行完全一致。

2. **给 R 的路径必须用正斜杠。** 库路径要嵌进生成的 R 字符串字面量里，
   Windows 反斜杠会被当成转义序列：`D:\tools\R\lib` 直接报
   `Error: '\R' is an unrecognized escape in character string`。统一转成
   `/` 后正常（R 在 Windows 上接受正斜杠）。

3. **UTF-8 显式处理。** R 会输出中文日志。子进程输出按**字节**读、显式
   `decode("utf-8", errors="replace")`，避免控制台代码页导致异常或乱码。

4. **不闪控制台。** `subprocess` 加 `CREATE_NO_WINDOW`，否则每次调用 R 都会
   弹出一个黑窗口。

5. **打包后路径解析。** 冻结后 `__file__` 指向包内部，因此
   `resource_base()` 在 `sys.frozen` 时改用 `sys.executable`；`.exe` 位于
   `06_GUI\dist\`，向上两级即仓库根。已单独写测试验证。

6. **`haplotypes.fasta` 只含 top-n 条序列。** 初版点选排名靠后的行会显示空白。
   现在会明确提示"该单倍型未导出序列，把 top-n 调大后重跑"，并给出它的变异组成。

7. **打包环境的代理坑。** 本机系统代理（`127.0.0.1:7890`）没运行，
   `pip install pyinstaller` 报 `ProxyError`；`--proxy ""` 反而被解析坏。
   最终用 `NO_PROXY=*` 绕过。只影响打包，不影响程序运行。

---

## 5. 验证

### 5.1 自动化自测

```powershell
python 06_GUI\tests\test_headless.py   # 路径解析 / R 定位 / doctor / 两个解析器
python 06_GUI\tests\test_e2e.py        # 真实跑一次分析（438 reads，Mode A）
python 06_GUI\tests\test_frozen.py     # 冻结产物路径解析 + 启动存活
```

结果：

```text
test_headless  -> HEADLESS CHECKS OK     (doctor 退出码 0)
test_e2e       -> END-TO-END OK          (12 条单倍型，top-5 序列全部解析成功)
test_frozen    -> FROZEN BUILD OK        (exe 8 秒后仍存活，仓库根可达，minimap2 可达)
```

`test_e2e` 的真实结果（E4-3，Mode A）：

```text
  1  H1   142 reads  33.3%  ref=FALSE  218delG
  2  H2   134 reads  31.5%  ref=TRUE   .
  3  H3   114 reads  26.8%  ref=FALSE  218delG;135C>T
  ...
 12  H12    1 reads   0.2%  ref=FALSE  218delG;136C>T
```

与命令行跑出的结果一致（H1 33.3% / H2 31.5% / H3 26.8%），说明外壳没有引入偏差。

### 5.2 人工验证

两次截图确认：

1. **空窗口**：标题 "nanoamp - 纳米孔 PCR 产物分析"，输入区、四个标签页、
   操作按钮、进度条、状态行全部正确渲染，中文显示正常。
2. **结果已填充**：单倍型表格 10 行数据、序列框显示 H1 的 530 bp 序列、
   状态行显示 "分析完成，输出目录：…（12 条单倍型）"。
3. **双击 exe**：`06_GUI\dist\nanoamp.exe` 启动后窗口正常打开。

---

## 6. 已知限制

1. **依赖 R。** exe 只打包界面，不含 R 运行时；目标机器必须装好 R 与 `nanoamp`
   包。好处是 exe 只有 10 MB。
2. **单文件打包每次启动要解压**，冷启动约 1–3 秒。
3. **无中英文切换**，文案目前为中文。
4. **没有批量模式**（CLI 的 `nanoamp batch` 未接入）。
5. **没有 GTF / CDS 功能注释**（R 核心里也尚未实现）。
6. **未在小屏（< 880×600）验证**。
7. **未在无 R 的干净机器上验证 exe 的报错提示**（逻辑上会弹出对话框，
   但只在本机验证过）。

---

## 7. 下一步

1. 在**无 R** 的机器上验证 exe：应给出清晰的中文提示而不是崩溃。
2. 把 CLI 的 `batch` 接入界面，支持一次选一整个目录。
3. 参数面板可折叠的"高级设置"（`min_reads` / `min_freq` / `min_identity` /
   `identity_cutoff` / 线程数 / `aligner`）。
4. 结果导出按钮（Excel / FASTA 另存为）。
5. 考虑给 exe 加图标，并在 RInno 方案之外固化 PyInstaller 发布流程。
6. 继续推进 GTF / CDS 功能注释。

---

## 8. 复现命令

```powershell
# 从源码运行
python 06_GUI\run_gui.py

# 自测
python 06_GUI\tests\test_headless.py
python 06_GUI\tests\test_e2e.py
python 06_GUI\tests\test_frozen.py

# 重新打包（需要 pyinstaller）
pip install pyinstaller
python 06_GUI\build_exe.py

# 或走 make
make gui-python
make gui-test
make gui-exe
```
