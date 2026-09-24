# 工作报告 17：去掉"傻瓜式"文案（界面字符串与全部 README）

- 日期：2026-09-24
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.16.md`（整理 `release/` 目录）
- 本轮委托（用户原话）：「仓库以及程序中有些字句太傻瓜式了，比如 nanoamp.exe 中的
  "分析逻辑由 nanoamp R 包执行，本窗口只是调用它的外壳"、"就绪。选择 FASTQ 和参考
  序列后点击"开始分析""，以及 install.exe 中的"这个程序会自动安装分析所需的一切：R、
  依赖包、主程序、命令和桌面快捷方式。全程无需联网，无需管理员权限，大约需要 3-10 分钟。"
  等等，还有仓库中的各种 README.md 和 README-CN.md 写得太傻瓜式了，请你进行修改，
  严肃一点」

---

## 1. 先定规则，再动手

改写涉及 30 份文档、界面字符串 60 余处，多人（多 agent）并行最容易走样，所以先写了
执行规范 `tmp/style_guide.md`，核心是三条：

1. **绝对不许改变**：命令、路径、版本号、数字、哈希、URL、代码块内容、表格数据、
   链接、专有术语（`环境自检`、`开始分析`、`取消操作`、`单倍型结果`、`QC 指标`、
   `输出文件`、`运行日志`、`R 包未安装`、`状态：可用`、`mode A/B/C` 等）。
2. **必须消除**：第二人称与口语称呼（你/你的/同学们/大家）、傻瓜化承诺
   （一键/傻瓜式/只要双击就行/不用管）、情绪与表情（感叹号、⚠️、💡、🎉、✅）、
   疑问式标题（"怎么办？"）、推销语（"最简单/强烈推荐"）、含糊的绝对化
   （"全程无需联网"）。
3. **行文**：陈述句说明"做什么、为什么、怎么验证"；可以更短更干，但操作步骤与
   排错信息不得减少；发现过时/错误描述不要编造，标 `TODO(待确认)` 上报。

## 2. 界面文案

### 2.1 `nanoamp.exe`（`02_code/PythonGUI/nanoamp_gui/app.py`，18 处）

| 原文 | 改后 |
|---|---|
| 就绪。选择 FASTQ 和参考序列后点击"开始分析"。 | 就绪。 |
| 分析逻辑由 nanoamp R 包执行，本窗口只是调用它的外壳。 | 本程序为 nanoamp R 包的图形界面。 |
| 选中某一行可查看该单倍型的完整序列 | 选中一行可查看对应单倍型序列。 |
| 未找到 R —— 点击"环境自检"查看详情 | 未找到 R。请运行环境自检。 |
| 请先选择**测速**文件、目的序列和输出目录。 | 请指定**测序**文件、目的序列与输出目录。（顺手修掉错别字） |
| 正在分析…（首次运行需加载 R 包，可能稍慢） | 正在分析…（首次运行需加载 R 包，耗时较长） |
| 用户请求取消，正在停止 R 进程… | 用户请求取消，正在终止 R 进程… |
| 分析已取消。…可以重新点击「开始分析」再跑一次。 | 分析已取消。部分结果保留在：… |
| 分析没有正常完成。请查看"运行日志"标签页，常见原因… | 分析未正常结束。常见原因为…，详见运行日志。 |
| A - 参考引导（推荐） / C - 精确匹配（仅诊断） | A - 参考引导（默认） / C - 精确匹配（诊断用） |

按钮名与标签页名（`开始分析`、`环境自检`、`取消操作`、`单倍型结果`、`QC 指标`、
`输出文件`、`运行日志`）保持不变——它们是测试与文档共同引用的术语。

### 2.2 `install.exe` / `uninstall.exe`（33 + 9 处）

安装窗口抬头从"nanoamp **一键安装**"改为"nanoamp 安装程序"，说明文字改为：

```text
安装程序将配置 R 运行环境与全部依赖包，安装 nanoamp 主程序，并注册命令行入口与桌面快捷方式。
仅需当前用户目录的写入权限，不需要管理员权限；预计 3–10 分钟（联网下载依赖时为 5–15 分钟）。
```

原文"**全程无需联网**"是 0.1.4 起就不成立的绝对化说法（只装 setup 包时需要联网下载
109 个固定版本依赖），本轮按事实改正。其余改动：勾选项去掉"（推荐）"、桌面快捷方式
描述去掉"（双击打开）"、"安装完成！接下来可以这样使用"→"安装完成。可用入口"、
"请把安装详情里的内容发给技术支持"→"请将「安装详情」中的内容提供给技术支持"、
`--check` 尾部"未找到 _offline 目录，安装包可能不完整"→"安装器将联网获取依赖包"
（含 `nanoamp doctor` 尾部同类提示）等。

卸载器：去除"你自己安装的 R 和你的 R 库"这类第二人称，成功对话框改为
"桌面快捷方式与 PATH 条目已一并清理。用户自行安装的 R 未被删除。"

## 3. 文档（28 份）

按规范分五组并行改写，我逐组复核：

| 组 | 文件 |
|---|---|
| 根目录 | `README.md`、`README-CN.md` |
| release | `release/README.md`、`01_R-package/`、`02_CLI/`、`03_GUI/`、`deps/`、`_build/` 各自 README |
| R 包 | `02_code/r/README.md`、`README-CN.md`、`inst/docs/INSTALL_DEPENDENCIES{,-CN}.md`、`inst/windows/README.md` |
| 02_code | `02_code/README.md`、`README-CN.md`、`cli/`、`gui/`、`PythonGUI/README.md`、`shared/docs/output_schema.md` |
| 依赖与数据 | `03_dependence/**（6 份）`、`01_data/README.md`、`README-raw.md`、`04_builds/README.md`、`00_materials/README.md` |

典型改动：`一键安装器`→`安装器`、`傻瓜式教程`→`教程`、`同学们`→`用户`、
`常见问题`→`故障排查`、`里面有什么`→`目录内容`、`怎么看结果`→`结果解读`、
`最稳`→`建议使用…`、`全程不联网`→`安装过程不需要联网`、去掉 ⚠️/💡 与全部感叹号、
表格里的 `☑` 改为"默认勾选"。

## 4. 顺手修正的事实错误

| 位置 | 原文 | 事实 |
|---|---|---|
| 根 `README.md` | 依赖下载"约 160 MB" | 实测 159.4 MB，统一为 159 MB |
| 根 `README.md` | "窗口上方有两处可以按需调整"（表里 3 项） | 改为"以下三项" |
| 根 `README.md` | §7 目录树未列 `release/_build/` | 补上 |
| `02_code/r/README-CN.md` | "仓库已内置 **Linux** x86_64 的 minimap2" | 本仓库是 Windows 变体，改为 Windows x86_64（仓库内编译、静态链接） |
| `02_code/README{,-CN}.md` | 状态表"Windows 安装包：计划使用 RInno" | 已实现：PyInstaller 构建，`release/_installer/` 产出 `install.exe`/`uninstall.exe` |
| `02_code/README{,-CN}.md` | "Python 版本已经取消"表述含混 | 明确为"早期计划过的 Python **CLI** 未实现；`PythonGUI/` 是桌面界面，不是 CLI" |
| `01_data/README-raw.md` | 抬头称原文件在 `01_data/test_data/`（该目录已在 report.13 删除） | 改为说明规范化后的存放方式与 `meta.tsv` 对应关系 |
| `03_dependence/offline-bundle/README.md` | `install_offline.ps1` 描述含已不存在的"repair the test-data link layer"；发行包 `dist/`(291 MB，含 msys2/src) 与已发布离线资产(248 MB) 口径混淆 | 删除失效描述；写明 248 MB 资产由 `build_assets.py` 从 `release/_offline/` 打包，`msys2/`、`src/` 仅用于重建比对程序、不随包发布 |
| `03_dependence/offline-bundle/install_offline.ps1` | "install all 90 R package binaries" | 实际 109，已改 |

## 5. 验证（不靠肉眼）

写了三个机械校验脚本，把"改写只动措辞"变成可检查的断言：

| 脚本 | 检查内容 | 结果 |
|---|---|---|
| `tmp/check_codeblocks.py` | 每个 ``` 代码块必须与推送版本逐字相同 | 28 份文档中 6 份的代码块有差异，逐行核对后**全部是注释/对齐**（如 `# 一键安装器`→`# 安装器`、窗口示意图标注 ①–⑥、目录树注释），无命令或事实改动 |
| `tmp/check_facts.py` | 数字与行内 `code` 记号不得丢失 | 无丢失；新增项均为**补充的发行事实**（0.1.5 / 34 MB / 248 MB / 159 MB）与路径修正 |
| `tmp/check_structure.py` | 标题层级序列与表格行数不变 | 仅 `02_code/README{,-CN}.md` 表格 +1 行（新增 Python/Tkinter GUI 状态行）；`release/README.md` 曾因文件被写入 UTF-8 BOM 少识别一个标题，**已去掉 BOM** 后一致 |

另：`py_compile` 三个改动过的 Python 文件通过；残留 `TODO(待确认)` 为 0（全部按事实落定）。

功能回归（用本轮重新打包的资产）：

- 12 个测试脚本全绿（安装器 8 + GUI 4）；
- 沙箱联网安装：109/109 版本与固定清单一致，`<安装目录>\bin\minimap2.exe` 与仓库同哈希，`nanoamp doctor` 通过；
- 安装后的 GUI 跑完 E4-3：12 条单倍型、`mapping_rate 0.997717`、`n_reads_total 438`；
- `release/03_GUI/nanoamp.exe` 启动后保持运行；
- 资产重新打包：setup `f526e10b…`（内容含新文案），离线依赖包 `2db72289…`（未变）。

## 6. 改动的文件

程序：`02_code/PythonGUI/nanoamp_gui/app.py`、`release/_installer/install_nanoamp.py`、
`release/_installer/uninstall_nanoamp.py`、`03_dependence/offline-bundle/install_offline.ps1`（说明文字）。
重新构建：`release/install.exe`、`release/uninstall.exe`、`release/03_GUI/nanoamp.exe`、
`02_code/PythonGUI/dist/nanoamp.exe`。
文档：§3 表中的 28 份 + `00_materials/README.md` 索引（追加本报告）。
数据：`release/_build/SHA256SUMS.txt`。

## 7. 遗留

1. **`00_materials/tutorial.md`（1322 行）本轮未改**：它是刻意写给非程序员的
   分步教程，语气本来就与 README 不同；是否一并"严肃化"需要用户决定。
2. **中英对称性**：`02_code/r/README.md` 含 `pwalign` 安装与排错条目，`README-CN.md`
   没有（既存差异），本轮未补。
3. 根目录 `README.md` 与 `README-CN.md` **都是中文**且分工不同（前者面向使用者，
   后者是仓库/开发者总览），无英文根 README；本轮未改结构。
4. v0.1.4 / v0.1.5 仍未发布；本轮同样不发 Release。
