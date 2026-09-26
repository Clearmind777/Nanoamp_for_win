# 工作报告 27：GUI 七项优化、注释页"卡死"修复与发布产物重建

- 日期：2026-09-27
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.26.md`（`.gitignore` 核查、发布产物重建、安装版端到端验证，提交 `6773bd8`）
- 本轮委托：
  1. 「注释结果」页双击/「查看蛋白序列…」误报"请先选一行"——请修复；
  2. 新增**分析名称**输入栏（留空用时间），「查看上次结果」显示该名称；
  3. 「变异注释」页的「输出变异级明细」应在勾选「功能注释…」后才出现（或改提示语）；
  4. 「单倍型结果」页上下两栏的间距改为可拖动；
  5. 每页添加水平滚动条；
  6. 「输出文件」页大小优先用 KB/MB/GB；
  7. 「QC 指标」页加「指标说明」勾选框，勾选后右侧列出所有指标说明，且与比对分析独立。
  然后验证、提交、推送。
- 执行中使用者补充：**新 GUI 的注释页一按「查看蛋白序列」/双击，程序就卡死**。
- 本轮提交：见 §6（已推送）

---

## 1. 七项逐条

| # | 委托 | 实现 |
|---|---|---|
| 1 | 蛋白序列打不开 | 见 §2（这是本轮最实质的修复） |
| 2 | 分析名称 | 输入区新增 `分析名称`（与「输出目录」同一行，所以不占额外高度）；`_current_analysis_name()` = 输入值或开始时间；状态栏**末尾**追加 `｜分析名称：…`、日志写一行、快照里存名字，「查看上次结果」的状态行与两个注释页标注都带上它（`_snapshot_label()` = `名称 · 时间`）。名字**不传给 R**，也不写结果文件 |
| 3 | 变异注释页 | 「输出变异级明细」勾选框本来就在「功能注释…」面板里（勾选功能注释后才出现）；本轮把该页的固定提示改成**随表单状态变化的提示**（`_update_variant_hint()`）：未开功能注释 → 说明要先勾「功能注释…」；已开但没勾明细 → 说明缺这一项并给出 `--annotation-detail`；两项都就绪 → 说明"设置已就绪，点开始分析"。**跑过一次后该页显示本次运行自己的结论**，不会被提示覆盖（`_annot_status_from_run`） |
| 4 | 可拖动分隔线 | 「单倍型结果」页改用 `ttk.Panedwindow(orient="vertical")`：上=表格（weight 3），下=序列框（weight 1），分隔线可用鼠标拖动 |
| 5 | 水平滚动条 | 新增 `_add_scrollbars(parent, widget, row, column)`，六个页面（单倍型/注释/变异注释/QC/输出文件/运行日志）统一加上水平+垂直滚动条；表格列改为**固定宽度、只有最后一列伸缩**（`stretch=False`），窗口变窄时横向滚动而不是把列挤扁。序列框用 `wrap="char"`（自动换行），本身不需要水平滚动条 |
| 6 | 文件大小 | `_human_size()`：`0 B` / `512 B` / `2.0 KB` / `150 KB` / `3.0 MB` / `5.0 GB`（B 不带小数，≥100 省略小数）；列标题由「大小 (字节)」改为「大小」 |
| 7 | QC 指标说明 | QC 页左上角新增「指标说明」勾选框，勾上后同一页右侧出现术语表（`QC_METRIC_HELP`，内容按 R 侧 `qc.tsv` 的真实指标写成，分「三种模式都有 / 模式 B 专属 / 模式 C 专属 / 功能注释」四组）。它与是否跑过分析无关，不启动任何运行 |

## 2. 注释页"卡死"：成因与修复（本轮最重要的一条）

**现象**：在「注释结果」页点一行，然后双击行或点「查看蛋白序列…」，程序像卡死。

**成因**（`tmp/repro_protein_click.py` 复现并打印）：

1. 点一行 → `<<TreeviewSelect>>` → `_on_select_annotation()` 会把「单倍型结果」里对应行也选中；
2. 那又触发 `_on_select_haplotype()` → 按单倍型筛选 → `_render_annotation_rows()` **删掉并重插整张注释表**；
3. 表格被重建后**选中状态丢失**（旧代码没有恢复），于是「查看蛋白序列…」/双击走到的
   `_open_protein_view()` 里 `self.annot_tree.selection()` 为空 → 弹出**模态**提示框
   「请先在「注释结果」里选中一行」。模态框会占住窗口（在 Windows 上还可能弹到主窗口后面），
   使用者看到的就是"卡死"。

复现输出（同一次点击，旧/新代码对比）：

```text
shipped  : selection after the click = ('H2|T1',)
shipped  : button -> window, window opened = True, dialogs = []
pre-fix  : selection after the click = ()
pre-fix  : button -> window, dialog = ['先选一行']
```

**修复**（三层，缺一层都会退回旧现象）：

- `_render_annotation_rows()` 重画后**恢复原来的选中行**（`_select_annot_row`），蛋白视图的
  `_protein_iid` 同时跟着更新；
- `_open_protein_view()` 改为先看表格选中行，否则回落到"最后一次点过的行"（只要它还在表里），
  两个都没有时才提示；双击改用 **`identify_row(event.y)`（鼠标下那一行）**，不再依赖选中状态；
- 顺手堵住两张表互相触发的死循环风险：程序化选中统一走 `_select_annot_row()` /
  `_select_haplotype_row()`（带 `_syncing_selection` 重入保护、且**已经是该行就不重复设置**），
  `_on_select_haplotype()` 只在**筛选条件真的变化**时才重画。

## 3. 验证过程里另外发现并修掉的两件事

1. **状态栏前缀踩到脚本**：我最初把分析名称写在状态栏**开头**（`「名字」分析完成…`），
   于是所有以 `startswith("分析完成")` 判断结束的验证脚本（包括仓库里既有的
   `tmp/gui_check*.py`）永远等不到结束，看起来像"跑不动"。已改为**在末尾追加**
   `｜分析名称：…`，"分析完成/分析失败/分析已取消"仍是行首，兼容既有判断。
2. **本机残留的安装指针**：`%LOCALAPPDATA%\nanoamp.path` 指向 `tmp\nanoamp`（沙箱安装留下的），
   `find_repo_root()` 会优先采用它，导致 `test_headless.py` 认为"找不到仓库根目录"。
   已删除该残留与 `tmp\nanoamp`，并让 `test_headless.py` 把 `LOCALAPPDATA` 隔离到临时目录
   （这类"测试结果取决于机器残留"的问题不该再出现）。

## 4. 验证

| 验证 | 结果 |
|---|---|
| `test_annotation_gui.py` | 全通过。新增 **6m**（点选行后选中状态保持、按钮/双击都能打开蛋白窗口、无"先选一行"弹窗、**带真实事件循环的死循环守卫**：重画次数 ≤ 6 且选中行仍在）、**6n**（分析名称：输入值/时间默认/缓存保留自己的名字/「查看上次结果」显示该名字并可切回）、**6o**（变异注释页三种状态的提示 + 运行结论不被覆盖）、**6p**（Panedwindow、分隔线、六个页面的水平滚动条、列宽策略）、**6q**（人类可读大小 6 例）、**6r**（指标说明：隐藏→显示、内容覆盖、独立于分析）；**7** 的窗口尺寸检查仍然通过（面板全关 720 px，只开注释 915 px，短屏注释表 54 px） |
| `tmp/repro_protein_click.py` | 复现旧行为（选中丢失 → 弹模态框）并证明新代码不再发生 |
| `test_bundled_r_lookup.py` / `test_cancel_analysis.py` / `test_frozen.py` | 通过（`test_frozen` 会启动新 exe） |
| 安装器自测 9 个脚本 | 全部通过 |
| 需要 R 包库的自测（`test_e2e`、`test_failure_reporting`） | **未通过**：本机 `D:\tools\R\R-4.6.1` 已在（使用者恢复），但 `D:\tools\R\lib`（nanoamp + 109 个包）仍缺失，运行到"真实跑一次分析"就失败；这与本轮改动无关 |
| 安装版端到端（`tmp/verify_round27_install.ps1` + `tmp/gui_check_round27.py`） | 解压新资产 → 沙箱静默安装（`--no-path`、非默认位置）→ 用**真实窗口**验证本轮七项与上一轮的注释场景（见 §5） |
| 发布产物 | `nanoamp.exe` 11,393,615 B（sha256 `db472884…`）；setup 包 sha256 `6e931188…`；离线包 `2db72289…`（重建后逐字节一致）；`build_assets.py` 逐条校验 18 / 113 个条目与工作树一致 |
| 固化字符串检查 | PYZ 常量里含 `分析名称`、`指标说明`、`功能注释没有打开`、`上一次运行：` 等新串，且不含已删除的标题后缀 |
| 文档 | 根 README（含窗口示意图，新增分析名称/拖动分隔线/水平滚动条说明）、README-CN、`02_code/PythonGUI/README.md`、`release/03_GUI/README.md`、`00_materials/tutorial.md` 均已更新；示意图重新生成（70 列，审计 0 处错位）；编码扫描无 BOM / 无替换字符 / 无乱码 |

## 5. 安装版端到端结果

脚本输出保存在 `tmp/round27_verify_out.txt`，要点：

```text
== 1) 查看蛋白序列 right after clicking a row ==
   OK   the clicked row is still selected after the link re-rendered the table  -- ('H12|amplicon_cds_118_237',)
   OK   「查看蛋白序列…」 opens the window
   OK   and does not ask for a selection  -- []
   OK   double-click selects the row under the cursor  -- ('H1|amplicon_cds_118_237',)
   OK   and opens its protein window
== 2) run 1 is named ==
   status: 分析完成，输出目录：…\gui_out\round27（12 条单倍型）｜分析名称：第一次·带注释
== 2b) run 2 unnamed ==
   status: …｜分析名称：2026-09-27 01:30:29
   OK   查看上次结果 names the previous run  -- 正在显示上一次运行：第一次·带注释 · 2026-09-27 01:30:29 的结果…
== 3) 变异注释页 ==
   OK   annotation off: it names both switches / detail off: it says so / both on: ready
== 4)+5) ==
   OK   paned window present / two panes / 六个页面都有水平滚动条
== 6) 输出文件 ==
   {'alignments.bam': '133 KB', 'annotation.tsv': '3.7 KB', 'variants.tsv': '86.1 KB', 'haplotypes.tsv': '1.5 KB', …}
   OK   every size uses a unit / the column heading is 大小
== 7) QC 指标说明 ==
   OK   the glossary starts hidden / ticking 指标说明 shows the glossary / covers the metrics
```

同一轮里上一轮的两个场景也复验通过（`tmp/gui_check_round26.py`，exit 0）：
指针文件定位非默认安装（`NANOAMP_HOME` 未设、`<install>\bin` 不在 PATH）时
`minimap2` 仍然是 `<install>\bin\minimap2.exe`；关掉注释后在同一个输出目录重跑，
注释两页 0 行并提示"未显示"，日志里没有空计数行，「查看上次结果」能把上一次的 12 行取回。

## 6. 提交与推送

- 代码：`02_code/PythonGUI/nanoamp_gui/app.py`、`02_code/PythonGUI/tests/test_annotation_gui.py`、
  `02_code/PythonGUI/tests/test_headless.py`；
- 文档：`README.md`、`README-CN.md`、`02_code/PythonGUI/README.md`、`release/03_GUI/README.md`、
  `00_materials/tutorial.md`；
- 产物：`release/03_GUI/nanoamp.exe`、`release/_build/SHA256SUMS.txt`、
  `release/RELEASE_NOTES-0.1.5.md`、`release/README.md`；
- 报告与索引：本文件、`00_materials/README.md`。
- **Release 仍未上传**（沿用上一轮约定）：仓库里的 setup 包与已发布的 v0.1.5 同名但内容不同，
  要发布请新建 tag（例如 v0.1.6）。

## 7. 仍未做

1. `D:\tools\R\lib`（nanoamp + 109 个包）未恢复 —— `tmp/r_setup_and_verify.ps1` 可离线重建，
   之后可复跑 `test_e2e` / `test_failure_reporting` 与 testthat；
2. 上游回灌（Linux 仓库的 L1–L13）；
3. 真机压力用例：C4 磁盘满、C9 ARM64、E2 高 DPI 截图；
4. GUI 大表虚拟化/分页（P2-2，可选）。
